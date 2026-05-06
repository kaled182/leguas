from datetime import timedelta
from decimal import Decimal

from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone


class EmpresaParceira(models.Model):
    """Empresa subcontratante que fornece motoristas (frota) à Léguas Franzinas."""

    nome = models.CharField(max_length=200, verbose_name="Nome da Empresa")
    nif = models.CharField(
        max_length=20, blank=True, verbose_name="NIF",
        help_text="Número de Identificação Fiscal (ex: PT123456789)",
    )
    morada = models.TextField(blank=True, verbose_name="Morada")
    codigo_postal = models.CharField(max_length=8, blank=True, verbose_name="Código Postal")
    cidade = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    telefone = models.CharField(max_length=20, blank=True)
    contacto_nome = models.CharField(max_length=150, blank=True, verbose_name="Nome do Contacto")
    iban = models.CharField(max_length=34, blank=True, verbose_name="IBAN")
    taxa_iva = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("23.00"),
        verbose_name="Taxa IVA (%)",
    )
    driver_default_price_per_package = models.DecimalField(
        "Valor por Pacote ao Driver (default da frota) (€)",
        max_digits=8, decimal_places=4, null=True, blank=True,
        help_text=(
            "Default pago aos motoristas desta frota por pacote entregue. "
            "Sobrepõe o default do parceiro mas é sobreposto pelo "
            "Driver.price_per_package."
        ),
    )
    ativo = models.BooleanField(default=True)
    notas = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Empresa Parceira"
        verbose_name_plural = "Empresas Parceiras"
        ordering = ["nome"]

    def __str__(self):
        return self.nome

    @property
    def num_motoristas(self):
        return self.motoristas.filter(is_active=True).count()


class FleetAutoEmitConfig(models.Model):
    """Configuração de auto-emissão de pré-faturas em lote por frota.

    Activa permite à task Celery `auto_emit_fleet_invoices` (corre 1x/dia)
    detectar frotas configuradas e emitir o lote automaticamente no dia
    do mês indicado, cobrindo o mês anterior.
    """
    PERIOD_CHOICES = [
        ("monthly", "Mensal (mês anterior completo)"),
        ("weekly", "Semanal (semana anterior, segunda a domingo)"),
    ]

    empresa = models.OneToOneField(
        EmpresaParceira, on_delete=models.CASCADE,
        related_name="auto_emit_config",
    )
    enabled = models.BooleanField("Activo", default=False)
    period_type = models.CharField(
        "Tipo de período", max_length=10,
        choices=PERIOD_CHOICES, default="monthly",
    )
    day_of_month = models.PositiveSmallIntegerField(
        "Dia do mês para emitir",
        default=1,
        help_text="Para período mensal — dia em que dispara (1-28)",
    )
    weekday = models.PositiveSmallIntegerField(
        "Dia da semana para emitir",
        default=0,
        help_text=(
            "Para período semanal — 0=Seg, 1=Ter,…, 6=Dom. "
            "Cobre semana anterior."
        ),
    )
    auto_send_whatsapp = models.BooleanField(
        "Enviar WhatsApp automaticamente após emitir",
        default=False,
    )
    last_emitted_at = models.DateTimeField(null=True, blank=True)
    last_emitted_period_from = models.DateField(null=True, blank=True)
    last_emitted_period_to = models.DateField(null=True, blank=True)
    last_summary = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuração Auto-emit"
        verbose_name_plural = "Configurações Auto-emit"

    def __str__(self):
        state = "ON" if self.enabled else "OFF"
        return f"{self.empresa.nome} — auto-emit [{state}]"


