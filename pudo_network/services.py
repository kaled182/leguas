"""Serviços da Rede PUDO — handshake de custódia idempotente.

`process_handshake` é o ponto único chamado pela API do estafeta e pela
receção no portal do lojista. Garantias:

- **Idempotência** pela `uuid` da transação (reenvio → mesmo resultado).
- **Redundância** driver↔PUDO: o PACOTE é reconciliado por
  (`store`, `tracking_ref`); se ambos os lados reportam o mesmo pacote, o
  segundo é um no-op de estado (regista transação/evento, não duplica).
"""
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from django.db import transaction
from django.utils import timezone

from .models import (
    PudoCustodyPackage,
    PudoDeliveryProof,
    PudoPickupOTP,
    PudoTransaction,
)

# Validade do OTP de levantamento (minutos).
PICKUP_OTP_TTL_MIN = 10


class PudoServiceError(Exception):
    """Erro de negócio amigável para as views (mensagem + status)."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


@dataclass
class HandshakeResult:
    transaction: PudoTransaction
    package: Optional[PudoCustodyPackage]
    idempotent: bool  # True → esta uuid já tinha sido processada


_OPEN_EXCLUDE = [
    PudoCustodyPackage.ENTREGUE_CLIENTE,
    PudoCustodyPackage.DEVOLVIDO_HUB,
]


@transaction.atomic
def process_handshake(*, uuid, tipo, store, tracking_ref, origin,
                      actor="", actor_type="SYSTEM", driver=None,
                      partner=None, source_kind=None, source_ref="",
                      device_ts=None, payload=None):
    """Processa um handshake e devolve `HandshakeResult`.

    Argumentos:
        uuid: chave de idempotência (str ou UUID).
        tipo: PudoTransaction.Tipo (ENTREGA/DEVOLUCAO).
        store: instância PudoStore.
        tracking_ref: código/waybill do pacote.
        origin: PudoTransaction.Origin.
        actor/actor_type: quem dispara (para o evento).
        driver: DriverProfile (opcional).
    """
    tracking_ref = (tracking_ref or "").strip()

    # 1) Idempotência: get_or_create protege contra corridas na uuid única.
    txn, created = PudoTransaction.objects.get_or_create(
        uuid=uuid,
        defaults={
            "tipo": tipo,
            "origin": origin,
            "store": store,
            "driver": driver,
            "tracking_ref": tracking_ref,
            "created_at_device": device_ts,
            "payload": payload or {},
            "status": PudoTransaction.Status.RECEBIDO,
        },
    )
    if not created:
        return HandshakeResult(
            transaction=txn, package=txn.custody_package, idempotent=True,
        )

    # 2) Reconciliar/criar o pacote sob custódia (redundância driver↔PUDO).
    pkg = (
        PudoCustodyPackage.objects.select_for_update()
        .filter(store=store, tracking_ref=tracking_ref)
        .exclude(status__in=_OPEN_EXCLUDE)
        .order_by("-id")
        .first()
    )
    if pkg is None:
        pkg = PudoCustodyPackage.objects.create(
            store=store, tracking_ref=tracking_ref, partner=partner,
            driver=driver,
            source_kind=source_kind or PudoCustodyPackage.SourceKind.MANUAL,
            source_ref=source_ref or "",
            status=PudoCustodyPackage.ATRIBUIDO_HUB,
        )
        pkg.log_event(
            from_status=None, to_status=PudoCustodyPackage.ATRIBUIDO_HUB,
            actor=actor, actor_type=actor_type, motivo="Criado no handshake",
        )

    # 3) Avançar o estado conforme o tipo (idempotente por natureza).
    if tipo == PudoTransaction.Tipo.ENTREGA:
        _advance_to_stock(pkg, actor, actor_type)
    elif tipo == PudoTransaction.Tipo.DEVOLUCAO:
        _advance_return(pkg, actor, actor_type)

    txn.custody_package = pkg
    txn.status = PudoTransaction.Status.PROCESSADO
    txn.save(update_fields=["custody_package", "status"])
    return HandshakeResult(transaction=txn, package=pkg, idempotent=False)


def _advance_to_stock(pkg, actor, actor_type):
    """Leva o pacote até EM_STOCK_PUDO. No-op se já lá está (redundância)."""
    if pkg.status == pkg.EM_STOCK_PUDO:
        return
    if pkg.status == pkg.ATRIBUIDO_HUB:
        pkg.transition_to(
            pkg.EM_TRANSITO, actor=actor, actor_type=actor_type,
            motivo="Saca assinada à rota",
        )
    if pkg.status == pkg.EM_TRANSITO:
        pkg.transition_to(
            pkg.EM_STOCK_PUDO, actor=actor, actor_type=actor_type,
            motivo="Handshake QR concluído",
        )


def _advance_return(pkg, actor, actor_type):
    """Encaminha o pacote para o fluxo de devolução (handshake reverso)."""
    if pkg.status == pkg.AGUARDA_DEVOLUCAO:
        pkg.transition_to(
            pkg.EM_DEVOLUCAO, actor=actor, actor_type=actor_type,
            motivo="Handshake reverso estafeta↔PUDO",
        )
    elif pkg.can_transition_to(pkg.AGUARDA_DEVOLUCAO):
        pkg.transition_to(
            pkg.AGUARDA_DEVOLUCAO, actor=actor, actor_type=actor_type,
            motivo="Marcado para devolução",
        )


# ─────────────────────────────────────────────────────────────────────
# Fase 2 — POD (entrega ao cliente), devoluções e aging
# ─────────────────────────────────────────────────────────────────────


def _client_phone(package):
    if (package.cliente_telefone or "").strip():
        return package.cliente_telefone.strip()
    from .notifications import _client_phone as from_payload
    return from_payload(package)


def send_pickup_otp(package, *, actor="", actor_type="PUDO"):
    """Gera e envia por WhatsApp um OTP de levantamento ao cliente.

    Levanta `PudoServiceError` se não houver telefone ou o envio falhar
    (a UI faz fallback para NIF/CC).
    """
    if package.status != package.EM_STOCK_PUDO:
        raise PudoServiceError("Pacote não está em stock para levantamento.")
    phone = _client_phone(package)
    if not phone:
        raise PudoServiceError(
            "Sem telefone do cliente — use NIF/CC.", status=409,
        )

    # anti-spam: 1 código/60s; invalida anteriores não usados
    recente = package.pickup_otps.filter(
        created_at__gte=timezone.now() - timedelta(seconds=60),
    ).exists()
    if recente:
        raise PudoServiceError("Código enviado há instantes. Aguarde.", status=429)
    package.pickup_otps.filter(used_at__isnull=True).update(
        used_at=timezone.now(),
    )

    code = PudoPickupOTP.generate_code()
    otp = PudoPickupOTP.objects.create(
        package=package, phone=phone, code=code,
        expires_at=timezone.now() + timedelta(minutes=PICKUP_OTP_TTL_MIN),
    )
    try:
        from system_config.whatsapp_helper import (
            WhatsAppWPPConnectAPI,
            to_whatsapp_number,
        )
        api = WhatsAppWPPConnectAPI.from_config()
        msg = (
            f"O seu código de levantamento no ponto {package.store.numero} "
            f"é:\n\n*{code}*\n\nVálido por {PICKUP_OTP_TTL_MIN} minutos."
        )
        api.send_text_reliable(to_whatsapp_number(phone), msg)
    except Exception as exc:  # noqa: BLE001
        otp.delete()
        raise PudoServiceError(
            f"Falha ao enviar o código: {exc}", status=502,
        )
    return otp


@transaction.atomic
def deliver_with_otp(package, code, *, levantador_nome="", actor="",
                     actor_type="PUDO"):
    """Valida o OTP e entrega ao cliente (POD método OTP)."""
    if package.status != package.EM_STOCK_PUDO:
        raise PudoServiceError("Pacote não está disponível para entrega.")
    otp = (
        package.pickup_otps.filter(used_at__isnull=True)
        .order_by("-created_at").first()
    )
    if not otp or not otp.is_valid:
        raise PudoServiceError("Código inválido ou expirado.")
    if (code or "").strip() != otp.code:
        otp.attempts += 1
        otp.save(update_fields=["attempts"])
        raise PudoServiceError("Código incorreto.")
    otp.used_at = timezone.now()
    otp.save(update_fields=["used_at"])

    PudoDeliveryProof.objects.create(
        package=package, metodo=PudoDeliveryProof.Metodo.OTP,
        levantador_nome=levantador_nome or package.cliente_nome or "",
        otp_ok=True, actor=actor,
    )
    package.transition_to(
        package.ENTREGUE_CLIENTE, actor=actor, actor_type=actor_type,
        motivo="POD via OTP",
    )
    return package


@transaction.atomic
def deliver_with_doc(package, doc_raw, *, levantador_nome="", terceiro=False,
                     actor="", actor_type="PUDO"):
    """Entrega validando NIF/CC (gravado SEMPRE mascarado — RGPD)."""
    if package.status != package.EM_STOCK_PUDO:
        raise PudoServiceError("Pacote não está disponível para entrega.")
    if not (doc_raw or "").strip():
        raise PudoServiceError("Documento obrigatório.")
    metodo = (
        PudoDeliveryProof.Metodo.TERCEIRO if terceiro
        else PudoDeliveryProof.Metodo.NIF
    )
    PudoDeliveryProof.objects.create(
        package=package, metodo=metodo,
        levantador_nome=levantador_nome or "",
        doc_mascarado=PudoDeliveryProof.mask_doc(doc_raw), actor=actor,
    )
    package.transition_to(
        package.ENTREGUE_CLIENTE, actor=actor, actor_type=actor_type,
        motivo=f"POD via {metodo}",
    )
    return package


@transaction.atomic
def mark_for_return(package, motivo, *, actor="", actor_type="PUDO"):
    """Marca o pacote para devolução (EM_STOCK/EXPIRADO → AGUARDA_DEVOLUCAO)."""
    if not package.can_transition_to(package.AGUARDA_DEVOLUCAO):
        raise PudoServiceError(
            f"Não é possível devolver a partir de {package.status}.",
        )
    valid = dict(PudoCustodyPackage.MotivoDevolucao.choices)
    if motivo not in valid:
        raise PudoServiceError("Motivo de devolução inválido.")
    package.motivo_devolucao = motivo
    package.transition_to(
        package.AGUARDA_DEVOLUCAO, actor=actor, actor_type=actor_type,
        motivo=valid[motivo],
    )
    return package


@transaction.atomic
def receive_return_at_hub(package, *, actor="", actor_type="ADMIN"):
    """Receção conferida no hub (EM_DEVOLUCAO → DEVOLVIDO_HUB)."""
    if package.status == package.AGUARDA_DEVOLUCAO:
        package.transition_to(
            package.EM_DEVOLUCAO, actor=actor, actor_type=actor_type,
            motivo="Recolhido do PUDO",
        )
    if package.status != package.EM_DEVOLUCAO:
        raise PudoServiceError(
            f"Estado {package.status} não permite receção no hub.",
        )
    package.transition_to(
        package.DEVOLVIDO_HUB, actor=actor, actor_type=actor_type,
        motivo="Receção conferida no hub",
    )
    return package


def mark_expired_packages():
    """Passa a EXPIRADO os pacotes em stock cujo aging_deadline já venceu.

    Chamado pela task Celery `pudo_network.mark_expired`. Devolve a contagem.
    """
    now = timezone.now()
    qs = PudoCustodyPackage.objects.filter(
        status=PudoCustodyPackage.EM_STOCK_PUDO,
        aging_deadline__isnull=False,
        aging_deadline__lt=now,
    )
    n = 0
    for pkg in qs.iterator():
        try:
            pkg.transition_to(
                pkg.EXPIRADO, actor="cron", actor_type="SYSTEM",
                motivo="Aging: prazo de levantamento ultrapassado",
            )
            n += 1
        except ValueError:
            continue
    return n
