"""Vistas para gerir os fechos de período contabilístico."""
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import AccountingPeriodLock
from .services_period_lock import (
    invalidate_lock_cache, locked_periods_summary,
)


def _is_staff(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


@login_required
def period_lock_list(request):
    """Lista os últimos 24 meses + estado de cada um."""
    today = timezone.localdate()
    months = []
    y, m = today.year, today.month
    for _ in range(24):
        m -= 1
        if m < 1:
            m = 12
            y -= 1
        months.append((y, m))

    lock_map = {
        (l.year, l.month): l
        for l in AccountingPeriodLock.objects.filter(
            year__gte=today.year - 3,
        ).select_related("locked_by", "unlocked_by")
    }

    rows = []
    for (y, m) in months:
        lock = lock_map.get((y, m))
        rows.append({
            "year": y,
            "month": m,
            "label": f"{m:02d}/{y}",
            "lock": lock,
            "is_locked": bool(lock and lock.is_locked),
        })

    return render(request, "accounting/period_lock_list.html", {
        "rows": rows,
        "can_manage": _is_staff(request.user),
        "history": locked_periods_summary(),
    })


@login_required
@user_passes_test(_is_staff)
@require_http_methods(["POST"])
def period_lock_toggle(request):
    """Fecha ou reabre o período (year, month) recebido no POST."""
    try:
        year = int(request.POST.get("year"))
        month = int(request.POST.get("month"))
    except (TypeError, ValueError):
        messages.error(request, "Período inválido.")
        return redirect("accounting:period_lock_list")

    notes = (request.POST.get("notes") or "").strip()
    action = (request.POST.get("action") or "").strip()

    lock, _created = AccountingPeriodLock.objects.get_or_create(
        year=year, month=month,
        defaults={"is_locked": False},
    )

    if action == "lock":
        lock.lock(user=request.user, notes=notes)
        msg = f"Período {month:02d}/{year} fechado."
    elif action == "unlock":
        if not lock.is_locked:
            messages.info(request, f"Período {month:02d}/{year} já estava aberto.")
            return redirect("accounting:period_lock_list")
        lock.unlock(user=request.user, reason=notes)
        msg = f"Período {month:02d}/{year} reaberto."
    else:
        messages.error(request, f"Acção desconhecida: {action}")
        return redirect("accounting:period_lock_list")

    invalidate_lock_cache()
    messages.success(request, msg)
    return redirect("accounting:period_lock_list")
