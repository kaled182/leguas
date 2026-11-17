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


def _selection(assignments, valid):
    """(CP, {CP: valor}) de uma lista de atribuições (hub principal no fim)."""
    chosen, negotiated = set(), {}
    for a in sorted(assignments, key=lambda a: a.is_primary):
        for cp in a.cp4s or []:
            if cp not in valid:
                continue
            chosen.add(cp)
            value = (a.cp_prices or {}).get(cp)
            if value:
                negotiated[cp] = value
    return chosen, negotiated


def _valid_cps():
    from settlements.models import CainiaoHubCP4

    return set(CainiaoHubCP4.objects.values_list("cp4", flat=True))


def fleet_cp_selection(empresa):
    """(CP selecionados, {CP: valor negociado}) da tabela da frota."""
    if empresa is None:
        return set(), {}
    return _selection(list(empresa.hub_assignments.all()), _valid_cps())


def driver_cp_selection(driver, include_fleet=True):
    """(CP selecionados, {CP: valor negociado}) do motorista.

    Junta todas as atribuições e ignora CP fora da configuração do parceiro.
    O hub principal fica por último e tem prioridade no valor.
    Com `include_fleet`, o motorista herda a tabela da frota; o valor da
    ficha do motorista ganha ao valor da frota (exceção por CP).
    """
    valid = _valid_cps()
    chosen, negotiated = _selection(list(driver.hub_assignments.all()), valid)
    fleet = driver.empresa_parceira if driver.empresa_parceira_id else None
    if include_fleet and fleet is not None:
        f_chosen, f_neg = _selection(list(fleet.hub_assignments.all()), valid)
        negotiated = {**f_neg, **negotiated}
        chosen |= f_chosen
    return chosen, negotiated


