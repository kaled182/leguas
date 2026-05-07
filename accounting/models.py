import os
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models


def validate_document_extension(value):
    """Valida as extensões de arquivo permitidas para upload"""
    allowed_extensions = [
        ".pdf",
        ".jpg",
        ".jpeg",
        ".png",
        ".xlsx",
        ".xls",
        ".doc",
        ".docx",
    ]
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in allowed_extensions:
        raise ValidationError(
            f'Arquivo não suportado. Extensões permitidas: {", ".join(allowed_extensions)}'
        )


def upload_to_revenues(instance, filename):
    """Define o caminho de upload para documentos de receitas"""
    return f"accounting/revenues/{instance.user.id}/{filename}"


def upload_to_expenses(instance, filename):
    """Define o caminho de upload para documentos de despesas"""
    return f"accounting/expenses/{instance.user.id}/{filename}"


# Create your models here.


class Revenues(models.Model):
    """
    Modelo para armazenar todas receitas/entradas da empresa
    """

    NATUREZA_CHOICES = [
        ("VENDA", "Venda de Serviços"),
        ("CONSULTORIA", "Consultoria"),
        ("PRODUTO", "Venda de Produtos"),
        ("JUROS", "Juros"),
        ("DIVIDENDOS", "Dividendos"),
        ("ROYALTIES", "Royalties"),
        ("OUTROS", "Outros"),
    ]

    FONTE_CHOICES = [
        ("CLIENTE_DIRETO", "Cliente Direto"),
        ("MARKETPLACE", "Marketplace"),
        ("PARCEIRO", "Parceiro"),
        ("INVESTIMENTO", "Investimento"),
        ("BANCO", "Banco"),
        ("GOVERNO", "Governo"),
        ("OUTROS", "Outros"),
    ]

    # Usuário que está registrando a receita
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="Usuário",
        help_text="Usuário responsável pelo registro",
    )

    # Natureza da entrada
    natureza = models.CharField(
        max_length=20,
        choices=NATUREZA_CHOICES,
        verbose_name="Natureza da Entrada",
        help_text="Tipo/categoria da receita",
    )

    # Valores
    valor_sem_iva = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Valor sem IVA",
        help_text="Valor da receita sem impostos",
    )

    valor_com_iva = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Valor com IVA",
        help_text="Valor da receita com impostos incluídos",
    )

    # Data da entrada
    data_entrada = models.DateField(
        verbose_name="Data da Entrada",
        help_text="Data em que a receita foi recebida",
    )

    # Fonte da entrada
    fonte = models.CharField(
        max_length=20,
        choices=FONTE_CHOICES,
        verbose_name="Fonte da Entrada",
        help_text="Origem/fonte da receita",
    )

    # Campos adicionais úteis
    descricao = models.TextField(
        blank=True,
        null=True,
        verbose_name="Descrição",
        help_text="Descrição detalhada da receita",
    )

    referencia = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Referência",
        help_text="Número de fatura, contrato ou outra referência",
    )

    # Upload de documento
    documento = models.FileField(
        upload_to=upload_to_revenues,
        validators=[validate_document_extension],
        blank=True,
        null=True,
        verbose_name="Documento",
        help_text="Upload do documento que comprova a receita (PDF, JPG, XLSX, etc.)",
    )

    # Metadados
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Receita"
        verbose_name_plural = "Receitas"
        ordering = ["-data_entrada", "-criado_em"]

    def __str__(self):
        return f"{self.natureza} - €{self.valor_com_iva} - {self.data_entrada}"

    @property
    def iva_valor(self):
        """Calcula o valor do IVA"""
        return self.valor_com_iva - self.valor_sem_iva

    @property
    def percentual_iva(self):
        """Calcula o percentual de IVA"""
        if self.valor_sem_iva > 0:
            return (
                (self.valor_com_iva - self.valor_sem_iva) / self.valor_sem_iva
            ) * 100
        return Decimal("0.00")

    @property
    def tem_documento(self):
        """Verifica se há documento anexado"""
        return bool(self.documento)

    @property
    def nome_documento(self):
        """Retorna o nome do arquivo sem o caminho"""
        if self.documento:
            return os.path.basename(self.documento.name)
        return None

    @property
    def extensao_documento(self):
        """Retorna a extensão do documento"""
        if self.documento:
            return os.path.splitext(self.documento.name)[1].lower()
        return None


