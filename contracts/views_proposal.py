"""Gerador de proposta para motoristas (candidatos).

A proposta usa as mesmas fontes que o contrato e a PF, para não divergir:
- tarifas por CP4 e hubs: HubZoneTariff + CainiaoHubCP4 (hub_options);
- pagamento e tarifa mínima: HubContractTerms de cada hub;
- prazos e valores de responsabilidade: ContractSettings;
- PUDO e mesma porta: ficha do parceiro CAINIAO (_multi_payload).
"""
import base64

from django.contrib.staticfiles import finders
from django.shortcuts import render
from django.utils import timezone
from django.templatetags.static import static
from django.urls import reverse

from .models import ContractSettings
from .views_generator import _multi_payload, admin_required


def _num(v):
    return float(v) if v is not None else None


def proposal_payload():
    from drivers_app.services_hubs import hub_options

    s = ContractSettings.get()
    hubs = []
    for opt in hub_options():
        hub, t = opt["hub"], opt["terms"]
        hubs.append({
            "id": hub.id,
            "name": hub.name,
            "address": hub.address or "",
            "has_terms": t is not None,
            "allows_monthly": t.allows_monthly if t else True,
            "allows_weekly": t.allows_weekly if t else False,
            "monthly_mode": t.monthly_payment_mode if t else "DAYS_AFTER_CLOSE",
            "monthly_value": t.monthly_payment_value if t else 30,
            "weekly_payday": t.weekly_payday if t else 1,
            "weekly_lag_weeks": t.weekly_lag_weeks if t else 4,
            "min_fare": t.min_fare_enabled if t else False,
            "min_fare_value": t.min_fare_value if t else 60,
            "min_fare_under": t.min_fare_under_volumes if t else 50,
            "cps": [{
                "cp": c["cp4"], "z": c["zone"], "esc": c["tier"],
                "p": _num(c["price_monthly"]), "s": _num(c["price_weekly"]),
            } for c in opt["cps"]],
        })
    return {
        "hubs": hubs,
        "settings": {
            "conf": s.route_confirm_until, "saida": s.hub_pickup_until,
            "perda": s.loss_min, "teto": s.loss_cap, "dano": s.damage,
            "local": s.wrong_place, "noshow": s.no_show, "dev": s.no_return,
            "resp": s.response_hours, "aviso": s.notice_days,
            "liq1": s.settle_with_notice_days, "liq2": s.settle_without_notice_days,
            "cauc": s.weekly_retention_weeks, "matur": s.weekly_maturation_days,
            "caucfix": s.monthly_deposit, "desc": float(s.weekly_discount),
        },
        "multi": _multi_payload(),
        "logo": static("contracts/proposal-logo.png"),
        "links": {
            "settings": reverse("admin:contracts_contractsettings_changelist"),
            "tariffs": reverse("admin:contracts_hubzonetariff_changelist"),
            "terms": reverse("admin:contracts_hubcontractterms_changelist"),
        },
    }


@admin_required
def proposal_generator(request):
    return render(request, "contracts/proposal_generator.html", {"gen": proposal_payload()})


def _static_text(path):
    with open(finders.find(path), encoding="utf-8") as f:
        return f.read()


@admin_required
def proposal_download(request):
    """O mesmo gerador num só ficheiro HTML (CSS, JS, logótipo e valores
    embutidos), para a equipa usar fora do sistema. Os valores ficam
    congelados na data do download."""
    gen = proposal_payload()
    with open(finders.find("contracts/proposal-logo.png"), "rb") as f:
        gen["logo"] = "data:image/png;base64," + base64.b64encode(f.read()).decode()
    gen["multi"].pop("edit_url", None)
    gen.pop("links", None)
    now = timezone.localtime()
    resp = render(request, "contracts/proposal_generator.html", {
        "gen": gen, "standalone": True, "snapshot": now.strftime("%d/%m/%Y %H:%M"),
        "css": _static_text("contracts/proposal.css"),
        "js": _static_text("contracts/proposal.js"),
    })
    resp["Content-Disposition"] = (
        f'attachment; filename="Gerador_Proposta_Motoristas_LeguasFranzinas_{now:%Y-%m-%d}.html"'
    )
    return resp
