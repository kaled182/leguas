"""Página "Prazos SLA por CP4": define T+1 / T+2 / T+3 por CP4 e mostra o
efeito de cada prazo nas entregas dos últimos 30 dias antes de gravar."""
from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import redirect, render
from django.utils import timezone

from .models import SlaZoneRule
from .services_sla import SLA_DAYS, sla_report

PREVIEW_DAYS = 30


def _is_admin(u):
    return u.is_authenticated and (u.is_staff or u.is_superuser)


@user_passes_test(_is_admin, login_url="/auth/login/")
def sla_rules(request):
    from contracts.models import HubZoneTariff
    from settlements.models import CainiaoHubCP4

    if request.method == "POST":
        cps = request.POST.getlist("cp")
        existing = {r.cp4: r for r in SlaZoneRule.objects.all()}
        changed = 0
        for cp in cps:
            if not (len(cp) == 4 and cp.isdigit()):
                continue
            try:
                days = int(request.POST.get(f"d_{cp}", SLA_DAYS))
            except ValueError:
                continue
            if days not in (1, 2, 3):
                continue
            label = (request.POST.get(f"l_{cp}") or "").strip()[:30]
            rule = existing.get(cp)
            if days == SLA_DAYS and not label:
                if rule:
                    rule.delete()
                    changed += 1
                continue
            if rule and rule.sla_days == days and rule.label == label:
                continue
            SlaZoneRule.objects.update_or_create(
                cp4=cp, defaults={"sla_days": days, "label": label, "updated_by": request.user},
            )
            changed += 1
        messages.success(request, f"Prazos guardados: {changed} CP4 alterado(s).")
        return redirect("dashboard_leguas:sla_rules")

    today = timezone.localdate()
    cp_hub = dict(CainiaoHubCP4.objects.values_list("cp4", "hub__name"))
    report = sla_report(today, days=PREVIEW_DAYS, cp_hub=cp_hub)
    stats = {c["key"]: c for c in report["cps"]}
    zone_names = dict(HubZoneTariff.objects.filter(is_active=True).values_list("cp4", "zone_name"))
    rules = {r.cp4: r for r in SlaZoneRule.objects.select_related("updated_by")}

    all_cps = set(cp_hub) | set(rules) | {cp for cp in stats if cp.isdigit() and stats[cp]["n"] >= 5}
    groups = defaultdict(list)
    for cp in sorted(all_cps):
        st = stats.get(cp, {})
        rule = rules.get(cp)
        groups[cp_hub.get(cp, "Sem hub")].append({
            "cp4": cp,
            "zone": zone_names.get(cp, ""),
            "n": st.get("n", 0),
            "sla": st.get("sla"),
            "sim": st.get("sim", [None, None, None]),
            "open_late": st.get("open_late", 0),
            "days": rule.sla_days if rule else SLA_DAYS,
            "label": rule.label if rule else "",
            "rule": rule,
        })
    hub_list = sorted(groups.items(), key=lambda kv: (kv[0] == "Sem hub", kv[0]))
    summary = {
        f"t{d}": sum(1 for rows in groups.values() for r in rows if r["days"] == d) for d in (1, 2, 3)
    }
    return render(request, "dashboard_leguas/sla_rules.html", {
        "hubs": hub_list,
        "summary": summary,
        "total": report["total"],
        "preview_days": PREVIEW_DAYS,
        "start": report["start"],
        "end": report["end"],
    })
