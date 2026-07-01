"""Modelos da Rede PUDO (add-on).

Fase 0 — Fundações: a loja como entidade gerida (`PudoStore`, identidade por
`numero` sequencial) e o acesso do lojista (`PudoAccess`, molde `EmpresaAccess`).

Convenções seguidas (validadas no código real da Léguas):
- Máquinas de estado são MANUAIS (`can_transition_to()` + histórico imutável);
  NÃO usamos django-fsm. Os modelos de custódia/handshake/ledger entram nas
  Fases 1-3 — aqui só ficam as fundações.
- Acessos de parceiros vivem FORA do `User` Django (molde `customauth.EmpresaAccess`),
  com `set_password`/`check_password` via `django.contrib.auth.hashers`.
"""
import secrets
import uuid as uuid_lib
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import User
from django.db import models, transaction
from django.utils import timezone


class PudoStore(models.Model):
    """Loja/ponto de recolha gerido pela Léguas (parceiro da Rede PUDO).

    Molde: `drivers_app.EmpresaParceira`. A IDENTIDADE do PUDO é o `numero`
    sequencial (ex.: ``PUDO-0001``), imutável após criação — é o que aparece em
    etiquetas, bigbags, QR do handshake e faturas. O `nome` é apenas descritivo.

    Carrier-agnostic desde o dia 1: `partner` é nullable — um pacote sob custódia
    pode originar de qualquer cliente, não só da Cainiao (ver §7 do plano).
    """

    class Status(models.TextChoices):
        ATIVO = "ATIVO", "Ativo"
        PAUSADO = "PAUSADO", "Pausado"
        INATIVO = "INATIVO", "Inativo"

    class CicloPagamento(models.TextChoices):
        SEMANAL = "SEMANAL", "Semanal"
        MENSAL = "MENSAL", "Mensal"

    # ─── Identidade ─────────────────────────────────────────────────
    numero = models.CharField(
        "Número PUDO", max_length=20, unique=True, editable=False, db_index=True,
        help_text="Identidade do PUDO (ex.: PUDO-0001). Gerado automaticamente.",
    )
    nome = models.CharField(
        "Nome (descritivo)", max_length=200,
        help_text="Apenas descritivo/enriquecimento. A identidade é o número.",
    )

    # ─── Dados fiscais / contacto (molde EmpresaParceira) ───────────
    nif = models.CharField("NIF", max_length=20, blank=True)
    morada = models.TextField("Morada", blank=True)
    codigo_postal = models.CharField("Código Postal", max_length=8, blank=True)
    cidade = models.CharField("Cidade", max_length=100, blank=True)
    email = models.EmailField("Email", blank=True)
    telefone = models.CharField("Telefone", max_length=20, blank=True)
    contacto_nome = models.CharField("Nome do Contacto", max_length=150, blank=True)
    iban = models.CharField("IBAN", max_length=34, blank=True)
    taxa_iva = models.DecimalField(
        "Taxa IVA (%)", max_digits=5, decimal_places=2, default=Decimal("23.00"),
    )

    # ─── Geo ────────────────────────────────────────────────────────
    latitude = models.DecimalField(
        "Latitude", max_digits=9, decimal_places=6, null=True, blank=True,
    )
    longitude = models.DecimalField(
        "Longitude", max_digits=9, decimal_places=6, null=True, blank=True,
    )

    # ─── Operação ───────────────────────────────────────────────────
    status = models.CharField(
        "Estado", max_length=10, choices=Status.choices, default=Status.ATIVO,
        db_index=True,
    )
    capacidade_max = models.PositiveIntegerField(
        "Capacidade máxima (pacotes)", default=0,
        help_text="0 = sem limite. Proxy grosseiro de espaço para o MVP; a regra "
                  "de overflow entra na Fase 1.",
    )
    horario = models.JSONField(
        "Horário", default=dict, blank=True,
        help_text="Horário de funcionamento (estrutura livre por dia da semana).",
    )

    # ─── Preço (faturação À LOJA — distinto do pagamento ao motorista) ─
    preco_1a_entrega = models.DecimalField(
        "Preço 1ª entrega (€)", max_digits=8, decimal_places=4,
        default=Decimal("0.0000"),
    )
    preco_adicional = models.DecimalField(
        "Preço entrega adicional (€)", max_digits=8, decimal_places=4,
        default=Decimal("0.0000"),
    )
    ciclo_pagamento = models.CharField(
        "Ciclo de pagamento", max_length=10, choices=CicloPagamento.choices,
        default=CicloPagamento.MENSAL,
    )

    # ─── Carrier-agnostic ───────────────────────────────────────────
    partner = models.ForeignKey(
        "core.Partner", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="pudo_stores", verbose_name="Cliente/Carrier (opcional)",
        help_text="Vazio = multi-carrier. Preencher restringe a um cliente.",
    )

    notas = models.TextField("Notas", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "PUDO (Loja da Rede)"
        verbose_name_plural = "PUDOs (Rede)"
        ordering = ["numero"]

    def __str__(self):
        return f"{self.numero} · {self.nome}"

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = self._gen_numero()
        super().save(*args, **kwargs)

    @staticmethod
    def _gen_numero():
        """Gera o próximo número sequencial ``PUDO-0001`` de forma atómica."""
        with transaction.atomic():
            last = (
                PudoStore.objects.select_for_update()
                .order_by("-id")
                .values_list("numero", flat=True)
                .first()
            )
            seq = 0
            if last and last.startswith("PUDO-"):
                try:
                    seq = int(last.split("-", 1)[1])
                except (ValueError, IndexError):
                    seq = 0
            return f"PUDO-{seq + 1:04d}"

    @property
    def is_operacional(self):
        return self.status == self.Status.ATIVO


class PudoAccess(models.Model):
    """Acesso ao portal de um PUDO. Molde: `customauth.EmpresaAccess`.

    Vive fora do `User` Django. Papéis resolvem a rotatividade de balcão:
    `DONO` vê financeiro; `ATENDENTE` só operação.
    """

    class Papel(models.TextChoices):
        DONO = "DONO", "Dono (vê financeiro)"
        ATENDENTE = "ATENDENTE", "Atendente (só operação)"

    store = models.OneToOneField(
        PudoStore, on_delete=models.CASCADE, related_name="access",
    )
    username = models.CharField(
        "Username", max_length=100, unique=True,
        help_text="Username único de login.",
    )
    email = models.EmailField("Email", blank=True)
    password = models.CharField("Password (hash)", max_length=255)
    papel = models.CharField(
        "Papel", max_length=10, choices=Papel.choices, default=Papel.DONO,
    )
    is_active = models.BooleanField(
        "Ativo", default=True,
        help_text="Desativar bloqueia o login sem apagar a conta.",
    )
    last_login = models.DateTimeField("Último login", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="created_pudo_accesses",
    )

    class Meta:
        verbose_name = "Acesso de PUDO"
        verbose_name_plural = "Acessos de PUDO"
        ordering = ["store__numero"]

    def __str__(self):
        return f"{self.username} ({self.store.numero})"

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    @property
    def pode_ver_financeiro(self):
        return self.papel == self.Papel.DONO


# ─────────────────────────────────────────────────────────────────────
# Fase 1 — Custódia online + handshake
# ─────────────────────────────────────────────────────────────────────

# SLA default de levantamento (dias) até o pacote expirar no PUDO.
DEFAULT_AGING_DAYS = 7


class PudoCustodyPackage(models.Model):
    """Um pacote sob custódia de um PUDO.

    Máquina de estados MANUAL (padrão `settlements.PartnerInvoice`): as
    transições permitidas estão em `_ALLOWED`; `transition_to()` valida,
    grava um `PudoCustodyEvent` imutável e dispara os hooks.

    Ligação ao pacote é CARRIER-AGNOSTIC por soft-link (`tracking_ref` +
    `partner` + `source_kind`/`source_ref`) — não amarrada a
    `CainiaoOperationTask` nem a `orders_manager.Order` (ver §5/§7 do plano).
    """

    # ─── Estados (§4 do plano) ──────────────────────────────────────
    ATRIBUIDO_HUB = "ATRIBUIDO_HUB"
    EM_TRANSITO = "EM_TRANSITO"
    EM_STOCK_PUDO = "EM_STOCK_PUDO"
    ENTREGUE_CLIENTE = "ENTREGUE_CLIENTE"
    EXPIRADO = "EXPIRADO"
    AGUARDA_DEVOLUCAO = "AGUARDA_DEVOLUCAO"
    EM_DEVOLUCAO = "EM_DEVOLUCAO"
    DEVOLVIDO_HUB = "DEVOLVIDO_HUB"
    DIVERGENCIA = "DIVERGENCIA"

    STATUS_CHOICES = [
        (ATRIBUIDO_HUB, "Atribuído ao hub"),
        (EM_TRANSITO, "Em trânsito"),
        (EM_STOCK_PUDO, "Em stock no PUDO"),
        (ENTREGUE_CLIENTE, "Entregue ao cliente"),
        (EXPIRADO, "Expirado"),
        (AGUARDA_DEVOLUCAO, "Aguarda devolução"),
        (EM_DEVOLUCAO, "Em devolução"),
        (DEVOLVIDO_HUB, "Devolvido ao hub"),
        (DIVERGENCIA, "Divergência"),
    ]

    # Transições permitidas from → {to}. Ver diagrama §4.
    _ALLOWED = {
        ATRIBUIDO_HUB: {EM_TRANSITO, DIVERGENCIA},
        EM_TRANSITO: {EM_STOCK_PUDO, DIVERGENCIA},
        EM_STOCK_PUDO: {
            ENTREGUE_CLIENTE, EXPIRADO, AGUARDA_DEVOLUCAO, DIVERGENCIA,
        },
        EXPIRADO: {AGUARDA_DEVOLUCAO, ENTREGUE_CLIENTE, DIVERGENCIA},
        AGUARDA_DEVOLUCAO: {EM_DEVOLUCAO, DIVERGENCIA},
        EM_DEVOLUCAO: {DEVOLVIDO_HUB, DIVERGENCIA},
        DEVOLVIDO_HUB: {DIVERGENCIA},
        # DIVERGENCIA nunca é terminal: força resolução humana e reentra.
        DIVERGENCIA: {EM_STOCK_PUDO, AGUARDA_DEVOLUCAO, DEVOLVIDO_HUB},
        ENTREGUE_CLIENTE: set(),  # terminal feliz
    }

    _TRANSITION_META = {
        ATRIBUIDO_HUB: {"label": "Atribuído", "color": "gray", "icon": "package"},
        EM_TRANSITO: {"label": "Em trânsito", "color": "amber", "icon": "truck"},
        EM_STOCK_PUDO: {"label": "Rececionar", "color": "sky", "icon": "package-check"},
        ENTREGUE_CLIENTE: {"label": "Entregar", "color": "emerald", "icon": "check"},
        EXPIRADO: {"label": "Expirar", "color": "orange", "icon": "alarm-clock"},
        AGUARDA_DEVOLUCAO: {"label": "Devolver", "color": "yellow", "icon": "corner-up-left"},
        EM_DEVOLUCAO: {"label": "Em devolução", "color": "yellow", "icon": "undo"},
        DEVOLVIDO_HUB: {"label": "Devolvido", "color": "slate", "icon": "warehouse"},
        DIVERGENCIA: {"label": "Divergência", "color": "rose", "icon": "alert-triangle"},
    }

    class SourceKind(models.TextChoices):
        CAINIAO = "CAINIAO", "Cainiao (CainiaoOperationTask)"
        ORDER = "ORDER", "Order (orders_manager)"
        MANUAL = "MANUAL", "Manual / outro carrier"

    store = models.ForeignKey(
        PudoStore, on_delete=models.PROTECT, related_name="custody_packages",
    )
    driver = models.ForeignKey(
        "drivers_app.DriverProfile", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="pudo_custody_packages",
        verbose_name="Motorista (entregou ao PUDO)",
    )
    bigbag = models.ForeignKey(
        "sorting.SortingBigbag", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="pudo_custody_packages",
    )

    # ─── Soft-link carrier-agnostic ao pacote ───────────────────────
    tracking_ref = models.CharField(
        "Referência do pacote", max_length=120, db_index=True,
        help_text="Waybill/código lido no handshake. Chave de negócio.",
    )
    partner = models.ForeignKey(
        "core.Partner", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="pudo_custody_packages", verbose_name="Carrier",
    )
    source_kind = models.CharField(
        "Origem", max_length=10, choices=SourceKind.choices,
        default=SourceKind.MANUAL,
    )
    source_ref = models.CharField(
        "Ref. origem", max_length=120, blank=True,
        help_text="PK/ref no sistema de origem (opcional).",
    )

    class MotivoDevolucao(models.TextChoices):
        NAO_LEVANTADO = "NAO_LEVANTADO", "Não levantado (expirou)"
        RECUSADO = "RECUSADO", "Recusado pelo cliente"
        MORADA_ERRADA = "MORADA_ERRADA", "Endereço/PUDO errado"
        DANIFICADO = "DANIFICADO", "Danificado"
        OUTRO = "OUTRO", "Outro"

    status = models.CharField(
        "Estado", max_length=20, choices=STATUS_CHOICES,
        default=ATRIBUIDO_HUB, db_index=True,
    )
    localizacao_prateleira = models.CharField(
        "Prateleira", max_length=60, blank=True,
    )
    cliente_nome = models.CharField("Nome do cliente", max_length=150, blank=True)
    cliente_telefone = models.CharField(
        "Telefone do cliente", max_length=20, blank=True,
    )
    motivo_devolucao = models.CharField(
        "Motivo de devolução", max_length=20,
        choices=MotivoDevolucao.choices, blank=True,
    )
    received_at = models.DateTimeField(
        "Rececionado no PUDO", null=True, blank=True,
    )
    aging_deadline = models.DateTimeField(
        "Prazo de levantamento", null=True, blank=True,
    )
    delivered_at = models.DateTimeField(
        "Entregue ao cliente", null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Pacote em custódia (PUDO)"
        verbose_name_plural = "Pacotes em custódia (PUDO)"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["store", "status"]),
            models.Index(fields=["store", "tracking_ref"]),
        ]

    def __str__(self):
        return f"{self.tracking_ref} @ {self.store.numero} [{self.status}]"

    # ── Workflow (padrão manual, sem django-fsm) ───────────────────
    def can_transition_to(self, new_status):
        return new_status in self._ALLOWED.get(self.status, set())

    def available_transitions(self):
        out = []
        for code in self._ALLOWED.get(self.status, set()):
            meta = self._TRANSITION_META.get(code, {})
            out.append({
                "status": code,
                "label": meta.get("label", code),
                "color": meta.get("color", "gray"),
                "icon": meta.get("icon", "arrow-right"),
            })
        return out

    @transaction.atomic
    def transition_to(self, new_status, *, actor="", actor_type="SYSTEM",
                      motivo="", meta=None):
        """Valida a transição, grava evento imutável e dispara hooks.

        Idempotente no ponto de chamada só quando `new_status == status`
        (devolve sem erro). Caso contrário exige transição permitida.
        """
        if new_status == self.status:
            return self
        if not self.can_transition_to(new_status):
            raise ValueError(
                f"Transição {self.status} → {new_status} não permitida."
            )
        old = self.status
        self.status = new_status
        self._run_transition_hooks(new_status)
        self.save()
        PudoCustodyEvent.objects.create(
            package=self, from_status=old, to_status=new_status,
            actor=actor or "", actor_type=actor_type or "SYSTEM",
            motivo=motivo or "", meta=meta or {},
        )
        return self

    def _run_transition_hooks(self, new_status):
        now = timezone.now()
        if new_status == self.EM_STOCK_PUDO:
            if not self.received_at:
                self.received_at = now
            if not self.aging_deadline:
                self.aging_deadline = now + timedelta(days=DEFAULT_AGING_DAYS)
            # Notificação ao cliente é best-effort (nunca quebra a transição).
            self._notify_client_arrived()
        elif new_status == self.ENTREGUE_CLIENTE:
            self.delivered_at = now
            # Ponto ÚNICO da faturação à loja (ledger imutável) — Fase 3.
            self._emit_billing_line()
            # Levantamento pelo cliente = interno (Q1): NÃO faz callback.
        elif new_status == self.DEVOLVIDO_HUB:
            # Devolução volta a montante (Q1): enfileira reconciliação.
            self._queue_upstream_return()

    def _notify_client_arrived(self):
        try:
            from .notifications import notify_client_arrived
            notify_client_arrived(self)
        except Exception:  # noqa: BLE001 — notificação nunca bloqueia
            pass

    def _emit_billing_line(self):
        """Emite a linha de ledger imutável à loja (idempotente por pacote)."""
        if PudoStoreBillingLine.objects.filter(package=self).exists():
            return
        store = self.store
        PudoStoreBillingLine.objects.create(
            store=store, package=self, tracking_ref=self.tracking_ref,
            valor=store.preco_1a_entrega, iva_pct=store.taxa_iva,
            ciclo_pagamento=store.ciclo_pagamento,
        )

    def _queue_upstream_return(self):
        """Enfileira a devolução para callback a montante (formato por definir).

        Q1: largar no PUDO já conta como delivered p/ Cainiao, levantamento é
        interno, mas a DEVOLUÇÃO precisa de voltar. O envio real (Cainiao/
        Ecoscooting) fica pendente até o formato estar fechado — aqui só se
        regista a intenção, de forma idempotente.
        """
        if PudoUpstreamReconciliation.objects.filter(
            package=self, tipo=PudoUpstreamReconciliation.Tipo.DEVOLUCAO,
        ).exists():
            return
        PudoUpstreamReconciliation.objects.create(
            package=self, tipo=PudoUpstreamReconciliation.Tipo.DEVOLUCAO,
            motivo=self.motivo_devolucao or "",
        )

    @property
    def is_terminal(self):
        return not self._ALLOWED.get(self.status)

    def log_event(self, *, from_status, to_status, actor="",
                  actor_type="SYSTEM", motivo="", meta=None):
        return PudoCustodyEvent.objects.create(
            package=self, from_status=from_status or "",
            to_status=to_status, actor=actor or "",
            actor_type=actor_type or "SYSTEM", motivo=motivo or "",
            meta=meta or {},
        )


