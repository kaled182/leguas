from datetime import datetime, date
from decimal import Decimal
from typing import Optional
import json

from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_http_methods
from django.db import transaction, models

from .models import CompensationPlan, PerPackageRate, ThresholdBonus
from ordersmanager_paack.models import Driver
from .services import _apply_pkg_rates, _apply_thresholds, _pick_plan

def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s: return None
    return datetime.strptime(s, "%Y-%m-%d").date()

def _plan_to_dict(plan: CompensationPlan, include_children=True):
    d = {
        "id": plan.id,
        "driver_id": plan.driver_id,
        "driver_name": plan.driver.name if plan.driver_id else None,
        "client": plan.client,
        "area_code": plan.area_code,
        "starts_on": plan.starts_on.isoformat(),
        "ends_on": plan.ends_on.isoformat() if plan.ends_on else None,
        "base_fixed": float(plan.base_fixed),
        "is_active": plan.is_active,
    }
    if include_children:
        d["rates"] = [{
            "id": r.id,
            "min_delivered": r.min_delivered,
            "max_delivered": r.max_delivered,
            "rate_eur": float(r.rate_eur),
            "priority": r.priority,
            "progressive": r.progressive
        } for r in plan.pkg_rates.all().order_by("priority","min_delivered")]
        d["thresholds"] = [{
            "id": t.id,
            "kind": t.kind,
            "start_at": t.start_at,
            "step": t.step,
            "amount_eur": float(t.amount_eur)
        } for t in plan.thresholds.all()]
    return d

@require_http_methods(["GET"])
def plans_list(request):
    qs = CompensationPlan.objects.select_related("driver").all()
    if request.GET.get("driver_id"): qs = qs.filter(driver_id=request.GET["driver_id"])
    if request.GET.get("client"): qs = qs.filter(client=request.GET["client"])
    if request.GET.get("area_code"): qs = qs.filter(area_code=request.GET["area_code"])
    if request.GET.get("active") in ("true","false"):
        qs = qs.filter(is_active=(request.GET["active"]=="true"))
    data = [_plan_to_dict(p) for p in qs.order_by("-starts_on","driver__name")[:500]]
    return JsonResponse(data, safe=False)

@require_http_methods(["GET"])
def plans_conflicts(request):
    driver_id = request.GET.get("driver_id")
    if not driver_id:
        return HttpResponseBadRequest("driver_id é obrigatório")
    client = request.GET.get("client")
    area = request.GET.get("area_code")
    qs = CompensationPlan.objects.filter(driver_id=driver_id, is_active=True)
    if client: qs = qs.filter(client=client)
    if area:   qs = qs.filter(area_code=area)

    conflicts = []
    plans = list(qs.order_by("starts_on"))
    for i in range(len(plans)):
        for j in range(i+1, len(plans)):
            a, b = plans[i], plans[j]
            a_end = a.ends_on or date.max
            b_end = b.ends_on or date.max
            if not (a_end < b.starts_on or b_end < a.starts_on):
                conflicts.append([_plan_to_dict(a, False), _plan_to_dict(b, False)])
    return JsonResponse(conflicts, safe=False)

@require_http_methods(["GET"])
def plan_detail(request, plan_id: int):
    plan = CompensationPlan.objects.select_related("driver").get(id=plan_id)
    return JsonResponse(_plan_to_dict(plan), safe=False)

@require_http_methods(["POST"])
@transaction.atomic
def plan_create(request):
    body = json.loads(request.body or "{}")
    driver_id = body.get("driver_id")
    if not driver_id: return HttpResponseBadRequest("driver_id é obrigatório")
    driver = Driver.objects.get(id=driver_id)

    plan = CompensationPlan.objects.create(
        driver=driver,
        client=body.get("client") or None,
        area_code=body.get("area_code") or None,
        starts_on=_parse_date(body.get("starts_on")),
        ends_on=_parse_date(body.get("ends_on")),
        base_fixed=Decimal(str(body.get("base_fixed") or 0)),
        is_active=bool(body.get("is_active", True)),
    )
    for r in body.get("rates", []):
        PerPackageRate.objects.create(
            plan=plan,
            min_delivered=int(r.get("min_delivered", 0)),
            max_delivered=r.get("max_delivered"),
            rate_eur=Decimal(str(r.get("rate_eur", 0))),
            priority=int(r.get("priority", 1)),
            progressive=bool(r.get("progressive", False)),
        )
    for t in body.get("thresholds", []):
        ThresholdBonus.objects.create(
            plan=plan,
            kind=t.get("kind","EACH_STEP"),
            start_at=int(t.get("start_at")),
            step=int(t.get("step",0)),
            amount_eur=Decimal(str(t.get("amount_eur"))),
        )
    return JsonResponse(_plan_to_dict(plan), status=201)