class Expenses(models.Model):
    """
    Modelo para armazenar todas despesas/saídas da empresa
    """

    NATUREZA_CHOICES = [
        ("OPERACIONAL", "Despesa Operacional"),
        ("MARKETING", "Marketing e Publicidade"),
        ("TECNOLOGIA", "Tecnologia e Software"),
        ("PESSOAL", "Pessoal e Salários"),
        ("ALUGUEL", "Aluguel e Utilities"),
        ("VIAGEM", "Viagens e Hospedagem"),
        ("MATERIAL", "Material de Escritório"),
        ("JURIDICO", "Serviços Jurídicos"),
        ("CONTABIL", "Serviços Contábeis"),
        ("FINANCEIRO", "Taxas e Juros"),
        ("MANUTENCAO", "Manutenção"),
        ("COMBUSTIVEL", "Combustível"),
        ("SEGURO", "Seguros"),
        ("IMPOSTOS", "Impostos e Taxas"),
        ("OUTROS", "Outros"),
    ]

    FONTE_CHOICES = [
        ("FORNECEDOR", "Fornecedor"),
        ("PRESTADOR", "Prestador de Serviços"),
        ("FUNCIONARIO", "Funcionário"),
        ("GOVERNO", "Governo"),
        ("BANCO", "Banco"),
        ("SEGURADORA", "Seguradora"),
        ("UTILIDADE", "Empresa de Utilidades"),
        ("OUTROS", "Outros"),
    ]

    # Usuário que está registrando a despesa
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="Usuário",
        help_text="Usuário responsável pelo registro",
    )

    # Natureza da saída
    natureza = models.CharField(
        max_length=20,
        choices=NATUREZA_CHOICES,
        verbose_name="Natureza da Despesa",
        help_text="Tipo/categoria da despesa",
    )

    # Valores
    valor_sem_iva = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Valor sem IVA",
        help_text="Valor da despesa sem impostos",
    )

    valor_com_iva = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Valor com IVA",
        help_text="Valor da despesa com impostos incluídos",
    )

    # Data da saída
    data_entrada = models.DateField(
        verbose_name="Data da Despesa",
        help_text="Data em que a despesa foi realizada",
    )

    # Fonte da despesa
    fonte = models.CharField(
        max_length=20,
        choices=FONTE_CHOICES,
        verbose_name="Fonte da Despesa",
        help_text="Origem/destinatário da despesa",
    )

    # Campos adicionais úteis
    descricao = models.TextField(
        blank=True,
        null=True,
        verbose_name="Descrição",
        help_text="Descrição detalhada da despesa",
    )

    referencia = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Referência",
        help_text="Número de fatura, recibo ou outra referência",
    )

    # Upload de documento
    documento = models.FileField(
        upload_to=upload_to_expenses,
        validators=[validate_document_extension],
        blank=True,
        null=True,
        verbose_name="Documento",
        help_text="Upload do documento que comprova a despesa (PDF, JPG, XLSX, etc.)",
    )

    # Status de pagamento
    pago = models.BooleanField(
        default=False,
        verbose_name="Pago",
        help_text="Indica se a despesa já foi paga",
    )

    data_pagamento = models.DateField(
        blank=True,
        null=True,
        verbose_name="Data do Pagamento",
        help_text="Data em que a despesa foi efetivamente paga",
    )

    # Metadados
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Despesa"
        verbose_name_plural = "Despesas"
        ordering = ["-data_entrada", "-criado_em"]

    def __str__(self):
        status = "✓" if self.pago else "✗"
        return (
            f"{self.natureza} - €{self.valor_com_iva} - {self.data_entrada} [{status}]"
        )

    @property
    def iva_valor(self):
        """Calcula o valor do IVA"""
        return self.valor_com_iva - self.valor_sem_iva

    @property
    def percentual_iva(self):
        """Calcula o percentual de IVA"""
        if self.valor_sem_iva > 0:
            return (
                (self.valor_com_iva - self.valor_sem_iva) / self.valor_sem_iva
            ) * 100
        return Decimal("0.00")

    @property
    def status_pagamento(self):
        """Retorna o status de pagamento em texto"""
        return "Pago" if self.pago else "Pendente"

    @property
    def tem_documento(self):
        """Verifica se há documento anexado"""
        return bool(self.documento)

    @property
    def nome_documento(self):
        """Retorna o nome do arquivo sem o caminho"""
        if self.documento:
            return os.path.basename(self.documento.name)
        return None

    @property
    def extensao_documento(self):
        """Retorna a extensão do documento"""
        if self.documento:
            return os.path.splitext(self.documento.name)[1].lower()
        return None


# ============================================================================
# Fase 1 — Centro de Custo + Categorias + Contas a Pagar (Bills)
#
# Sistema de DRE (Demonstração de Resultados) com agregação por:
#   - HUB Cainiao (Aveiro, Viana, …)
#   - Frota própria (não inclui frotas parceiras — essas são prestadores
#     de serviço com recibo verde, contabilizadas via DriverPreInvoice)
#   - Geral / Administrativo
# ============================================================================


