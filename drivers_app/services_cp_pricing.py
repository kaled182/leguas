"""Preço por pacote ao motorista, por CP (decisão C1, 2026-10-26).

Ordem, por pacote entregue à porta:
  1. CP selecionado na ficha com valor negociado → valor negociado;
  2. CP com tarifa do hub (HubZoneTariff) → tarifa padrão, coluna do
     regime da PF (semanal se o período tem até 8 dias, senão mensal);
  3. CP sem tarifa → preço do motorista → frota → parceiro
     (core.finance.resolve_driver_price).
Só vale para PF com início em ContractSettings.cp_pricing_from ou
depois. Antes disso (ou campo vazio) usa sempre o passo 3.
Overrides por pacote e "mesma porta" continuam a ter prioridade (são
aplicados por quem chama).
"""
from decimal import Decimal, InvalidOperation

from .services_payments import is_weekly_period

SOURCE_LABELS = {
    "negociado": "valor negociado do CP",
    "tarifa": "tarifa padrão do CP",
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
        from contracts.models import ContractSettings, HubZoneTariff
        from core.finance import resolve_driver_price

        base, _src = resolve_driver_price(driver, partner)
        self.base = base or Decimal("0")
        settings = ContractSettings.get()
        self.active = bool(
            settings.cp_pricing_from and periodo_inicio >= settings.cp_pricing_from
        )
        self.regime = "SEMANAL" if is_weekly_period(periodo_inicio, periodo_fim) else "MENSAL"
        self.negotiated = {}
        self.tariffs = {}
        if not self.active:
            return
        assigned_hubs = []
        for a in driver.hub_assignments.order_by("is_primary"):
            assigned_hubs.append(a.hub_id)
            prices = a.cp_prices or {}
            for cp in a.cp4s or []:
                d = _dec(prices.get(cp))
                if d:
                    self.negotiated[cp] = d
        # Tarifa em vigor no início da PF; com o mesmo CP em 2 hubs, ganha
        # o hub do motorista (o principal por último = prioridade).
        rank = {h: i + 1 for i, h in enumerate(assigned_hubs)}
        rows = HubZoneTariff.objects.filter(
            is_active=True, valid_from__lte=periodo_inicio,
        ).order_by("valid_from")
        best = {}
        for t in rows:
            key = (rank.get(t.hub_id, 0), t.valid_from)
            if t.cp4 not in best or key >= best[t.cp4][0]:
                best[t.cp4] = (key, t)
        for cp, (_k, t) in best.items():
            self.tariffs[cp] = t.price_for(self.regime, settings).quantize(Decimal("0.01"))

    def price(self, zip_code):
        cp = (zip_code or "").strip()[:4]
        if self.active:
            if cp in self.negotiated:
                return self.negotiated[cp], "negociado", cp
            if cp in self.tariffs:
                return self.tariffs[cp], "tarifa", cp
        return self.base, "base", cp
