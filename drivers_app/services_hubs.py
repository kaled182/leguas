"""Hubs e CP do motorista: sugestão a partir das entregas, opções por hub
e completude dos dados exigidos pelo contrato."""
from collections import Counter, defaultdict
from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import Substr
from django.utils import timezone

SUGGEST_DAYS = 60
# Um hub/CP entra na sugestão a partir desta fração das entregas.
SUGGEST_MIN_SHARE = 0.05

PLACEHOLDER_PHONES = {"000000000", "+351000000000"}


def is_placeholder_phone(v):
    return (v or "").strip() in PLACEHOLDER_PHONES


def is_placeholder_email(v):
    return (v or "").strip().lower().endswith("@import.local")


def hub_options():
    """[{hub, terms, cps:[{cp4, zone, tier, price_monthly, price_weekly}]}].

    CP de cada hub = CP4 do hub (CainiaoHubCP4) ∪ CP com tarifa activa.
    """
    from contracts.models import ContractSettings, HubZoneTariff
    from settlements.models import CainiaoHub

    settings = ContractSettings.get()
    tariffs = defaultdict(dict)
    for t in HubZoneTariff.objects.filter(is_active=True).order_by("valid_from"):
        tariffs[t.hub_id][t.cp4] = t  # a mais recente fica
    out = []
    for hub in CainiaoHub.objects.prefetch_related("cp4_codes").order_by("name"):
        terms = getattr(hub, "contract_terms", None)
        cps = set(hub.cp4_list()) | set(tariffs[hub.id])
        rows = []
        for cp in sorted(cps):
            t = tariffs[hub.id].get(cp)
            rows.append({
                "cp4": cp,
                "zone": t.zone_name if t else "",
                "tier": t.tier if t else "",
                "price_monthly": t.price_for("MENSAL", settings) if t else None,
                "price_weekly": t.price_for("SEMANAL", settings) if t else None,
                "tariff": t,
            })
        out.append({"hub": hub, "terms": terms, "cps": rows})
    return out


def driver_hub_suggestions(driver, days=SUGGEST_DAYS, today=None):
    """Entregas do motorista por hub e CP4 nos últimos `days` dias.

    Devolve [{hub_id, hub_name, n, share, suggested, cps:[{cp4, n, suggested}]}],
    ordenado por entregas. CP4 sem hub aparecem com hub_id=None.
    """
    from settlements.models import CainiaoHubCP4

    from .portal_views import _driver_base_queryset

    today = today or timezone.localdate()
    qs = _driver_base_queryset(driver, today - timedelta(days=days), today).filter(
        task_status="Delivered",
    )
    by_cp = Counter()
    for r in qs.annotate(cp4=Substr("zip_code", 1, 4)).values("cp4").annotate(n=Count("id")):
        if r["cp4"]:
            by_cp[r["cp4"]] += r["n"]
    total = sum(by_cp.values())
    if not total:
        return []

    cp_hub = {}
    for cp4, hub_id, hub_name in CainiaoHubCP4.objects.values_list(
        "cp4", "hub_id", "hub__name",
    ):
        cp_hub.setdefault(cp4, (hub_id, hub_name))

    hubs = {}
    for cp4, n in by_cp.items():
        hub_id, hub_name = cp_hub.get(cp4, (None, "Sem hub"))
        h = hubs.setdefault(hub_id, {"hub_id": hub_id, "hub_name": hub_name, "n": 0, "cps": []})
        h["n"] += n
        h["cps"].append({"cp4": cp4, "n": n, "suggested": n >= total * SUGGEST_MIN_SHARE})
    out = sorted(hubs.values(), key=lambda h: -h["n"])
    for h in out:
        h["share"] = round(h["n"] / total * 100)
        h["suggested"] = h["hub_id"] is not None and h["n"] >= total * SUGGEST_MIN_SHARE
        h["cps"].sort(key=lambda c: -c["n"])
    return out


def contract_completeness(driver):
    """(% preenchido, [rótulos em falta]) dos dados exigidos pelo contrato."""
    checks = [
        ("Nome completo", bool(driver.nome_completo)),
        ("NIF", bool(driver.nif)),
        ("Telefone real", bool(driver.telefone) and not is_placeholder_phone(driver.telefone)),
        ("Email real", bool(driver.email) and not is_placeholder_email(driver.email)),
        ("Morada", bool(driver.endereco_residencia)),
        ("Carta de condução (n.º)", bool(driver.driving_license_number)),
        ("Validade da carta", bool(driver.driving_license_expiry)),
        ("IBAN", bool(driver.iban)),
        ("Seguro acidentes de trabalho", bool(driver.insurance_work_policy)),
        ("Seguro automóvel", bool(driver.insurance_auto_policy)),
        ("Regime de pagamento", bool(driver.payment_regime)),
        ("Hub e CP contratados", any(a.cp4s for a in driver.hub_assignments.all())),
    ]
    if driver.provider_type == "SOCIEDADE":
        checks += [
            ("Gerente (nome)", bool(driver.company_rep_name)),
            ("Gerente (NIF)", bool(driver.company_rep_nif)),
        ]
    else:
        checks += [
            ("Documento de identificação", bool(driver.id_doc_type and driver.id_doc_number)),
            ("Validade do documento", bool(driver.id_doc_expiry)),
        ]
    done = sum(1 for _l, ok in checks if ok)
    missing = [label for label, ok in checks if not ok]
    return round(done / len(checks) * 100), missing