@require_http_methods(["PUT","PATCH"])
@transaction.atomic
def plan_update(request, plan_id: int):
    body = json.loads(request.body or "{}")
    plan = CompensationPlan.objects.get(id=plan_id)

    for field in ["client","area_code","is_active"]:
        if field in body: setattr(plan, field, body[field] or None)
    if "starts_on" in body: plan.starts_on = _parse_date(body["starts_on"])
    if "ends_on" in body:   plan.ends_on   = _parse_date(body["ends_on"])
    if "base_fixed" in body: plan.base_fixed = Decimal(str(body["base_fixed"] or 0))
    if "driver_id" in body:
        plan.driver = Driver.objects.get(id=body["driver_id"])
    plan.save()

    if "rates" in body:
        plan.pkg_rates.all().delete()
        for r in body["rates"]:
            PerPackageRate.objects.create(
                plan=plan,
                min_delivered=int(r.get("min_delivered", 0)),
                max_delivered=r.get("max_delivered"),
                rate_eur=Decimal(str(r.get("rate_eur", 0))),
                priority=int(r.get("priority", 1)),
                progressive=bool(r.get("progressive", False)),
            )
    if "thresholds" in body:
        plan.thresholds.all().delete()
        for t in body["thresholds"]:
            ThresholdBonus.objects.create(
                plan=plan,
                kind=t.get("kind","EACH_STEP"),
                start_at=int(t.get("start_at")),
                step=int(t.get("step",0)),
                amount_eur=Decimal(str(t.get("amount_eur"))),
            )
    return JsonResponse(_plan_to_dict(plan))

@require_http_methods(["POST"])
@transaction.atomic
def plan_clone(request, plan_id: int):
    body = json.loads(request.body or "{}")
    src = CompensationPlan.objects.get(id=plan_id)
    dst = CompensationPlan.objects.create(
        driver = src.driver,
        client = body.get("client", src.client),
        area_code = body.get("area_code", src.area_code),
        starts_on = _parse_date(body.get("starts_on")) or src.starts_on,
        ends_on   = _parse_date(body.get("ends_on")) or src.ends_on,
        base_fixed = src.base_fixed,
        is_active  = body.get("is_active", src.is_active),
    )
    for r in src.pkg_rates.all():
        PerPackageRate.objects.create(
            plan=dst, min_delivered=r.min_delivered, max_delivered=r.max_delivered,
            rate_eur=r.rate_eur, priority=r.priority, progressive=r.progressive
        )
    for t in src.thresholds.all():
        ThresholdBonus.objects.create(
            plan=dst, kind=t.kind, start_at=t.start_at, step=t.step, amount_eur=t.amount_eur
        )
    return JsonResponse(_plan_to_dict(dst), status=201)

@require_http_methods(["DELETE"])
@transaction.atomic
def plan_delete(request, plan_id: int):
    CompensationPlan.objects.filter(id=plan_id).delete()
    return JsonResponse({"ok": True})

@require_http_methods(["GET"])
def plan_preview(request):
    delivered = int(request.GET.get("delivered", "0"))
    driver_id = request.GET.get("driver_id")
    client = request.GET.get("client")
    area = request.GET.get("area_code")
    day = _parse_date(request.GET.get("date")) or date.today()

    if driver_id:
        driver = Driver.objects.get(id=driver_id)
        plan = _pick_plan(driver, client, area, day)
    else:
        plan_id = request.GET.get("plan_id")
        if not plan_id: return HttpResponseBadRequest("plan_id ou driver_id é obrigatório")
        plan = CompensationPlan.objects.get(id=plan_id)

    base = Decimal(plan.base_fixed if plan else 0)
    by_pkg = _apply_pkg_rates(plan, delivered)
    bonus = _apply_thresholds(plan, delivered)
    gross = base + by_pkg + bonus

    return JsonResponse({
        "plan_id": plan.id if plan else None,
        "delivered": delivered,
        "base_fixed": float(base),
        "by_package": float(by_pkg),
        "bonus": float(bonus),
        "gross": float(gross),
    })
