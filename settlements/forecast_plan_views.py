"""Endpoints para o Plano de Distribuição (Kanban driver-centric).

Permite ao operador escalar drivers por CP4 para o dia seguinte com
drag-and-drop. Suporta sugestão automática (histórico), capacidades
configuráveis e publicação com notificação WhatsApp.
"""
import json
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.db.models.functions import Substr
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_http_methods

from drivers_app.models import DriverProfile, EmpresaParceira
from .models import (
    CainiaoHub, CainiaoManualForecast, CainiaoOperationTask,
    CainiaoPlanningPackage, ForecastPlan, ForecastPlanAssignment,
    ForecastPlanCP4Skip,
)


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _historical_capacity(driver, days=14):
    """Média diária de Delivered nos últimos `days` dias."""
    if not driver:
        return 0
    end = timezone.now().date()
    start = end - timedelta(days=days)
    ids = set()
    names = set()
    if driver.courier_id_cainiao:
        ids.add(driver.courier_id_cainiao)
    if driver.apelido:
        names.add(driver.apelido)
    for m in driver.courier_mappings.filter(
        partner__name__iexact="CAINIAO",
    ):
        if m.courier_id:
            ids.add(m.courier_id)
        if m.courier_name:
            names.add(m.courier_name)
    if not (ids or names):
        return 0
    qs = CainiaoOperationTask.objects.filter(
        task_date__range=(start, end),
        task_status="Delivered",
    )
    dq = Q()
    if ids:
        dq |= Q(courier_id_cainiao__in=ids)
    if names:
        dq |= Q(courier_name__in=names)
    qs = qs.filter(dq)
    distinct_days = qs.values_list("task_date", flat=True).distinct().count()
    if distinct_days == 0:
        return 0
    total = qs.count()
    return int(round(total / distinct_days))


def _effective_capacity(driver):
    """Daily_capacity configurada OU média histórica."""
    if driver.daily_capacity and driver.daily_capacity > 0:
        return driver.daily_capacity, "configured"
    avg = _historical_capacity(driver)
    return avg, "historical"


def _forecast_volume_per_cp4(target_date, hub):
    """Volume estimado por CP4 — combina 3 fontes:

    1. Forecast (CainiaoPlanningPackage do dia previsto)
    2. Manual (CainiaoManualForecast — input directo do operador)
    3. Backlog (CainiaoOperationTask do último dia anterior, status
       Driver_received/Attempt Failure/Unassign/Assigned)

    Returns: dict {cp4: {total, forecast, manual, backlog}}
    """
    from django.db.models import Max
    hub_cp4_set = set()
    if hub:
        hub_cp4_set = set(hub.cp4_codes.values_list("cp4", flat=True))

    by_cp4 = {}

    def _ensure(cp4):
        if cp4 not in by_cp4:
            by_cp4[cp4] = {
                "cp4": cp4,
                "forecast": 0,
                "manual": 0,
                "backlog": 0,
            }
        return by_cp4[cp4]

    # 1. FORECAST (CainiaoPlanningPackage)
    qs = CainiaoPlanningPackage.objects.filter(operation_date=target_date)
    if hub_cp4_set:
        hq = Q()
        for cp4 in hub_cp4_set:
            hq |= Q(receiver_zip__startswith=cp4)
        qs = qs.filter(hq)
    for r in (
        qs.exclude(receiver_zip="")
        .annotate(cp4=Substr("receiver_zip", 1, 4))
        .values("cp4")
        .annotate(n=Count("id"))
    ):
        _ensure(r["cp4"])["forecast"] += r["n"]

    # 2. MANUAL (CainiaoManualForecast)
    manual_qs = CainiaoManualForecast.objects.filter(
        operation_date=target_date,
    )
    if hub_cp4_set:
        manual_qs = manual_qs.filter(cp4__in=hub_cp4_set)
    for mf in manual_qs:
        _ensure(mf.cp4)["manual"] += mf.qty

    # 3. BACKLOG (Operation Tasks pendentes do dia anterior mais próximo)
    most_recent = CainiaoOperationTask.objects.filter(
        task_date__lt=target_date,
    ).aggregate(d=Max("task_date"))["d"]
    if most_recent:
        bqs = CainiaoOperationTask.objects.filter(
            task_date=most_recent,
            task_status__in=[
                "Driver_received", "Attempt Failure",
                "Unassign", "Assigned",
            ],
        )
        if hub_cp4_set:
            bq = Q()
            for cp4 in hub_cp4_set:
                bq |= Q(zip_code__startswith=cp4)
            bqs = bqs.filter(bq)
        for r in (
            bqs.exclude(zip_code="")
            .annotate(cp4=Substr("zip_code", 1, 4))
            .values("cp4")
            .annotate(n=Count("id"))
        ):
            _ensure(r["cp4"])["backlog"] += r["n"]

    # Calcular total final
    for cp4_data in by_cp4.values():
        cp4_data["total"] = (
            cp4_data["forecast"]
            + cp4_data["manual"]
            + cp4_data["backlog"]
        )

    return by_cp4