class EmpresaParceiraLancamento(models.Model):
    """Lançamento manual de serviço/custo para uma Empresa Parceira."""

    STATUS_CHOICES = [
        ("RASCUNHO", "Rascunho"),
        ("APROVADO", "Aprovado"),
        ("PENDENTE", "Pendente Pagamento"),
        ("PAGO", "Pago"),
        ("CANCELADO", "Cancelado"),
    ]

    empresa = models.ForeignKey(
        EmpresaParceira,
        on_delete=models.CASCADE,
        related_name="lancamentos",
        verbose_name="Empresa Parceira",
    )
    descricao = models.CharField(max_length=300, verbose_name="Descrição do Serviço")
    # Cálculo de entregas
    qtd_entregas = models.PositiveIntegerField(
        "Qtd. Entregas", default=0,
        help_text="Número de caixas/pacotes entregues",
    )
    valor_por_entrega = models.DecimalField(
        "Valor por Entrega (€)", max_digits=8, decimal_places=4, default=Decimal("0.0000"),
    )
    # Componentes de valor
    valor_base = models.DecimalField(
        "Base Entregas (€)", max_digits=12, decimal_places=2, default=Decimal("0.00"),
        help_text="Preenchido automaticamente (qtd × valor) ou manualmente",
    )
    valor_bonus = models.DecimalField(
        "Valor Bónus (€)", max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    pacotes_perdidos = models.DecimalField(
        "Pacotes Perdidos (€)", max_digits=12, decimal_places=2, default=Decimal("0.00"),
        help_text="Desconto por pacotes perdidos",
    )
    adiantamentos = models.DecimalField(
        "Adiantamentos / Combustível (€)", max_digits=12, decimal_places=2, default=Decimal("0.00"),
    )
    periodo_inicio = models.DateField("Período Início", db_index=True)
    periodo_fim = models.DateField("Período Fim")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="RASCUNHO", db_index=True
    )
    data_pagamento = models.DateField("Data de Pagamento", null=True, blank=True)
    referencia_pagamento = models.CharField(
        "Referência de Pagamento", max_length=200, blank=True,
        help_text="MB WAY, Transferência, etc.",
    )
    comprovante_pagamento = models.FileField(
        "Comprovante de Pagamento",
        upload_to="empresa_lancamentos/comprovativos/%Y/%m/",
        null=True, blank=True,
    )
    taxa_iva = models.DecimalField(
        "Taxa IVA (%)", max_digits=5, decimal_places=2, default=Decimal("23.00"),
        help_text="Taxa de IVA aplicada a este lançamento",
    )
    notas = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lancamentos_criados",
    )

    class Meta:
        ordering = ["-periodo_inicio"]
        verbose_name = "Lançamento Manual"
        verbose_name_plural = "Lançamentos Manuais"

    def __str__(self):
        return f"{self.empresa.nome} — {self.descricao} ({self.periodo_inicio})"

    @property
    def total_a_receber(self):
        return (
            self.valor_base
            + self.valor_bonus
            - self.pacotes_perdidos
            - self.adiantamentos
        )

    @property
    def valor_iva(self):
        return (self.total_a_receber * self.taxa_iva / Decimal("100")).quantize(Decimal("0.01"))

    @property
    def total_com_iva(self):
        return self.total_a_receber + self.valor_iva


