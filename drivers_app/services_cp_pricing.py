"""Preço por pacote ao motorista, por CP (decisão de 2026-10-31).

Ordem, por pacote entregue à porta:
  1. CP selecionado na ficha com valor negociado → valor negociado;
  2. sem valor negociado → preço do motorista → frota → parceiro
     (core.finance.resolve_driver_price).
A tarifa do hub (HubZoneTariff) não entra no pagamento: um CP só muda o
preço quando o valor está definido na ficha do motorista.
Só vale para PF com início em ContractSettings.cp_pricing_from ou
depois. Antes disso (ou campo vazio) usa sempre o passo 2.
Overrides por pacote e "mesma porta" continuam a ter prioridade (são
aplicados por quem chama).
"""
from decimal import Decimal, InvalidOperation

SOURCE_LABELS = {
    "negociado": "valor negociado do CP",
    "base": "preço do motorista/frota/parceiro",
}


def _dec(v):
    try:
        d = Decimal(str(v).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None
    return d if d > 0 else None


class CpPricer:
    """Chamar `pricer.price(zip_code)` → (preço, origem, cp4)."""

    def __init__(self, driver, partner, periodo_inicio, periodo_fim):
        from contracts.models import ContractSettings
        from core.finance import resolve_driver_price

        base, _src = resolve_driver_price(driver, partner)
        self.base = base or Decimal("0")
        settings = ContractSettings.get()
        self.active = bool(
            settings.cp_pricing_from and periodo_inicio >= settings.cp_pricing_from
        )
        self.negotiated = {}
        if not self.active:
            return
        # order_by: o hub principal fica por último e tem prioridade.
        for a in driver.hub_assignments.order_by("is_primary"):
            prices = a.cp_prices or {}
            for cp in a.cp4s or []:
                d = _dec(prices.get(cp))
                if d:
                    self.negotiated[cp] = d

    def price(self, zip_code):
        cp = (zip_code or "").strip()[:4]
        if self.active and cp in self.negotiated:
            return self.negotiated[cp], "negociado", cp
        return self.base, "base", cp