class PudoTransaction(models.Model):
    """O handshake (custódia) — âncora de idempotência.

    Reenvios com a mesma `uuid` devolvem o mesmo resultado (nunca duplicam).
    Como driver e PUDO podem ambos reportar (redundância), a reconciliação
    do PACOTE faz-se por (`store`, `tracking_ref`); a `uuid` protege cada
    submissão individual.
    """

    class Tipo(models.TextChoices):
        ENTREGA = "ENTREGA", "Entrega ao PUDO"
        DEVOLUCAO = "DEVOLUCAO", "Devolução"

    class Origin(models.TextChoices):
        DRIVER_APP = "DRIVER_APP", "App do estafeta"
        PUDO_WEB = "PUDO_WEB", "Portal do lojista"
        ADMIN = "ADMIN", "Admin"

    class Status(models.TextChoices):
        RECEBIDO = "RECEBIDO", "Recebido"
        PROCESSADO = "PROCESSADO", "Processado"
        DIVERGENCIA = "DIVERGENCIA", "Divergência"

    uuid = models.UUIDField(
        "UUID", unique=True, default=uuid_lib.uuid4, editable=False,
        help_text="Chave de idempotência (gerada no dispositivo/cliente).",
    )
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    origin = models.CharField(max_length=12, choices=Origin.choices)
    store = models.ForeignKey(
        PudoStore, on_delete=models.PROTECT, related_name="transactions",
    )
    driver = models.ForeignKey(
        "drivers_app.DriverProfile", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="pudo_transactions",
    )
    custody_package = models.ForeignKey(
        PudoCustodyPackage, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="transactions",
    )
    tracking_ref = models.CharField(max_length=120, blank=True, db_index=True)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.RECEBIDO,
    )
    payload = models.JSONField(default=dict, blank=True)
    created_at_device = models.DateTimeField(null=True, blank=True)
    synced_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Transação PUDO (handshake)"
        verbose_name_plural = "Transações PUDO (handshake)"
        ordering = ["-synced_at"]

    def __str__(self):
        return f"{self.tipo} {self.tracking_ref} ({self.uuid})"


