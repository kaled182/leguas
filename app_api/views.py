"""Endpoints da API da app do motorista (/api/app/v1/).

Auth por token Bearer (ver auth.py). Respostas JSON limpas. POST sem CSRF
(autenticação por token, não por cookie de sessão).
"""
import json

from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from customauth.otp_service import (
    OTPError,
    resolve_driver_by_phone,
    send_otp,
    verify_otp,
)

from .auth import app_token_required, issue_token
from .serializers import (
    claim_dict,
    driver_dict,
    pre_invoice_detail,
    pre_invoice_summary,
)


def _json_body(request):
    try:
        return json.loads(request.body or b"{}")
    except (ValueError, TypeError):
        return {}


# ─── Auth ───────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def request_code(request):
    """Pede um código OTP por WhatsApp para o número do motorista."""
    data = _json_body(request)
    phone = (data.get("phone") or "").strip()
    try:
        profile = resolve_driver_by_phone(phone)
        masked = send_otp(profile)
    except OTPError as exc:
        return JsonResponse({"error": exc.message}, status=exc.status)
    return JsonResponse({"sent": True, "masked_phone": masked})


@csrf_exempt
@require_http_methods(["POST"])
def verify_code(request):
    """Valida o código e devolve um token Bearer + o perfil do motorista."""
    data = _json_body(request)
    phone = (data.get("phone") or "").strip()
    code = (data.get("code") or "").strip()
    try:
        profile = resolve_driver_by_phone(phone)
        verify_otp(profile, code)
    except OTPError as exc:
        return JsonResponse({"error": exc.message}, status=exc.status)

    tok = issue_token(profile, user_agent=request.headers.get("User-Agent", ""))
    return JsonResponse({
        "token": tok.key,
        "token_type": "Bearer",
        "expires_in": int(
            (tok.expires_at - timezone.now()).total_seconds()
        ) if tok.expires_at else None,
        "driver": driver_dict(profile),
    })


@csrf_exempt
@require_http_methods(["POST"])
@app_token_required
def logout(request):
    """Revoga o token atual."""
    request.app_token.revoked = True
    request.app_token.save(update_fields=["revoked"])
    return HttpResponse(status=204)


# ─── Perfil ─────────────────────────────────────────────────────────

@require_http_methods(["GET"])
@app_token_required
def me(request):
    return JsonResponse(driver_dict(request.driver_profile))


# ─── Faturas (pré-faturas) ──────────────────────────────────────────

@require_http_methods(["GET"])
@app_token_required
def invoices(request):
    from settlements.models import DriverPreInvoice

    qs = DriverPreInvoice.objects.filter(
        driver=request.driver_profile,
    ).order_by("-periodo_fim")
    status = (request.GET.get("status") or "").strip()
    if status:
        qs = qs.filter(status=status)
    ano = (request.GET.get("ano") or "").strip()
    if ano.isdigit():
        qs = qs.filter(periodo_fim__year=int(ano))
    return JsonResponse({"results": [pre_invoice_summary(pf) for pf in qs]})


@require_http_methods(["GET"])
@app_token_required
def invoice_detail(request, pk):
    from settlements.models import DriverPreInvoice

    pf = DriverPreInvoice.objects.filter(
        id=pk, driver=request.driver_profile,
    ).first()
    if not pf:
        return JsonResponse({"error": "Pré-fatura não encontrada."}, status=404)
    return JsonResponse(pre_invoice_detail(pf))


@require_http_methods(["GET"])
@app_token_required
def invoice_pdf(request, pk):
    from settlements.models import DriverPreInvoice
    from settlements.reports.pdf_generator import PDFGenerator

    pf = DriverPreInvoice.objects.filter(
        id=pk, driver=request.driver_profile,
    ).first()
    if not pf:
        return JsonResponse({"error": "Pré-fatura não encontrada."}, status=404)
    try:
        buf = PDFGenerator().generate_pre_invoice_pdf(pf)
        data = buf.getvalue() if hasattr(buf, "getvalue") else bytes(buf)
    except Exception as exc:  # noqa: BLE001
        return JsonResponse(
            {"error": f"Falha ao gerar o PDF: {exc}"}, status=500,
        )
    resp = HttpResponse(data, content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="PreFatura_{pf.numero}.pdf"'
    return resp


# ─── Descontos (DriverClaim) ────────────────────────────────────────

@require_http_methods(["GET"])
@app_token_required
def discounts(request):
    from settlements.models import DriverClaim

    qs = DriverClaim.objects.filter(
        driver=request.driver_profile,
    ).order_by("-occurred_at")
    status = (request.GET.get("status") or "").strip()
    if status:
        qs = qs.filter(status=status)
    items = list(qs)
    counts = {
        "total": len(items),
        "pending": sum(1 for c in items if c.status == "PENDING"),
        "approved": sum(1 for c in items if c.status == "APPROVED"),
        "rejected": sum(1 for c in items if c.status == "REJECTED"),
        "appealed": sum(1 for c in items if c.status == "APPEALED"),
    }
    return JsonResponse({
        "results": [claim_dict(c) for c in items],
        "counts": counts,
    })


# ─── Reclamações (tickets) ──────────────────────────────────────────

@csrf_exempt
@require_http_methods(["GET", "POST"])
@app_token_required
def complaints(request):
    from drivers_app.models import CustomerComplaint
    from drivers_app.views import _complaint_to_dict

    profile = request.driver_profile

    if request.method == "POST":
        data = _json_body(request)
        obrigatorios = [
            "numero_pacote", "tipo", "descricao", "nome_cliente",
            "telefone_cliente", "morada", "codigo_postal", "cidade",
        ]
        em_falta = [f for f in obrigatorios if not (data.get(f) or "").strip()]
        if em_falta:
            return JsonResponse(
                {"success": False,
                 "error": "Campos obrigatórios em falta: " + ", ".join(em_falta)},
                status=400,
            )
        tipos_validos = {c[0] for c in CustomerComplaint.TIPO_CHOICES}
        tipo = data.get("tipo")
        if tipo not in tipos_validos:
            return JsonResponse(
                {"success": False, "error": f"Tipo inválido: {tipo}"},
                status=400,
            )
        try:
            comp = CustomerComplaint.objects.create(
                driver=profile,
                numero_pacote=data["numero_pacote"].strip()[:100],
                tipo=tipo,
                descricao=data["descricao"].strip(),
                nome_cliente=data["nome_cliente"].strip()[:200],
                telefone_cliente=data["telefone_cliente"].strip()[:30],
                email_cliente=(data.get("email_cliente") or "").strip()[:200],
                morada=data["morada"].strip(),
                codigo_postal=data["codigo_postal"].strip()[:20],
                cidade=data["cidade"].strip()[:100],
            )
        except Exception as exc:  # noqa: BLE001
            return JsonResponse(
                {"success": False, "error": f"{type(exc).__name__}: {exc}"},
                status=500,
            )
        return JsonResponse(
            {"success": True, "complaint": _complaint_to_dict(comp)},
            status=201,
        )

    # GET
    qs = CustomerComplaint.objects.filter(
        driver=profile,
    ).order_by("-created_at")
    status = (request.GET.get("status") or "").strip()
    if status:
        qs = qs.filter(status=status)
    return JsonResponse({
        "complaints": [_complaint_to_dict(c) for c in qs],
        "tipo_choices": [
            {"value": v, "label": label}
            for v, label in CustomerComplaint.TIPO_CHOICES
        ],
        "status_choices": [
            {"value": v, "label": label}
            for v, label in CustomerComplaint.STATUS_CHOICES
        ],
    })
