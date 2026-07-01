"""Serviços da Rede PUDO — handshake de custódia idempotente.

`process_handshake` é o ponto único chamado pela API do estafeta e pela
receção no portal do lojista. Garantias:

- **Idempotência** pela `uuid` da transação (reenvio → mesmo resultado).
- **Redundância** driver↔PUDO: o PACOTE é reconciliado por
  (`store`, `tracking_ref`); se ambos os lados reportam o mesmo pacote, o
  segundo é um no-op de estado (regista transação/evento, não duplica).
"""
import hashlib
import hmac
import uuid as uuidlib
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Optional

from django.db import IntegrityError, transaction
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum
from django.utils import timezone

from .models import (
    PudoCustodyPackage,
    PudoDeliveryProof,
    PudoDeviceKey,
    PudoHandshakeNonce,
    PudoPickupOTP,
    PudoStore,
    PudoStoreBillingLine,
    PudoStoreStatement,
    PudoTransaction,
    PudoUpstreamReconciliation,
)

# TTL máximo aceite para um QR offline assinado (segundos) — curto p/ replay.
SIGNED_QR_MAX_TTL = 300

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


def coerce_uuid(value):
    """Devolve um UUID válido a partir de `value`.

    Aceita UUID, string UUID, ou qualquer texto (ex.: fallback de clientes em
    HTTP sem `crypto.randomUUID`). Texto não-UUID é convertido num UUID
    DETERMINÍSTICO (uuid5) — preserva a idempotência para o mesmo input.
    Vazio/None → UUID aleatório.
    """
    if isinstance(value, uuidlib.UUID):
        return value
    text = str(value or "").strip()
    if not text:
        return uuidlib.uuid4()
    try:
        return uuidlib.UUID(text)
    except (ValueError, AttributeError, TypeError):
        return uuidlib.uuid5(uuidlib.NAMESPACE_OID, text)


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
    uuid = coerce_uuid(uuid)  # tolera fallback não-UUID de clientes HTTP

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


# ─────────────────────────────────────────────────────────────────────
# Fase 3 — Fecho periódico de extratos (snapshot)
# ─────────────────────────────────────────────────────────────────────

_IVA_EXPR = ExpressionWrapper(
    F("valor") * (Decimal("1") + F("iva_pct") / Decimal("100")),
    output_field=DecimalField(max_digits=14, decimal_places=6),
)


def _prev_month_bounds(today):
    first_this = today.replace(day=1)
    last_prev = first_this - timedelta(days=1)
    first_prev = last_prev.replace(day=1)
    return first_prev, last_prev


@transaction.atomic
def close_period(store, periodo_inicio, periodo_fim):
    """Fecha (snapshot) o extrato de uma loja para o período. Idempotente."""
    existing = PudoStoreStatement.objects.filter(
        store=store, periodo_inicio=periodo_inicio, periodo_fim=periodo_fim,
    ).first()
    if existing:
        return existing

    lines = PudoStoreBillingLine.objects.filter(
        store=store, statement__isnull=True,
        emitted_at__date__gte=periodo_inicio,
        emitted_at__date__lte=periodo_fim,
    )
    agg = lines.aggregate(
        total=Sum("valor"), com_iva=Sum(_IVA_EXPR), n=Count("id"),
    )
    if not agg["n"]:
        return None

    stmt = PudoStoreStatement.objects.create(
        store=store, ciclo_pagamento=store.ciclo_pagamento,
        periodo_inicio=periodo_inicio, periodo_fim=periodo_fim,
        total_valor=agg["total"] or Decimal("0"),
        total_com_iva=agg["com_iva"] or Decimal("0"),
        n_linhas=agg["n"],
    )
    # Linka as linhas via update() (não passa pelo save() imutável do ledger).
    lines.update(statement=stmt)
    return stmt


def emit_due_statements(today=None):
    """Emite os extratos cujo período fecha HOJE, conforme o ciclo da loja.

    - MENSAL: fecha o mês anterior no dia 1.
    - SEMANAL: fecha a semana anterior (seg–dom) à segunda-feira.

    Corrida diária (task `pudo_network.emit_statements`); idempotente.
    Devolve a lista de statements criados.
    """
    today = today or timezone.localdate()
    created = []

    if today.day == 1:
        ini, fim = _prev_month_bounds(today)
        for store in PudoStore.objects.filter(
            ciclo_pagamento=PudoStore.CicloPagamento.MENSAL,
        ):
            stmt = close_period(store, ini, fim)
            if stmt:
                created.append(stmt)

    if today.weekday() == 0:  # segunda-feira
        fim = today - timedelta(days=1)
        ini = today - timedelta(days=7)
        for store in PudoStore.objects.filter(
            ciclo_pagamento=PudoStore.CicloPagamento.SEMANAL,
        ):
            stmt = close_period(store, ini, fim)
            if stmt:
                created.append(stmt)

    return created