class PudoCustodyEvent(models.Model):
    """Histórico append-only da custódia. Molde `OrderStatusHistory`."""

    class ActorType(models.TextChoices):
        DRIVER = "DRIVER", "Estafeta"
        PUDO = "PUDO", "Lojista"
        ADMIN = "ADMIN", "Admin"
        SYSTEM = "SYSTEM", "Sistema"

    package = models.ForeignKey(
        PudoCustodyPackage, on_delete=models.CASCADE, related_name="events",
    )
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20)
    actor = models.CharField(max_length=120, blank=True)
    actor_type = models.CharField(
        max_length=10, choices=ActorType.choices, default=ActorType.SYSTEM,
    )
    motivo = models.CharField(max_length=255, blank=True)
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Evento de custódia (PUDO)"
        verbose_name_plural = "Eventos de custódia (PUDO)"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.package_id}: {self.from_status}→{self.to_status}"


# ─────────────────────────────────────────────────────────────────────
# Fase 2 — POD (prova de entrega) + OTP de levantamento + devoluções
# ─────────────────────────────────────────────────────────────────────

class PudoPickupOTP(models.Model):
    """Código de uso único para levantamento pelo cliente. Molde
    `customauth.DriverLoginOTP` — enviado por WhatsApp ao destinatário."""

    package = models.ForeignKey(
        PudoCustodyPackage, on_delete=models.CASCADE, related_name="pickup_otps",
    )
    phone = models.CharField("Telefone", max_length=20, blank=True)
    code = models.CharField("Código", max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)

    MAX_ATTEMPTS = 5

    class Meta:
        verbose_name = "OTP de levantamento (PUDO)"
        verbose_name_plural = "OTPs de levantamento (PUDO)"
        ordering = ["-created_at"]

    def __str__(self):
        return f"OTP {self.package_id} · {self.code}"

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_valid(self):
        return (
            self.used_at is None
            and not self.is_expired
            and self.attempts < self.MAX_ATTEMPTS
        )

    @staticmethod
    def generate_code():
        return f"{secrets.randbelow(1_000_000):06d}"