def _move_assignments(qs, hub, cp_hub, owner_field):
    """Passa os CP de `hub` para o hub atual de cada CP (motorista ou frota)."""
    model = qs.model
    for a in qs.filter(hub=hub).select_for_update():
        by_hub = defaultdict(list)
        for cp in a.cp4s or []:
            if cp in cp_hub:
                by_hub[cp_hub[cp]].append(cp)
        primary = a.is_primary
        owner_id = getattr(a, f"{owner_field}_id")
        for hub_id, cps in by_hub.items():
            dest, _ = model.objects.get_or_create(
                **{f"{owner_field}_id": owner_id}, hub_id=hub_id,
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


def retire_hub(hub):
    """Apaga um hub sem CP no parceiro.

    Os CP do hub foram para outro hub: fichas e tarifas seguem esses CP.
    Os CP que já não existem no parceiro saem da ficha do motorista.
    """
    from contracts.models import HubZoneTariff
    from settlements.models import CainiaoHubCP4

    from .models import DriverHubAssignment, FleetHubAssignment

    cp_hub = dict(CainiaoHubCP4.objects.exclude(hub=hub).values_list("cp4", "hub_id"))
    with transaction.atomic():
        _move_assignments(DriverHubAssignment.objects, hub, cp_hub, "driver")
        _move_assignments(FleetHubAssignment.objects, hub, cp_hub, "empresa")
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
        ("Hub e CP contratados", bool(driver_cp_selection(driver)[0])),
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


def fleet_hub_suggestions(empresa, days=SUGGEST_DAYS, today=None):
    """Soma de `driver_hub_suggestions` dos motoristas ativos da frota.

    Mesmo formato. Um CP entra na sugestão com 5% ou mais das entregas
    da frota.
    """
    hubs = {}
    for d in empresa.motoristas.filter(is_active=True):
        for h in driver_hub_suggestions(d, days=days, today=today):
            agg = hubs.setdefault(h["hub_id"], {
                "hub_id": h["hub_id"], "hub_name": h["hub_name"], "n": 0, "cps": {},
            })
            agg["n"] += h["n"]
            for c in h["cps"]:
                agg["cps"][c["cp4"]] = agg["cps"].get(c["cp4"], 0) + c["n"]
    total = sum(h["n"] for h in hubs.values())
    if not total:
        return []
    out = sorted(hubs.values(), key=lambda h: -h["n"])
    for h in out:
        h["share"] = round(h["n"] / total * 100)
        h["suggested"] = h["hub_id"] is not None and h["n"] >= total * SUGGEST_MIN_SHARE
        h["cps"] = sorted(
            ({"cp4": cp, "n": n, "suggested": n >= total * SUGGEST_MIN_SHARE}
             for cp, n in h["cps"].items()),
            key=lambda c: -c["n"],
        )
    return out


def fleet_drivers_cp_table(empresa):
    """CP e valores das fichas dos motoristas ativos da frota.

    Devolve {hub_id: {cp4: valor mais frequente}} para importar para a
    tabela da frota. Só conta a ficha própria de cada motorista.
    """
    from settlements.models import CainiaoHubCP4

    cp_hub = dict(CainiaoHubCP4.objects.values_list("cp4", "hub_id"))
    votes = defaultdict(Counter)
    for d in empresa.motoristas.filter(is_active=True):
        chosen, negotiated = driver_cp_selection(d, include_fleet=False)
        for cp in chosen:
            votes[cp][negotiated.get(cp, "")] += 1
    out = defaultdict(dict)
    for cp, c in votes.items():
        if cp in cp_hub:
            out[cp_hub[cp]][cp] = c.most_common(1)[0][0]
    return {h: dict(v) for h, v in out.items()}


def save_hub_post(post, owner, model, owner_field):
    """Grava hubs/CP do formulário 'hubs' (ficha do motorista ou frota).

    Campos: hub_<id>, primary_hub, cp_<hub>, cpp_<hub>_<cp>.
    Devolve (alterações [antes, depois] ou None, [erros]).
    """
    from decimal import Decimal, InvalidOperation

    from settlements.models import CainiaoHub

    owned = model.objects.filter(**{owner_field: owner})
    primary = post.get("primary_hub", "")
    keep = set()
    errors = []

    def snap():
        return {
            a.hub_id: (sorted(a.cp4s), a.is_primary, dict(sorted((a.cp_prices or {}).items())))
            for a in owned.all()
        }

    before = snap()
    for hub in CainiaoHub.objects.all():
        cps = sorted(set(post.getlist(f"cp_{hub.id}")))
        if not cps and post.get(f"hub_{hub.id}") != "on":
            continue
        prices = {}
        for cp in cps:
            raw = (post.get(f"cpp_{hub.id}_{cp}") or "").strip().replace(",", ".")
            if not raw:
                continue
            try:
                val = Decimal(raw).quantize(Decimal("0.01"))
            except InvalidOperation:
                errors.append(f"{hub.name} CP {cp}: valor '{raw}' inválido")
                continue
            if val <= 0 or val > 10:
                errors.append(f"{hub.name} CP {cp}: valor tem de estar entre 0,01 € e 10 €")
                continue
            prices[cp] = str(val)
        keep.add(hub.id)
        model.objects.update_or_create(
            **{owner_field: owner}, hub=hub,
            defaults={"cp4s": cps, "is_primary": str(hub.id) == primary, "cp_prices": prices},
        )
    owned.exclude(hub_id__in=keep).delete()
    if keep and not owned.filter(is_primary=True).exists():
        first = owned.order_by("hub__name").first()
        first.is_primary = True
        first.save(update_fields=["is_primary"])
    after = snap()
    if before == after:
        return None, errors
    names = dict(CainiaoHub.objects.values_list("id", "name"))

    def fmt(d):
        return "; ".join(
            f"{names.get(h, h)}{' (principal)' if p else ''}: "
            + (", ".join(f"{x}{'=' + pr[x] + '€' if x in pr else ''}" for x in c) or "—")
            for h, (c, p, pr) in sorted(d.items())
        )

    return [fmt(before), fmt(after)], errors


def hub_view_options(assignments, selected, negotiated, inherited=None):
    """`hub_options()` com o estado de uma ficha (motorista ou frota).

    `inherited` = (CP, {CP: valor}) da frota, para a ficha do motorista.
    """
    inh_chosen, inh_neg = inherited or (set(), {})
    by_hub = {a.hub_id: a for a in assignments}
    options = hub_options()
    for opt in options:
        a = by_hub.get(opt["hub"].id)
        for cp in opt["cps"]:
            cp["checked"] = cp["cp4"] in selected
            cp["negotiated"] = negotiated.get(cp["cp4"], "") if cp["checked"] else ""
            cp["from_fleet"] = cp["cp4"] in inh_chosen
            cp["fleet_price"] = inh_neg.get(cp["cp4"], "") if cp["from_fleet"] else ""
        opt["assigned"] = a is not None or any(cp["checked"] for cp in opt["cps"])
        opt["inherited"] = any(cp["from_fleet"] for cp in opt["cps"])
        opt["primary"] = bool(a and a.is_primary)
    # O hub principal pode já não existir no parceiro.
    shown = [opt for opt in options if opt["assigned"]]
    if shown and not any(opt["primary"] for opt in shown):
        shown[0]["primary"] = True
    return options