def _serialize_assignment(a):
    return {
        "id": a.id,
        "cp4": a.cp4,
        "kind": a.assignee_kind,
        "driver_id": a.driver_id,
        "driver_name": (
            a.driver.apelido or a.driver.nome_completo
            if a.driver else ""
        ),
        "fleet_id": a.fleet_id,
        "fleet_name": a.fleet.nome if a.fleet else "",
        "manual_name": a.manual_name,
        "display_name": a.display_name,
        "qty": a.qty,
        "notes": a.notes,
    }


def _historical_cp4_score(driver, cp4, days=30):
    """Calcula score de afinidade do driver com um CP4.

    Score = (deliveries_in_cp4 * 0.7) + (success_rate * 30)
    Mais entregas + maior taxa de sucesso = melhor candidato.
    """
    if not driver:
        return 0
    end = timezone.now().date()
    start = end - timedelta(days=days)
    ids = set()
    names = set()
    if driver.courier_id_cainiao:
        ids.add(driver.courier_id_cainiao)
    if driver.apelido:
        names.add(driver.apelido)
    for m in driver.courier_mappings.filter(
        partner__name__iexact="CAINIAO",
    ):
        if m.courier_id:
            ids.add(m.courier_id)
        if m.courier_name:
            names.add(m.courier_name)
    if not (ids or names):
        return 0

    qs = CainiaoOperationTask.objects.filter(
        task_date__range=(start, end),
        zip_code__startswith=cp4,
    )
    dq = Q()
    if ids:
        dq |= Q(courier_id_cainiao__in=ids)
    if names:
        dq |= Q(courier_name__in=names)
    qs = qs.filter(dq)
    total = qs.count()
    if total == 0:
        return 0
    delivered = qs.filter(task_status="Delivered").count()
    success_rate = delivered / total
    return delivered * 0.7 + success_rate * 30


