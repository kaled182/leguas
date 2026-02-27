"""
Context processors para drivers_app.
Adiciona contadores de motoristas ao contexto global.
"""
from .models import DriverProfile


def drivers_counts(request):
    """
    Adiciona contadores de motoristas pendentes e ativos ao contexto.
    Usado no menu lateral para badges de notificacao.
    """
    try:
        pending_count = DriverProfile.objects.filter(
            status__in=['PENDENTE', 'EM_ANALISE']
        ).count()
        
        active_count = DriverProfile.objects.filter(
            status='ATIVO',
            is_active=True
        ).count()
        
        return {
            'pending_drivers_count': pending_count,
            'active_drivers_count': active_count,
        }
    except Exception:
        return {
            'pending_drivers_count': 0,
            'active_drivers_count': 0,
        }
