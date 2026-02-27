from django import template
from ..constants import STATUS_LABELS, STATUS_COLORS

register = template.Library()

@register.filter(name='format_status')
def format_status(value):
    """
    Format the status value using the STATUS_LABELS mapping
    """
    if not value:
        return "-"
    
    return STATUS_LABELS.get(value, value.replace('_', ' ').title())


@register.filter(name='status_color')
def status_color(value):
    """
    Get the CSS color class for a given status
    """
    if not value:
        return "text-gray-600"
    
    return STATUS_COLORS.get(value, "text-gray-600")
