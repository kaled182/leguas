"""Hubs e CP do motorista: sugestão a partir das entregas, opções por hub
e completude dos dados exigidos pelo contrato."""
from collections import Counter, defaultdict
from datetime import timedelta

from django.db import transaction
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

    Hubs e CP seguem a configuração do parceiro (CainiaoHubCP4): um hub sem
    CP não aparece. A tarifa é só referência, por isso vale a de outro hub
    quando o hub do CP não tem tarifa.
    """
    from contracts.models import ContractSettings, HubZoneTariff
    from settlements.models import CainiaoHub

    settings = ContractSettings.get()
    tariffs = defaultdict(dict)
    any_hub = {}
    for t in HubZoneTariff.objects.filter(is_active=True).order_by("valid_from"):
        tariffs[t.hub_id][t.cp4] = t  # a mais recente fica
        any_hub[t.cp4] = t
    out = []
    for hub in CainiaoHub.objects.prefetch_related("cp4_codes").order_by("name"):
        terms = getattr(hub, "contract_terms", None)
        rows = []
        for cp in sorted(hub.cp4_list()):
            t = tariffs[hub.id].get(cp) or any_hub.get(cp)
            rows.append({
                "cp4": cp,
                "zone": t.zone_name if t else "",
                "tier": t.tier if t else "",
                "price_monthly": t.price_for("MENSAL", settings) if t else None,
                "price_weekly": t.price_for("SEMANAL", settings) if t else None,
                "tariff": t,
            })
        if rows:
            out.append({"hub": hub, "terms": terms, "cps": rows})
    return out


def driver_cp_selection(driver):
    """(CP selecionados, {CP: valor negociado}) do motorista.

    Junta todas as atribuições e ignora CP fora da configuração do parceiro.
    O hub principal fica por último e tem prioridade no valor.
    """
    from settlements.models import CainiaoHubCP4

    valid = set(CainiaoHubCP4.objects.values_list("cp4", flat=True))
    chosen, negotiated = set(), {}
    for a in driver.hub_assignments.order_by("is_primary"):
        for cp in a.cp4s or []:
            if cp not in valid:
                continue
            chosen.add(cp)
            value = (a.cp_prices or {}).get(cp)
            if value:
                negotiated[cp] = value
    return chosen, negotiated


def retire_hub(hub):
    """Apaga um hub sem CP no parceiro.

    Os CP do hub foram para outro hub: fichas e tarifas seguem esses CP.
    Os CP que já não existem no parceiro saem da ficha do motorista.
    """
    from contracts.models import HubZoneTariff
    from settlements.models import CainiaoHubCP4

    from .models import DriverHubAssignment

    cp_hub = dict(CainiaoHubCP4.objects.exclude(hub=hub).values_list("cp4", "hub_id"))
    with transaction.atomic():
        for a in DriverHubAssignment.objects.filter(hub=hub).select_for_update():
            by_hub = defaultdict(list)
            for cp in a.cp4s or []:
                if cp in cp_hub:
                    by_hub[cp_hub[cp]].append(cp)
            primary = a.is_primary
            for hub_id, cps in by_hub.items():
                dest, _ = DriverHubAssignment.objects.get_or_create(
                    driver_id=a.driver_id, hub_id=hub_id,
                    defaults={"cp4s": [], "cp_prices": {}},
                )
                moved = {c: v for c, v in (a.cp_prices or {}).items() if c in cps}
                dest.cp4s = sorted(set(dest.cp4s or []) | set(cps))
                dest.cp_prices = (
                    {**(dest.cp_prices or {}), **moved} if a.is_primary
                    else {**moved, **(dest.cp_prices or {})}
                )
                dest.is_primary = dest.is_primary or primary
                primary = False
                dest.save(update_fields=["cp4s", "cp_prices", "is_primary"])
            a.delete()
        for t in HubZoneTariff.objects.filter(hub=hub, cp4__in=list(cp_hub)):
            if not HubZoneTariff.objects.filter(
                hub_id=cp_hub[t.cp4], cp4=t.cp4, valid_from=t.valid_from,
            ).exists():
                t.hub_id = cp_hub[t.cp4]
                t.save(update_fields=["hub"])
        hub.delete()


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
