"""Views CRUD para o Calendário de Feriados.

Página única em /settlements/calendar/ com:
  - Selector de ano
  - Vista calendário (12 meses) com feriados destacados
  - Tabela editável com modal de criação/edição
  - Importar preset PT (calcula Páscoa para o ano)
"""
import json
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.utils.dateparse import parse_date
from django.utils import timezone

from .models import BonusBlackoutDate, Holiday


def _easter_sunday(year):
    """Algoritmo Anonymous Gregorian (Meeus/Jones/Butcher)."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    L = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * L) // 451
    month = (h + L - 7 * m + 114) // 31
    day = ((h + L - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _pt_movable_holidays(year):
    """Calcula feriados móveis PT para o ano."""
    easter = _easter_sunday(year)
    return [
        (easter - timedelta(days=47), "Carnaval"),
        (easter - timedelta(days=2),  "Sexta-Feira Santa"),
        (easter,                      "Páscoa"),
        (easter + timedelta(days=60), "Corpo de Deus"),
    ]


def _serialize(h):
    return {
        "id": h.id,
        "name": h.name,
        "date": h.date.strftime("%Y-%m-%d"),
        "date_display": h.date.strftime("%d/%m/%Y"),
        "is_recurring_yearly": h.is_recurring_yearly,
        "scope": h.scope,
        "scope_display": h.get_scope_display(),
        "region": h.region,
        "notes": h.notes,
    }


@login_required
def holiday_list(request):
    """Página principal do calendário."""
    try:
        year = int(request.GET.get("year") or timezone.now().year)
    except (TypeError, ValueError):
        year = timezone.now().year

    # Feriados deste ano (recorrentes + datas exatas no ano)
    recurring = Holiday.objects.filter(is_recurring_yearly=True)
    fixed = Holiday.objects.filter(
        is_recurring_yearly=False, date__year=year,
    )

    # Materializar todos para mostrar no calendário visual
    holidays_in_year = []
    for h in recurring:
        d = date(year, h.date.month, h.date.day)
        holidays_in_year.append({
            "id": h.id, "date": d, "name": h.name,
            "is_recurring": True, "scope": h.scope, "region": h.region,
            "notes": h.notes,
        })
    for h in fixed:
        holidays_in_year.append({
            "id": h.id, "date": h.date, "name": h.name,
            "is_recurring": False, "scope": h.scope, "region": h.region,
            "notes": h.notes,
        })
    holidays_in_year.sort(key=lambda x: x["date"])

    # Lista todas as entradas (para tabela admin)
    all_holidays = list(Holiday.objects.all())

    # Bloqueios de bonificação (datas onde, mesmo sendo domingo/feriado,
    # não há bónus). Filtramos pelo ano selecionado + entradas futuras.
    blackouts = list(
        BonusBlackoutDate.objects.filter(
            date__year=year,
        ).order_by("date")
    )
    blackouts_serialized = [
        {
            "id": b.id,
            "date": b.date.strftime("%Y-%m-%d"),
            "date_display": b.date.strftime("%d/%m/%Y"),
            "reason": b.reason,
        }
        for b in blackouts
    ]

    return render(
        request,
        "settlements/holiday_calendar.html",
        {
            "year": year,
            "year_prev": year - 1,
            "year_next": year + 1,
            "holidays_in_year": holidays_in_year,
            "all_holidays": all_holidays,
            "blackouts": blackouts,
            "blackouts_serialized": blackouts_serialized,
            "available_years": list(range(year - 3, year + 4)),
        },
    )


@login_required
@require_http_methods(["POST"])
def holiday_create(request):
    """Cria um feriado a partir de form data ou JSON."""
    if request.content_type == "application/json":
        body = json.loads(request.body or b"{}")
    else:
        body = request.POST

    name = (body.get("name") or "").strip()
    date_str = (body.get("date") or "").strip()
    is_recurring = bool(body.get("is_recurring_yearly"))
    if isinstance(is_recurring, str):
        is_recurring = is_recurring.lower() in ("true", "1", "on", "yes")
    scope = (body.get("scope") or "national").strip()
    region = (body.get("region") or "").strip()
    notes = (body.get("notes") or "").strip()

    if not name or not date_str:
        return JsonResponse(
            {"success": False, "error": "Nome e data são obrigatórios."},
            status=400,
        )

    parsed = parse_date(date_str)
    if not parsed:
        return JsonResponse(
            {"success": False, "error": "Data inválida."},
            status=400,
        )

    h = Holiday.objects.create(
        name=name, date=parsed,
        is_recurring_yearly=is_recurring,
        scope=scope, region=region, notes=notes,
    )
    return JsonResponse({"success": True, "holiday": _serialize(h)})


@login_required
@require_http_methods(["POST"])
def holiday_update(request, holiday_id):
    try:
        h = Holiday.objects.get(id=holiday_id)
    except Holiday.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Feriado não encontrado."},
            status=404,
        )

    if request.content_type == "application/json":
        body = json.loads(request.body or b"{}")
    else:
        body = request.POST

    if "name" in body:
        name = (body.get("name") or "").strip()
        if name:
            h.name = name
    if "date" in body:
        parsed = parse_date(body.get("date") or "")
        if parsed:
            h.date = parsed
    if "is_recurring_yearly" in body:
        v = body.get("is_recurring_yearly")
        if isinstance(v, str):
            v = v.lower() in ("true", "1", "on", "yes")
        h.is_recurring_yearly = bool(v)
    if "scope" in body:
        h.scope = (body.get("scope") or "national").strip()
    if "region" in body:
        h.region = (body.get("region") or "").strip()
    if "notes" in body:
        h.notes = (body.get("notes") or "").strip()

    h.save()
    return JsonResponse({"success": True, "holiday": _serialize(h)})


@login_required
@require_http_methods(["POST"])
def holiday_delete(request, holiday_id):
    try:
        h = Holiday.objects.get(id=holiday_id)
    except Holiday.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Feriado não encontrado."},
            status=404,
        )
    h.delete()
    return JsonResponse({"success": True})


@login_required
@require_http_methods(["POST"])
def holiday_import_preset(request):
    """Importa o preset PT (móveis) para um ano específico.

    Os feriados de data fixa são recorrentes (já criados pelo seed
    inicial). Esta acção apenas adiciona os móveis (Páscoa+derivados)
    para o ano dado.
    """
    body = (json.loads(request.body or b"{}")
            if request.content_type == "application/json"
            else request.POST)
    try:
        year = int(body.get("year") or timezone.now().year)
    except (TypeError, ValueError):
        return JsonResponse(
            {"success": False, "error": "Ano inválido."}, status=400,
        )

    created = 0
    skipped = 0
    for d, name in _pt_movable_holidays(year):
        existing = Holiday.objects.filter(date=d, name=name).first()
        if existing:
            skipped += 1
            continue
        Holiday.objects.create(
            name=name, date=d, is_recurring_yearly=False,
            scope="national",
            notes=(
                f"Feriado móvel — adicionar entrada nova "
                f"nos anos seguintes"
            ),
        )
        created += 1

    return JsonResponse({
        "success": True, "year": year,
        "created": created, "skipped": skipped,
    })


@login_required
def holiday_check(request):
    """API helper: GET ?date=YYYY-MM-DD&region=Aveiro → {is_holiday, name}.

    Pode ser usado pelo modal driver / UI da pré-fatura para mostrar
    badges em datas de bónus.
    """
    date_str = request.GET.get("date") or ""
    region = (request.GET.get("region") or "").strip() or None
    parsed = parse_date(date_str)
    if not parsed:
        return JsonResponse(
            {"success": False, "error": "Data inválida."}, status=400,
        )

    h = Holiday.get_holiday(parsed, region=region)
    return JsonResponse({
        "success": True,
        "date": date_str,
        "is_holiday": bool(h),
        "is_sunday": parsed.weekday() == 6,
        "name": h.name if h else "",
        "scope": h.scope if h else "",
    })


# ════════════════════════════════════════════════════════════════════════
# Bloqueios de Bonificação (BonusBlackoutDate)
# ════════════════════════════════════════════════════════════════════════
@login_required
@require_http_methods(["POST"])
def blackout_create(request):
    """Cria um bloqueio de bonificação para uma data específica."""
    body = (json.loads(request.body or b"{}")
            if request.content_type == "application/json"
            else request.POST)
    date_str = (body.get("date") or "").strip()
    reason = (body.get("reason") or "").strip()
    parsed = parse_date(date_str)
    if not parsed:
        return JsonResponse(
            {"success": False, "error": "Data inválida."}, status=400,
        )
    obj, created = BonusBlackoutDate.objects.get_or_create(
        date=parsed,
        defaults={
            "reason": reason,
            "created_by": request.user if request.user.is_authenticated else None,
        },
    )
    if not created and reason and obj.reason != reason:
        obj.reason = reason
        obj.save(update_fields=["reason", "updated_at"])
    return JsonResponse({
        "success": True,
        "blackout": {
            "id": obj.id,
            "date": obj.date.strftime("%Y-%m-%d"),
            "date_display": obj.date.strftime("%d/%m/%Y"),
            "reason": obj.reason,
        },
        "created": created,
    })


@login_required
@require_http_methods(["POST"])
def blackout_delete(request, blackout_id):
    """Remove um bloqueio de bonificação."""
    try:
        b = BonusBlackoutDate.objects.get(id=blackout_id)
    except BonusBlackoutDate.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Bloqueio não encontrado."},
            status=404,
        )
    b.delete()
    return JsonResponse({"success": True})
