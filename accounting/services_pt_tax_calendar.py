"""Calendário Fiscal Português — datas-limite legais por tipo de imposto.

Baseado nas regras em vigor em Portugal (2024-2026):

IVA (CIVA art. 41º + DL 41/2016):
  - Regime mensal: declaração e pagamento até dia 20 do segundo mês
    seguinte ao mês de referência.
    Ex: IVA de Janeiro 2026 → vence 20/Março/2026.
  - Regime trimestral: declaração e pagamento até dia 20 do segundo
    mês seguinte ao fim do trimestre.
    Ex: IVA Q1 (jan-mar) → vence 20/Maio.

IRC (CIRC):
  - Modelo 22: até 31 de Maio do ano seguinte ao período.
  - Pagamentos por Conta (PPC): 31/Jul, 30/Set, 15/Dez do ano corrente.

IRS — Retenções na Fonte (CIRS art. 98º):
  - Retidas no mês M, entregues até dia 20 do mês M+1.

IRS — Declaração Anual (Modelo 3):
  - Período de entrega: 1/Abril a 30/Junho do ano seguinte.
  - Pagamento (se houver): até 31/Agosto.

SS — Segurança Social:
  - Contribuições mensais: pagamento entre dia 10 e dia 20 do mês
    seguinte ao mês de remuneração. Deadline dia 20.

IUC — Imposto Único de Circulação:
  - Anual, vence até ao último dia do mês de matrícula do veículo.
"""
from calendar import monthrange
from datetime import date


def iva_due_date(periodo_ano: int, periodo_mes: int, regime: str = "mensal") -> date:
    """Devolve a data-limite de pagamento do IVA.

    Args:
      periodo_ano, periodo_mes: período de referência (ex: 2026, 1 = Janeiro)
      regime: 'mensal' ou 'trimestral'. Se trimestral, periodo_mes é o
              último mês do trimestre (3, 6, 9, 12).

    Regra: dia 20 do segundo mês seguinte (mensal) ou do segundo mês
    seguinte ao trimestre (trimestral).
    """
    m = periodo_mes + 2
    y = periodo_ano + (m - 1) // 12
    m = ((m - 1) % 12) + 1
    return date(y, m, min(20, monthrange(y, m)[1]))


def irs_retencoes_due_date(periodo_ano: int, periodo_mes: int) -> date:
    """IRS — Retenção na Fonte: dia 20 do mês seguinte."""
    m = periodo_mes + 1
    y = periodo_ano + (m - 1) // 12
    m = ((m - 1) % 12) + 1
    return date(y, m, min(20, monthrange(y, m)[1]))


def ss_due_date(periodo_ano: int, periodo_mes: int) -> date:
    """Segurança Social: dia 20 do mês seguinte."""
    return irs_retencoes_due_date(periodo_ano, periodo_mes)


def irc_payment_dates(ano: int) -> list:
    """IRC — devolve lista [(label, date)] das principais datas no ano:
       PPC1 (31/Jul), PPC2 (30/Set), PPC3 (15/Dez), Modelo 22 (31/Mai do ano+1).
    """
    return [
        ("Modelo 22 + acerto", date(ano + 1, 5, 31)),
        ("Pagamento por Conta 1/3", date(ano, 7, 31)),
        ("Pagamento por Conta 2/3", date(ano, 9, 30)),
        ("Pagamento por Conta 3/3", date(ano, 12, 15)),
    ]


def irs_declaracao_dates(ano: int) -> list:
    """IRS — Declaração anual (Modelo 3): entrega 1/Abr–30/Jun, pagamento até 31/Ago."""
    return [
        ("Entrega Modelo 3 — abre", date(ano + 1, 4, 1)),
        ("Entrega Modelo 3 — fecha", date(ano + 1, 6, 30)),
        ("Pagamento Modelo 3", date(ano + 1, 8, 31)),
    ]


def iuc_due_date(matricula_mes: int, ano_referencia: int) -> date:
    """IUC — vence no último dia do mês de matrícula."""
    last = monthrange(ano_referencia, matricula_mes)[1]
    return date(ano_referencia, matricula_mes, last)


# Mapa tipo de imposto → função para sugerir data de vencimento
def suggest_due_date(tipo: str, periodo_ano: int, periodo_mes: int = None,
                     regime: str = "mensal") -> date | None:
    """Sugere a data-limite legal portuguesa para o imposto indicado.

    Para tipos sem regra automática (OUTRO, IUC sem mês de matrícula
    conhecido, declarações anuais sem mês), devolve None.
    """
    if tipo == "IVA" and periodo_mes:
        return iva_due_date(periodo_ano, periodo_mes, regime)
    if tipo == "IRS_RETENCOES" and periodo_mes:
        return irs_retencoes_due_date(periodo_ano, periodo_mes)
    if tipo == "SS" and periodo_mes:
        return ss_due_date(periodo_ano, periodo_mes)
    if tipo == "IRC" and not periodo_mes:
        # Default: M22 do ano (acerto)
        return date(periodo_ano + 1, 5, 31)
    if tipo == "IUC" and periodo_mes:
        return iuc_due_date(periodo_mes, periodo_ano)
    return None