# ─────────────────────────────────────────────────────────────────────
# Fase 2 — Reconciliação a montante (devoluções → carrier)
# ─────────────────────────────────────────────────────────────────────


def build_upstream_payload(record):
    """Compõe o payload de devolução a enviar a montante.

    Estrutura estável e legível; o mapeamento para o formato final do
    carrier (Cainiao/Ecoscooting) faz-se no `_send_upstream` quando o spec
    estiver fechado (Q1).
    """
    pkg = record.package
    return {
        "tracking_ref": pkg.tracking_ref,
        "pudo": pkg.store.numero,
        "carrier": pkg.partner.name if pkg.partner_id else None,
        "source_kind": pkg.source_kind,
        "source_ref": pkg.source_ref,
        "motivo": record.motivo,
        "returned_at": (
            pkg.updated_at.isoformat() if pkg.updated_at else None
        ),
    }


def _send_upstream(record, payload):
    """Envio real a montante — POR CONFIGURAR (aguarda spec do carrier).

    Levanta NotImplementedError de propósito: até o endpoint/formato estarem
    definidos, o registo fica PENDENTE com o payload já composto e pronto.
    """
    raise NotImplementedError("Envio a montante por configurar (spec Q1).")


def process_upstream_reconciliations(limit=200):
    """Prepara/drena a fila de reconciliação a montante.

    Enquanto o `_send_upstream` não estiver ligado, compõe e persiste o
    payload de cada registo PENDENTE (deixando-o pronto a enviar) e regista
    a razão. Quando o spec chegar, passa a marcar ENVIADO. Idempotente.
    Devolve (preparados, enviados).
    """
    qs = PudoUpstreamReconciliation.objects.filter(
        status=PudoUpstreamReconciliation.Status.PENDENTE,
    ).select_related("package", "package__store", "package__partner")[:limit]

    preparados = enviados = 0
    for rec in qs:
        payload = build_upstream_payload(rec)
        try:
            _send_upstream(rec, payload)
            rec.status = PudoUpstreamReconciliation.Status.ENVIADO
            rec.sent_at = timezone.now()
            rec.payload = payload
            rec.last_error = ""
            rec.save(update_fields=["status", "sent_at", "payload", "last_error"])
            enviados += 1
        except NotImplementedError as exc:
            # Ainda sem spec: guarda o payload composto, mantém PENDENTE.
            rec.payload = payload
            rec.last_error = str(exc)
            rec.save(update_fields=["payload", "last_error"])
            preparados += 1
        except Exception as exc:  # noqa: BLE001
            rec.status = PudoUpstreamReconciliation.Status.ERRO
            rec.last_error = str(exc)[:255]
            rec.save(update_fields=["status", "last_error"])
    return preparados, enviados


# ─────────────────────────────────────────────────────────────────────
# Fase 4 — Offline-first: chave de dispositivo, assinatura e sync em lote
# ─────────────────────────────────────────────────────────────────────


def issue_device_key(driver, *, rotate=False):
    """Devolve (criando se preciso) o segredo de assinatura do estafeta."""
    key, _created = PudoDeviceKey.objects.get_or_create(
        driver_profile=driver,
        defaults={"secret": PudoDeviceKey.generate_secret()},
    )
    if rotate:
        key.secret = PudoDeviceKey.generate_secret()
        key.is_active = True
        key.rotated_at = timezone.now()
        key.save(update_fields=["secret", "is_active", "rotated_at"])
    return key


def signing_string(*, uuid, pudo, tracking_ref, tipo, nonce, exp):
    """Canonicaliza os campos a assinar. Tem de bater com o lado do device."""
    return "|".join([
        str(uuid), str(pudo), str(tracking_ref), str(tipo),
        str(nonce), str(exp),
    ])


def sign_payload(secret, *, uuid, pudo, tracking_ref, tipo, nonce, exp):
    """Assinatura HMAC-SHA256 (hex) — usada em testes e como referência do
    algoritmo que o device implementa."""
    msg = signing_string(
        uuid=uuid, pudo=pudo, tracking_ref=tracking_ref, tipo=tipo,
        nonce=nonce, exp=exp,
    )
    return hmac.new(
        secret.encode(), msg.encode(), hashlib.sha256,
    ).hexdigest()


def _consume_nonce(nonce, driver, exp_ts):
    """Regista o nonce (uso-único). Levanta PudoServiceError em replay."""
    try:
        PudoHandshakeNonce.objects.create(
            nonce=nonce, driver_profile=driver,
            expires_at=timezone.datetime.fromtimestamp(
                exp_ts, tz=timezone.get_current_timezone(),
            ),
        )
    except IntegrityError:
        raise PudoServiceError("Nonce já usado (replay).", status=409)


