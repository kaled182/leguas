"""Views do Sorting de pacotes em bigbags virtuais."""
import json
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from drivers_app.models import DriverProfile

from . import services as svc
from .models import SortingBigbag, SortingParcel, SortingSession


# ─────────────────────────────────────────────────────────────────────────
# Páginas
# ─────────────────────────────────────────────────────────────────────────
@login_required
def sorting_workspace(request):
    """Página de trabalho do sorting (criar sessão, ler pacotes, bigbags)."""
    session_id = request.GET.get("session")
    session = None
    if session_id:
        session = SortingSession.objects.filter(id=session_id).first()
    if session is None:
        session = (
            SortingSession.objects
            .filter(status=SortingSession.STATUS_OPEN)
            .order_by("-created_at").first()
        )
    return render(request, "sorting/workspace.html", {
        "session": session,
        "mode_choices": SortingSession.MODE_CHOICES,
        "hubs": _hub_choices(),
    })


@login_required
def sorting_history(request):
    """Lista de sessões de sorting (histórico para conferência)."""
    qs = SortingSession.objects.select_related("created_by").all()
    status = (request.GET.get("status") or "").strip()
    if status:
        qs = qs.filter(status=status)
    hub = (request.GET.get("hub") or "").strip()
    if hub:
        qs = qs.filter(hub=hub)
    sessions = list(qs[:200])

    # CP4 distintos por sessão (uma query só), anexados a cada sessão.
    cp4_map = {}
    if sessions:
        rows = (
            SortingBigbag.objects
            .filter(session_id__in=[s.id for s in sessions])
            .exclude(cp4="")
            .values_list("session_id", "cp4")
            .distinct()
        )
        for sid, cp4 in rows:
            cp4_map.setdefault(sid, set()).add(cp4)
    for s in sessions:
        s.cp4_list = sorted(cp4_map.get(s.id, []))

    return render(request, "sorting/history.html", {
        "sessions": sessions,
        "status_choices": SortingSession.STATUS_CHOICES,
        "hubs": _hub_choices(),
    })


def _hub_choices():
    """HUBs conhecidos a partir das tasks Cainiao (para o seletor)."""
    try:
        from settlements.models import CainiaoOperationTask
        return list(
            CainiaoOperationTask.objects
            .exclude(hub="").values_list("hub", flat=True)
            .distinct().order_by("hub")[:50]
        )
    except Exception:
        return []