class CostCenter(models.Model):
    """Centro de Custo — onde a despesa é alocada para análise de margem."""

    TYPE_HUB = "HUB"
    TYPE_FLEET = "FROTA"
    TYPE_ADMIN = "ADMIN"
    TYPE_GERAL = "GERAL"
    TYPE_OUTRO = "OUTRO"
    TYPE_CHOICES = [
        (TYPE_HUB, "HUB Cainiao"),
        (TYPE_FLEET, "Frota Própria"),
        (TYPE_ADMIN, "Administrativo"),
        (TYPE_GERAL, "Geral"),
        (TYPE_OUTRO, "Outro"),
    ]

    name = models.CharField("Nome", max_length=80, unique=True)
    code = models.CharField(
        "Código", max_length=20, unique=True,
        help_text="Curto e único, ex: HUB-AVE, FROTA-1, ADMIN",
    )
    type = models.CharField(
        "Tipo", max_length=10, choices=TYPE_CHOICES,
        default=TYPE_GERAL,
    )
    cainiao_hub = models.ForeignKey(
        "settlements.CainiaoHub",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="cost_centers",
        verbose_name="HUB Cainiao (auto-receita)",
        help_text=(
            "Se preencheres, a receita Cainiao deste HUB é "
            "atribuída automaticamente a este centro de custo no DRE."
        ),
    )
    is_active = models.BooleanField("Activo", default=True)
    notes = models.TextField("Notas", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Centro de Custo"
        verbose_name_plural = "Centros de Custo"
        ordering = ["type", "name"]

    def __str__(self):
        return f"[{self.code}] {self.name}"


class ExpenseCategory(models.Model):
    """Categoria de despesa — para agrupamento no DRE."""

    NATURE_DIRETO = "DIRETO"
    NATURE_VARIAVEL = "VARIAVEL"
    NATURE_FIXO = "FIXO"
    NATURE_FINANCEIRO = "FINANCEIRO"
    NATURE_CHOICES = [
        (NATURE_DIRETO, "Custo Directo de Operação"),
        (NATURE_VARIAVEL, "Custo Variável"),
        (NATURE_FIXO, "Custo Fixo"),
        (NATURE_FINANCEIRO, "Encargo Financeiro"),
    ]

    name = models.CharField("Nome", max_length=80, unique=True)
    code = models.CharField("Código", max_length=20, unique=True)
    nature = models.CharField(
        "Natureza no DRE", max_length=12, choices=NATURE_CHOICES,
        default=NATURE_VARIAVEL,
    )
    icon = models.CharField(
        "Ícone Lucide", max_length=40, blank=True,
        help_text="ex: fuel, wrench, building, heart-pulse",
    )
    is_active = models.BooleanField("Activo", default=True)
    sort_order = models.PositiveIntegerField("Ordem", default=100)

    class Meta:
        verbose_name = "Categoria de Despesa"
        verbose_name_plural = "Categorias de Despesas"
        ordering = ["nature", "sort_order", "name"]

    def __str__(self):
        return self.name


class FornecedorTag(models.Model):
    """Tag livre para classificar fornecedores (combustível, peças, internet,
    arrendamento, etc.). Substitui um sistema de choices fixas — o operador
    cria as tags conforme as necessidades.
    """
    name = models.CharField("Nome", max_length=40, unique=True)
    slug = models.SlugField("Slug", max_length=50, unique=True)
    color = models.CharField(
        "Cor (Tailwind)", max_length=20, blank=True,
        help_text="ex: violet, emerald, amber, blue, red. Vazio = cinza.",
    )
    is_active = models.BooleanField("Activo", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Tag de Fornecedor"
        verbose_name_plural = "Tags de Fornecedor"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)[:50]
        super().save(*args, **kwargs)


class Fornecedor(models.Model):
    """Cadastro persistente de fornecedores e prestadores de serviços.

    Substitui o input string solta no formulário de Bill. Quando seleccionado
    no lançamento, pré-preenche NIF, IBAN, MB entidade/referência, taxa IVA,
    centro de custo, recorrência. Permite agregar histórico por fornecedor
    (quanto pagamos ao mecânico X este ano).
    """

    TIPO_EMPRESA = "EMPRESA"
    TIPO_PARTICULAR = "PARTICULAR"
    TIPO_ESTADO = "ESTADO"
    TIPO_CHOICES = [
        (TIPO_EMPRESA, "Empresa"),
        (TIPO_PARTICULAR, "Particular"),
        (TIPO_ESTADO, "Estado / Entidade Pública"),
    ]

    FORMA_TRANSFERENCIA = "TRANSFERENCIA"
    FORMA_MULTIBANCO = "MULTIBANCO"
    FORMA_DEBITO_DIRETO = "DEBITO_DIRETO"
    FORMA_DINHEIRO = "DINHEIRO"
    FORMA_CHEQUE = "CHEQUE"
    FORMA_CHOICES = [
        (FORMA_TRANSFERENCIA, "Transferência"),
        (FORMA_MULTIBANCO, "Multibanco (Entidade/Ref.)"),
        (FORMA_DEBITO_DIRETO, "Débito Directo"),
        (FORMA_DINHEIRO, "Dinheiro"),
        (FORMA_CHEQUE, "Cheque"),
    ]

    RECORRENCIA_PONTUAL = "PONTUAL"
    RECORRENCIA_MENSAL = "MENSAL"
    RECORRENCIA_TRIMESTRAL = "TRIMESTRAL"
    RECORRENCIA_SEMESTRAL = "SEMESTRAL"
    RECORRENCIA_ANUAL = "ANUAL"
    RECORRENCIA_CHOICES = [
        (RECORRENCIA_PONTUAL, "Pontual"),
        (RECORRENCIA_MENSAL, "Mensal"),
        (RECORRENCIA_TRIMESTRAL, "Trimestral"),
        (RECORRENCIA_SEMESTRAL, "Semestral"),
        (RECORRENCIA_ANUAL, "Anual"),
    ]

    # Identificação
    name = models.CharField("Nome / Razão Social", max_length=150)
    nif = models.CharField(
        "NIF", max_length=20, blank=True, db_index=True,
        help_text="9 dígitos para empresas/particulares portugueses.",
    )
    tipo = models.CharField(
        "Tipo", max_length=12, choices=TIPO_CHOICES,
        default=TIPO_EMPRESA,
    )
    tags = models.ManyToManyField(
        FornecedorTag, blank=True, related_name="fornecedores",
        verbose_name="Tags",
    )

    # Categorização (auto-fill na Conta a Pagar)
    default_categoria = models.ForeignKey(
        ExpenseCategory, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="fornecedores_default",
        verbose_name="Categoria Default",
    )
    default_centro_custo = models.ForeignKey(
        CostCenter, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="fornecedores_default",
        verbose_name="Centro de Custo Default",
    )
    default_iva_rate = models.DecimalField(
        "Taxa IVA Default (%)", max_digits=5, decimal_places=2,
        default=Decimal("23.00"),
    )
    iva_dedutivel = models.BooleanField(
        "IVA Dedutível", default=False,
        help_text=(
            "Se marcado, o IVA das contas deste fornecedor entra no "
            "apuramento como crédito (gasóleo, peças, serviços com NIF)."
        ),
    )

    # Pagamento
    forma_pagamento = models.CharField(
        "Forma de Pagamento Default", max_length=20,
        choices=FORMA_CHOICES, default=FORMA_TRANSFERENCIA,
    )
    iban = models.CharField("IBAN", max_length=34, blank=True)
    mb_entidade = models.CharField(
        "Entidade MB", max_length=5, blank=True,
        help_text="5 dígitos.",
    )
    mb_referencia = models.CharField(
        "Referência MB", max_length=15, blank=True,
        help_text="9 dígitos (ou variável). Para pagamentos fixos.",
    )

    # Recorrência
    recorrencia_default = models.CharField(
        "Recorrência Default", max_length=15,
        choices=RECORRENCIA_CHOICES, default=RECORRENCIA_PONTUAL,
    )
    dia_vencimento = models.PositiveSmallIntegerField(
        "Dia do Vencimento", null=True, blank=True,
        help_text=(
            "1-31. Usado para gerar próxima conta automática "
            "(Fase Extras). Vazio = sem agendamento."
        ),
    )

    # Contrato (rendas, seguros — alertas de renovação no futuro)
    data_inicio_contrato = models.DateField(
        "Início do Contrato", null=True, blank=True,
    )
    data_fim_contrato = models.DateField(
        "Fim do Contrato", null=True, blank=True,
    )

    # Contacto
    email = models.EmailField("Email", blank=True)
    telefone = models.CharField("Telefone", max_length=30, blank=True)
    morada = models.TextField("Morada", blank=True)

    # Auditoria
    notas = models.TextField("Notas", blank=True)
    is_active = models.BooleanField("Activo", default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="fornecedores_created",
    )

    class Meta:
        verbose_name = "Fornecedor"
        verbose_name_plural = "Fornecedores"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["nif"], condition=~models.Q(nif=""),
                name="unique_fornecedor_nif_when_filled",
            ),
        ]
        indexes = [
            models.Index(fields=["is_active", "name"]),
        ]

    def __str__(self):
        if self.nif:
            return f"{self.name} ({self.nif})"
        return self.name