@transaction.atomic
def process_signed_handshake(payload, *, origin, expected_driver=None):
    """Verifica um handshake offline assinado e processa-o.

    Verifica: assinatura HMAC (chave do estafeta), TTL curto (`exp`), e
    consome o `nonce` (uso-único, anti-replay). Depois delega em
    `process_handshake` (que é idempotente pela `uuid`).

    `payload` deve conter: uuid, pudo, tracking_ref, tipo, nonce, exp, sig,
    driver (id do estafeta; obrigatório quando `expected_driver` é None,
    ex.: leitura pelo PUDO que não tem o token do estafeta).
    """
    required = ["uuid", "pudo", "tracking_ref", "nonce", "exp", "sig"]
    faltam = [k for k in required if not str(payload.get(k) or "").strip()]
    if faltam:
        raise PudoServiceError("Campos em falta: " + ", ".join(faltam))

    tipo = (payload.get("tipo") or PudoTransaction.Tipo.ENTREGA).upper()
    if tipo not in PudoTransaction.Tipo.values:
        raise PudoServiceError(f"tipo inválido: {tipo}")

    # Resolver o estafeta e a sua chave
    driver = expected_driver
    if driver is None:
        from drivers_app.models import DriverProfile
        driver = DriverProfile.objects.filter(
            id=payload.get("driver"),
        ).first()
    if driver is None:
        raise PudoServiceError("Estafeta não identificado.", status=404)
    key = PudoDeviceKey.objects.filter(
        driver_profile=driver, is_active=True,
    ).first()
    if not key:
        raise PudoServiceError("Sem chave de dispositivo ativa.", status=409)

    # TTL curto (exp é epoch em segundos)
    try:
        exp_ts = int(payload["exp"])
    except (TypeError, ValueError):
        raise PudoServiceError("exp inválido.")
    now_ts = int(timezone.now().timestamp())
    if exp_ts < now_ts:
        raise PudoServiceError("QR expirado.", status=409)
    if exp_ts - now_ts > SIGNED_QR_MAX_TTL:
        raise PudoServiceError("TTL do QR demasiado longo.", status=400)

    # Assinatura
    expected_sig = sign_payload(
        key.secret, uuid=payload["uuid"], pudo=payload["pudo"],
        tracking_ref=payload["tracking_ref"], tipo=tipo,
        nonce=payload["nonce"], exp=exp_ts,
    )
    if not hmac.compare_digest(expected_sig, str(payload["sig"])):
        raise PudoServiceError("Assinatura inválida.", status=401)

    # Uso-único (anti-replay) — depois da assinatura estar validada
    _consume_nonce(payload["nonce"], driver, exp_ts)

    store = PudoStore.objects.filter(numero__iexact=str(payload["pudo"])).first()
    if store is None and str(payload["pudo"]).isdigit():
        store = PudoStore.objects.filter(id=int(payload["pudo"])).first()
    if store is None:
        raise PudoServiceError("PUDO não encontrado.", status=404)

    result = process_handshake(
        uuid=payload["uuid"], tipo=tipo, store=store,
        tracking_ref=payload["tracking_ref"], origin=origin,
        actor=str(driver.id), actor_type="DRIVER", driver=driver,
        payload={"offline": True, "nonce": payload["nonce"]},
    )
    return result


def sync_batch(items, driver, *, origin):
    """Drena a fila offline do dispositivo: uma lista de handshakes.

    Cada item é processado de forma independente e idempotente; um item com
    erro não impede os restantes. Devolve a lista de resultados por item.
    """
    out = []
    for i, item in enumerate(items or []):
        ref = str((item or {}).get("uuid") or i)
        try:
            if item.get("sig"):
                res = process_signed_handshake(
                    item, origin=origin, expected_driver=driver,
                )
            else:
                store = PudoStore.objects.filter(
                    numero__iexact=str(item.get("pudo")),
                ).first()
                if store is None:
                    raise PudoServiceError("PUDO não encontrado.", status=404)
                res = process_handshake(
                    uuid=item.get("uuid"),
                    tipo=(item.get("tipo") or PudoTransaction.Tipo.ENTREGA),
                    store=store, tracking_ref=item.get("tracking_ref", ""),
                    origin=origin, actor=str(driver.id), actor_type="DRIVER",
                    driver=driver, payload=item.get("payload") or {},
                )
            out.append({
                "ref": ref, "success": True,
                "idempotent": res.idempotent,
                "status": res.package.status if res.package else None,
            })
        except PudoServiceError as exc:
            out.append({"ref": ref, "success": False, "error": exc.message})
        except Exception as exc:  # noqa: BLE001
            out.append({"ref": ref, "success": False, "error": str(exc)})
    return out


def purge_expired_nonces():
    """Limpa nonces expirados (housekeeping opcional)."""
    return PudoHandshakeNonce.objects.filter(
        expires_at__lt=timezone.now(),
    ).delete()[0]