def _serialize_plan(plan, *, with_drivers=False):
    """Serializa plano completo: assignments + volumes esperados."""
    assignments = list(plan.assignments.select_related(
        "driver", "fleet",
    ))
    volume_per_cp4 = _forecast_volume_per_cp4(
        plan.operation_date, plan.hub,
    )
    skipped_set = set(
        plan.skipped_cp4s.values_list("cp4", flat=True)
    )

    # Por CP4: total previsto vs total atribuído
    cp4_summary = []
    cp4_assigned = {}
    for a in assignments:
        cp4_assigned[a.cp4] = cp4_assigned.get(a.cp4, 0) + a.qty
    all_cp4s = set(volume_per_cp4.keys()) | set(cp4_assigned.keys())
    for cp4 in sorted(all_cp4s):
        v = volume_per_cp4.get(
            cp4, {"forecast": 0, "manual": 0, "backlog": 0, "total": 0},
        )
        forecast_total = v["total"]
        assigned = cp4_assigned.get(cp4, 0)
        cp4_summary.append({
            "cp4": cp4,
            "forecast": forecast_total,    # total combinado (compat)
            "forecast_pkg": v["forecast"],  # do ficheiro Planning
            "manual": v["manual"],          # input manual
            "backlog": v["backlog"],        # pendentes do dia anterior
            "assigned": assigned,
            "remaining": max(0, forecast_total - assigned),
            "over_assigned": assigned > forecast_total,
            "skipped": cp4 in skipped_set,
        })

    # Por assignee (driver | fleet | manual)
    driver_groups = {}
    for a in assignments:
        if a.driver_id:
            key = f"d:{a.driver_id}"
            kind = "driver"
        elif a.fleet_id:
            key = f"f:{a.fleet_id}"
            kind = "fleet"
        elif a.manual_name:
            key = f"m:{a.manual_name}"
            kind = "manual"
        else:
            key = "?"
            kind = "?"
        if key not in driver_groups:
            driver_groups[key] = {
                "key": key,
                "kind": kind,
                "driver_id": a.driver_id,
                "fleet_id": a.fleet_id,
                "manual_name": a.manual_name,
                "name": a.display_name,
                "total_assigned": 0,
                "cp4s": [],
            }
        driver_groups[key]["total_assigned"] += a.qty
        driver_groups[key]["cp4s"].append({
            "cp4": a.cp4, "qty": a.qty, "assignment_id": a.id,
        })

    driver_groups_list = sorted(
        driver_groups.values(),
        key=lambda g: -g["total_assigned"],
    )

    payload = {
        "id": plan.id,
        "operation_date": plan.operation_date.strftime("%Y-%m-%d"),
        "hub_id": plan.hub_id,
        "hub_name": plan.hub.name if plan.hub else None,
        "status": plan.status,
        "status_display": plan.get_status_display(),
        "notes": plan.notes,
        "notify_on_publish": plan.notify_on_publish,
        "published_at": (
            plan.published_at.strftime("%Y-%m-%d %H:%M")
            if plan.published_at else None
        ),
        "assignments": [_serialize_assignment(a) for a in assignments],
        "cp4_summary": cp4_summary,
        "driver_groups": driver_groups_list,
        "totals": {
            "forecast_total": sum(
                v["total"] for v in volume_per_cp4.values()
            ),
            "forecast_pkg_total": sum(
                v["forecast"] for v in volume_per_cp4.values()
            ),
            "manual_total": sum(
                v["manual"] for v in volume_per_cp4.values()
            ),
            "backlog_total": sum(
                v["backlog"] for v in volume_per_cp4.values()
            ),
            "assigned_total": sum(cp4_assigned.values()),
            "n_drivers": len(driver_groups),
            "n_cp4s": len(volume_per_cp4),
        },
    }

    if with_drivers:
        # Lista de drivers disponíveis para arrastar
        drivers = DriverProfile.objects.filter(is_active=True).order_by(
            "nome_completo",
        )
        avail = []
        for d in drivers:
            cap, cap_src = _effective_capacity(d)
            current_load = sum(
                a.qty for a in assignments if a.driver_id == d.id
            )
            avail.append({
                "id": d.id,
                "name": d.apelido or d.nome_completo,
                "full_name": d.nome_completo,
                "fleet": (
                    d.empresa_parceira.nome
                    if d.empresa_parceira else ""
                ),
                "capacity": cap,
                "capacity_source": cap_src,
                "current_load": current_load,
                "load_pct": (
                    round(current_load * 100 / cap)
                    if cap > 0 else 0
                ),
            })
        payload["available_drivers"] = avail

        # Frotas disponíveis para atribuir CP4 inteiro
        fleets = EmpresaParceira.objects.filter(ativo=True).order_by("nome")
        avail_fleets = []
        for f in fleets:
            current_load = sum(
                a.qty for a in assignments if a.fleet_id == f.id
            )
            avail_fleets.append({
                "id": f.id,
                "name": f.nome,
                "n_drivers": f.num_motoristas,
                "current_load": current_load,
            })
        payload["available_fleets"] = avail_fleets

    return payload


# ──────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────

