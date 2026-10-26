"""Central de Motoristas — vista admin moderna que substitui modais por
páginas dedicadas e reúne KPIs, filtros e acções rápidas."""
from collections import Counter
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Max, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import (
    DriverDocument, DriverProfile, DriverProfileChangeRequest, EmpresaParceira,
)
from .services_activity import INACTIVITY_DAYS, daily_activity, refresh_driver_activity


def _is_admin(u):
    return u.is_authenticated and (u.is_staff or u.is_superuser)


admin_required = user_passes_test(_is_admin, login_url="/auth/login/")


# Separadores: chave → (rótulo, filtro sobre DriverProfile)
TABS = [
    ("ativos", "Activos", Q(status="ATIVO", inactive_since__isnull=True)),
    ("inativos", f"Inactivos +{INACTIVITY_DAYS}d", Q(status="ATIVO", inactive_since__isnull=False)),
    ("pendentes", "Pendentes", Q(status__in=["PENDENTE", "EM_ANALISE"])),
    ("bloqueados", "Bloqueados", Q(status__in=["BLOQUEADO", "IRREGULAR"])),
    ("todos", "Todos", Q()),
]
TAB_FILTERS = {k: f for k, _l, f in TABS}

# Buckets de "dias desde a última atividade" (gráfico + filtro)
IDLE_BUCKETS = [
    ("hoje", "Hoje", 0, 0),
    ("1-3", "1–3 dias", 1, 3),
    ("4-7", "4–7 dias", 4, 7),
    ("8-14", "8–14 dias", 8, 14),
    ("15-30", "15–30 dias", 15, 30),
    ("30+", "+30 dias", 31, None),
]
SPARK_DAYS = 14
CHART_DAYS = 30


def _idle_bucket(days):
    if days is None:
        return "nunca"
    for key, _label, lo, hi in IDLE_BUCKETS:
        if days >= lo and (hi is None or days <= hi):
            return key
    return "30+"


def _contract_driver_ids():
    """Motoristas com contrato: assinado no portal (não revogado) ou
    contrato em papel anexado como documento CONTRATO."""
    from contracts.models import DriverContract

    signed = set(
        DriverContract.objects.filter(revoked_at__isnull=True)
        .values_list("driver_id", flat=True)
    )
    attached = set(
        DriverDocument.objects.filter(tipo_documento="CONTRATO")
        .values_list("motorista_id", flat=True)
    )
    return signed | attached


