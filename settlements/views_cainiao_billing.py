"""Views da importação da pré-fatura Cainiao."""
from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

log = logging.getLogger(__name__)


@login_required
@require_http_methods(["POST"])
def cainiao_billing_upload(request):
    """Recebe upload XLSX da pré-fatura Cainiao e dispara import.

    Idempotente: se o mesmo ficheiro já foi importado (mesmo SHA256),
    redirecciona para o detalhe existente sem criar nada.
    """
    from .services_cainiao_billing import import_cainiao_billing

    file = request.FILES.get("file")
    if not file:
        messages.error(request, "Nenhum ficheiro enviado.")
        return redirect("invoice-list")

    if not file.name.lower().endswith(".xlsx"):
        messages.error(
            request,
            "O ficheiro tem de ser .xlsx (Excel). "
            f"Recebido: {file.name}",
        )
        return redirect("invoice-list")

    try:
        session, outcome = import_cainiao_billing(
            file, file.name, user=request.user,
        )
    except ValueError as e:
        messages.error(request, f"Erro ao processar ficheiro: {e}")
        return redirect("invoice-list")
    except Exception as e:
        log.exception("Falha inesperada a importar pré-fatura Cainiao")
        messages.error(
            request,
            f"Erro inesperado: {e}. Veja os logs do servidor.",
        )
        return redirect("invoice-list")

    if outcome == "already_imported":
        messages.info(
            request,
            f"Este ficheiro já tinha sido importado em "
            f"{session.imported_at.strftime('%d/%m/%Y %H:%M')}. "
            "A abrir o detalhe existente.",
        )
    else:
        messages.success(
            request,
            f"Pré-fatura Cainiao importada: "
            f"{session.total_lines} linhas, "
            f"€{session.total_amount:.2f} líquido "
            f"({session.period_from.strftime('%d/%m')}→"
            f"{session.period_to.strftime('%d/%m/%Y')}).",
        )

    return redirect(
        "cainiao-billing-detail",
        import_id=session.id,
    )


@login_required
def cainiao_billing_detail(request, import_id):
    """Página de detalhe da importação Cainiao.

    Esta página tem 5 tabs (Resumo, Linhas, Reconciliação,
    Preços Especiais, Claims). Nesta Fase 2 mostramos apenas um stub
    com KPIs básicos — as outras tabs serão preenchidas nas Fases 4-7.
    """
    from .models import CainiaoBillingImport

    session = get_object_or_404(
        CainiaoBillingImport.objects.select_related(
            "partner_invoice", "imported_by",
        ),
        id=import_id,
    )

    return render(
        request, "settlements/cainiao_billing_detail.html",
        {
            "session": session,
            "active_tab": request.GET.get("tab", "summary"),
        },
    )


@login_required
@require_http_methods(["POST"])
def cainiao_billing_delete(request, import_id):
    """Apagar uma sessão de importação (cascade nas linhas).

    Se houver PartnerInvoice associada e estiver PAGA, bloqueia.
    """
    from .models import CainiaoBillingImport

    session = get_object_or_404(CainiaoBillingImport, id=import_id)

    if session.partner_invoice and session.partner_invoice.status == "PAID":
        return JsonResponse({
            "success": False,
            "error": (
                "Não é possível apagar — a PartnerInvoice associada já "
                "está marcada como paga. Cancele primeiro a fatura."
            ),
        }, status=400)

    summary = (
        f"Cainiao {session.period_from}→{session.period_to} "
        f"({session.total_lines} linhas)"
    )
    if session.partner_invoice:
        session.partner_invoice.delete()
    session.delete()

    messages.success(request, f"Importação eliminada: {summary}")
    return redirect("invoice-list")
