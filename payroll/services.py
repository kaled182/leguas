"""Serviços de folha de pagamento: cálculo IRS, SS, geração mensal,
aprovação (cria Imposto), pagamento (cria Bill espelho).
"""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction

from .models import (
    Employee, Payroll, PayrollComponent, IRSTable, IRSEscalao,
)

# Constantes oficiais Portugal 2026
SS_RATE_EMPREGADO = Decimal("0.11")   # 11% — sobre bruto
SS_RATE_EMPREGADOR = Decimal("0.2375")  # 23.75% — TSU


def calculate_ss(bruto):
    """Desconto de Segurança Social do empregado (11%)."""
    return (bruto * SS_RATE_EMPREGADO).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP,
    )


def calculate_irs(bruto, tabela_id, ano):
    """Calcula IRS retido na fonte usando IRSTable.

    Modelo linear simplificado: procura o escalão cujo limite_superior
    >= bruto e aplica taxa - parcela_abater. Se não houver tabela activa
    no ano, devolve 0.
    """
    if bruto <= 0:
        return Decimal("0.00")
    try:
        tabela = IRSTable.objects.get(
            ano=ano, tabela_id=tabela_id, is_active=True,
        )
    except IRSTable.DoesNotExist:
        return Decimal("0.00")
    # Encontra o escalão certo
    esc = tabela.escaloes.filter(
        limite_superior__gte=bruto,
    ).order_by("limite_superior").first()
    if not esc:
        # Acima do último escalão — usa o último
        esc = tabela.escaloes.order_by("-limite_superior").first()
    if not esc:
        return Decimal("0.00")
    valor = bruto * (esc.taxa / Decimal("100"))
    valor -= esc.parcela_abater
    if valor < 0:
        valor = Decimal("0.00")
    return valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@transaction.atomic
def generate_monthly_payroll(
    employee, ano, mes, dias_uteis=None, recreate=False,
):
    """Gera (ou regenera) a folha mensal de UM funcionário.

    - Cria Payroll status=RASCUNHO.
    - Adiciona componentes: vencimento base, diuturnidades, sub. refeição,
      duodécimos Natal/Férias (se subsidios_mode=DUODECIMOS), SS empregado,
      IRS retenção.
    - Retorna o Payroll.

    Se já existe e `recreate=True`, apaga componentes e regenera.
    Se já existe e `recreate=False`, devolve a existente sem mexer.
    """
    pf, created = Payroll.objects.get_or_create(
        employee=employee, periodo_ano=ano, periodo_mes=mes,
        defaults={"status": Payroll.STATUS_RASCUNHO},
    )
    if not created and not recreate:
        return pf
    if not created and recreate:
        if pf.status != Payroll.STATUS_RASCUNHO:
            raise ValueError(
                f"Folha {pf} já está em {pf.get_status_display()} — "
                "não pode ser regenerada.",
            )
        pf.componentes.all().delete()

    # Vencimento base (ajustado por part-time)
    vb = employee.vencimento_efectivo
    PayrollComponent.objects.create(
        payroll=pf,
        tipo=PayrollComponent.TIPO_VENCIMENTO_BASE,
        descricao="Vencimento base mensal",
        valor=vb,
    )

    # Diuturnidades
    if employee.diuturnidades > 0:
        PayrollComponent.objects.create(
            payroll=pf,
            tipo=PayrollComponent.TIPO_DIUTURNIDADE,
            descricao="Diuturnidades",
            valor=employee.diuturnidades,
        )

    # Subsídio de alimentação
    dias = dias_uteis if dias_uteis is not None else employee.dias_uteis_mes_default
    if employee.subs_alimentacao_dia > 0 and dias > 0:
        valor_alim = (
            employee.subs_alimentacao_dia * Decimal(dias)
        ).quantize(Decimal("0.01"))
        PayrollComponent.objects.create(
            payroll=pf,
            tipo=PayrollComponent.TIPO_SUB_REFEICAO,
            descricao=f"€{employee.subs_alimentacao_dia}/dia × {dias} dias",
            valor=valor_alim,
            quantidade=Decimal(dias),
        )

    # Subsídios Natal/Férias — duodécimos
    if employee.subsidios_mode == Employee.SUBSIDIOS_DUODECIMOS:
        duodec = (vb / Decimal("12")).quantize(Decimal("0.01"))
        PayrollComponent.objects.create(
            payroll=pf, tipo=PayrollComponent.TIPO_SUB_NATAL,
            descricao="1/12 do subsídio de Natal", valor=duodec,
        )
        PayrollComponent.objects.create(
            payroll=pf, tipo=PayrollComponent.TIPO_SUB_FERIAS,
            descricao="1/12 do subsídio de Férias", valor=duodec,
        )
    elif employee.subsidios_mode == Employee.SUBSIDIOS_LUMP_SUM:
        if mes == 6:  # Junho — subsídio de férias
            PayrollComponent.objects.create(
                payroll=pf, tipo=PayrollComponent.TIPO_SUB_FERIAS,
                descricao="Subsídio de Férias (anual)", valor=vb,
            )
        elif mes == 12:  # Dezembro — subsídio de Natal
            PayrollComponent.objects.create(
                payroll=pf, tipo=PayrollComponent.TIPO_SUB_NATAL,
                descricao="Subsídio de Natal (anual)", valor=vb,
            )

    # Calcula bruto provisório para SS/IRS
    pf.recalcular()
    bruto = pf.total_bruto

    # SS empregado (11%)
    ss = calculate_ss(bruto)
    if ss > 0:
        PayrollComponent.objects.create(
            payroll=pf, tipo=PayrollComponent.TIPO_SS_EMPREGADO,
            descricao="11% sobre bruto", valor=ss,
        )

    # IRS retenção
    irs = calculate_irs(bruto, employee.irs_tabela, ano)
    if irs > 0:
        PayrollComponent.objects.create(
            payroll=pf, tipo=PayrollComponent.TIPO_IRS_RETENCAO,
            descricao=f"Tabela {employee.irs_tabela} · {ano}",
            valor=irs,
        )

    # Recalcula com SS+IRS incluídos
    pf.recalcular()
    pf.save()
    return pf