class DriverProfile(models.Model):
    """Perfil completo do motorista com todos os dados pessoais e profissionais"""

    # Status do Cadastro
    STATUS_CHOICES = [
        ("PENDENTE", "Pendente - Aguardando documentos"),
        ("EM_ANALISE", "Em Analise - Documentos enviados"),
        ("ATIVO", "Ativo - Aprovado"),
        ("BLOQUEADO", "Bloqueado - Documentos expirados"),
        ("IRREGULAR", "Irregular - Problemas no cadastro"),
    ]

    # Vinculo Profissional
    VINCULO_CHOICES = [
        ("DIRETO", "Direto - Recibos Verdes"),
        ("PARCEIRO", "Parceiro - Frota"),
    ]

    # === A. DADOS PESSOAIS E IDENTIFICACAO ===
    nif = models.CharField(
        max_length=9,
        unique=True,
        validators=[RegexValidator(r"^\d{9}$", "NIF deve conter exatamente 9 digitos")],
        verbose_name="NIF",
    )
    nome_completo = models.CharField(max_length=200, verbose_name="Nome Completo")
    apelido = models.CharField(
        "Apelido / Alias",
        max_length=100,
        blank=True,
        db_index=True,
        help_text=(
            "Apelido usado nas plataformas dos parceiros (ex: 'Helena_Duarte_MRB_LF')."
            " Útil para encontrar rápido em relatórios."
        ),
    )
    courier_id_cainiao = models.CharField(
        "Courier ID Cainiao",
        max_length=50,
        blank=True,
        db_index=True,
        unique=False,  # mantido não-único para tolerar duplicados históricos
        help_text=(
            "Identificador único Cainiao deste motorista (não muda). "
            "Usado para fazer match na importação Driver Statistic."
        ),
    )
    niss = models.CharField(
        max_length=11,
        validators=[RegexValidator(r"^\d{11}$", "NISS deve conter 11 digitos")],
        verbose_name="NISS",
        blank=True,
        null=True,
    )
    data_nascimento = models.DateField(
        verbose_name="Data de Nascimento", null=True, blank=True
    )
    nacionalidade = models.CharField(max_length=100, default="Portugal")
    telefone = models.CharField(
        max_length=20,
        validators=[RegexValidator(r"^\+?[0-9]{9,15}$", "Telefone invalido")],
        verbose_name="Telefone",
    )
    email = models.EmailField(verbose_name="Email")
    endereco_residencia = models.TextField(verbose_name="Endereco Completo", blank=True)
    codigo_postal = models.CharField(
        max_length=8, blank=True, verbose_name="Codigo Postal"
    )
    cidade = models.CharField(max_length=100, blank=True)

    # === C. VINCULO PROFISSIONAL ===
    tipo_vinculo = models.CharField(
        max_length=10,
        choices=VINCULO_CHOICES,
        default="DIRETO",
        verbose_name="Tipo de Vinculo",
    )
    nome_frota = models.CharField(
        max_length=200, blank=True, verbose_name="Nome da Frota (se Parceiro)"
    )
    empresa_parceira = models.ForeignKey(
        EmpresaParceira,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="motoristas",
        verbose_name="Empresa Parceira",
    )

    # === OPERACIONAL =====================================================
    daily_capacity = models.PositiveIntegerField(
        "Capacidade Diária (pacotes)",
        null=True, blank=True,
        help_text=(
            "Capacidade-alvo de pacotes/dia. Usada no planeamento "
            "automático. Se vazio, calcula via média histórica "
            "(últimos 14 dias entregues)."
        ),
    )

    # === FINANCEIRO (Fase 1) ============================================
    price_per_package = models.DecimalField(
        "Valor por Pacote (€)",
        max_digits=8, decimal_places=4, null=True, blank=True,
        help_text="Valor que o motorista recebe por pacote entregue. "
                  "Se vazio, usa o preço configurado no Parceiro.",
    )
    advance_monthly_limit = models.DecimalField(
        "Limite Mensal de Adiantamentos (€)",
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text="Limite acumulado de adiantamentos por mês. Vazio = sem limite.",
    )
    bonus_performance_enabled = models.BooleanField(
        "Aplicar Bónus Performance",
        default=True,
        help_text="Override: permite desligar bónus de performance neste motorista.",
    )
    caucao_pct = models.DecimalField(
        "Retenção de Caução (%)",
        max_digits=5, decimal_places=2, default=0,
        help_text="Percentagem retida até o motorista atingir o nº configurado de entregas sem claim.",
    )
    caucao_threshold_deliveries = models.PositiveIntegerField(
        "Entregas para Libertar Caução",
        default=0,
        help_text="Nº de entregas consecutivas sem claim para libertar caução.",
    )
    VAT_REGIME_CHOICES = [
        ("normal",      "Regime Normal"),
        ("isento",      "Isento (art. 53º)"),
        ("simplificado", "Simplificado"),
    ]
    vat_regime = models.CharField(
        "Regime de IVA",
        max_length=20, choices=VAT_REGIME_CHOICES, default="isento",
    )
    irs_retention_pct = models.DecimalField(
        "Retenção IRS (%)",
        max_digits=5, decimal_places=2, default=0,
        help_text="Override do IRS. 0 = usar do Parceiro.",
    )

    # === STATUS E CONTROLE ===
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default="PENDENTE",
        verbose_name="Status do Cadastro",
    )
    is_active = models.BooleanField(default=False, verbose_name="Ativo no Sistema")
    importado_auto = models.BooleanField(
        default=False,
        verbose_name="Importado Automaticamente",
        help_text="Driver criado por importação de planilha — dados pessoais pendentes de atualização",
    )

    # === METADADOS ===
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Data de Aprovacao"
    )
    approved_by = models.CharField(
        max_length=100, blank=True, verbose_name="Aprovado por"
    )

    # Observacoes internas
    observacoes = models.TextField(blank=True, verbose_name="Observacoes Internas")

    class Meta:
        verbose_name = "Perfil de Motorista"
        verbose_name_plural = "Perfis de Motoristas"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.nome_completo} - {self.nif}"

    def has_expired_documents(self):
        """Verifica se algum documento esta expirado"""
        return self.documents.filter(data_validade__lt=timezone.now().date()).exists()

    def get_documents_expiring_soon(self, days=30):
        """Retorna documentos que expiram em X dias"""
        future_date = timezone.now().date() + timedelta(days=days)
        return self.documents.filter(
            data_validade__lte=future_date,
            data_validade__gt=timezone.now().date(),
        )