class PudoDeliveryProof(models.Model):
    """Prova de entrega (POD) ao cliente. RGPD: nunca guardar foto de
    documento; o NIF/CC é sempre gravado MASCARADO."""

    class Metodo(models.TextChoices):
        OTP = "OTP", "OTP (WhatsApp)"
        NIF = "NIF", "NIF/CC (mascarado)"
        TERCEIRO = "TERCEIRO", "Levantado por terceiro"

    package = models.OneToOneField(
        PudoCustodyPackage, on_delete=models.CASCADE, related_name="delivery_proof",
    )
    metodo = models.CharField(max_length=10, choices=Metodo.choices)
    levantador_nome = models.CharField("Nome de quem levantou", max_length=150, blank=True)
    doc_mascarado = models.CharField(
        "Documento (mascarado)", max_length=40, blank=True,
        help_text="Ex.: ***456**9. Nunca guardar o número completo nem foto.",
    )
    otp_ok = models.BooleanField(default=False)
    assinatura = models.TextField("Assinatura (opcional)", blank=True)
    actor = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Prova de entrega (POD)"
        verbose_name_plural = "Provas de entrega (POD)"
        ordering = ["-created_at"]

    def __str__(self):
        return f"POD {self.package_id} ({self.metodo})"

    @staticmethod
    def mask_doc(raw):
        """Mascara um NIF/CC, deixando só os últimos 2 dígitos visíveis."""
        digits = "".join(ch for ch in (raw or "") if ch.isalnum())
        if len(digits) <= 2:
            return "*" * len(digits)
        return "*" * (len(digits) - 2) + digits[-2:]


