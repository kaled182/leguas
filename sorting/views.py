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
    sessions = qs[:200]
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
# Export — Excel da sessão (uma folha por sessão; uma linha por pacote)
# ─────────────────────────────────────────────────────────────────────────
@login_required
def session_export_xlsx(request, session_id):
    import openpyxl

    session = get_object_or_404(SortingSession, id=session_id)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sorting"
    ws.append([
        "Bigbag", "CP4", "Zona", "Motorista", "Waybill", "Código Postal",
        "Localidade", "Estado", "Lido em",
    ])
    parcels = (
        session.parcels.select_related("bigbag", "bigbag__driver")
        .order_by("cp4", "zona_nome", "scanned_at")
    )
    for p in parcels:
        b = p.bigbag
        ws.append([
            b.codigo if b else "(não classificado)",
            p.cp4,
            p.zona_nome,
            (b.driver.nome_completo if b and b.driver else ""),
            p.waybill_number,
            p.cp,
            p.localidade,
            p.get_status_display(),
            p.scanned_at.strftime("%Y-%m-%d %H:%M") if p.scanned_at else "",
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
        f'attachment; filename="sorting_sessao_{session.id}.xlsx"'
    )
    return resp