def upload_to_imposto_guia(instance, filename):
    yyyy = (instance.periodo_ano or 0) or "novo"
    return f"accounting/impostos/{yyyy}/{filename}"


class Imposto(models.Model):
    """Imposto — fiscalmente separado de `Bill`.

    Cobre IVA, IRC, IRS, SS, IUC e outros. Permite modalidade PARCELADO
    com N instâncias filhas (via `parent`), cada uma com a sua própria
    guia, vencimento e estado de pagamento.

    Para entrar no fluxo de caixa, o pagamento de cada parcela cria
    uma `Bill` espelho automaticamente (ver `criar_bill_espelho`).
    """

    TIPO_IVA = "IVA"
    TIPO_IRC = "IRC"
    TIPO_IRS_RETENCOES = "IRS_RETENCOES"
    TIPO_IRS_DECLARACAO = "IRS_DECLARACAO"
    TIPO_SS = "SS"
    TIPO_IUC = "IUC"
    TIPO_OUTRO = "OUTRO"
    TIPO_CHOICES = [
        (TIPO_IVA, "IVA"),
        (TIPO_IRC, "IRC"),
        (TIPO_IRS_RETENCOES, "IRS — Retenções na Fonte"),
        (TIPO_IRS_DECLARACAO, "IRS — Declaração Anual"),
        (TIPO_SS, "Segurança Social"),
        (TIPO_IUC, "IUC (Imposto Único de Circulação)"),
        (TIPO_OUTRO, "Outro"),
    ]

    MODALIDADE_MENSAL = "MENSAL_VIGENTE"
    MODALIDADE_PARCELADO = "PARCELADO"
    MODALIDADE_PONTUAL = "PONTUAL"
    MODALIDADE_CHOICES = [
        (MODALIDADE_MENSAL, "Mensal — período vigente"),
        (MODALIDADE_PARCELADO, "Parcelado (N prestações)"),
        (MODALIDADE_PONTUAL, "Pontual"),
    ]

    STATUS_PENDENTE = "PENDENTE"
    STATUS_PAGO = "PAGO"
    STATUS_EM_ATRASO = "EM_ATRASO"
    STATUS_ANULADO = "ANULADO"
    STATUS_CHOICES = [
        (STATUS_PENDENTE, "Pendente"),
        (STATUS_PAGO, "Pago"),
        (STATUS_EM_ATRASO, "Em Atraso"),
        (STATUS_ANULADO, "Anulado"),
    ]

    # Identificação
    nome = models.CharField(
        "Designação", max_length=200,
        help_text=(
            "ex: 'IVA Janeiro 2026', 'IRC 2024 — Plano 6 prestações', "
            "'SS Fevereiro 2026'."
        ),
    )
    tipo = models.CharField(
        "Tipo", max_length=20, choices=TIPO_CHOICES, db_index=True,
    )
    modalidade = models.CharField(
        "Modalidade", max_length=20, choices=MODALIDADE_CHOICES,
        default=MODALIDADE_MENSAL, db_index=True,
    )
    fornecedor = models.ForeignKey(
        Fornecedor, on_delete=models.PROTECT,
        related_name="impostos",
        null=True, blank=True,
        help_text=(
            "Entidade credora (Autoridade Tributária, Segurança Social). "
            "Cria como Fornecedor tipo=ESTADO."
        ),
    )

    # Período
    periodo_ano = models.PositiveSmallIntegerField(
        "Ano de Referência", db_index=True,
    )
    periodo_mes = models.PositiveSmallIntegerField(
        "Mês de Referência", null=True, blank=True,
        help_text="1-12. Para impostos mensais. Vazio = anual/parcelado.",
    )

    # Valor
    valor = models.DecimalField(
        "Valor", max_digits=12, decimal_places=2,
        help_text=(
            "Para o pai PARCELADO = total da dívida. "
            "Para uma prestação = valor da prestação."
        ),
    )

    # Pagamento (oficial)
    mb_entidade = models.CharField("Entidade MB", max_length=5, blank=True)
    mb_referencia = models.CharField(
        "Referência MB", max_length=20, blank=True,
    )
    guia_pagamento = models.FileField(
        "Guia / Comprovativo", upload_to=upload_to_imposto_guia,
        null=True, blank=True,
    )

    # Datas
    data_vencimento = models.DateField("Data de Vencimento", db_index=True)
    data_pagamento = models.DateField(
        "Data de Pagamento", null=True, blank=True,
    )

    status = models.CharField(
        "Estado", max_length=12, choices=STATUS_CHOICES,
        default=STATUS_PENDENTE, db_index=True,
    )

    # Parcelamento (PARCELADO)
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE,
        null=True, blank=True, related_name="parcelas",
        help_text="Imposto-pai (apenas para prestações de PARCELADO).",
    )
    parcela_numero = models.PositiveSmallIntegerField(
        "Nº da Prestação", null=True, blank=True,
    )
    parcela_total = models.PositiveSmallIntegerField(
        "Total de Prestações", null=True, blank=True,
    )

    # Mirror em Bill (criado quando paga, para entrar no fluxo de caixa)
    bill_espelho = models.OneToOneField(
        "Bill", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="imposto_origem",
        help_text=(
            "Bill criada automaticamente quando o imposto é marcado "
            "como PAGO, para entrar no DRE / Fluxo de Caixa."
        ),
    )

    # Auditoria
    notas = models.TextField("Notas", blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="impostos_criados",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Imposto"
        verbose_name_plural = "Impostos"
        ordering = ["-data_vencimento", "-id"]
        indexes = [
            models.Index(fields=["tipo", "periodo_ano", "periodo_mes"]),
            models.Index(fields=["status", "data_vencimento"]),
            models.Index(fields=["parent", "parcela_numero"]),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.nome} · €{self.valor}"

    @property
    def is_parent(self):
        """True se este imposto é o pai de uma série de parcelas."""
        return (
            self.modalidade == self.MODALIDADE_PARCELADO
            and self.parent_id is None
        )

    @property
    def is_parcela(self):
        """True se é uma prestação dentro de um plano parcelado."""
        return self.parent_id is not None

    def update_status_from_parcelas(self):
        """Para um pai PARCELADO: deriva status agregado das parcelas
        e guarda. Sem parcelas, mantém o que já tinha."""
        if not self.is_parent:
            return
        children = list(self.parcelas.all())
        if not children:
            return
        all_paid = all(c.status == self.STATUS_PAGO for c in children)
        any_overdue = any(c.status == self.STATUS_EM_ATRASO for c in children)
        if all_paid:
            new_status = self.STATUS_PAGO
        elif any_overdue:
            new_status = self.STATUS_EM_ATRASO
        else:
            new_status = self.STATUS_PENDENTE
        if new_status != self.status:
            self.status = new_status
            self.save(update_fields=["status", "updated_at"])


def upload_to_bills(instance, filename):
    bill_id = instance.bill_id or "novo"
    return f"accounting/bills/{bill_id}/{filename}"


class Bill(models.Model):
    """Conta a Pagar — registo individual de despesa com fornecedor.

    Diferente de `Expenses` (legacy): suporta categoria por FK,
    centro de custo, recorrência, status mais rico, múltiplos anexos.
    """

    STATUS_AWAITING = "AWAITING"
    STATUS_PENDING = "PENDING"
    STATUS_PAID = "PAID"
    STATUS_OVERDUE = "OVERDUE"
    STATUS_REJECTED = "REJECTED"
    STATUS_CANCELLED = "CANCELLED"
    STATUS_CHOICES = [
        (STATUS_AWAITING, "A Aguardar Aprovação"),
        (STATUS_PENDING, "Pendente"),
        (STATUS_PAID, "Pago"),
        (STATUS_OVERDUE, "Vencido"),
        (STATUS_REJECTED, "Rejeitada"),
        (STATUS_CANCELLED, "Cancelado"),
    ]

    RECURRENCE_NONE = "NONE"
    RECURRENCE_MONTHLY = "MONTHLY"
    RECURRENCE_QUARTERLY = "QUARTERLY"
    RECURRENCE_YEARLY = "YEARLY"
    RECURRENCE_CHOICES = [
        (RECURRENCE_NONE, "Pontual"),
        (RECURRENCE_MONTHLY, "Mensal"),
        (RECURRENCE_QUARTERLY, "Trimestral"),
        (RECURRENCE_YEARLY, "Anual"),
    ]

    description = models.CharField(
        "Descrição", max_length=200,
        help_text="ex: Aluguer Setembro 2026, Combustível Frota 1",
    )
    fornecedor = models.ForeignKey(
        "Fornecedor", on_delete=models.PROTECT,
        null=True, blank=True, related_name="bills",
        verbose_name="Fornecedor (cadastro)",
        help_text=(
            "Selecciona um fornecedor pré-cadastrado. Se vazio, usa o "
            "campo 'supplier' livre (legado / lançamento avulso)."
        ),
    )
    supplier = models.CharField(
        "Fornecedor (livre)", max_length=120, blank=True,
        help_text=(
            "Nome do fornecedor — usado quando 'fornecedor' (FK) não "
            "está preenchido. Para novos lançamentos, prefere o cadastro."
        ),
    )
    supplier_nif = models.CharField(
        "NIF", max_length=20, blank=True,
    )
    invoice_number = models.CharField(
        "Nº Factura", max_length=50, blank=True,
    )
    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.PROTECT,
        related_name="bills",
        verbose_name="Categoria",
    )
    cost_center = models.ForeignKey(
        CostCenter,
        on_delete=models.PROTECT,
        related_name="bills",
        verbose_name="Centro de Custo",
    )
    amount_net = models.DecimalField(
        "Valor sem IVA", max_digits=12, decimal_places=2,
    )
    iva_rate = models.DecimalField(
        "Taxa IVA (%)", max_digits=5, decimal_places=2,
        default=Decimal("23.00"),
    )
    amount_total = models.DecimalField(
        "Valor com IVA", max_digits=12, decimal_places=2,
    )
    issue_date = models.DateField("Data Emissão")
    due_date = models.DateField("Data Vencimento")
    paid_date = models.DateField("Data Pagamento", null=True, blank=True)
    paid_amount = models.DecimalField(
        "Valor Pago", max_digits=12, decimal_places=2,
        null=True, blank=True,
    )
    payment_reference = models.CharField(
        "Referência Pagamento", max_length=200, blank=True,
        help_text="MB WAY, IBAN, transferência, etc.",
    )
    payment_proof = models.FileField(
        "Comprovativo de Pagamento",
        upload_to="bills/comprovativos/%Y/%m/",
        null=True, blank=True,
    )
    status = models.CharField(
        "Estado", max_length=10, choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    recurrence = models.CharField(
        "Recorrência", max_length=10, choices=RECURRENCE_CHOICES,
        default=RECURRENCE_NONE,
    )
    parent = models.ForeignKey(
        "self", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="instances",
        verbose_name="Conta-mãe (recorrência)",
    )
    notes = models.TextField("Notas internas", blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="bills_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Conta a Pagar"
        verbose_name_plural = "Contas a Pagar"
        ordering = ["-due_date", "-id"]
        indexes = [
            models.Index(fields=["status", "due_date"]),
            models.Index(fields=["category", "issue_date"]),
            models.Index(fields=["cost_center", "issue_date"]),
        ]

    def __str__(self):
        return (
            f"{self.description} · €{self.amount_total} · "
            f"{self.get_status_display()}"
        )

    @property
    def is_overdue(self):
        from datetime import date as _d
        if self.status == self.STATUS_PAID:
            return False
        return self.due_date < _d.today()

    @property
    def iva_amount(self):
        return self.amount_total - self.amount_net

    def needs_approval(self):
        """True se a bill cai sob uma regra de aprovação activa."""
        rule = ApprovalRule.rule_for_amount(self.amount_total)
        return rule is not None

    def save(self, *args, **kwargs):
        # Em criação: se cai numa regra de aprovação, fica AWAITING
        is_new = self.pk is None
        if (
            is_new
            and self.status == self.STATUS_PENDING
            and self.needs_approval()
        ):
            self.status = self.STATUS_AWAITING
        # OVERDUE não se aplica enquanto AWAITING/REJECTED/CANCELLED
        if (
            self.status == self.STATUS_PENDING
            and self.is_overdue
        ):
            self.status = self.STATUS_OVERDUE
        elif (
            self.status == self.STATUS_OVERDUE
            and not self.is_overdue
        ):
            self.status = self.STATUS_PENDING
        super().save(*args, **kwargs)

    # ── Recorrência ─────────────────────────────────────────────────────
    OFFSET_MONTHS = {
        RECURRENCE_MONTHLY: 1,
        RECURRENCE_QUARTERLY: 3,
        RECURRENCE_YEARLY: 12,
    }

    def _add_months(self, d, months):
        from calendar import monthrange
        m = d.month - 1 + months
        y = d.year + m // 12
        m = m % 12 + 1
        last_day = monthrange(y, m)[1]
        return d.replace(year=y, month=m, day=min(d.day, last_day))

    @property
    def is_recurrence_template(self):
        """Esta Bill é a "mãe" de uma recorrência."""
        return self.recurrence != self.RECURRENCE_NONE and self.parent_id is None

    def latest_in_chain(self):
        """A última instância gerada nesta cadeia de recorrência (ou self
        se ainda não houve)."""
        if not self.is_recurrence_template:
            template = self.parent if self.parent_id else self
        else:
            template = self
        latest = (
            Bill.objects.filter(parent=template)
            .order_by("-due_date").first()
        )
        return latest or template

    def next_due_date(self):
        """Próxima data de vencimento esperada na cadeia."""
        offset = self.OFFSET_MONTHS.get(self.recurrence)
        if not offset:
            return None
        last = self.latest_in_chain()
        return self._add_months(last.due_date, offset)

    def generate_next_instance(self, by_user=None):
        """Cria a próxima instância na cadeia de recorrência.

        Retorna a Bill criada, ou None se não houver recorrência ou
        a próxima já existir.
        """
        if self.recurrence == self.RECURRENCE_NONE:
            return None
        template = self if self.is_recurrence_template else (
            self.parent or self
        )
        offset = self.OFFSET_MONTHS.get(self.recurrence)
        if not offset:
            return None
        last = template.latest_in_chain()
        next_due = self._add_months(last.due_date, offset)
        # Evitar duplicados — se já existe instância com essa due_date
        if Bill.objects.filter(
            parent=template, due_date=next_due,
        ).exists():
            return None
        next_issue = self._add_months(last.issue_date, offset)
        new_bill = Bill.objects.create(
            description=template.description,
            supplier=template.supplier,
            supplier_nif=template.supplier_nif,
            invoice_number="",  # número novo, fica em branco
            category=template.category,
            cost_center=template.cost_center,
            amount_net=template.amount_net,
            iva_rate=template.iva_rate,
            amount_total=template.amount_total,
            issue_date=next_issue,
            due_date=next_due,
            status=Bill.STATUS_PENDING,
            recurrence=template.recurrence,
            parent=template,
            notes=(
                f"Auto-gerada a partir de #{template.pk} "
                f"({template.get_recurrence_display()})"
            ),
            created_by=by_user,
        )
        return new_bill


class ApprovalRule(models.Model):
    """Regra de aprovação por valor — define quem pode aprovar acima de
    um certo limite. Bills com valor acima do menor limite onde há regras
    activas exigem aprovação antes de poderem ser pagas.
    """
    name = models.CharField("Nome", max_length=80)
    min_amount = models.DecimalField(
        "Valor mínimo (€)", max_digits=12, decimal_places=2,
        help_text=(
            "Bills com amount_total ≥ este valor exigem aprovação. "
            "Use 0 para exigir aprovação em todas as bills."
        ),
    )
    approvers = models.ManyToManyField(
        User, related_name="bill_approval_rules",
        help_text="Utilizadores que podem aprovar bills nesta faixa.",
    )
    is_active = models.BooleanField("Activa", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Regra de Aprovação"
        verbose_name_plural = "Regras de Aprovação"
        ordering = ["min_amount"]

    def __str__(self):
        return f"{self.name} (≥ €{self.min_amount})"

    @classmethod
    def rule_for_amount(cls, amount):
        """Retorna a regra mais específica que se aplica a este valor,
        ou None se nenhuma regra se aplica (= não precisa aprovação)."""
        return cls.objects.filter(
            is_active=True, min_amount__lte=amount,
        ).order_by("-min_amount").first()


class BillApproval(models.Model):
    """Registo de aprovação ou rejeição de uma Bill."""
    DECISION_APPROVED = "APPROVED"
    DECISION_REJECTED = "REJECTED"
    DECISION_CHOICES = [
        (DECISION_APPROVED, "Aprovada"),
        (DECISION_REJECTED, "Rejeitada"),
    ]

    bill = models.ForeignKey(
        "Bill", on_delete=models.CASCADE,
        related_name="approvals",
    )
    approver = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name="bill_approvals",
    )
    decision = models.CharField(
        "Decisão", max_length=10, choices=DECISION_CHOICES,
    )
    comments = models.TextField("Comentários", blank=True)
    decided_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Aprovação"
        verbose_name_plural = "Aprovações"
        ordering = ["-decided_at"]

    def __str__(self):
        return (
            f"{self.bill.description} → {self.get_decision_display()} "
            f"por {self.approver} em {self.decided_at:%d/%m/%Y}"
        )


class BankStatement(models.Model):
    """Extracto bancário importado (CSV/OFX). Cada upload = 1 statement."""
    name = models.CharField("Nome / Banco", max_length=80)
    period_from = models.DateField("Período de", null=True, blank=True)
    period_to = models.DateField("Período até", null=True, blank=True)
    file = models.FileField(
        "Ficheiro original",
        upload_to="accounting/statements/",
        validators=[validate_document_extension],
        null=True, blank=True,
    )
    n_transactions = models.PositiveIntegerField(default=0)
    n_matched = models.PositiveIntegerField(default=0)
    uploaded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name="bank_statements_uploaded",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Extracto Bancário"
        verbose_name_plural = "Extractos Bancários"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.name} · {self.uploaded_at:%d/%m/%Y}"


class BankTransaction(models.Model):
    """Transacção individual num extracto. Pode ser conciliada com 1 Bill."""
    DIRECTION_DEBIT = "DEBIT"   # saída (pagamento)
    DIRECTION_CREDIT = "CREDIT"  # entrada
    DIRECTION_CHOICES = [
        (DIRECTION_DEBIT, "Débito"),
        (DIRECTION_CREDIT, "Crédito"),
    ]

    statement = models.ForeignKey(
        BankStatement, on_delete=models.CASCADE,
        related_name="transactions",
    )
    date = models.DateField("Data")
    description = models.CharField("Descrição", max_length=300)
    direction = models.CharField(
        "Sentido", max_length=6, choices=DIRECTION_CHOICES,
    )
    amount = models.DecimalField(
        "Valor (€)", max_digits=12, decimal_places=2,
        help_text="Sempre positivo — usa direction para sentido.",
    )
    external_id = models.CharField(
        "ID externo", max_length=80, blank=True,
        help_text="Identificador único do banco (FITID OFX, ref…).",
    )
    matched_bill = models.ForeignKey(
        "Bill", on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="bank_transactions",
        verbose_name="Conta conciliada",
    )
    matched_at = models.DateTimeField(null=True, blank=True)
    matched_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="bank_transactions_matched",
    )

    class Meta:
        verbose_name = "Transacção Bancária"
        verbose_name_plural = "Transacções Bancárias"
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["statement", "date"]),
            models.Index(fields=["matched_bill"]),
        ]

    def __str__(self):
        s = "+" if self.direction == self.DIRECTION_CREDIT else "-"
        return f"{self.date} · {s}€{self.amount} · {self.description[:40]}"

    def suggest_bill_matches(self, tolerance_days=5):
        """Sugere Bills (PAID ou PENDING) compatíveis com esta transacção
        por valor exacto e data próxima."""
        if self.direction != self.DIRECTION_DEBIT:
            return Bill.objects.none()
        from datetime import timedelta
        return Bill.objects.filter(
            amount_total=self.amount,
            bank_transactions__isnull=True,
            paid_date__range=(
                self.date - timedelta(days=tolerance_days),
                self.date + timedelta(days=tolerance_days),
            ),
        ).order_by("paid_date")[:5]

    def suggest_pf_matches(self, tolerance_days=5):
        """Sugere PFs (DriverPreInvoice) PAGAS compatíveis com a transacção.

        Match por valor exacto + data próxima de data_pagamento + bonus
        score se nome do motorista aparece na descrição da transacção.
        """
        if self.direction != self.DIRECTION_DEBIT:
            return []
        from datetime import timedelta
        from settlements.models import DriverPreInvoice
        candidates = list(
            DriverPreInvoice.objects.filter(
                total_a_receber=self.amount,
                status="PAGO",
                data_pagamento__range=(
                    self.date - timedelta(days=tolerance_days),
                    self.date + timedelta(days=tolerance_days),
                ),
            ).select_related("driver")[:10]
        )
        # Score: nome do motorista presente na descrição → topo
        desc_lower = (self.description or "").lower()
        scored = []
        for pf in candidates:
            score = 0
            if pf.driver.apelido and pf.driver.apelido.lower() in desc_lower:
                score += 10
            if pf.driver.nome_completo:
                first = pf.driver.nome_completo.split()[0].lower()
                if first in desc_lower:
                    score += 5
            scored.append((score, pf))
        scored.sort(key=lambda x: -x[0])
        return [pf for _s, pf in scored[:5]]


