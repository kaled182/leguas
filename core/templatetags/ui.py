"""Formatos pt-PT e ajudas dos componentes base."""
from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()

NBSP = " "
MINUS = "−"
EMPTY = "—"

# Estado Cainiao: (texto, tom). O valor original fica no tooltip.
CAINIAO_STATUS = {
    "Delivered": ("Entregue", "success"),
    "Attempt Failure": ("Falhada", "danger"),
    "Driver_received": ("Em distribuição", "warning"),
    "Assigned": ("Atribuído", "neutral"),
    "Unassign": ("Por atribuir", "neutral"),
    "Stale_Armazem": ("Parado no armazém", "warning"),
    "Wrong HUB": ("Hub errado", "neutral"),
    "Exception": ("Exceção", "danger"),
}


def _decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _number(value, places):
    number = _decimal(value)
    if number is None:
        return None
    sign = MINUS if number < 0 else ""
    text = f"{abs(number):,.{places}f}"
    return sign + text.replace(",", NBSP).replace(".", ",")


@register.filter
def eur(value):
    text = _number(value, 2)
    return EMPTY if text is None else f"{text}{NBSP}€"


@register.filter
def pt_int(value):
    text = _number(value, 0)
    return EMPTY if text is None else text


@register.filter
def pct(value, places=1):
    text = _number(value, int(places))
    return EMPTY if text is None else f"{text}{NBSP}%"


@register.filter
def status_label(value):
    return CAINIAO_STATUS.get(value, (value, "neutral"))[0]


@register.filter
def status_tone(value):
    return CAINIAO_STATUS.get(value, (value, "neutral"))[1]


@register.simple_tag(takes_context=True)
def query_with(context, **changes):
    """Query string atual com alterações: mantém os filtros no URL."""
    query = context["request"].GET.copy()
    for key, value in changes.items():
        if value in (None, ""):
            query.pop(key, None)
        else:
            query[key] = value
    return f"?{query.urlencode()}" if query else "?"