class DriverDocument(models.Model):
    """Documentos do motorista com controle de validade"""

    TIPO_DOCUMENTO_CHOICES = [
        ("CC", "Cartao de Cidadao"),
        ("TR", "Titulo de Residencia"),
        ("PP", "Passaporte"),
        ("MI", "Manifestacao de Interesse"),
        ("CNH_FRENTE", "Carta de Conducao - Frente"),
        ("CNH_VERSO", "Carta de Conducao - Verso"),
        ("ADR", "Certificado ADR"),
        ("RC", "Registo Criminal"),
        ("DECLARACAO_ATIVIDADE", "Declaracao de Inicio de Atividade"),
        ("OUTRO", "Outro Documento"),
    ]

    motorista = models.ForeignKey(
        DriverProfile,
        on_delete=models.CASCADE,
        related_name="documents",
        verbose_name="Motorista",
    )
    tipo_documento = models.CharField(
        max_length=30,
        choices=TIPO_DOCUMENTO_CHOICES,
        verbose_name="Tipo de Documento",
    )
    arquivo = models.FileField(
        upload_to="driver_documents/%Y/%m/", verbose_name="Arquivo"
    )
    data_validade = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data de Validade",
        help_text="Sistema alerta 30 dias antes do vencimento",
    )
    categoria_cnh = models.CharField(
        max_length=10,
        blank=True,
        verbose_name="Categoria CNH",
        help_text="Ex: B, C, D",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Data de Upload")
    observacoes = models.TextField(blank=True, verbose_name="Observacoes")

    class Meta:
        verbose_name = "Documento do Motorista"
        verbose_name_plural = "Documentos dos Motoristas"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.motorista.nome_completo} - {self.get_tipo_documento_display()}"

    @property
    def is_expired(self):
        """Verifica se documento esta vencido"""
        if self.data_validade:
            return self.data_validade < timezone.now().date()
        return False

    @property
    def days_until_expiration(self):
        """Dias ate o vencimento"""
        if self.data_validade:
            delta = self.data_validade - timezone.now().date()
            return delta.days
        return None

    @property
    def file_extension(self):
        """Retorna a extensao do arquivo"""
        import os

        if self.arquivo:
            return os.path.splitext(self.arquivo.name)[1].lower()
        return ""


class Vehicle(models.Model):
    """Veiculo do motorista"""

    TIPO_VEICULO_CHOICES = [
        ("MOTA", "Mota"),
        ("LIGEIRO", "Ligeiro de Mercadorias"),
        ("CARRINHA_35T", "Carrinha ate 3.5t"),
        ("CARRINHA_GRANDE", "Carrinha acima 3.5t"),
        ("OUTRO", "Outro"),
    ]

    motorista = models.ForeignKey(
        DriverProfile,
        on_delete=models.CASCADE,
        related_name="vehicles",
        verbose_name="Motorista",
    )
    matricula = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Matricula",
        validators=[RegexValidator(r"^[A-Z0-9-]+$", "Matricula invalida")],
    )
    marca = models.CharField(max_length=100, verbose_name="Marca")
    modelo = models.CharField(max_length=100, verbose_name="Modelo")
    tipo_veiculo = models.CharField(
        max_length=20,
        choices=TIPO_VEICULO_CHOICES,
        verbose_name="Tipo de Veiculo",
    )
    ano = models.PositiveIntegerField(null=True, blank=True, verbose_name="Ano")
    cor = models.CharField(max_length=50, blank=True, verbose_name="Cor")

    # Status
    is_active = models.BooleanField(default=True, verbose_name="Veiculo Ativo")

    # Metadados
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Veiculo"
        verbose_name_plural = "Veiculos"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.matricula} - {self.marca} {self.modelo}"

    def has_expired_documents(self):
        """Verifica se algum documento do veiculo esta expirado"""
        return self.vehicle_documents.filter(
            data_validade__lt=timezone.now().date()
        ).exists()