@login_required
def forecast_plan_get_or_create(request):
    """GET ?date=YYYY-MM-DD&hub_id=N — devolve plano (cria DRAFT se não existe)."""
    date_str = request.GET.get("date") or ""
    hub_id_str = request.GET.get("hub_id") or ""

    target_date = parse_date(date_str)
    if not target_date:
        return JsonResponse(
            {"success": False, "error": "Data inválida"}, status=400,
        )

    hub = None
    if hub_id_str:
        try:
            hub = CainiaoHub.objects.prefetch_related("cp4_codes").get(
                id=int(hub_id_str),
            )
        except (CainiaoHub.DoesNotExist, ValueError):
            pass

    plan, created = ForecastPlan.objects.get_or_create(
        operation_date=target_date,
        hub=hub,
        defaults={
            "status": ForecastPlan.STATUS_DRAFT,
            "created_by": request.user,
        },
    )

    return JsonResponse({
        "success": True,
        "created": created,
        "plan": _serialize_plan(plan, with_drivers=True),
    })


@login_required
@require_http_methods(["POST"])
def forecast_plan_assign(request, plan_id):
    """POST cria/actualiza assignment.

    Body JSON:
      cp4: str (4 dígitos)
      driver_id: int (opcional se manual_name dado)
      manual_name: str (opcional se driver_id dado)
      qty: int (>0). Se 0, apaga.
      assignment_id: int (opcional, para editar existente)
    """
    plan = get_object_or_404(ForecastPlan, id=plan_id)
    if plan.status == ForecastPlan.STATUS_PUBLISHED:
        return JsonResponse(
            {"success": False, "error":
             "Plano publicado — não é possível modificar."},
            status=400,
        )

    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse(
            {"success": False, "error": "JSON inválido"}, status=400,
        )

    cp4 = (body.get("cp4") or "").strip()
    driver_id = body.get("driver_id")
    fleet_id = body.get("fleet_id")
    manual_name = (body.get("manual_name") or "").strip()
    try:
        qty = int(body.get("qty") or 0)
    except (TypeError, ValueError):
        return JsonResponse(
            {"success": False, "error": "qty inválido"}, status=400,
        )
    assignment_id = body.get("assignment_id")

    if not cp4 or not cp4.isdigit() or len(cp4) != 4:
        return JsonResponse(
            {"success": False, "error":
             "CP4 inválido"}, status=400,
        )
    if not driver_id and not fleet_id and not manual_name:
        return JsonResponse(
            {"success": False, "error":
             "driver_id, fleet_id ou manual_name obrigatório"}, status=400,
        )

    driver = None
    if driver_id:
        try:
            driver = DriverProfile.objects.get(id=int(driver_id))
        except (DriverProfile.DoesNotExist, ValueError, TypeError):
            return JsonResponse(
                {"success": False, "error":
                 "driver_id inválido"}, status=400,
            )

    fleet = None
    if fleet_id:
        try:
            fleet = EmpresaParceira.objects.get(id=int(fleet_id))
        except (EmpresaParceira.DoesNotExist, ValueError, TypeError):
            return JsonResponse(
                {"success": False, "error":
                 "fleet_id inválido"}, status=400,
            )

    # qty=0 => apagar
    if qty <= 0:
        deleted = 0
        if assignment_id:
            n, _ = ForecastPlanAssignment.objects.filter(
                plan=plan, id=assignment_id,
            ).delete()
            deleted = n
        else:
            qfilter = {"plan": plan, "cp4": cp4}
            if driver:
                qfilter["driver"] = driver
            elif fleet:
                qfilter["fleet"] = fleet
            else:
                qfilter["manual_name"] = manual_name
            n, _ = ForecastPlanAssignment.objects.filter(**qfilter).delete()
            deleted = n
        return JsonResponse({
            "success": True, "deleted": deleted,
            "plan": _serialize_plan(plan, with_drivers=True),
        })

    # Criar ou actualizar
    if assignment_id:
        try:
            a = ForecastPlanAssignment.objects.get(
                plan=plan, id=assignment_id,
            )
        except ForecastPlanAssignment.DoesNotExist:
            return JsonResponse(
                {"success": False, "error":
                 "Assignment não encontrado"}, status=404,
            )
        a.cp4 = cp4
        a.driver = driver
        a.fleet = fleet if not driver else None
        a.manual_name = (
            manual_name if not (driver or fleet) else ""
        )
        a.qty = qty
        a.save()
        return JsonResponse({
            "success": True, "assignment": _serialize_assignment(a),
            "plan": _serialize_plan(plan, with_drivers=True),
        })

    # Lookup existing for this (plan, cp4, assignee)
    qfilter = {"plan": plan, "cp4": cp4}
    if driver:
        qfilter["driver"] = driver
    elif fleet:
        qfilter["fleet"] = fleet
    else:
        qfilter["manual_name"] = manual_name
    a = ForecastPlanAssignment.objects.filter(**qfilter).first()
    if a:
        a.qty = qty
        a.save()
    else:
        a = ForecastPlanAssignment.objects.create(
            plan=plan, cp4=cp4,
            driver=driver,
            fleet=fleet if not driver else None,
            manual_name=(
                manual_name if not (driver or fleet) else ""
            ),
            qty=qty,
        )

    return JsonResponse({
        "success": True, "assignment": _serialize_assignment(a),
        "plan": _serialize_plan(plan, with_drivers=True),
    })


