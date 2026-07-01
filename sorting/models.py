"""Modelos do Sorting de pacotes em BIGBAGS virtuais por CP4/geozona.

Fluxo: cria-se uma SortingSession (modo CP4 ou Geozona), leem-se os pacotes
um a um (scan), cada pacote é resolvido (CP/zona via geozonas.triagem) e cai
numa SortingBigbag (criada on-the-fly). Cada bigbag tem um motorista. Ao
finalizar, a sessão fica como histórico para conferência futura.
"""
from django.conf import settings
from django.db import models


class SortingSession(models.Model):
    MODE_CP4 = "CP4"
    MODE_ZONA = "ZONA"
    MODE_CHOICES = [
        (MODE_CP4, "Por CP4 (total)"),
        (MODE_ZONA, "Por Geozona"),
    ]

    STATUS_OPEN = "EM_ANDAMENTO"
    STATUS_DONE = "FINALIZADO"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Em Andamento"),
        (STATUS_DONE, "Finalizado"),
    ]

    nome = models.CharField("Nome da Sessão", max_length=160, blank=True)
    hub = models.CharField("HUB", max_length=120, blank=True, db_index=True)
    mode = models.CharField(
        "Modo", max_length=10, choices=MODE_CHOICES, default=MODE_CP4,
    )
    status = models.CharField(
        "Estado", max_length=20, choices=STATUS_CHOICES,
        default=STATUS_OPEN, db_index=True,
    )
    observacao = models.TextField("Observação", blank=True)
    target_cps = models.CharField(
        "CP4 alvo", max_length=255, blank=True,
        help_text="CP4 esperados nesta sessão (vírgulas). Vazio = aceita todos.",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="sorting_sessions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    finished_at = models.DateTimeField("Finalizada em", null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Sessão de Sorting"
        verbose_name_plural = "Sessões de Sorting"

    def __str__(self):
        return f"{self.nome or 'Sorting'} #{self.pk} [{self.get_status_display()}]"

    @property
    def is_open(self):
        return self.status == self.STATUS_OPEN


class SortingBigbag(models.Model):
    """Bigbag virtual de uma sessão — agrupa pacotes de um CP4 (e zona)."""

    session = models.ForeignKey(
        SortingSession, on_delete=models.CASCADE, related_name="bigbags",
    )
    cp4 = models.CharField("CP4", max_length=4, blank=True, db_index=True)
    # Zona (quando modo Geozona). Snapshot do nome para o histórico.
    zona = models.ForeignKey(
        "geozonas.ZonaGeo", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="sorting_bigbags",
    )
    zona_nome = models.CharField("Zona", max_length=120, blank=True)
    codigo = models.CharField("Código Bigbag", max_length=80, blank=True)

    driver = models.ForeignKey(
        "drivers_app.DriverProfile", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="sorting_bigbags",
        verbose_name="Motorista",
    )
    observacao = models.CharField("Observação", max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["cp4", "zona_nome", "id"]
        verbose_name = "Bigbag (Sorting)"
        verbose_name_plural = "Bigbags (Sorting)"
        # Uma bigbag por (sessão, cp4, zona). zona NULL = CP4 total / sem zona.
        unique_together = [("session", "cp4", "zona")]

    def __str__(self):
        return self.codigo or f"BB {self.cp4} {self.zona_nome}".strip()

    @property
    def label(self):
        if self.zona_nome:
            return f"{self.cp4} · {self.zona_nome}"
        return self.cp4 or "(sem CP)"


class SortingParcel(models.Model):
    STATUS_OK = "OK"            # resolvido e colocado numa bigbag
    STATUS_UNRESOLVED = "UNRESOLVED"  # sem CP/zona — não classificado
    STATUS_CHOICES = [
        (STATUS_OK, "Classificado"),
        (STATUS_UNRESOLVED, "Não Classificado"),
    ]

    session = models.ForeignKey(
        SortingSession, on_delete=models.CASCADE, related_name="parcels",
    )
    bigbag = models.ForeignKey(
        SortingBigbag, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="parcels",
    )
    waybill_number = models.CharField("Waybill", max_length=100, db_index=True)
    cp = models.CharField("Código Postal", max_length=12, blank=True)
    cp4 = models.CharField("CP4", max_length=4, blank=True, db_index=True)
    zona_nome = models.CharField("Zona", max_length=120, blank=True)
    localidade = models.CharField("Localidade", max_length=160, blank=True)

    # Dados do destinatário (snapshot da BD ao ler — para a folha do motorista)
    nome_cliente = models.CharField("Cliente", max_length=200, blank=True)
    telefone_cliente = models.CharField("Telefone", max_length=40, blank=True)
    morada = models.CharField("Morada", max_length=255, blank=True)

    status = models.CharField(
        "Estado", max_length=20, choices=STATUS_CHOICES, default=STATUS_OK,
        db_index=True,
    )
    # Lido mas fora dos CP4 alvo da sessão (aceite, mas sinalizado).
    divergent = models.BooleanField("Divergente", default=False, db_index=True)
    note = models.CharField("Nota", max_length=200, blank=True)

    scanned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="sorting_scans",
    )
    scanned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-scanned_at"]
        verbose_name = "Pacote (Sorting)"
        verbose_name_plural = "Pacotes (Sorting)"
        indexes = [
            models.Index(
                fields=["session", "waybill_number"],
                name="sorting_sor_session_wb_idx",
            ),
        ]

    def __str__(self):
        return f"{self.waybill_number} → {self.zona_nome or self.cp4}"
