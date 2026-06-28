"""Views do módulo de Processamento de Tickets Cainiao (abertura/recurso
em massa a partir da planilha de exceptions).

Fluxo:
  1. Upload da planilha  → create_batch_from_file (parse + cruzamento)
  2. Página de trabalho  → tabela com estado interno + motorista resolvido
  3. Anexos por linha    → colar (Ctrl+V) ou drag&drop, sem sair do browser
  4. Abertura em massa   → cria CustomerComplaint + copia anexos
  5. Download em massa    → ZIP de PDFs + planilha de estado (xlsx)
"""
import json
import zipfile
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import (
    CustomerComplaint,
    CustomerComplaintAttachment,
    DriverProfile,
    TicketImportAttachment,
    TicketImportBatch,
    TicketImportRow,
)
from . import services_ticket_import as svc


# ─────────────────────────────────────────────────────────────────────────
# Serialização
# ─────────────────────────────────────────────────────────────────────────
def _row_to_dict(row):
    return {
        "id": row.id,
        "exception_id": row.exception_id,
        "waybill_number": row.waybill_number,
        "ticket_no": row.ticket_no,
        "exception_name": row.exception_name,
        "ticket_type": row.ticket_type,
        "description": row.description,
        "hub": row.hub,
        "exception_creation_time": (
            row.exception_creation_time.isoformat()
            if row.exception_creation_time else None
        ),
        "driver_name_raw": row.driver_name_raw,
        "driver_id": row.driver_id,
        "driver_nome": row.driver.nome_completo if row.driver else "",
        "internal_status": row.internal_status,
        "internal_status_display": row.get_internal_status_display(),
        "category": row.category,
        "category_display": row.get_category_display(),
        "is_severe": row.is_severe,
        "is_delivered": row.is_delivered,
        "delivered_at": (
            row.delivered_at.isoformat() if row.delivered_at else None
        ),
        "row_action": row.row_action,
        "row_action_display": row.get_row_action_display(),
        "complaint_id": row.complaint_id,
        "claim_id_ref": row.claim_id_ref,
        "can_open": row.can_open,
        "selected": row.selected,
        "suggested_tipo": row.suggested_tipo,
        "operator_notes": row.operator_notes,
        "n_attachments": row.attachments.count(),
        "attachments": [
            {"id": a.id, "url": a.ficheiro.url, "descricao": a.descricao}
            for a in row.attachments.all()
        ],
    }


# ─────────────────────────────────────────────────────────────────────────
# Página + upload
# ─────────────────────────────────────────────────────────────────────────
@login_required
def admin_tickets_cainiao(request):
    """Página principal do módulo. Abre no batch mais recente (ou vazia)."""
    batch_id = request.GET.get("batch")
    if batch_id:
        batch = TicketImportBatch.objects.filter(id=batch_id).first()
    else:
        batch = TicketImportBatch.objects.order_by("-created_at").first()

    recent_batches = TicketImportBatch.objects.order_by("-created_at")[:15]
    return render(request, "drivers_app/admin_tickets_cainiao.html", {
        "batch": batch,
        "recent_batches": recent_batches,
        "tipo_choices": CustomerComplaint.TIPO_CHOICES,
        "status_choices": TicketImportRow.INTERNAL_STATUS_CHOICES,
    })


def _validate_xlsx(request):
    f = request.FILES.get("file")
    if not f:
        return None, JsonResponse(
            {"success": False, "error": "Sem ficheiro."}, status=400,
        )
    if not (f.name or "").lower().endswith((".xlsx", ".xlsm")):
        return None, JsonResponse(
            {"success": False, "error": "Envie um ficheiro .xlsx."}, status=400,
        )
    return f, None


@login_required
@require_http_methods(["POST"])
def tickets_import_preview(request):
    """Faz parse e devolve as categorias/contagens para o operador escolher
    o que importar, SEM criar nada na BD."""
    f, err = _validate_xlsx(request)
    if err:
        return err
    try:
        data = svc.preview_categories(f)
    except Exception as exc:  # noqa: BLE001
        import logging
        logging.getLogger("drivers_app").exception("preview falhou")
        return JsonResponse(
            {"success": False, "error": f"{type(exc).__name__}: {exc}"},
            status=500,
        )
    return JsonResponse({"success": True, **data})