@login_required
@require_http_methods(["POST"])
def forecast_plan_delete_assignment(request, assignment_id):
    """Apaga uma assignment específica."""
    a = get_object_or_404(ForecastPlanAssignment, id=assignment_id)
    plan = a.plan
    if plan.status == ForecastPlan.STATUS_PUBLISHED:
        return JsonResponse(
            {"success": False, "error":
             "Plano publicado — não é possível modificar."},
            status=400,
        )
    a.delete()
    return JsonResponse({
        "success": True, "plan": _serialize_plan(plan, with_drivers=True),
    })


@login_required
@require_http_methods(["POST"])
def forecast_plan_clear(request, plan_id):
    """Apaga todas as assignments do plano."""
    plan = get_object_or_404(ForecastPlan, id=plan_id)
    if plan.status == ForecastPlan.STATUS_PUBLISHED:
        return JsonResponse(
            {"success": False, "error":
             "Plano publicado — não é possível limpar."},
            status=400,
        )
    n, _ = plan.assignments.all().delete()
    return JsonResponse({
        "success": True, "deleted": n,
        "plan": _serialize_plan(plan, with_drivers=True),
    })


@login_required
@require_http_methods(["POST"])
def forecast_plan_toggle_skip(request, plan_id):
    """Marca/desmarca um CP4 como ignorado no plano.

    Body: { cp4: '4500', reason: '' (opcional), skip: bool }
    Se skip=true: cria entry. Se skip=false: apaga.
    """
    plan = get_object_or_404(ForecastPlan, id=plan_id)
    if plan.status == ForecastPlan.STATUS_PUBLISHED:
        return JsonResponse(
            {"success": False, "error":
             "Plano publicado — não modificável."}, status=400,
        )
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        body = {}
    cp4 = (body.get("cp4") or "").strip()
    if not cp4 or not cp4.isdigit() or len(cp4) != 4:
        return JsonResponse(
            {"success": False, "error": "CP4 inválido"}, status=400,
        )
    skip = bool(body.get("skip", True))

    if skip:
        ForecastPlanCP4Skip.objects.update_or_create(
            plan=plan, cp4=cp4,
            defaults={"reason": (body.get("reason") or "").strip()},
        )
        # Apagar quaisquer assignments existentes para esse CP4
        plan.assignments.filter(cp4=cp4).delete()
    else:
        ForecastPlanCP4Skip.objects.filter(plan=plan, cp4=cp4).delete()

    return JsonResponse({
        "success": True, "skip": skip,
        "plan": _serialize_plan(plan, with_drivers=True),
    })


