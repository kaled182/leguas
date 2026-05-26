"""Helpers para verificar se um período está fechado contabilisticamente.

Usados por:
  - Views de edição (Bills, Impostos, PFs, PartnerInvoice) para bloquear
    alterações fora da janela de meses abertos
  - Templates para apresentar selo "🔒 Mês fechado"
"""
from datetime import date
from functools import lru_cache

from django.utils import timezone


def is_period_locked(d) -> bool:
    """True se o mês de `d` (date|datetime) está bloqueado.

    Staff/superuser deve verificar `is_period_locked_for_user(d, user)`
    em vez desta para permitir override.
    """
    if d is None:
        return False
    if hasattr(d, "date"):
        d = d.date()
    if not isinstance(d, date):
        return False
    return _is_locked_cached(d.year, d.month)


def is_period_locked_for_user(d, user) -> bool:
    """True se o período está bloqueado E o utilizador não tem privilégio
    para sobrepor o lock (não é staff/superuser)."""
    if user and (user.is_superuser or user.is_staff):
        return False
    return is_period_locked(d)


@lru_cache(maxsize=512)
def _is_locked_cached(year: int, month: int) -> bool:
    from .models import AccountingPeriodLock
    return AccountingPeriodLock.objects.filter(
        year=year, month=month, is_locked=True,
    ).exists()


def invalidate_lock_cache():
    """Chamar após criar/alterar locks."""
    _is_locked_cached.cache_clear()


def locked_periods_summary():
    """Lista locks recentes para UI."""
    from .models import AccountingPeriodLock
    return list(
        AccountingPeriodLock.objects
        .select_related("locked_by", "unlocked_by")
        .order_by("-year", "-month")[:48]
    )