class VehicleDocument(models.Model):
    """Documentos do veiculo"""

    TIPO_DOC_VEICULO_CHOICES = [
        ("DUA", "DUA - Documento Unico Automovel"),
        ("IPO", "Folha da Inspecao (IPO)"),
        ("SEGURO", "Certificado de Seguro (Carta Verde)"),
        ("OUTRO", "Outro Documento"),
    ]

    veiculo = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name="vehicle_documents",
        verbose_name="Veiculo",
    )
    tipo_documento = models.CharField(
        max_length=20,
        choices=TIPO_DOC_VEICULO_CHOICES,
        verbose_name="Tipo de Documento",
    )
    arquivo = models.FileField(
        upload_to="vehicle_documents/%Y/%m/", verbose_name="Arquivo"
    )
    data_validade = models.DateField(
        null=True, blank=True, verbose_name="Data de Validade"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Data de Upload")
    observacoes = models.TextField(blank=True, verbose_name="Observacoes")

    class Meta:
        verbose_name = "Documento do Veiculo"
        verbose_name_plural = "Documentos dos Veiculos"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.veiculo.matricula} - {self.get_tipo_documento_display()}"

    @property
    def is_expired(self):
        """Verifica se documento esta vencido"""
        if self.data_validade:
            return self.data_validade < timezone.now().date()
        return False

    @property
    def file_extension(self):
        """Retorna a extensao do arquivo"""
        import os

        if self.arquivo:
            return os.path.splitext(self.arquivo.name)[1].lower()
        return ""


class DriverReferral(models.Model):
    """
    Registo de indicação entre motoristas.
    Um motorista só pode ser indicado por uma única pessoa (OneToOne em 'referred').
    """

    referrer = models.ForeignKey(
        DriverProfile,
        on_delete=models.CASCADE,
        related_name="referrals_given",
        verbose_name="Quem indicou",
    )
    referred = models.OneToOneField(
        DriverProfile,
        on_delete=models.CASCADE,
        related_name="referral_received",
        verbose_name="Motorista indicado",
    )
    comissao_por_pacote = models.DecimalField(
        "Comissão por pacote (€)",
        max_digits=8,
        decimal_places=4,
        default=Decimal("0.0500"),
        help_text="Valor em € pago por cada pacote entregue pelo motorista indicado.",
    )
    ativo = models.BooleanField("Ativo", default=True)
    notas = models.TextField("Notas", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Indicação"
        verbose_name_plural = "Indicações"
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.referrer.nome_completo} → {self.referred.nome_completo}"
            f" (€{self.comissao_por_pacote}/pct)"
        )


# ============================================================================
# RECLAMAÇÕES DE CLIENTES (Customer Complaints / Delivery Disputes)
# ============================================================================