# ─────────────────────────────────────────────────────────────────────────
# API — Sessões
# ─────────────────────────────────────────────────────────────────────────
@login_required
@require_http_methods(["POST"])
def session_create(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        data = request.POST.dict()
    mode = (data.get("mode") or SortingSession.MODE_CP4).strip().upper()
    if mode not in {c for c, _ in SortingSession.MODE_CHOICES}:
        mode = SortingSession.MODE_CP4
    session = SortingSession.objects.create(
        nome=(data.get("nome") or "").strip()[:160],
        hub=(data.get("hub") or "").strip()[:120],
        mode=mode,
        target_cps=(data.get("target_cps") or "").strip()[:255],
        observacao=(data.get("observacao") or "").strip(),
        created_by=request.user,
    )
    return JsonResponse({"success": True, "session_id": session.id})


@login_required
def session_detail(request, session_id):
    session = get_object_or_404(SortingSession, id=session_id)
    return JsonResponse({"success": True, **svc.session_summary(session)})


@login_required
def session_parcels(request, session_id):
    """Pacotes de uma bigbag (ou todos) — para conferência."""
    session = get_object_or_404(SortingSession, id=session_id)
    qs = session.parcels.all()
    bigbag_id = request.GET.get("bigbag")
    if bigbag_id:
        qs = qs.filter(bigbag_id=bigbag_id)
    return JsonResponse({
        "success": True,
        "parcels": [svc.parcel_to_dict(p) for p in qs],
    })


@login_required
@require_http_methods(["POST"])
def session_finish(request, session_id):
    session = get_object_or_404(SortingSession, id=session_id)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        data = {}
    obs = (data.get("observacao") or "").strip()
    if obs:
        session.observacao = obs
    session.status = SortingSession.STATUS_DONE
    session.finished_at = timezone.now()
    session.save(update_fields=["status", "finished_at", "observacao", "updated_at"])
    return JsonResponse({"success": True, **svc.session_summary(session)})


@login_required
@require_http_methods(["POST"])
def session_reopen(request, session_id):
    session = get_object_or_404(SortingSession, id=session_id)
    session.status = SortingSession.STATUS_OPEN
    session.finished_at = None
    session.save(update_fields=["status", "finished_at", "updated_at"])
    return JsonResponse({"success": True})


# ─────────────────────────────────────────────────────────────────────────
# API — Scan + bigbags
# ─────────────────────────────────────────────────────────────────────────
@login_required
@require_http_methods(["POST"])
def scan(request, session_id):
    session = get_object_or_404(SortingSession, id=session_id)
    if not session.is_open:
        return JsonResponse(
            {"success": False, "error": "Sessão finalizada. Reabra para ler."},
            status=409,
        )
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        data = request.POST.dict()
    waybill = (data.get("waybill") or "").strip()
    if not waybill:
        return JsonResponse(
            {"success": False, "error": "Waybill vazio."}, status=400,
        )
    result = svc.scan_parcel(session, waybill, user=request.user)
    return JsonResponse({"success": True, **result})


@login_required
@require_http_methods(["POST"])
def bigbag_update(request, bigbag_id):
    bigbag = get_object_or_404(SortingBigbag, id=bigbag_id)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        data = request.POST.dict()
    fields = []
    if "driver_id" in data:
        drv = data.get("driver_id")
        if drv in (None, "", "null"):
            bigbag.driver = None
        else:
            bigbag.driver = get_object_or_404(DriverProfile, id=drv)
        fields.append("driver")
    if "observacao" in data:
        bigbag.observacao = (data.get("observacao") or "")[:255]
        fields.append("observacao")
    if fields:
        bigbag.save(update_fields=fields)
    return JsonResponse({"success": True, "bigbag": svc.bigbag_to_dict(bigbag)})


@login_required
@require_http_methods(["POST"])
def parcel_delete(request, parcel_id):
    """Remove um pacote mal lido."""
    parcel = get_object_or_404(SortingParcel, id=parcel_id)
    bigbag = parcel.bigbag
    parcel.delete()
    return JsonResponse({
        "success": True,
        "bigbag": svc.bigbag_to_dict(bigbag) if bigbag else None,
    })


@login_required
def driver_search(request):
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
            {"id": d.id, "nome_completo": d.nome_completo, "apelido": d.apelido}
            for d in qs
        ],
    })


# ─────────────────────────────────────────────────────────────────────────
# Export — Excel (total da sessão ou por bigbag/CP4)
# ─────────────────────────────────────────────────────────────────────────
_XLSX_CT = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


def _parcels_xlsx(parcels, sheet_title="Sorting"):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_title[:31]
    ws.append([
        "Bigbag", "CP4", "Zona", "Motorista", "Waybill", "Código Postal",
        "Localidade", "Cliente", "Telefone", "Morada", "Estado", "Lido em",
    ])
    for p in parcels:
        b = p.bigbag
        ws.append([
            b.codigo if b else "(não classificado)",
            p.cp4, p.zona_nome,
            (b.driver.nome_completo if b and b.driver else ""),
            p.waybill_number, p.cp, p.localidade,
            p.nome_cliente, p.telefone_cliente, p.morada,
            p.get_status_display(),
            p.scanned_at.strftime("%Y-%m-%d %H:%M") if p.scanned_at else "",
        ])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


@login_required
def session_export_xlsx(request, session_id):
    session = get_object_or_404(SortingSession, id=session_id)
    parcels = (
        session.parcels.select_related("bigbag", "bigbag__driver")
        .order_by("cp4", "zona_nome", "scanned_at")
    )
    content = _parcels_xlsx(parcels, "Sorting")
    resp = HttpResponse(content, content_type=_XLSX_CT)
    resp["Content-Disposition"] = (
        f'attachment; filename="sorting_sessao_{session.id}.xlsx"'
    )
    return resp