@login_required
@require_http_methods(["POST"])
def forecast_plan_auto_distribute(request, plan_id):
    """Sugere distribuição automática baseada em capacidade.

    Body JSON (opcional):
      replace: bool (default True) — apaga existentes antes
      driver_ids: [int] (opcional) — restringe a estes drivers
    """
    plan = get_object_or_404(ForecastPlan, id=plan_id)
    if plan.status == ForecastPlan.STATUS_PUBLISHED:
        return JsonResponse(
            {"success": False, "error":
             "Plano publicado — não é possível redistribuir."},
            status=400,
        )

    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        body = {}
    replace = body.get("replace", True)
    driver_ids_filter = body.get("driver_ids") or []

    volume_per_cp4 = _forecast_volume_per_cp4(
        plan.operation_date, plan.hub,
    )
    # Excluir CP4s skipped do plano
    skipped_set = set(
        plan.skipped_cp4s.values_list("cp4", flat=True)
    )
    # Filtrar CP4s sem volume nenhum E não-skipped
    cp4_qty_pairs = [
        (cp4, v["total"])
        for cp4, v in volume_per_cp4.items()
        if v["total"] > 0 and cp4 not in skipped_set
    ]
    if not cp4_qty_pairs:
        return JsonResponse(
            {"success": False, "error":
             "Sem volume previsto para esta data/hub. "
             "Adiciona previsão manual ou aguarda ficheiro forecast."},
            status=400,
        )

    # Drivers disponíveis com capacidade
    drivers_qs = DriverProfile.objects.filter(is_active=True)
    if driver_ids_filter:
        drivers_qs = drivers_qs.filter(id__in=driver_ids_filter)

    pool = []
    for d in drivers_qs:
        cap, src = _effective_capacity(d)
        if cap <= 0:
            continue
        pool.append({
            "driver": d,
            "capacity": cap,
            "remaining": cap,
            "source": src,
        })

    if not pool:
        return JsonResponse(
            {"success": False, "error":
             "Nenhum driver com capacidade configurada/histórica"},
            status=400,
        )

    # Algoritmo aprimorado:
    # Para cada CP4 (maior volume primeiro), ordenar drivers por:
    #   composite_score = (history_score em CP4) + (remaining_capacity_pct * factor)
    # Privilegia driver com afinidade histórica + capacidade disponível.
    cp4_sorted = sorted(cp4_qty_pairs, key=lambda kv: -kv[1])

    # Pré-calcular history score para cada (driver, cp4)
    history_cache = {}  # (driver_id, cp4) -> score

    def _hist_score(driver, cp4):
        key = (driver.id, cp4)
        if key not in history_cache:
            history_cache[key] = _historical_cp4_score(driver, cp4)
        return history_cache[key]

    new_assignments = []  # (cp4, driver, qty)
    for cp4, total_qty in cp4_sorted:
        remaining_qty = total_qty
        while remaining_qty > 0:
            # Score composto: histórico CP4 + capacidade disponível
            def _composite(p):
                hist = _hist_score(p["driver"], cp4)
                cap_pct = (
                    p["remaining"] * 100.0 / p["capacity"]
                    if p["capacity"] > 0 else 0
                )
                # Hist domina se driver é especialista neste CP4;
                # capacidade desempata
                return hist + (cap_pct * 0.3)

            pool.sort(key=lambda p: -_composite(p))
            top = pool[0]
            if top["remaining"] <= 0:
                # ninguém tem capacidade — atribui ao melhor por histórico
                # mesmo em over-capacity (flag visível no UI)
                new_assignments.append(
                    (cp4, top["driver"], remaining_qty),
                )
                top["remaining"] -= remaining_qty
                remaining_qty = 0
                break
            take = min(remaining_qty, top["remaining"])
            new_assignments.append((cp4, top["driver"], take))
            top["remaining"] -= take
            remaining_qty -= take

    with transaction.atomic():
        if replace:
            plan.assignments.all().delete()
        # Bulk create
        bulk = [
            ForecastPlanAssignment(
                plan=plan, cp4=cp4, driver=driver, qty=qty,
            )
            for (cp4, driver, qty) in new_assignments
        ]
        ForecastPlanAssignment.objects.bulk_create(bulk)

    plan.refresh_from_db()
    return JsonResponse({
        "success": True,
        "n_assignments": len(new_assignments),
        "plan": _serialize_plan(plan, with_drivers=True),
    })