@login_required
@require_http_methods(["POST"])
def tickets_import_upload(request):
    """Recebe o xlsx (e categorias a importar) e cria o batch."""
    f, err = _validate_xlsx(request)
    if err:
        return err

    # categorias a importar (lista) — vazio/ausente = todas
    raw_cats = request.POST.get("categories", "")
    categories = [c for c in raw_cats.split(",") if c.strip()] or None
    auto_close = request.POST.get("auto_close", "1") != "0"

    try:
        batch = svc.create_batch_from_file(
            f, filename=f.name, user=request.user,
            categories=categories, auto_close_delivered=auto_close,
        )
    except Exception as exc:  # noqa: BLE001
        import logging
        logging.getLogger("drivers_app").exception("tickets_import_upload falhou")
        return JsonResponse(
            {"success": False, "error": f"{type(exc).__name__}: {exc}"},
            status=500,
        )
    return JsonResponse({
        "success": True,
        "batch_id": batch.id,
        "total_rows": batch.total_rows,
        "n_auto_closed": getattr(batch, "n_auto_closed", 0),
    })


# ─────────────────────────────────────────────────────────────────────────
# Listagem de linhas (com filtros) + KPIs
# ─────────────────────────────────────────────────────────────────────────
@login_required
def tickets_import_rows_api(request, batch_id):
    batch = get_object_or_404(TicketImportBatch, id=batch_id)
    qs = (
        batch.rows.select_related("driver")
        .prefetch_related("attachments")
    )

    status = request.GET.get("status", "").strip()
    hub = request.GET.get("hub", "").strip()
    exc_name = request.GET.get("exception_name", "").strip()
    category = request.GET.get("category", "").strip()
    action = request.GET.get("action", "").strip()
    search = request.GET.get("q", "").strip()
    only_no_driver = request.GET.get("no_driver", "") == "1"
    # Por omissão esconde ignorados/fechados; ?show_handled=1 mostra tudo.
    show_handled = request.GET.get("show_handled", "") == "1"

    if status:
        qs = qs.filter(internal_status=status)
    if hub:
        qs = qs.filter(hub__icontains=hub)
    if exc_name:
        qs = qs.filter(exception_name__icontains=exc_name)
    if category:
        qs = qs.filter(category=category)
    if action:
        qs = qs.filter(row_action=action)
    elif not show_handled:
        qs = qs.exclude(
            row_action__in=[
                TicketImportRow.ACTION_IGNORED, TicketImportRow.ACTION_CLOSED,
            ]
        )
    if only_no_driver:
        qs = qs.filter(driver__isnull=True)
    if search:
        from django.db.models import Q
        qs = qs.filter(
            Q(waybill_number__icontains=search)
            | Q(ticket_no__icontains=search)
            | Q(description__icontains=search)
            | Q(driver_name_raw__icontains=search)
        )

    rows = [_row_to_dict(r) for r in qs]

    # KPIs sobre o batch inteiro (não filtrado)
    from django.db.models import Count
    by_status = {
        d["internal_status"]: d["n"]
        for d in batch.rows.values("internal_status").annotate(n=Count("id"))
    }
    by_cat = {
        d["category"]: d["n"]
        for d in batch.rows.values("category").annotate(n=Count("id"))
    }
    by_action = {
        d["row_action"]: d["n"]
        for d in batch.rows.values("row_action").annotate(n=Count("id"))
    }
    cat_labels = dict(TicketImportRow.CATEGORY_CHOICES)
    kpis = {
        "total": batch.total_rows,
        "sem_reclamacao": by_status.get(TicketImportRow.STATUS_SEM_RECLAMACAO, 0),
        "aberta": by_status.get(TicketImportRow.STATUS_ABERTA, 0),
        "fechada": by_status.get(TicketImportRow.STATUS_FECHADA, 0),
        "em_recurso": by_status.get(TicketImportRow.STATUS_EM_RECURSO, 0),
        "descontada": by_status.get(TicketImportRow.STATUS_DESCONTADA, 0),
        "sem_motorista": batch.rows.filter(driver__isnull=True).count(),
        "ignorados": by_action.get(TicketImportRow.ACTION_IGNORED, 0),
        "fechados_op": by_action.get(TicketImportRow.ACTION_CLOSED, 0),
        "categories": [
            {"category": c, "label": cat_labels.get(c, c), "count": n}
            for c, n in sorted(by_cat.items(), key=lambda kv: -kv[1])
        ],
        "hubs": list(
            batch.rows.exclude(hub="")
            .values_list("hub", flat=True).distinct().order_by("hub")
        ),
    }

    return JsonResponse({"success": True, "rows": rows, "kpis": kpis})