class PudoUpstreamReconciliation(models.Model):
    """Fila de reconciliação a montante (devoluções → Cainiao/Ecoscooting).

    O formato/endpoint reais dependem da Q1 (por fechar); esta fila regista a
    intenção de forma idempotente para um cron/serviço enviar depois."""

    class Tipo(models.TextChoices):
        DEVOLUCAO = "DEVOLUCAO", "Devolução"

    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        ENVIADO = "ENVIADO", "Enviado"
        ERRO = "ERRO", "Erro"

    package = models.ForeignKey(
        PudoCustodyPackage, on_delete=models.CASCADE,
        related_name="upstream_reconciliations",
    )
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDENTE,
        db_index=True,
    )
    motivo = models.CharField(max_length=40, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Reconciliação a montante (PUDO)"
        verbose_name_plural = "Reconciliações a montante (PUDO)"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.tipo} {self.package_id} [{self.status}]"


# ─────────────────────────────────────────────────────────────────────
# Fase 3 — Faturação à loja (ledger imutável)
# ─────────────────────────────────────────────────────────────────────


class PudoStoreBillingLine(models.Model):
    """Ledger IMUTÁVEL de faturação à loja. Molde `PreInvoicePudo`.

    Emitida uma única vez no POD (ver `PudoCustodyPackage._emit_billing_line`).
    O extrato do lojista LÊ este ledger — nunca se recalcula uma linha viva.
    """

    store = models.ForeignKey(
        PudoStore, on_delete=models.PROTECT, related_name="billing_lines",
    )
    package = models.OneToOneField(
        PudoCustodyPackage, on_delete=models.PROTECT, related_name="billing_line",
    )
    tracking_ref = models.CharField(max_length=120, db_index=True)
    valor = models.DecimalField(max_digits=8, decimal_places=4)
    iva_pct = models.DecimalField(max_digits=5, decimal_places=2)
    ciclo_pagamento = models.CharField(max_length=10)
    emitted_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Linha de faturação à loja (PUDO)"
        verbose_name_plural = "Faturação à loja (PUDO)"
        ordering = ["-emitted_at"]
        indexes = [models.Index(fields=["store", "emitted_at"])]

    def __str__(self):
        return f"{self.store.numero} · {self.tracking_ref} · {self.valor}€"

    @property
    def valor_com_iva(self):
        return self.valor * (Decimal("1") + self.iva_pct / Decimal("100"))

    def save(self, *args, **kwargs):
        # Imutável: uma vez criada, não permite update do valor/estado.
        if self.pk:
            raise ValueError("PudoStoreBillingLine é imutável (ledger).")
        super().save(*args, **kwargs)