@login_required
@require_http_methods(["POST"])
def forecast_plan_publish(request, plan_id):
    """Publica o plano. Opcionalmente envia WhatsApp aos drivers.

    Body: { notify: bool }
    """
    plan = get_object_or_404(ForecastPlan, id=plan_id)
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        body = {}
    notify = bool(body.get("notify", plan.notify_on_publish))

    plan.status = ForecastPlan.STATUS_PUBLISHED
    plan.published_at = timezone.now()
    plan.published_by = request.user
    plan.notify_on_publish = notify
    plan.save()

    notif_results = {"sent": 0, "failed": 0, "no_phone": 0}
    if notify:
        notif_results = _send_plan_whatsapp(plan)

    return JsonResponse({
        "success": True,
        "notification": notif_results,
        "plan": _serialize_plan(plan, with_drivers=True),
    })


@login_required
@require_http_methods(["POST"])
def forecast_plan_unpublish(request, plan_id):
    """Volta um plano publicado para DRAFT."""
    plan = get_object_or_404(ForecastPlan, id=plan_id)
    plan.status = ForecastPlan.STATUS_DRAFT
    plan.save(update_fields=["status", "updated_at"])
    return JsonResponse({
        "success": True,
        "plan": _serialize_plan(plan, with_drivers=True),
    })


def _send_plan_whatsapp(plan):
    """Envia WhatsApp a cada driver do plano com o seu briefing."""
    from django.conf import settings
    from system_config.whatsapp_helper import WhatsAppWPPConnectAPI

    sent = 0
    failed = 0
    no_phone = 0

    if not getattr(settings, "WPPCONNECT_URL", ""):
        return {
            "sent": 0, "failed": 0, "no_phone": 0,
            "error": "WPPCONNECT_URL não configurado",
        }

    try:
        api = WhatsAppWPPConnectAPI(
            base_url=settings.WPPCONNECT_URL,
            session_name=settings.WPPCONNECT_SESSION,
            auth_token=settings.WPPCONNECT_TOKEN,
            secret_key=settings.WPPCONNECT_SECRET,
        )
    except Exception:
        return {
            "sent": 0, "failed": 0, "no_phone": 0,
            "error": "Falha ao iniciar WhatsApp API",
        }

    # Agrupar por driver (real)
    by_driver = {}
    for a in plan.assignments.select_related("driver"):
        if not a.driver_id:
            continue  # manual names não enviam
        if a.driver_id not in by_driver:
            by_driver[a.driver_id] = {"driver": a.driver, "lines": [], "total": 0}
        by_driver[a.driver_id]["lines"].append((a.cp4, a.qty))
        by_driver[a.driver_id]["total"] += a.qty

    date_str = plan.operation_date.strftime("%d/%m/%Y")
    hub_str = f" · {plan.hub.name}" if plan.hub else ""

    for grp in by_driver.values():
        d = grp["driver"]
        tel = (d.telefone or "").strip()
        if not tel:
            no_phone += 1
            continue
        digits = "".join(c for c in tel if c.isdigit())
        if len(digits) == 9 and digits.startswith("9"):
            digits = "351" + digits

        cp4_lines = "\n".join(
            f"  • CP4 *{cp4}*: ~{qty} pacotes"
            for cp4, qty in sorted(grp["lines"])
        )
        msg = (
            f"📦 *Plano para {date_str}*{hub_str}\n"
            f"👤 {d.apelido or d.nome_completo}\n\n"
            f"{cp4_lines}\n\n"
            f"📊 *Total: ~{grp['total']} pacotes*\n\n"
            f"_Plano publicado a {timezone.now().strftime('%d/%m %H:%M')}._"
        )
        try:
            api.send_text(number=digits, text=msg)
            sent += 1
        except Exception:
            failed += 1

    return {"sent": sent, "failed": failed, "no_phone": no_phone}