@login_required
def bigbag_export_xlsx(request, bigbag_id):
    bigbag = get_object_or_404(
        SortingBigbag.objects.select_related("driver"), id=bigbag_id,
    )
    parcels = bigbag.parcels.order_by("scanned_at")
    content = _parcels_xlsx(parcels, f"BB {bigbag.cp4}")
    resp = HttpResponse(content, content_type=_XLSX_CT)
    safe = (bigbag.codigo or f"bigbag_{bigbag.id}").replace("/", "-")
    resp["Content-Disposition"] = f'attachment; filename="{safe}.xlsx"'
    return resp


# ─────────────────────────────────────────────────────────────────────────
# Etiqueta de fecho/despacho (PDF) — por bigbag ou todas da sessão
# ─────────────────────────────────────────────────────────────────────────
def _build_label_flowables(bigbag, styles):
    """Constrói os elementos de uma etiqueta (para 1 bigbag)."""
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
    from reportlab.graphics.barcode import code128
    from reportlab.graphics.shapes import Drawing

    session = bigbag.session
    cp7 = svc.bigbag_cp7_list(bigbag)
    n = bigbag.parcels.count()
    driver = bigbag.driver.nome_completo if bigbag.driver else "— (sem motorista)"
    mode = session.get_mode_display()
    grouping = (
        f"GEOZONA: {bigbag.zona_nome}" if bigbag.zona_nome
        else f"CP4: {bigbag.cp4}"
    )

    title = Paragraph(
        "<b>LÉGUAS FRANZINAS — ETIQUETA DE DESPACHO</b>", styles["h"],
    )
    big = Paragraph(f"<b>{bigbag.label}</b>", styles["big"])

    rows = [
        ["HUB", session.hub or "—"],
        ["Modo", mode],
        ["Agrupamento", grouping],
        ["Motorista", driver],
        ["Nº de Pacotes", str(n)],
        ["Bigbag", bigbag.codigo or f"BB-{bigbag.id}"],
        ["Sessão", f"#{session.id} — {session.nome or ''}"],
        ["Códigos Postais", ", ".join(cp7) if cp7 else "—"],
    ]
    if bigbag.observacao:
        rows.append(["Observação", bigbag.observacao])

    tbl = Table(rows, colWidths=[3.2 * cm, 11.5 * cm])
    tbl.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#6B7280")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.HexColor("#E5E7EB")),
    ]))

    # Código de barras do código da bigbag
    bc_value = bigbag.codigo or f"BB-{bigbag.id}"
    bc = code128.Code128(bc_value, barHeight=1.4 * cm, barWidth=1.0)
    d = Drawing(bc.width, 1.4 * cm)
    d.add(bc)

    return [
        title, Spacer(1, 0.2 * cm), big, Spacer(1, 0.3 * cm),
        tbl, Spacer(1, 0.4 * cm), d,
        Paragraph(bc_value, styles["mono"]),
    ]


def _labels_pdf(bigbags, filename):
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import PageBreak, SimpleDocTemplate

    base = getSampleStyleSheet()["Normal"]
    styles = {
        "h": ParagraphStyle("h", parent=base, fontSize=11, leading=14),
        "big": ParagraphStyle(
            "big", parent=base, fontSize=22, leading=24,
        ),
        "mono": ParagraphStyle(
            "mono", parent=base, fontSize=9, alignment=TA_CENTER,
            fontName="Helvetica",
        ),
    }
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        leftMargin=1.8 * cm, rightMargin=1.8 * cm,
    )
    story = []
    for i, b in enumerate(bigbags):
        if i > 0:
            story.append(PageBreak())
        story.extend(_build_label_flowables(b, styles))
    if not story:
        story.append(getSampleStyleSheet()["Normal"].clone("x"))
    doc.build(story)
    buf.seek(0)
    resp = HttpResponse(buf.getvalue(), content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


@login_required
def bigbag_label_pdf(request, bigbag_id):
    bigbag = get_object_or_404(
        SortingBigbag.objects.select_related("driver", "session"),
        id=bigbag_id,
    )
    safe = (bigbag.codigo or f"bigbag_{bigbag.id}").replace("/", "-")
    return _labels_pdf([bigbag], f"etiqueta_{safe}.pdf")


@login_required
def session_labels_pdf(request, session_id):
    session = get_object_or_404(SortingSession, id=session_id)
    bigbags = list(
        session.bigbags.select_related("driver", "session")
        .order_by("cp4", "zona_nome")
    )
    return _labels_pdf(bigbags, f"etiquetas_sessao_{session.id}.pdf")