# ─────────────────────────────────────────────────────────────────────────
# Atualização de uma linha (motorista, seleção, tipo, notas)
# ─────────────────────────────────────────────────────────────────────────
@login_required
@require_http_methods(["POST"])
def tickets_import_row_update(request, row_id):
    row = get_object_or_404(TicketImportRow, id=row_id)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        data = request.POST.dict()

    fields = []
    if "driver_id" in data:
        drv_id = data.get("driver_id")
        if drv_id in (None, "", "null"):
            row.driver = None
        else:
            row.driver = get_object_or_404(DriverProfile, id=drv_id)
        fields.append("driver")
    if "selected" in data:
        row.selected = bool(data["selected"])
        fields.append("selected")
    if "suggested_tipo" in data:
        row.suggested_tipo = (data.get("suggested_tipo") or "").strip()
        fields.append("suggested_tipo")
    if "operator_notes" in data:
        row.operator_notes = (data.get("operator_notes") or "").strip()
        fields.append("operator_notes")
    if "row_action" in data:
        val = (data.get("row_action") or "").strip().upper()
        valid = {c for c, _ in TicketImportRow.ROW_ACTION_CHOICES}
        if val not in valid:
            val = TicketImportRow.ACTION_NONE
        row.row_action = val
        fields.append("row_action")

    if fields:
        row.save(update_fields=fields + ["updated_at"])
    return JsonResponse({"success": True, "row": _row_to_dict(row)})


def _apply_row_action(batch, ids, action):
    """Define a disposição (IGNORED/CLOSED/'') de várias linhas. Quando
    CLOSED e existe reclamação aberta, fecha também a reclamação."""
    qs = batch.rows.all()
    if isinstance(ids, list) and ids:
        qs = qs.filter(id__in=ids)
    else:
        qs = qs.filter(selected=True)

    n = 0
    close_complaints = []
    for row in qs:
        row.row_action = action
        row.save(update_fields=["row_action", "updated_at"])
        if (action == TicketImportRow.ACTION_CLOSED
                and row.complaint_id
                and row.complaint
                and row.complaint.status not in ("FECHADO", "CANCELADO")):
            close_complaints.append(row.complaint)
        n += 1

    for complaint in close_complaints:
        complaint.status = "FECHADO"
        complaint.data_fecho = timezone.now()
        complaint.save(update_fields=["status", "data_fecho", "updated_at"])

    return n, len(close_complaints)


@login_required
@require_http_methods(["POST"])
def tickets_import_bulk_action(request, batch_id):
    """Aplica Ignorar / Fechar / Reabrir a linhas selecionadas ou por ids."""
    batch = get_object_or_404(TicketImportBatch, id=batch_id)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        data = {}
    action = (data.get("action") or "").strip().upper()
    valid = {c for c, _ in TicketImportRow.ROW_ACTION_CHOICES}
    if action not in valid:
        return JsonResponse(
            {"success": False, "error": "Ação inválida."}, status=400,
        )
    n, n_complaints = _apply_row_action(batch, data.get("ids"), action)
    return JsonResponse({
        "success": True, "n": n, "n_complaints_closed": n_complaints,
    })


@login_required
@require_http_methods(["POST"])
def tickets_import_auto_close(request, batch_id):
    """Re-verifica os Expedited Delivery e fecha os já entregues."""
    batch = get_object_or_404(TicketImportBatch, id=batch_id)
    n = svc.auto_close_delivered_expedited(batch)
    return JsonResponse({"success": True, "n_closed": n})


