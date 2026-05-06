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
    """Página de detalhe da importação Cainiao com 5 tabs."""
    from collections import defaultdict
    from decimal import Decimal
    from django.core.paginator import Paginator
    from django.db.models import Count, Sum
    from django.db.models.functions import Coalesce
    from .models import CainiaoBillingImport
    from .services_cainiao_billing import reconciliation_for_import

    session = get_object_or_404(
        CainiaoBillingImport.objects.select_related(
            "partner_invoice", "imported_by",
        ),
        id=import_id,
    )

    active_tab = request.GET.get("tab", "summary")
    ctx = {"session": session, "active_tab": active_tab}

    # ── Tab: Resumo ──────────────────────────────────────────────────
    if active_tab == "summary":
        # Top 10 motoristas (envio fee, agregado)
        top_drivers = list(
            session.lines.filter(fee_type="envio fee")
            .values("driver_id", "driver__nome_completo", "staff_id")
            .annotate(
                deliveries=Count("id"),
                total=Coalesce(Sum("amount"), Decimal("0")),
            )
            .order_by("-deliveries")[:10]
        )

        # Breakdown por billing_id (lote/corte)
        billing_breakdown = list(
            session.lines.values("cainiao_billing_id")
            .annotate(
                lines=Count("id"),
                total=Coalesce(Sum("amount"), Decimal("0")),
                envios=Count("id", filter=Q_envio()),
                claims=Count("id", filter=Q_claim()),
            )
            .order_by("-lines")
        )

        # Distribuição de preços (envio fee)
        price_dist = list(
            session.lines.filter(fee_type="envio fee")
            .values("amount")
            .annotate(n=Count("id"))
            .order_by("-n")[:10]
        )

        ctx.update({
            "top_drivers": top_drivers,
            "billing_breakdown": billing_breakdown,
            "price_dist": price_dist,
        })

    # ── Tab: Linhas (paginadas) ──────────────────────────────────────
    elif active_tab == "lines":
        qs = session.lines.select_related("driver", "task")
        # Filtros
        f_fee = request.GET.get("fee_type", "")
        f_billing = request.GET.get("billing_id", "")
        f_search = (request.GET.get("q") or "").strip()
        if f_fee in ("envio fee", "compensacion"):
            qs = qs.filter(fee_type=f_fee)
        if f_billing:
            qs = qs.filter(cainiao_billing_id=f_billing)
        if f_search:
            qs = qs.filter(waybill_number__icontains=f_search)
        paginator = Paginator(qs, 100)
        page = paginator.get_page(request.GET.get("page", 1))
        # Listas para os filtros
        billing_ids = list(
            session.lines.values_list(
                "cainiao_billing_id", flat=True,
            ).distinct().order_by("cainiao_billing_id"),
        )
        ctx.update({
            "lines_page": page,
            "filter_fee_type": f_fee,
            "filter_billing_id": f_billing,
            "filter_search": f_search,
            "billing_ids_filter": billing_ids,
        })

    # ── Tab: Reconciliação ───────────────────────────────────────────
    elif active_tab == "reconciliation":
        recon = reconciliation_for_import(session)
        # Paginar as duas listas grandes
        from django.core.paginator import Paginator as P
        ctx.update({
            "recon": recon,
            "paid_no_task_page": P(
                recon["paid_no_task"], 50,
            ).get_page(request.GET.get("p1", 1)),
            "delivered_no_billing_page": P(
                recon["delivered_no_billing"], 50,
            ).get_page(request.GET.get("p2", 1)),
        })

    # ── Tab: Preços Especiais ────────────────────────────────────────
    elif active_tab == "special_prices":
        qs = session.lines.filter(
            fee_type="envio fee",
        ).exclude(amount=Decimal("1.60")).select_related(
            "driver", "task", "price_override",
        ).order_by("-amount", "-biz_time")
        paginator = Paginator(qs, 100)
        page = paginator.get_page(request.GET.get("page", 1))
        # Distribuição de preços
        dist = (
            session.lines.filter(fee_type="envio fee")
            .exclude(amount=Decimal("1.60"))
            .values("amount")
            .annotate(n=Count("id"), total=Sum("amount"))
            .order_by("-n")
        )
        already_overridden = qs.filter(price_override__isnull=False).count()
        ctx.update({
            "special_page": page,
            "special_dist": list(dist),
            "special_total": qs.count(),
            "already_overridden": already_overridden,
        })

    # ── Tab: Claims ──────────────────────────────────────────────────
    elif active_tab == "claims":
        from drivers_app.models import DriverProfile
        from .models import DriverClaim
        qs = (
            session.lines.filter(fee_type="compensacion")
            .select_related("driver", "task", "claim")
            .order_by("-biz_time")
        )
        # Drivers activos para o select (compactos)
        drivers_options = list(
            DriverProfile.objects
            .filter(is_active=True)
            .values("id", "nome_completo", "apelido", "courier_id_cainiao")
            .order_by("nome_completo")
        )
        ctx.update({
            "claim_lines": list(qs),
            "claims_total_value": qs.aggregate(
                s=Coalesce(Sum("amount"), Decimal("0")),
            )["s"],
            "claims_unassigned": qs.filter(claim__isnull=True).count(),
            "claims_assigned": qs.filter(claim__isnull=False).count(),
            "claims_with_suggestion": qs.filter(
                claim__isnull=True, driver__isnull=False,
            ).count(),
            "drivers_options": drivers_options,
            "claim_types": DriverClaim.CLAIM_TYPES,
        })

    return render(
        request, "settlements/cainiao_billing_detail.html", ctx,
    )


