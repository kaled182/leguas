"""
Context processors para drivers_app.
Adiciona contadores de motoristas ao contexto global.
"""

from .models import DriverProfile, DriverProfileChangeRequest


def portal_layout(request):
    """Define qual layout o portal do driver deve estender:
    - Admin Django (staff/superuser) → estende paack_dashboard/base.html (com sidebar)
    - Driver via DriverAccess → estende _layout.html (limpo)
    """
    is_admin = (
        request.user.is_authenticated
        and (request.user.is_staff or request.user.is_superuser)
    )
    return {
        "portal_layout": (
            "paack_dashboard/base.html"
            if is_admin
            else "drivers_app/portal/_layout.html"
        ),
        "is_admin_view": is_admin,
    }


def drivers_counts(request):
    """
    Adiciona contadores de motoristas e pedidos pendentes ao contexto.
    Usado no menu lateral para badges de notificacao.
    """
    # Só calcula para utilizadores com acesso admin (poupa queries)
    if not request.user.is_authenticated or not (request.user.is_staff or request.user.is_superuser):
        return {
            "pending_drivers_count": 0,
            "active_drivers_count": 0,
            "pending_change_requests_count": 0,
            "drivers_missing_contracts": 0,
        }

    try:
        pending_count = DriverProfile.objects.filter(
            status__in=["PENDENTE", "EM_ANALISE"]
        ).count()

        active_count = DriverProfile.objects.filter(
            status="ATIVO", is_active=True
        ).count()

        change_requests_pending = DriverProfileChangeRequest.objects.filter(
            status="pending",
        ).count()

        # Drivers sem contrato (cálculo leve — só conta se há templates ativos)
        missing_count = 0
        try:
            from contracts.models import ContractTemplate, DriverContract
            from django.utils import timezone
            today = timezone.now().date()
            from django.db.models import Q
            active_templates = ContractTemplate.objects.filter(
                is_active=True, effective_from__lte=today,
            ).filter(
                Q(expires_at__isnull=True) | Q(expires_at__gte=today)
            )
            if active_templates.exists():
                # Contagem aproximada — drivers que NÃO têm pelo menos 1 contrato activo
                signed_drivers = DriverContract.objects.filter(
                    revoked_at__isnull=True,
                ).values_list("driver_id", flat=True).distinct()
                total_drivers = DriverProfile.objects.filter(is_active=True).count()
                missing_count = max(0, total_drivers - len(set(signed_drivers)))
        except Exception:
            pass

        return {
            "pending_drivers_count": pending_count,
            "active_drivers_count": active_count,
            "pending_change_requests_count": change_requests_pending,
            "drivers_missing_contracts": missing_count,
        }
    except Exception:
        return {
            "pending_drivers_count": 0,
            "active_drivers_count": 0,
            "pending_change_requests_count": 0,
            "drivers_missing_contracts": 0,
        }
