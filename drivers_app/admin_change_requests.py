"""Vistas admin para aprovar/rejeitar pedidos de alteração de perfil."""
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import DriverProfile, DriverProfileChangeRequest


def _is_admin(u):
    return u.is_authenticated and (u.is_staff or u.is_superuser)


admin_required = user_passes_test(_is_admin, login_url="/auth/login/")


@admin_required
def change_requests_list(request):
    """Lista pedidos de alteração com filtros."""
    status = request.GET.get("status", "pending")
    qs = DriverProfileChangeRequest.objects.select_related(
        "driver", "reviewed_by",
    ).order_by("-requested_at")

    if status:
        qs = qs.filter(status=status)

    counts = {
        "pending": DriverProfileChangeRequest.objects.filter(status="pending").count(),
        "approved": DriverProfileChangeRequest.objects.filter(status="approved").count(),
        "rejected": DriverProfileChangeRequest.objects.filter(status="rejected").count(),
        "cancelled": DriverProfileChangeRequest.objects.filter(status="cancelled").count(),
    }

    return render(request, "drivers_app/admin/change_requests_list.html", {
        "requests": qs[:200],
        "status_filter": status,
        "counts": counts,
    })


@admin_required
@require_http_methods(["POST"])
def change_request_action(request, pk):
    """Aprovar ou rejeitar um pedido."""
    cr = get_object_or_404(DriverProfileChangeRequest, pk=pk)
    action = request.POST.get("action", "")
    notes = request.POST.get("notes", "").strip()

    if cr.status != "pending":
        messages.warning(request, "Este pedido já foi revisto.")
        return redirect("drivers_app:change_requests_list")

    if action == "approve":
        cr.apply_to_driver()
        cr.status = "approved"
        cr.reviewed_at = timezone.now()
        cr.reviewed_by = request.user
        cr.review_notes = notes
        cr.save()
        messages.success(
            request,
            f"Pedido aprovado: {cr.driver.apelido or cr.driver_id} · {cr.get_field_display()} actualizado.",
        )
    elif action == "reject":
        cr.status = "rejected"
        cr.reviewed_at = timezone.now()
        cr.reviewed_by = request.user
        cr.review_notes = notes or "Rejeitado pelo administrador."
        cr.save()
        messages.success(request, "Pedido rejeitado.")
    else:
        messages.error(request, "Acção inválida.")

    return redirect("drivers_app:change_requests_list")


def get_pending_count():
    """Helper: count pending requests (para notificações)."""
    return DriverProfileChangeRequest.objects.filter(status="pending").count()