@transaction.atomic
def generate_monthly_batch(ano, mes, dias_uteis=None):
    """Gera folhas de todos os funcionários activos no mês."""
    results = {"created": [], "skipped": [], "errors": []}
    qs = Employee.objects.filter(ativo=True)
    for emp in qs:
        # Skip se admitido depois do mês ou saiu antes
        if emp.data_admissao and emp.data_admissao > date(ano, mes, 28):
            results["skipped"].append({"emp": emp.id, "reason": "admitido depois"})
            continue
        if emp.data_saida and emp.data_saida < date(ano, mes, 1):
            results["skipped"].append({"emp": emp.id, "reason": "já saiu"})
            continue
        try:
            pf = generate_monthly_payroll(emp, ano, mes, dias_uteis=dias_uteis)
            results["created"].append(pf.id)
        except Exception as e:
            results["errors"].append({"emp": emp.id, "error": str(e)})
    return results


def _meses_pt():
    return [
        "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
    ]


def _ultimo_dia_mes_seguinte(ano, mes):
    """Vencimento dos impostos (SS/IRS retido): dia 20 do mês seguinte."""
    if mes == 12:
        return date(ano + 1, 1, 20)
    return date(ano, mes + 1, 20)


@transaction.atomic
def approve_payroll(payroll, user=None):
    """APROVA a folha: cria Imposto SS (TSU 23.75%) + Imposto IRS retido.

    Após aprovação, a folha fica imutável (componentes não são editáveis).
    """
    from accounting.models import Fornecedor, Imposto

    if payroll.status != Payroll.STATUS_RASCUNHO:
        raise ValueError(
            f"Folha está em {payroll.get_status_display()} — só "
            "rascunhos podem ser aprovados.",
        )

    payroll.recalcular()

    # Localiza fornecedores Estado
    forn_ss = Fornecedor.objects.filter(
        tipo="ESTADO", name__icontains="Segurança Social",
    ).first()
    forn_at = Fornecedor.objects.filter(
        tipo="ESTADO", name__icontains="Autoridade Tributária",
    ).first()

    venc = _ultimo_dia_mes_seguinte(payroll.periodo_ano, payroll.periodo_mes)
    mes_nome = _meses_pt()[payroll.periodo_mes - 1]

    # TSU empregador (sempre — não depende de SS empregado)
    if payroll.tsu_empregador > 0:
        imp_tsu = Imposto.objects.create(
            nome=(
                f"TSU SS Empregador — {payroll.employee.nome} · "
                f"{mes_nome} {payroll.periodo_ano}"
            ),
            tipo=Imposto.TIPO_SS,
            modalidade=Imposto.MODALIDADE_MENSAL,
            fornecedor=forn_ss,
            periodo_ano=payroll.periodo_ano,
            periodo_mes=payroll.periodo_mes,
            valor=payroll.tsu_empregador,
            data_vencimento=venc,
            status=Imposto.STATUS_PENDENTE,
            created_by=user,
        )
        payroll.tsu_imposto = imp_tsu

    # IRS retido (se houve retenção)
    irs_comp = payroll.componentes.filter(
        tipo=PayrollComponent.TIPO_IRS_RETENCAO,
    ).first()
    if irs_comp and irs_comp.valor > 0:
        imp_irs = Imposto.objects.create(
            nome=(
                f"IRS Retenção — {payroll.employee.nome} · "
                f"{mes_nome} {payroll.periodo_ano}"
            ),
            tipo=Imposto.TIPO_IRS_RETENCOES,
            modalidade=Imposto.MODALIDADE_MENSAL,
            fornecedor=forn_at,
            periodo_ano=payroll.periodo_ano,
            periodo_mes=payroll.periodo_mes,
            valor=irs_comp.valor,
            data_vencimento=venc,
            status=Imposto.STATUS_PENDENTE,
            created_by=user,
        )
        payroll.irs_imposto = imp_irs

    payroll.status = Payroll.STATUS_APROVADO
    payroll.save()
    return payroll


