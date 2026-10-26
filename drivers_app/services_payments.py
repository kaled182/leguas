"""Datas previstas de pagamento das PF, pelas regras dos contratos.

Regra (geradores de contrato em uso):
  - PF semanal (período até 8 dias): a semana de segunda a domingo é paga
    no dia de pagamento (terça) N semanas depois da segunda-feira dessa
    semana. Ex.: semana de 7/09 → terça 6/10 (N = 4).
  - PF mensal (período maior):
      DAYS_AFTER_CLOSE N  → dia seguinte ao fecho + N dias (Viana: 30);
      DAY_OF_NEXT_MONTH D → dia D do mês seguinte ao fecho (Aveiro: 15).
O tipo vem do período da PF, não do regime atual do motorista: uma PF
antiga mantém a regra com que foi emitida.
As condições vêm do hub principal do motorista; sem hub, usa os valores
por omissão de HubContractTerms.
"""
import calendar
from datetime import date, timedelta

WEEKLY_MAX_DAYS = 8
DEFAULTS = {
    "monthly_payment_mode": "DAYS_AFTER_CLOSE",
    "monthly_payment_value": 30,
    "weekly_payday": 1,
    "weekly_lag_weeks": 4,
}


def _terms_dict(terms):
    if terms is None:
        return dict(DEFAULTS)
    return {k: getattr(terms, k) for k in DEFAULTS}


def primary_hub_terms(driver):
    """HubContractTerms do hub principal (ou do 1.º hub) do motorista."""
    a = (
        driver.hub_assignments.select_related("hub__contract_terms")
        .order_by("-is_primary", "hub__name").first()
    )
    if not a:
        return None
    return getattr(a.hub, "contract_terms", None)


def is_weekly_period(periodo_inicio, periodo_fim):
    return (periodo_fim - periodo_inicio).days + 1 <= WEEKLY_MAX_DAYS


def expected_payment_date(periodo_inicio, periodo_fim, terms=None):
    t = _terms_dict(terms)
    if is_weekly_period(periodo_inicio, periodo_fim):
        monday = periodo_inicio - timedelta(days=periodo_inicio.weekday())
        return monday + timedelta(weeks=t["weekly_lag_weeks"], days=t["weekly_payday"])
    if t["monthly_payment_mode"] == "DAY_OF_NEXT_MONTH":
        y, m = periodo_fim.year, periodo_fim.month + 1
        if m == 13:
            y, m = y + 1, 1
        day = min(t["monthly_payment_value"], calendar.monthrange(y, m)[1])
        return date(y, m, day)
    return periodo_fim + timedelta(days=1 + t["monthly_payment_value"])


def expected_for_pf(pf):
    if not pf.periodo_inicio or not pf.periodo_fim:
        return None
    return expected_payment_date(
        pf.periodo_inicio, pf.periodo_fim, primary_hub_terms(pf.driver),
    )


def next_weekday(today, weekday):
    """Próximo dia `weekday` (0=seg) a partir de hoje, inclusive."""
    return today + timedelta(days=(weekday - today.weekday()) % 7)


def pf_amount(pf):
    """Valor que sai da tesouraria (como na caixa "A pagar"): com IVA
    quando o motorista está no regime normal."""
    if pf.vat_amount and pf.vat_amount > 0:
        return pf.total_com_iva
    return pf.total_a_receber or 0