@login_required
@require_http_methods(["POST"])
def tickets_import_bulk_select(request, batch_id):
    """Marca/desmarca seleção em massa (respeita filtro de ids enviado)."""
    batch = get_object_or_404(TicketImportBatch, id=batch_id)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        data = {}
    selected = bool(data.get("selected"))
    ids = data.get("ids")
    qs = batch.rows.all()
    if isinstance(ids, list):
        qs = qs.filter(id__in=ids)
    qs.update(selected=selected, updated_at=timezone.now())
    return JsonResponse({"success": True})


# ─────────────────────────────────────────────────────────────────────────
# Anexos por linha (colar / drag&drop / ficheiro)
# ─────────────────────────────────────────────────────────────────────────
@login_required
@require_http_methods(["POST"])
def tickets_import_row_attach(request, row_id):
    row = get_object_or_404(TicketImportRow, id=row_id)
    files = request.FILES.getlist("file") or request.FILES.getlist("files")
    if not files:
        return JsonResponse(
            {"success": False, "error": "Sem ficheiro(s)."}, status=400,
        )
    created = []
    for f in files:
        att = TicketImportAttachment.objects.create(
            row=row,
            ficheiro=f,
            descricao=(request.POST.get("descricao") or "")[:200],
        )
        created.append({"id": att.id, "url": att.ficheiro.url})
    return JsonResponse({
        "success": True,
        "attachments": created,
        "n_attachments": row.attachments.count(),
    })


@login_required
@require_http_methods(["POST"])
def tickets_import_attach_delete(request, att_id):
    att = get_object_or_404(TicketImportAttachment, id=att_id)
    row = att.row
    att.ficheiro.delete(save=False)
    att.delete()
    return JsonResponse(
        {"success": True, "n_attachments": row.attachments.count()},
    )


# ─────────────────────────────────────────────────────────────────────────
# Abertura em massa de reclamações
# ─────────────────────────────────────────────────────────────────────────
@login_required
@require_http_methods(["POST"])
def tickets_import_bulk_open(request, batch_id):
    """Abre CustomerComplaint para as linhas selecionadas que ainda não têm
    reclamação. Copia os anexos carregados e re-classifica a linha."""
    batch = get_object_or_404(TicketImportBatch, id=batch_id)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        data = {}

    ids = data.get("ids")
    rows = batch.rows.select_related("driver").prefetch_related("attachments")
    if isinstance(ids, list) and ids:
        rows = rows.filter(id__in=ids)
    else:
        rows = rows.filter(selected=True)

    created, skipped = [], []
    for row in rows:
        # Guards: precisa de motorista e não pode já ter reclamação
        if not row.can_open:
            skipped.append({"id": row.id, "reason": "Já tem reclamação/claim."})
            continue
        if not row.driver_id:
            skipped.append({"id": row.id, "reason": "Sem motorista resolvido."})
            continue

        waybill = (row.waybill_number or "").strip()
        if not waybill:
            skipped.append({"id": row.id, "reason": "Sem waybill (tracking)."})
            continue

        # Guard anti-duplicado (mesma regra de driver_complaint_create)
        today = timezone.localdate()
        dup = (
            CustomerComplaint.objects
            .filter(numero_pacote__iexact=waybill, created_at__date=today)
            .exclude(status="CANCELADO")
            .first()
        )
        if dup:
            row.complaint = dup
            row.internal_status = TicketImportRow.STATUS_ABERTA
            row.save(update_fields=["complaint", "internal_status", "updated_at"])
            skipped.append({
                "id": row.id,
                "reason": f"Já existe reclamação hoje (#{dup.id}).",
            })
            continue

        cust = svc.lookup_customer_data(waybill)
        tipo = row.suggested_tipo or "ENTREGA_FALSA"

        complaint = CustomerComplaint.objects.create(
            driver=row.driver,
            numero_pacote=waybill,
            tipo=tipo,
            descricao=(row.description or row.exception_name or "Ticket Cainiao"),
            nome_cliente=cust["nome_cliente"] or "(a confirmar)",
            telefone_cliente=cust["telefone_cliente"] or "",
            email_cliente=cust["email_cliente"] or "",
            morada=cust["morada"] or "(a confirmar)",
            codigo_postal=cust["codigo_postal"] or "",
            cidade=cust["cidade"] or "",
            data_entrega=cust["data_entrega"],
            notas=(
                f"Aberto via Processador de Tickets Cainiao.\n"
                f"Ticket Nº: {row.ticket_no} | Exception: {row.exception_name}"
                + (f"\n{row.operator_notes}" if row.operator_notes else "")
            ),
            created_by=request.user,
        )

        # Copia os anexos da linha para a reclamação
        for att in row.attachments.all():
            CustomerComplaintAttachment.objects.create(
                complaint=complaint,
                tipo="RECLAMACAO",
                ficheiro=att.ficheiro,
                descricao=att.descricao,
            )

        row.complaint = complaint
        row.internal_status = TicketImportRow.STATUS_ABERTA
        row.selected = False
        row.save(update_fields=[
            "complaint", "internal_status", "selected", "updated_at",
        ])
        created.append({"row_id": row.id, "complaint_id": complaint.id})

    return JsonResponse({
        "success": True,
        "created": created,
        "skipped": skipped,
        "n_created": len(created),
        "n_skipped": len(skipped),
    })