@admin_required
def drivers_central(request):
    """Central de motoristas: separadores activos/inactivos, KPIs e gráficos."""
    from customauth.models import DriverAccess

    # ─── Filtros ───
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    vinculo = request.GET.get("vinculo", "")
    fleet_id = request.GET.get("fleet", "")
    sort = request.GET.get("sort", "name")
    flag = request.GET.get("flag", "")
    idle = request.GET.get("idle", "")
    # ?status=X (links antigos) abre o separador "todos" filtrado.
    tab = request.GET.get("tab") or ("todos" if status else "ativos")
    if tab not in TAB_FILTERS:
        tab = "ativos"

    today = timezone.localdate()
    chart_from = today - timedelta(days=CHART_DAYS - 1)

    pending_change_ids = set(
        DriverProfileChangeRequest.objects.filter(status="pending")
        .values_list("driver_id", flat=True)
    )
    contract_ids = _contract_driver_ids()
    access_ids = set(
        DriverAccess.objects.filter(is_active=True, driver_profile__isnull=False)
        .values_list("driver_profile_id", flat=True)
    )
    activity = daily_activity(chart_from, today)
    worked_today_ids = {did for did, days in activity.items() if today in days}

    # ─── Base (filtros de pesquisa, sem separador) ───
    base = DriverProfile.objects.select_related("empresa_parceira")
    if q:
        base = base.filter(
            Q(nome_completo__icontains=q)
            | Q(apelido__icontains=q)
            | Q(nif__icontains=q)
            | Q(courier_id_cainiao__icontains=q)
            | Q(telefone__icontains=q)
            | Q(email__icontains=q)
        )
    if status:
        base = base.filter(status=status)
    if vinculo:
        base = base.filter(tipo_vinculo=vinculo)
    if fleet_id == "none":
        base = base.filter(empresa_parceira__isnull=True)
    elif fleet_id:
        base = base.filter(empresa_parceira_id=fleet_id)

    tab_counts = {k: base.filter(f).count() for k, _l, f in TABS}
    in_tab = base.filter(TAB_FILTERS[tab])

    # Contagens das flags dentro do separador actual
    tab_ids = set(in_tab.values_list("id", flat=True))
    flag_counts = {
        "pending_changes": len(tab_ids & pending_change_ids),
        "no_contract": len(tab_ids - contract_ids),
        "no_access": len(tab_ids - access_ids),
        "worked_today": len(tab_ids & worked_today_ids),
        "never": in_tab.filter(last_activity_date__isnull=True).count(),
    }

    qs = in_tab
    if flag == "pending_changes":
        qs = qs.filter(id__in=pending_change_ids)
    elif flag == "no_contract":
        qs = qs.exclude(id__in=contract_ids)
    elif flag == "no_access":
        qs = qs.exclude(id__in=access_ids)
    elif flag == "worked_today":
        qs = qs.filter(id__in=worked_today_ids)
    elif flag == "never":
        qs = qs.filter(last_activity_date__isnull=True)

    if idle == "nunca":
        qs = qs.filter(last_activity_date__isnull=True)
    elif idle:
        for key, _label, lo, hi in IDLE_BUCKETS:
            if key == idle:
                qs = qs.filter(last_activity_date__lte=today - timedelta(days=lo))
                if hi is not None:
                    qs = qs.filter(last_activity_date__gte=today - timedelta(days=hi))

    drivers_list = list(qs)

    # ─── Anotar linhas ───
    spark_days = [today - timedelta(days=i) for i in range(SPARK_DAYS - 1, -1, -1)]
    for d in drivers_list:
        days = activity.get(d.id, {})
        d.has_pending_changes = d.id in pending_change_ids
        d.has_contract = d.id in contract_ids
        d.has_access = d.id in access_ids
        d.deliveries_30d = sum(days.values())
        d.active_days_30d = len(days)
        d.idle_days = (today - d.last_activity_date).days if d.last_activity_date else None
        peak = max([days.get(x, 0) for x in spark_days] + [1])
        d.spark = [
            {"day": x, "n": days.get(x, 0), "worked": x in days,
             "h": max(8, round(days.get(x, 0) / peak * 100)) if x in days else 0}
            for x in spark_days
        ]

    if sort == "recent":
        drivers_list.sort(key=lambda d: d.created_at, reverse=True)
    elif sort == "activity":
        drivers_list.sort(key=lambda d: (d.last_activity_date is None, d.idle_days or 0))
    elif sort == "idle":
        drivers_list.sort(key=lambda d: (d.idle_days is None, -(d.idle_days or 0)))
    elif sort == "deliveries":
        drivers_list.sort(key=lambda d: -d.deliveries_30d)
    else:
        sort = "name"
        drivers_list.sort(key=lambda d: (d.nome_completo or d.apelido or "").lower())

    # ─── KPIs globais ───
    all_drivers = DriverProfile.objects.all()
    status_ativo = all_drivers.filter(status="ATIVO")
    active_ids = set(status_ativo.filter(inactive_since__isnull=True).values_list("id", flat=True))
    deliveries_by_day = Counter()
    drivers_by_day = Counter()
    for did, days in activity.items():
        for day, n in days.items():
            deliveries_by_day[day] += n
            drivers_by_day[day] += 1
    chart_days = [chart_from + timedelta(days=i) for i in range(CHART_DAYS)]
    worked_days = [x for x in chart_days if drivers_by_day[x]]
    total_deliveries_30d = sum(deliveries_by_day.values())
    driver_days_30d = sum(drivers_by_day.values())

    kpis = {
        "total": all_drivers.count(),
        "ativos": len(active_ids),
        "inativos": status_ativo.filter(inactive_since__isnull=False).count(),
        "pendentes": all_drivers.filter(status__in=["PENDENTE", "EM_ANALISE"]).count(),
        "worked_today": len(worked_today_ids),
        "avg_drivers_day": (
            round(sum(drivers_by_day[x] for x in worked_days) / len(worked_days), 1)
            if worked_days else 0
        ),
        "deliveries_30d": total_deliveries_30d,
        "avg_per_driver_day": (
            round(total_deliveries_30d / driver_days_30d, 1) if driver_days_30d else 0
        ),
        "active_no_contract": len(active_ids - contract_ids),
        "no_contract": all_drivers.exclude(id__in=contract_ids).count(),
        "no_access": all_drivers.exclude(id__in=access_ids).count(),
        "pending_changes": len(pending_change_ids),
        "new_30d": all_drivers.filter(created_at__date__gte=chart_from).count(),
        "newly_inactive_7d": status_ativo.filter(
            inactive_since__gte=today - timedelta(days=7),
        ).count(),
    }
    kpis["contract_pct"] = (
        round((kpis["ativos"] - kpis["active_no_contract"]) / kpis["ativos"] * 100)
        if kpis["ativos"] else 0
    )

    # ─── Gráficos ───
    idle_counter = Counter()
    for last in status_ativo.values_list("last_activity_date", flat=True):
        idle_counter[_idle_bucket((today - last).days if last else None)] += 1
    idle_chart = [
        {"key": k, "label": label, "n": idle_counter[k]} for k, label, _lo, _hi in IDLE_BUCKETS
    ] + [{"key": "nunca", "label": "Sem registo", "n": idle_counter["nunca"]}]

    fleet_rows = {}
    for fid, fname, inactive in status_ativo.values_list(
        "empresa_parceira_id", "empresa_parceira__nome", "inactive_since",
    ):
        key = fid or "none"
        row = fleet_rows.setdefault(key, {
            "id": key, "label": fname or "Independentes", "ativos": 0, "inativos": 0,
        })
        row["inativos" if inactive else "ativos"] += 1
    fleet_chart = sorted(
        fleet_rows.values(), key=lambda r: -(r["ativos"] + r["inativos"]),
    )[:10]

    charts = {
        "days": [x.strftime("%d/%m") for x in chart_days],
        "drivers": [drivers_by_day[x] for x in chart_days],
        "deliveries": [deliveries_by_day[x] for x in chart_days],
        "idle": idle_chart,
        "fleets": fleet_chart,
    }

    last_check = all_drivers.aggregate(m=Max("activity_checked_at"))["m"]
    fleets = EmpresaParceira.objects.filter(ativo=True).order_by("nome")

    return render(request, "drivers_app/admin/drivers_central.html", {
        "drivers": drivers_list,
        "kpis": kpis,
        "counts": kpis,
        "tabs": [(k, label, tab_counts[k]) for k, label, _f in TABS],
        "tab": tab,
        "flag_counts": flag_counts,
        "idle_chart": idle_chart,
        "charts": charts,
        "inactivity_days": INACTIVITY_DAYS,
        "last_check": last_check,
        "today": today,
        "q": q,
        "status_filter": status,
        "vinculo_filter": vinculo,
        "fleet_filter": fleet_id,
        "sort_filter": sort,
        "flag_filter": flag,
        "idle_filter": idle,
        "fleets": fleets,
        "shown_count": len(drivers_list),
        "filtered_count": tab_counts[tab],
    })


@admin_required
@require_POST
def drivers_activity_refresh(request):
    """Recalcula a atividade agora (o mesmo que a task horária)."""
    r = refresh_driver_activity()
    messages.success(
        request,
        f"Atividade recalculada: {r['checked']} motoristas, "
        f"{r['inactivated']} passaram a inactivos, {r['reactivated']} reactivados.",
    )
    nxt = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        nxt = "drivers_app:drivers_central"
    return redirect(nxt)