class BillAttachment(models.Model):
    """Anexo de uma Conta a Pagar — factura, comprovante, etc."""

    KIND_INVOICE = "INVOICE"
    KIND_PROOF = "PROOF"
    KIND_OTHER = "OTHER"
    KIND_CHOICES = [
        (KIND_INVOICE, "Factura / Recibo"),
        (KIND_PROOF, "Comprovante de Pagamento"),
        (KIND_OTHER, "Outro"),
    ]

    bill = models.ForeignKey(
        Bill, on_delete=models.CASCADE,
        related_name="attachments",
    )
    kind = models.CharField(
        "Tipo", max_length=10, choices=KIND_CHOICES,
        default=KIND_INVOICE,
    )
    file = models.FileField(
        "Ficheiro",
        upload_to=upload_to_bills,
        validators=[validate_document_extension],
    )
    description = models.CharField(
        "Descrição", max_length=200, blank=True,
    )
    uploaded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="bill_attachments",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Anexo"
        verbose_name_plural = "Anexos"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.get_kind_display()}: {self.filename}"

    @property
    def filename(self):
        return os.path.basename(self.file.name) if self.file else ""

    @property
    def extension(self):
        if self.file:
            return os.path.splitext(self.file.name)[1].lower()
        return ""

    @property
    def is_image(self):
        return self.extension in (".jpg", ".jpeg", ".png", ".gif")

    @property
    def is_pdf(self):
        return self.extension == ".pdf"