def Q_envio():
    from django.db.models import Q
    return Q(fee_type="envio fee")


def Q_claim():
    from django.db.models import Q
    return Q(fee_type="compensacion")


@login_required
@require_http_methods(["POST"])
def cainiao_billing_assign_claim(request, import_id, line_id):
    """Cria ou actualiza DriverClaim para uma compensación.

    Body:
      driver_id: ID do DriverProfile (obrigatório)
      claim_type: ORDER_LOSS / OTHER / ... (default ORDER_LOSS)
    """
    from drivers_app.models import DriverProfile
    from .models import (
        CainiaoBillingImport, CainiaoBillingLine, DriverClaim,
    )

    session = get_object_or_404(CainiaoBillingImport, id=import_id)
    line = get_object_or_404(
        CainiaoBillingLine, id=line_id, import_session=session,
    )
    if line.fee_type != "compensacion":
        return JsonResponse({
            "success": False,
            "error": "Esta linha não é uma compensación.",
        }, status=400)
    if line.claim_id:
        return JsonResponse({
            "success": False,
            "error": (
                f"Linha já tem DriverClaim #{line.claim_id} "
                "associado."
            ),
        }, status=400)

    driver_id = request.POST.get("driver_id")
    if not driver_id:
        return JsonResponse({
            "success": False, "error": "driver_id obrigatório.",
        }, status=400)
    driver = get_object_or_404(DriverProfile, id=driver_id)

    claim_type = request.POST.get("claim_type") or "ORDER_LOSS"
    if claim_type not in dict(DriverClaim.CLAIM_TYPES):
        claim_type = "ORDER_LOSS"

    # Valor: o XLSX tem negativo (-30). DriverClaim usa positivo.
    amount = abs(line.amount)

    description = (
        f"Cainiao Billing #{session.id} ({line.cainiao_billing_id}). "
        f"Waybill: {line.waybill_number}. "
        f"Motivo: {line.fb2 or '—'}"
    )[:2000]

    claim = DriverClaim.objects.create(
        driver=driver,
        claim_type=claim_type,
        amount=amount,
        description=description,
        occurred_at=line.biz_time,
        waybill_number=line.waybill_number,
        operation_task_date=(
            line.task.task_date if line.task else line.biz_time.date()
        ),
        auto_detected=False,
        created_by=(
            request.user if request.user.is_authenticated else None
        ),
    )
    line.claim = claim
    line.driver = driver
    line.save(update_fields=["claim", "driver"])

    return JsonResponse({
        "success": True,
        "claim_id": claim.id,
        "driver_name": driver.nome_completo,
        "amount": str(amount),
    })


@login_required
@require_http_methods(["POST"])
def cainiao_billing_assign_claims_bulk(request, import_id):
    """Cria DriverClaim para todas as compensaciones com driver sugerido.

    Driver sugerido = line.driver (resolvido no import via task) ou
    line.task.courier_id_cainiao mapeado para DriverProfile.

    Linhas sem driver sugerido são ignoradas (devolvidas como skipped).
    """
    from .models import (
        CainiaoBillingImport, DriverClaim,
    )
    from django.db import transaction

    session = get_object_or_404(CainiaoBillingImport, id=import_id)
    claim_type = request.POST.get("claim_type") or "ORDER_LOSS"
    if claim_type not in dict(DriverClaim.CLAIM_TYPES):
        claim_type = "ORDER_LOSS"

    qs = session.lines.filter(
        fee_type="compensacion",
        claim__isnull=True,
        driver__isnull=False,
    ).select_related("driver", "task")

    created = 0
    with transaction.atomic():
        for line in qs:
            description = (
                f"Cainiao Billing #{session.id} "
                f"({line.cainiao_billing_id}). "
                f"Waybill: {line.waybill_number}. "
                f"Motivo: {line.fb2 or '—'}"
            )[:2000]
            claim = DriverClaim.objects.create(
                driver=line.driver,
                claim_type=claim_type,
                amount=abs(line.amount),
                description=description,
                occurred_at=line.biz_time,
                waybill_number=line.waybill_number,
                operation_task_date=(
                    line.task.task_date if line.task
                    else line.biz_time.date()
                ),
                auto_detected=False,
                created_by=(
                    request.user if request.user.is_authenticated else None
                ),
            )
            line.claim = claim
            line.save(update_fields=["claim"])
            created += 1

    skipped_no_driver = session.lines.filter(
        fee_type="compensacion", claim__isnull=True, driver__isnull=True,
    ).count()

    if created:
        messages.success(
            request,
            f"{created} DriverClaim criados. "
            f"{skipped_no_driver} ignorados (sem driver sugerido — "
            "atribua manualmente).",
        )
    else:
        messages.warning(
            request,
            f"Nenhum claim criado. "
            f"{skipped_no_driver} linhas precisam de atribuição manual.",
        )
    return redirect(
        f"{reverse('cainiao-billing-detail', args=[session.id])}"
        f"?tab=claims",
    )


