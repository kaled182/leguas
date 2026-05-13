"""Modelos da Folha de Pagamento — funcionários mensalistas PT.

Cobertura Fase 1 (MVP):
- Employee: cadastro do funcionário (CSC/Termo/Part-time/Estágio)
- Payroll: folha mensal por funcionário (status flow)
- PayrollComponent: linhas individuais (vencimento, sub. refeição, IRS, SS, etc.)
- IRSTable: tabelas oficiais AT (admin pode editar/adicionar ano novo)
"""
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class Employee(models.Model):
    """Funcionário mensalista da Léguas Franzinas.

    Distinto de DriverProfile (recibos verdes / Cat. B). Funcionários
    mensalistas têm contrato CLT, recebem subsídios (Natal/Férias),
    descontam SS (11%) + IRS na fonte, e geram TSU (23.75%) para o
    empregador.
    """

    CONTRATO_SEM_TERMO = "SEM_TERMO"
    CONTRATO_TERMO_CERTO = "TERMO_CERTO"
    CONTRATO_TERMO_INCERTO = "TERMO_INCERTO"
    CONTRATO_PART_TIME = "PART_TIME"
    CONTRATO_ESTAGIO = "ESTAGIO"
    CONTRATO_CHOICES = [
        (CONTRATO_SEM_TERMO, "Contrato Sem Termo (efectivo)"),
        (CONTRATO_TERMO_CERTO, "Contrato a Termo Certo"),
        (CONTRATO_TERMO_INCERTO, "Contrato a Termo Incerto"),
        (CONTRATO_PART_TIME, "Part-Time"),
        (CONTRATO_ESTAGIO, "Estágio (IEFP / profissional)"),
    ]

    SUBSIDIOS_DUODECIMOS = "DUODECIMOS"
    SUBSIDIOS_LUMP_SUM = "LUMP_SUM"
    SUBSIDIOS_CHOICES = [
        (SUBSIDIOS_DUODECIMOS, "Duodécimos (1/12 mensal)"),
        (SUBSIDIOS_LUMP_SUM, "Lump-sum (Jun/Dez)"),
    ]

    nome = models.CharField("Nome completo", max_length=200)
    nif = models.CharField(
        "NIF", max_length=20, blank=True,
        help_text="Número de Identificação Fiscal (9 dígitos PT).",
    )
    niss = models.CharField(
        "NISS", max_length=20, blank=True,
        help_text="Número de Identificação da Segurança Social.",
    )
    iban = models.CharField("IBAN", max_length=34, blank=True)
    email = models.EmailField(blank=True)
    telefone = models.CharField(max_length=20, blank=True)

    # Contrato
    contrato_tipo = models.CharField(
        "Tipo de Contrato", max_length=20, choices=CONTRATO_CHOICES,
        default=CONTRATO_SEM_TERMO,
    )
    part_time_pct = models.DecimalField(
        "% do tempo (part-time)", max_digits=5, decimal_places=2,
        default=Decimal("100.00"),
        help_text="100 = full-time. 50 = meio horário, etc.",
    )
    data_admissao = models.DateField("Data de Admissão")
    data_saida = models.DateField(
        "Data de Saída", null=True, blank=True,
        help_text="Vazio = ainda activo.",
    )
    ativo = models.BooleanField(default=True, db_index=True)

    # Remuneração base
    vencimento_base = models.DecimalField(
        "Vencimento Base (€/mês)", max_digits=10, decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    diuturnidades = models.DecimalField(
        "Diuturnidades (€/mês)", max_digits=10, decimal_places=2,
        default=Decimal("0.00"),
    )
    subs_alimentacao_dia = models.DecimalField(
        "Sub. Alimentação (€/dia)", max_digits=6, decimal_places=2,
        default=Decimal("9.60"),
        help_text=(
            "Valor por dia útil. 2026: até €6.00 dinheiro ou €9.60 "
            "cartão isento de IRS/SS. Acima do limite tributado."
        ),
    )
    dias_uteis_mes_default = models.PositiveSmallIntegerField(
        "Dias úteis/mês (default)", default=22,
        help_text="Para cálculo do subsídio de alimentação.",
    )

    # IRS — tabela aplicável (depende composição familiar e dependentes)
    irs_tabela = models.PositiveSmallIntegerField(
        "Tabela IRS", default=1,
        help_text=(
            "1: Não casado 0 dep | 2: Não casado 1+ dep | "
            "3: Casado 2 tit 0 dep | 4: Casado 2 tit 1+ dep | "
            "5: Casado 1 tit 0 dep | 6: Casado 1 tit 1+ dep | "
            "7: Não casado deficiente | 8: Casado 2 tit defic | "
            "9: Casado 1 tit defic"
        ),
    )
    dependentes_irs = models.PositiveSmallIntegerField(
        "Nº Dependentes", default=0,
    )

    # Subsídios Natal/Férias — modalidade
    subsidios_mode = models.CharField(
        "Modalidade subs. Natal/Férias", max_length=20,
        choices=SUBSIDIOS_CHOICES, default=SUBSIDIOS_DUODECIMOS,
    )

    # Integração contabilidade
    fornecedor = models.OneToOneField(
        "accounting.Fornecedor",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="employee",
        help_text="Espelho como Fornecedor — usado nas Bills do salário.",
    )
    cost_center = models.ForeignKey(
        "accounting.CostCenter",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Centro de Custo",
        help_text="Centro de custo onde imputar o custo salarial.",
    )

    notas = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Funcionário"
        verbose_name_plural = "Funcionários"
        ordering = ["-ativo", "nome"]

    def __str__(self):
        return f"{self.nome} ({self.get_contrato_tipo_display()})"

    @property
    def vencimento_efectivo(self):
        """Vencimento ajustado por % part-time."""
        return (
            self.vencimento_base * self.part_time_pct / Decimal("100")
        ).quantize(Decimal("0.01"))


class Payroll(models.Model):
    """Folha de pagamento mensal de um funcionário.

    Status flow:
      RASCUNHO → APROVADO (gera Imposto SS + Imposto IRS retido)
              → PAGO (gera Bill espelho — entra DRE/Fluxo de Caixa)
              → CANCELADO (cancela Impostos + Bill em cascata)
    """

    STATUS_RASCUNHO = "RASCUNHO"
    STATUS_APROVADO = "APROVADO"
    STATUS_PAGO = "PAGO"
    STATUS_CANCELADO = "CANCELADO"
    STATUS_CHOICES = [
        (STATUS_RASCUNHO, "Rascunho"),
        (STATUS_APROVADO, "Aprovado"),
        (STATUS_PAGO, "Pago"),
        (STATUS_CANCELADO, "Cancelado"),
    ]

    employee = models.ForeignKey(
        Employee, on_delete=models.PROTECT, related_name="payrolls",
    )
    periodo_ano = models.PositiveSmallIntegerField(db_index=True)
    periodo_mes = models.PositiveSmallIntegerField(db_index=True)

    status = models.CharField(
        "Estado", max_length=15, choices=STATUS_CHOICES,
        default=STATUS_RASCUNHO, db_index=True,
    )

    # Totais (calculados pelas componentes)
    total_bruto = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
    )
    total_descontos = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
    )
    total_liquido = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
    )

    # Encargos do empregador (gerados ao APROVAR)
    tsu_empregador = models.DecimalField(
        "TSU Empregador (23.75%)", max_digits=12, decimal_places=2,
        default=Decimal("0.00"),
    )

    # FKs para entidades fiscais/financeiras criadas em cascata
    tsu_imposto = models.OneToOneField(
        "accounting.Imposto",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="payroll_tsu",
        help_text="Imposto SS 23.75% criado ao APROVAR.",
    )
    irs_imposto = models.OneToOneField(
        "accounting.Imposto",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="payroll_irs",
        help_text="Imposto IRS retido (AT) criado ao APROVAR.",
    )
    bill_espelho = models.OneToOneField(
        "accounting.Bill",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="payroll_origem",
        help_text="Bill criada ao marcar PAGO (entra no DRE).",
    )

    data_pagamento = models.DateField(null=True, blank=True)
    notas = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+",
    )

    class Meta:
        verbose_name = "Folha de Pagamento"
        verbose_name_plural = "Folhas de Pagamento"
        ordering = ["-periodo_ano", "-periodo_mes", "employee__nome"]
        unique_together = [("employee", "periodo_ano", "periodo_mes")]
        indexes = [
            models.Index(fields=["-periodo_ano", "-periodo_mes"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return (
            f"{self.employee.nome} — {self.periodo_mes:02d}/{self.periodo_ano} "
            f"({self.get_status_display()})"
        )

    @property
    def periodo_label(self):
        meses = [
            "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
            "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
        ]
        try:
            return f"{meses[self.periodo_mes - 1]} {self.periodo_ano}"
        except IndexError:
            return f"{self.periodo_mes:02d}/{self.periodo_ano}"

    def recalcular(self):
        """Recalcula totais a partir das componentes."""
        bruto = Decimal("0.00")
        descontos = Decimal("0.00")
        for c in self.componentes.all():
            if c.tipo in PayrollComponent.TIPOS_BRUTO:
                bruto += c.valor
            elif c.tipo in PayrollComponent.TIPOS_DESCONTO:
                descontos += c.valor
        self.total_bruto = bruto
        self.total_descontos = descontos
        self.total_liquido = bruto - descontos
        # TSU sempre sobre bruto tributado (simplificado: sobre total bruto
        # menos sub. refeição até limite). Aqui usamos o bruto cheio — ajuste
        # fino fica para Fase 2 quando integrarmos limites de isenção.
        self.tsu_empregador = (bruto * Decimal("0.2375")).quantize(Decimal("0.01"))


class PayrollComponent(models.Model):
    """Linha individual de uma folha de pagamento (bruto ou desconto)."""

    # Tipos brutos (somam ao bruto)
    TIPO_VENCIMENTO_BASE = "VENCIMENTO_BASE"
    TIPO_DIUTURNIDADE = "DIUTURNIDADE"
    TIPO_SUB_REFEICAO = "SUB_REFEICAO"
    TIPO_SUB_NATAL = "SUB_NATAL"
    TIPO_SUB_FERIAS = "SUB_FERIAS"
    TIPO_HORA_EXTRA = "HORA_EXTRA"
    TIPO_PREMIO = "PREMIO"
    TIPO_TRAB_NOTURNO = "TRAB_NOTURNO"
    TIPO_OUTRO_BRUTO = "OUTRO_BRUTO"

    # Tipos descontos (subtraem ao bruto para chegar ao líquido)
    TIPO_IRS_RETENCAO = "IRS_RETENCAO"
    TIPO_SS_EMPREGADO = "SS_EMPREGADO"
    TIPO_FALTA = "FALTA"
    TIPO_PENHORA = "PENHORA"
    TIPO_OUTRO_DESCONTO = "OUTRO_DESCONTO"

    TIPO_CHOICES = [
        (TIPO_VENCIMENTO_BASE, "Vencimento Base"),
        (TIPO_DIUTURNIDADE, "Diuturnidade"),
        (TIPO_SUB_REFEICAO, "Subsídio de Alimentação"),
        (TIPO_SUB_NATAL, "Subsídio de Natal"),
        (TIPO_SUB_FERIAS, "Subsídio de Férias"),
        (TIPO_HORA_EXTRA, "Horas Extra"),
        (TIPO_PREMIO, "Prémio / Comissão"),
        (TIPO_TRAB_NOTURNO, "Trabalho Nocturno"),
        (TIPO_OUTRO_BRUTO, "Outro (bruto)"),
        (TIPO_IRS_RETENCAO, "IRS — Retenção na Fonte"),
        (TIPO_SS_EMPREGADO, "Seg. Social Empregado (11%)"),
        (TIPO_FALTA, "Falta / Atraso"),
        (TIPO_PENHORA, "Penhora Judicial"),
        (TIPO_OUTRO_DESCONTO, "Outro (desconto)"),
    ]

    TIPOS_BRUTO = {
        TIPO_VENCIMENTO_BASE, TIPO_DIUTURNIDADE, TIPO_SUB_REFEICAO,
        TIPO_SUB_NATAL, TIPO_SUB_FERIAS, TIPO_HORA_EXTRA, TIPO_PREMIO,
        TIPO_TRAB_NOTURNO, TIPO_OUTRO_BRUTO,
    }
    TIPOS_DESCONTO = {
        TIPO_IRS_RETENCAO, TIPO_SS_EMPREGADO, TIPO_FALTA,
        TIPO_PENHORA, TIPO_OUTRO_DESCONTO,
    }

    payroll = models.ForeignKey(
        Payroll, on_delete=models.CASCADE, related_name="componentes",
    )
    tipo = models.CharField(
        "Tipo", max_length=30, choices=TIPO_CHOICES, db_index=True,
    )
    descricao = models.CharField(
        "Descrição", max_length=200, blank=True,
    )
    valor = models.DecimalField(
        "Valor (€)", max_digits=10, decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Sempre positivo. O sinal vem do tipo (bruto vs desconto).",
    )
    quantidade = models.DecimalField(
        "Quantidade", max_digits=8, decimal_places=2,
        default=Decimal("1.00"),
        help_text="Para horas extra (h), faltas (dias), sub. refeição (dias).",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Componente da Folha"
        verbose_name_plural = "Componentes da Folha"
        ordering = ["tipo", "id"]

    def __str__(self):
        return f"{self.get_tipo_display()}: €{self.valor}"

    @property
    def is_bruto(self):
        return self.tipo in self.TIPOS_BRUTO


class IRSTable(models.Model):
    """Tabela de retenção de IRS na fonte — edita por ano e tabela.

    Cada combinação (ano, tabela_id) tem múltiplos escalões com taxas.
    O admin pode adicionar tabelas novas quando a AT publica.
    """

    ano = models.PositiveSmallIntegerField(db_index=True)
    tabela_id = models.PositiveSmallIntegerField(
        help_text="1-9 (ver Employee.irs_tabela)",
    )
    nome = models.CharField(
        max_length=200, blank=True,
        help_text="Ex: 'Tabela I — Não casado, sem dependentes'",
    )
    is_active = models.BooleanField(default=True)
    notas = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Tabela IRS"
        verbose_name_plural = "Tabelas IRS"
        ordering = ["-ano", "tabela_id"]
        unique_together = [("ano", "tabela_id")]

    def __str__(self):
        return f"IRS {self.ano} · Tabela {self.tabela_id} — {self.nome or '—'}"


class IRSEscalao(models.Model):
    """Escalão de uma tabela IRS.

    Para cada escalão: limite superior do rendimento mensal e taxa
    marginal. Linear simplificado: o IRS retido = rendimento × taxa.
    (Modelo real da AT é mais complexo com parcela a abater por dependente,
    mas para o MVP usamos taxa única por escalão.)
    """

    tabela = models.ForeignKey(
        IRSTable, on_delete=models.CASCADE, related_name="escaloes",
    )
    limite_superior = models.DecimalField(
        "Limite superior (€)", max_digits=10, decimal_places=2,
        help_text="Rendimento mensal até este valor entra neste escalão.",
    )
    taxa = models.DecimalField(
        "Taxa (%)", max_digits=5, decimal_places=2,
        default=Decimal("0.00"),
    )
    parcela_abater = models.DecimalField(
        "Parcela a abater (€)", max_digits=10, decimal_places=2,
        default=Decimal("0.00"),
        help_text="Por dependente (se aplicável). Default 0 para MVP.",
    )

    class Meta:
        verbose_name = "Escalão IRS"
        verbose_name_plural = "Escalões IRS"
        ordering = ["tabela", "limite_superior"]

    def __str__(self):
        return f"≤ €{self.limite_superior} → {self.taxa}%"