class CustomerComplaint(models.Model):
    """Registo de reclamação de cliente — entrega falsa, item faltando, etc."""

    TIPO_CHOICES = [
        ("ENTREGA_FALSA", "Entrega Falsa"),
        ("ITEM_FALTANDO", "Item Faltando"),
        ("PACOTE_DANIFICADO", "Pacote Danificado"),
        ("ENTREGA_ATRASADA", "Entrega Atrasada"),
        ("OUTRO", "Outro"),
    ]

    STATUS_CHOICES = [
        ("ABERTO", "Aberto"),
        ("NOTIFICADO", "Motorista Notificado"),
        ("RESPONDIDO", "Resposta Recebida"),
        ("FECHADO", "Fechado"),
        ("CANCELADO", "Cancelado"),
    ]

    driver = models.ForeignKey(
        "DriverProfile",
        on_delete=models.PROTECT,
        related_name="customer_complaints",
        verbose_name="Motorista",
    )

    # Dados do pacote
    numero_pacote = models.CharField(
        "Nº Pacote / Tracking",
        max_length=100,
        db_index=True,
    )
    data_entrega = models.DateTimeField(
        "Data/Hora da Entrega",
        null=True,
        blank=True,
        help_text="Data e hora em que a entrega foi realizada (ou tentada).",
    )
    tipo = models.CharField(
        "Tipo de Reclamação",
        max_length=30,
        choices=TIPO_CHOICES,
        default="ENTREGA_FALSA",
        db_index=True,
    )
    descricao = models.TextField(
        "Relato do Cliente",
        help_text="Descrição detalhada da reclamação do cliente.",
    )

    # Dados do cliente
    nome_cliente = models.CharField("Nome do Cliente", max_length=200)
    telefone_cliente = models.CharField("Telefone do Cliente", max_length=30)
    email_cliente = models.CharField("Email do Cliente", max_length=200, blank=True)

    # Endereço de entrega
    morada = models.TextField("Morada", help_text="Rua, nº, andar, etc.")
    codigo_postal = models.CharField("Código Postal", max_length=20)
    cidade = models.CharField("Cidade", max_length=100)

    # Status e workflow
    status = models.CharField(
        "Status",
        max_length=20,
        choices=STATUS_CHOICES,
        default="ABERTO",
        db_index=True,
    )
    data_notificacao = models.DateTimeField(
        "Data de Notificação ao Motorista", null=True, blank=True
    )
    data_resposta = models.DateTimeField(
        "Data de Resposta do Motorista", null=True, blank=True
    )
    data_fecho = models.DateTimeField("Data de Fecho", null=True, blank=True)

    # Prazo de resposta (deadline da transportadora / plataforma)
    deadline = models.DateTimeField(
        "Deadline",
        null=True,
        blank=True,
        help_text="Prazo limite para resposta/resolução (ex: prazo da plataforma).",
    )

    # Resposta do motorista
    resposta_driver = models.TextField("Resposta do Motorista", blank=True)

    notas = models.TextField("Notas Internas", blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="complaints_created",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Reclamação de Cliente"
        verbose_name_plural = "Reclamações de Clientes"

    def __str__(self):
        return (
            f"[{self.get_status_display()}] {self.numero_pacote}"
            f" — {self.driver.nome_completo}"
        )

    def whatsapp_text(self):
        """Gera o texto padrão para notificação ao motorista via WhatsApp."""
        return (
            f"Segue reclamação, por favor ligar para o cliente e pedir SMS ou "
            f"mensagem via WhatsApp confirmando a entrega do pacote "
            f"{self.numero_pacote} para que possamos fechar o ticket.\n\n"
            f"Segue endereço e contato do cliente.\n\n"
            f"Zip Code/City:\n{self.codigo_postal} /{self.cidade}\n"
            f"Address:\n{self.morada}\n\n"
            f"{self.nome_cliente}\n\n"
            f"{self.telefone_cliente}"
        )


class CustomerComplaintAttachment(models.Model):
    """Anexo de uma reclamação — print da reclamação ou resposta do motorista."""

    TIPO_CHOICES = [
        ("RECLAMACAO", "Print da Reclamação"),
        ("RESPOSTA_DRIVER", "Resposta do Motorista"),
        ("OUTRO", "Outro"),
    ]

    complaint = models.ForeignKey(
        CustomerComplaint,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    tipo = models.CharField(
        "Tipo",
        max_length=20,
        choices=TIPO_CHOICES,
        default="RECLAMACAO",
    )
    ficheiro = models.FileField(
        "Ficheiro",
        upload_to="complaints/%Y/%m/",
    )
    descricao = models.CharField("Descrição", max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_tipo_display()} — {self.complaint.numero_pacote}"


class DriverProfileChangeRequest(models.Model):
    """Pedido de alteração de campo do perfil do motorista — requer aprovação."""

    STATUS_CHOICES = [
        ("pending", "Pendente"),
        ("approved", "Aprovado"),
        ("rejected", "Rejeitado"),
        ("cancelled", "Cancelado pelo motorista"),
    ]

    # Campos que o driver pode pedir para alterar (whitelist)
    EDITABLE_FIELDS = [
        ("telefone", "Telefone"),
        ("email", "Email"),
        ("endereco_residencia", "Endereço"),
        ("codigo_postal", "Código Postal"),
        ("cidade", "Cidade"),
        ("nacionalidade", "Nacionalidade"),
    ]

    driver = models.ForeignKey(
        "drivers_app.DriverProfile",
        on_delete=models.CASCADE,
        related_name="change_requests",
    )
    field = models.CharField(
        "Campo",
        max_length=50,
        choices=EDITABLE_FIELDS,
        db_index=True,
    )
    old_value = models.TextField("Valor anterior", blank=True)
    new_value = models.TextField("Novo valor", blank=True)
    status = models.CharField(
        "Estado", max_length=15,
        choices=STATUS_CHOICES, default="pending",
        db_index=True,
    )

    requested_at = models.DateTimeField(default=timezone.now, db_index=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        "auth.User", null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_change_requests",
    )
    review_notes = models.TextField(
        "Notas da revisão", blank=True,
        help_text="Motivo de rejeição ou observações da aprovação.",
    )

    class Meta:
        verbose_name = "Pedido de Alteração de Perfil"
        verbose_name_plural = "Pedidos de Alteração de Perfil"
        ordering = ["-requested_at"]
        indexes = [
            models.Index(fields=["status", "-requested_at"]),
            models.Index(fields=["driver", "-requested_at"]),
        ]

    def __str__(self):
        return f"{self.driver.apelido or self.driver_id} · {self.field} · {self.status}"

    def apply_to_driver(self):
        """Aplica o new_value ao DriverProfile."""
        if self.status != "pending":
            return False
        setattr(self.driver, self.field, self.new_value)
        self.driver.save(update_fields=[self.field, "updated_at"] if hasattr(self.driver, "updated_at") else [self.field])
        return True


class DriverAutoEmitConfig(models.Model):
    """Auto-emissão de pré-faturas individuais por motorista.

    Análogo a FleetAutoEmitConfig mas para drivers. A task Celery
    `auto_emit_driver_pre_invoices` corre diariamente e cria PFs
    automaticamente para drivers configurados, no dia escolhido.
    """
    PERIOD_CHOICES = [
        ("monthly", "Mensal (mês anterior completo)"),
        ("biweekly", "Quinzenal (15 dias anteriores)"),
        ("weekly", "Semanal (semana anterior, segunda a domingo)"),
    ]
    driver = models.OneToOneField(
        "DriverProfile", on_delete=models.CASCADE,
        related_name="auto_emit_config",
    )
    enabled = models.BooleanField("Activo", default=False)
    period_type = models.CharField(
        "Tipo de período", max_length=10,
        choices=PERIOD_CHOICES, default="monthly",
    )
    day_of_month = models.PositiveSmallIntegerField(
        "Dia do mês para emitir", default=1,
        help_text="Para mensal/quinzenal — 1-28",
    )
    weekday = models.PositiveSmallIntegerField(
        "Dia da semana para emitir", default=0,
        help_text="Para semanal — 0=Seg, 6=Dom",
    )
    auto_approve = models.BooleanField(
        "Auto-aprovar (passar a APROVADO)",
        default=False,
        help_text="Se desligado, fica em CALCULADO para revisão manual.",
    )
    auto_send_whatsapp = models.BooleanField(
        "Enviar WhatsApp ao motorista após emitir",
        default=False,
    )
    last_emitted_at = models.DateTimeField(null=True, blank=True)
    last_emitted_period_from = models.DateField(null=True, blank=True)
    last_emitted_period_to = models.DateField(null=True, blank=True)
    last_pf_id = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Auto-emit (Motorista)"
        verbose_name_plural = "Auto-emit (Motoristas)"

    def __str__(self):
        state = "ON" if self.enabled else "OFF"
        return f"{self.driver.nome_completo} — auto-emit [{state}]"


class DriverMergeAudit(models.Model):
    """Registo de uma operação de unificação (merge) de dois motoristas.

    Quando dois cadastros do mesmo motorista existem (ex: importação
    duplicada com courier_ids diferentes), o admin pode unificá-los:
    todos os FKs do source são reassignados ao target e o source é
    eliminado. Este registo guarda o histórico para auditoria.
    """
    source_driver_repr = models.CharField(
        "Source (apagado)", max_length=200,
        help_text="Snapshot textual do driver source antes do delete.",
    )
    source_driver_id = models.IntegerField(
        "Source ID original", db_index=True,
    )
    target_driver = models.ForeignKey(
        "DriverProfile", on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="merges_received",
        verbose_name="Driver target (que recebeu os dados)",
    )
    transferred_counts = models.JSONField(
        "Quantidades transferidas", default=dict,
        help_text="Ex: {'pre_invoices': 3, 'access': 2, 'mappings': 5}",
    )
    notes = models.TextField("Notas", blank=True)
    merged_at = models.DateTimeField(auto_now_add=True, db_index=True)
    merged_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="driver_merges_performed",
    )

    class Meta:
        verbose_name = "Auditoria de Unificação"
        verbose_name_plural = "Auditorias de Unificação"
        ordering = ["-merged_at"]

    def __str__(self):
        target = self.target_driver.nome_completo if self.target_driver else "(target removido)"
        return f"{self.source_driver_repr} → {target}"
