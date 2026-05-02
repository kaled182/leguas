"""Filtros custom para templates accounting."""
from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


def _to_decimal(v):
    if v is None or v == "":
        return Decimal("0")
    try:
        return Decimal(str(v))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


@register.filter(name="sub")
def sub(value, arg):
    """Subtracção: {{ a|sub:b }} → a - b."""
    return _to_decimal(value) - _to_decimal(arg)


@register.filter(name="add_dec")
def add_dec(value, arg):
    """Soma decimal (alternativa robusta ao add do Django)."""
    return _to_decimal(value) + _to_decimal(arg)