@transaction.atomic
def mark_payroll_paid(payroll, paid_date=None, user=None):
    """Marca a folha como PAGA: cria Bill espelho com o valor líquido.

    A Bill entra no DRE/Fluxo de Caixa como despesa de "Salários".
    Requer fornecedor associado ao Employee (criado em ensure_employee_fornecedor).
    """
    from accounting.models import Bill, ExpenseCategory, CostCenter

    if payroll.status not in (Payroll.STATUS_APROVADO, Payroll.STATUS_RASCUNHO):
        raise ValueError(
            "Só folhas APROVADAS (ou rascunhos prontos) podem ser pagas.",
        )
    if payroll.status == Payroll.STATUS_RASCUNHO:
        # Auto-aprovar primeiro
        approve_payroll(payroll, user=user)

    if not paid_date:
        paid_date = date.today()

    # Garante que o Employee tem Fornecedor
    ensure_employee_fornecedor(payroll.employee)

    # Categoria 'Salários' (cria se não existe)
    cat, _ = ExpenseCategory.objects.get_or_create(
        code="SALARIOS",
        defaults={
            "name": "Salários e Vencimentos",
            "nature": "FIXO",
            "icon": "users",
        },
    )

    # Centro de custo do funcionário ou genérico
    cc = payroll.employee.cost_center
    if not cc:
        cc = CostCenter.objects.filter(code__iexact="ADMIN").first()
    if not cc:
        cc, _ = CostCenter.objects.get_or_create(
            code="ADMIN",
            defaults={"name": "Administrativo", "type": "ADMIN"},
        )

    mes_nome = _meses_pt()[payroll.periodo_mes - 1]
    bill = Bill.objects.create(
        description=(
            f"Salário — {payroll.employee.nome} · "
            f"{mes_nome} {payroll.periodo_ano}"
        ),
        fornecedor=payroll.employee.fornecedor,
        supplier=payroll.employee.nome,
        supplier_nif=payroll.employee.nif,
        category=cat,
        cost_center=cc,
        amount_net=payroll.total_liquido,
        iva_rate=Decimal("0"),
        amount_total=payroll.total_liquido,
        issue_date=paid_date,
        due_date=paid_date,
        paid_date=paid_date,
        paid_amount=payroll.total_liquido,
        status=Bill.STATUS_PAID,
    )
    payroll.bill_espelho = bill
    payroll.status = Payroll.STATUS_PAGO
    payroll.data_pagamento = paid_date
    payroll.save()
    return payroll


@transaction.atomic
def cancel_payroll(payroll, user=None):
    """Cancela a folha: anula Impostos + Bill em cascata.

    Não permite cancelar folhas com Bill espelho em status 'PAID'
    antigo (>30 dias) — preserva histórico fiscal.
    """
    if payroll.status == Payroll.STATUS_CANCELADO:
        return payroll

    # Anula Impostos
    for imp in (payroll.tsu_imposto, payroll.irs_imposto):
        if imp and imp.status != "ANULADO":
            imp.status = "ANULADO"
            imp.save(update_fields=["status", "updated_at"])

    # Reverte Bill (se ainda existe)
    if payroll.bill_espelho:
        from accounting.models import Bill
        b = payroll.bill_espelho
        if b.status != Bill.STATUS_CANCELLED:
            b.status = Bill.STATUS_CANCELLED
            b.save(update_fields=["status", "updated_at"])

    payroll.status = Payroll.STATUS_CANCELADO
    payroll.save()
    return payroll


def ensure_employee_fornecedor(employee):
    """Garante que o Employee tem um Fornecedor espelho (tipo=PARTICULAR)."""
    from accounting.models import Fornecedor
    if employee.fornecedor:
        return employee.fornecedor
    f = Fornecedor.objects.create(
        name=employee.nome,
        nif=employee.nif,
        tipo="PARTICULAR",
        email=employee.email,
        telefone=employee.telefone,
        iban=employee.iban,
        notas=f"Auto-criado para folha de pagamento (Employee #{employee.id}).",
    )
    employee.fornecedor = f
    employee.save(update_fields=["fornecedor", "updated_at"])
    return f