@login_required
@require_http_methods(["POST"])
def cainiao_billing_create_overrides(request, import_id):
    """Cria PackagePriceOverride para linhas com preço ≠ €1.60.

    Body:
      mode = "all" | "selected"
      line_ids = "1,2,3" (necessário se mode=selected)
    """
    from decimal import Decimal
    from django.db import transaction
    from .models import (
        CainiaoBillingImport, CainiaoBillingLine, PackagePriceOverride,
    )

    session = get_object_or_404(CainiaoBillingImport, id=import_id)
    mode = request.POST.get("mode", "selected")

    qs = session.lines.filter(
        fee_type="envio fee",
    ).exclude(amount=Decimal("1.60")).filter(price_override__isnull=True)

    if mode == "selected":
        ids = (request.POST.get("line_ids") or "").split(",")
        ids = [int(i) for i in ids if i.strip().isdigit()]
        if not ids:
            messages.error(request, "Nenhuma linha seleccionada.")
            return redirect(
                "cainiao-billing-detail",
                import_id=session.id,
            )
        qs = qs.filter(id__in=ids)

    created = 0
    skipped_existing = 0
    skipped_no_waybill = 0

    with transaction.atomic():
        for line in qs.select_related("task"):
            if not line.waybill_number:
                skipped_no_waybill += 1
                continue
            # Se já existe override (criado fora desta tab), só liga
            existing = PackagePriceOverride.objects.filter(
                waybill_number=line.waybill_number,
            ).first()
            if existing:
                line.price_override = existing
                line.save(update_fields=["price_override"])
                skipped_existing += 1
                continue
            task_date = (
                line.task.task_date if line.task
                else line.biz_time.date()
            )
            cp4 = ""
            original_name = ""
            if line.task:
                cp4 = (line.task.zip_code or "")[:4]
                original_name = line.task.courier_name or ""
            override = PackagePriceOverride.objects.create(
                waybill_number=line.waybill_number,
                task_date=task_date,
                cp4=cp4,
                original_courier_name=original_name,
                price=line.amount,
                reason=(
                    f"Cainiao billing import #{session.id} "
                    f"({session.period_from.strftime('%d/%m')}"
                    f"–{session.period_to.strftime('%d/%m/%Y')})"
                )[:200],
                created_by=(
                    request.user if request.user.is_authenticated else None
                ),
            )
            line.price_override = override
            line.save(update_fields=["price_override"])
            created += 1

    if created:
        messages.success(
            request,
            f"{created} PackagePriceOverride criados. "
            f"{skipped_existing} já existiam (linkados). "
            f"{skipped_no_waybill} ignorados (sem waybill).",
        )
    elif skipped_existing:
        messages.info(
            request,
            f"{skipped_existing} overrides já existiam — todos linkados.",
        )
    else:
        messages.warning(request, "Nenhum override criado.")

    return redirect(
        f"{reverse('cainiao-billing-detail', args=[session.id])}"
        f"?tab=special_prices",
    )


@login_required
@require_http_methods(["POST"])
def cainiao_billing_reresolve(request, import_id):
    """Re-corre a resolução de task/driver para um import existente.

    Útil quando o EPOD Task List é importado DEPOIS da pré-fatura
    Cainiao — as tasks agora existem mas o matching original não
    as encontrou.
    """
    from .models import CainiaoBillingImport
    from .services_cainiao_billing import reresolve_matching

    session = get_object_or_404(CainiaoBillingImport, id=import_id)
    try:
        result = reresolve_matching(session)
    except Exception as e:
        log.exception("reresolve_matching falhou")
        messages.error(request, f"Erro ao reprocessar matching: {e}")
        return redirect(
            "cainiao-billing-detail", import_id=session.id,
        )

    messages.success(
        request,
        f"Matching reprocessado: "
        f"{result['newly_resolved_task']} tasks ligadas, "
        f"{result['newly_resolved_driver']} drivers ligados "
        f"(em {result['total']} linhas).",
    )
    return redirect(
        "cainiao-billing-detail", import_id=session.id,
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