# ─────────────────────────────────────────────────────────────────────────
# Exports: ZIP de PDFs + planilha de estado
# ─────────────────────────────────────────────────────────────────────────
@login_required
def tickets_import_export_zip(request, batch_id):
    """ZIP com o PDF de cada reclamação ligada às linhas deste batch."""
    from .views import driver_complaint_pdf

    batch = get_object_or_404(TicketImportBatch, id=batch_id)
    complaint_ids = list(
        batch.rows.exclude(complaint__isnull=True)
        .values_list("complaint_id", flat=True).distinct()
    )

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for cid in complaint_ids:
            try:
                resp = driver_complaint_pdf(request, cid)
                content = getattr(resp, "content", b"")
                if content:
                    zf.writestr(f"reclamacao_{cid}.pdf", content)
            except Exception:
                continue
    buf.seek(0)

    resp = HttpResponse(buf.getvalue(), content_type="application/zip")
    resp["Content-Disposition"] = (
        f'attachment; filename="reclamacoes_lote_{batch.id}.zip"'
    )
    return resp


@login_required
def tickets_import_export_xlsx(request, batch_id):
    """Exporta a planilha de estado: cada linha com motorista resolvido,
    estado interno e nº da reclamação criada."""
    import openpyxl

    batch = get_object_or_404(TicketImportBatch, id=batch_id)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Estado Tickets"

    headers = [
        "Exception ID", "Tracking Number", "Ticket No.", "Exception Name",
        "Ticket Type", "HUB", "Criação Exception", "Driver (planilha)",
        "Motorista Resolvido", "Estado Interno", "Reclamação Nº",
        "Nº Anexos", "Notas Operador",
    ]
    ws.append(headers)

    for r in batch.rows.select_related("driver").prefetch_related("attachments"):
        ws.append([
            r.exception_id,
            r.waybill_number,
            r.ticket_no,
            r.exception_name,
            r.ticket_type,
            r.hub,
            (r.exception_creation_time.strftime("%Y-%m-%d %H:%M")
             if r.exception_creation_time else ""),
            r.driver_name_raw,
            r.driver.nome_completo if r.driver else "",
            r.get_internal_status_display(),
            r.complaint_id or "",
            r.attachments.count(),
            r.operator_notes,
        ])

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    resp = HttpResponse(
        buf.getvalue(),
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )
    resp["Content-Disposition"] = (
        f'attachment; filename="estado_tickets_lote_{batch.id}.xlsx"'
    )
    return resp


# ─────────────────────────────────────────────────────────────────────────
# Pesquisa de motoristas (reaproveitada pelo seletor de motorista da linha)
# ─────────────────────────────────────────────────────────────────────────
@login_required
def tickets_import_driver_search(request):
    q = (request.GET.get("q") or "").strip()
    qs = DriverProfile.objects.all()
    if q:
        from django.db.models import Q
        qs = qs.filter(
            Q(nome_completo__icontains=q)
            | Q(apelido__icontains=q)
            | Q(courier_id_cainiao__icontains=q)
        )
    qs = qs.order_by("nome_completo")[:20]
    return JsonResponse({
        "success": True,
        "drivers": [
            {
                "id": d.id,
                "nome_completo": d.nome_completo,
                "apelido": d.apelido,
            }
            for d in qs
        ],
    })