@login_required
def forecast_plan_history(request):
    """Lista planos guardados (para escolher um anterior).

    Query params: hub_id, limit (default 30)
    """
    try:
        limit = max(1, min(100, int(request.GET.get("limit") or 30)))
    except (TypeError, ValueError):
        limit = 30
    hub_id_str = request.GET.get("hub_id") or ""
    qs = ForecastPlan.objects.all()
    if hub_id_str:
        try:
            qs = qs.filter(hub_id=int(hub_id_str))
        except ValueError:
            pass
    rows = []
    for p in qs.select_related("hub").annotate(
        n_assignments=Count("assignments"),
        total_qty=Sum("assignments__qty"),
    )[:limit]:
        rows.append({
            "id": p.id,
            "operation_date": p.operation_date.strftime("%Y-%m-%d"),
            "operation_date_display": p.operation_date.strftime("%d/%m/%Y"),
            "hub_id": p.hub_id,
            "hub_name": p.hub.name if p.hub else "Todos",
            "status": p.status,
            "status_display": p.get_status_display(),
            "n_assignments": p.n_assignments,
            "total_qty": p.total_qty or 0,
            "published_at": (
                p.published_at.strftime("%d/%m/%Y %H:%M")
                if p.published_at else None
            ),
        })
    return JsonResponse({"success": True, "rows": rows})


@login_required
@require_http_methods(["POST"])
def forecast_plan_clone_to(request, plan_id):
    """Clona assignments de um plano para outro (data/hub diferentes).

    Body: { target_date: 'YYYY-MM-DD', target_hub_id: int|null }
    Útil para "copiar plano de ontem para hoje".
    """
    src = get_object_or_404(ForecastPlan, id=plan_id)
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse(
            {"success": False, "error": "JSON inválido"}, status=400,
        )
    target_date = parse_date(body.get("target_date") or "")
    if not target_date:
        return JsonResponse(
            {"success": False, "error":
             "target_date obrigatório"}, status=400,
        )
    hub_id = body.get("target_hub_id")
    target_hub = None
    if hub_id:
        try:
            target_hub = CainiaoHub.objects.get(id=int(hub_id))
        except (CainiaoHub.DoesNotExist, ValueError, TypeError):
            pass

    target_plan, _ = ForecastPlan.objects.get_or_create(
        operation_date=target_date, hub=target_hub,
        defaults={"created_by": request.user},
    )
    if target_plan.status == ForecastPlan.STATUS_PUBLISHED:
        return JsonResponse(
            {"success": False, "error":
             "Plano de destino já publicado — não pode receber clone"},
            status=400,
        )

    with transaction.atomic():
        target_plan.assignments.all().delete()
        bulk = [
            ForecastPlanAssignment(
                plan=target_plan, cp4=a.cp4, driver=a.driver,
                manual_name=a.manual_name, qty=a.qty, notes=a.notes,
            )
            for a in src.assignments.all()
        ]
        ForecastPlanAssignment.objects.bulk_create(bulk)

    return JsonResponse({
        "success": True,
        "n_assignments": len(bulk),
        "plan": _serialize_plan(target_plan, with_drivers=True),
    })


@login_required
@require_http_methods(["POST"])
def driver_set_capacity(request, driver_id):
    """Configura DriverProfile.daily_capacity rapidamente.

    Body: { capacity: int|null }
    """
    d = get_object_or_404(DriverProfile, id=driver_id)
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        body = {}
    cap = body.get("capacity")
    if cap in (None, "", 0):
        d.daily_capacity = None
    else:
        try:
            cap_i = int(cap)
            if cap_i > 0:
                d.daily_capacity = cap_i
            else:
                d.daily_capacity = None
        except (TypeError, ValueError):
            return JsonResponse(
                {"success": False, "error":
                 "capacity inválido"}, status=400,
            )
    d.save(update_fields=["daily_capacity"])
    eff_cap, src = _effective_capacity(d)
    return JsonResponse({
        "success": True,
        "driver_id": d.id,
        "daily_capacity": d.daily_capacity,
        "effective_capacity": eff_cap,
        "capacity_source": src,
    })
