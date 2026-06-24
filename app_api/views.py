"""Endpoints da API da app do motorista (/api/app/v1/).

Auth por token Bearer (ver auth.py). Respostas JSON limpas. POST sem CSRF
(autenticação por token, não por cookie de sessão).
"""
import json
import re
import unicodedata

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
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
    driver_option_dict,
    driver_dict,
    incidence_dict,
    pre_invoice_detail,
    pre_invoice_summary,
)


def _json_body(request):
    try:
        return json.loads(request.body or b"{}")
    except (ValueError, TypeError):
        return {}


def _linked_admin_user(profile):
    access = getattr(profile, "access", None)
    user = getattr(access, "user", None)
    if user and user.is_active and (user.is_staff or user.is_superuser):
        return user
    return None


def _can_use_admin_features(profile):
    return _linked_admin_user(profile) is not None


def _parse_float(value, default=0.0):
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_json_payload(value, default=None):
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:  # noqa: BLE001
            return default
    return default


def _resolve_target_driver_profile(request, assigned_driver_id):
    from drivers_app.models import DriverProfile

    if not assigned_driver_id:
        return request.driver_profile

    if not _can_use_admin_features(request.driver_profile):
        return None

    try:
        return DriverProfile.objects.filter(id=int(assigned_driver_id), is_active=True).first()
    except (TypeError, ValueError):
        return None


def _normalize_for_learning(text):
    if not text:
        return ""
    text = str(text).lower().strip()
    text = "".join(
        char for char in unicodedata.normalize("NFD", text)
        if unicodedata.category(char) != "Mn"
    )
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = " ".join(text.split())
    return text


def _save_ocr_learning(field_name, original_value, corrected_value, was_confirmed, incidence=None):
    from .models import OcrCorrectionLearning

    if not original_value or not corrected_value:
        return

    normalized_original = _normalize_for_learning(original_value)
    normalized_corrected = _normalize_for_learning(corrected_value)

    learning, created = OcrCorrectionLearning.objects.get_or_create(
        field_name=field_name,
        normalized_original=normalized_original,
        defaults={
            "original_value": str(original_value),
            "corrected_value": str(corrected_value),
            "normalized_corrected": normalized_corrected,
            "score": 0.7 if was_confirmed else 0.5,
            "incidence": incidence,
        },
    )

    if not created:
        learning.original_value = str(original_value)
        learning.corrected_value = str(corrected_value)
        learning.normalized_corrected = normalized_corrected
        learning.update_score(was_confirmed=was_confirmed)
        if incidence:
            learning.incidence = incidence
    learning.save()


def _resolve_zone_name(query):
    from geozonas.services.triagem import resolver_triagem

    q = (query or "").strip()
    if not q:
        return ""

    try:
        triage = resolver_triagem(q)
        zone = (triage or {}).get("zona") or {}
        return (zone.get("nome") or "").strip()
    except Exception:  # noqa: BLE001
        return ""


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


# ─── Triagem / separação por zona ───────────────────────────────────

@require_http_methods(["GET"])
@app_token_required
def sorting(request):
    """Triagem: dado um CP (4990-008) ou uma etiqueta/waybill em `q`,
    devolve a zona de entrega (nome+cor) e a localização, para o motorista
    separar os pacotes por zona na própria app. Reusa o serviço do Modo
    Triagem do geozonas."""
    from geozonas.services.triagem import resolver_triagem

    if not _can_use_admin_features(request.driver_profile):
        return JsonResponse(
            {"ok": False, "error": "Apenas utilizadores admin podem usar a triagem."},
            status=403,
        )

    q = (request.GET.get("q") or "").strip()
    if not q:
        return JsonResponse(
            {"ok": False, "error": "Indica um CP ou waybill (parâmetro q)."},
            status=400,
        )
    return JsonResponse(resolver_triagem(q))


# ─── Incidences ─────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
@app_token_required
def incidences_add(request):
    from .models import IncidencePacket

    assigned_driver_id = request.POST.get("assigned_user_id")
    target_profile = _resolve_target_driver_profile(request, assigned_driver_id)
    if target_profile is None:
        return JsonResponse(
            {"success": False, "message": "Utilizador de atribuicao invalido."},
            status=400,
        )

    barcode = (request.POST.get("barcode") or request.POST.get("qr_code") or "").strip()
    if not barcode:
        return JsonResponse(
            {"success": False, "message": "Codigo de barras e obrigatorio."},
            status=400,
        )

    if IncidencePacket.objects.filter(barcode=barcode).exists():
        return JsonResponse(
            {
                "success": False,
                "status": "duplicate",
                "message": "Pacote ja foi registrado",
                "data": {"qr_code": barcode},
            },
            status=200,
        )

    parsed_ocr = _parse_json_payload(request.POST.get("ocr_data"), default={})
    zone_query = (
        request.POST.get("postal_code")
        or (parsed_ocr or {}).get("postal_code")
        or request.POST.get("tracking_number")
        or barcode
    )

    incidence = IncidencePacket.objects.create(
        driver_profile=target_profile,
        barcode=barcode,
        tracking_number=(request.POST.get("tracking_number") or barcode).strip(),
        client_name=(request.POST.get("client_name") or "").strip() or "Sem nome",
        address=(request.POST.get("address") or "").strip() or "Sem endereco",
        latitude=_parse_float(request.POST.get("latitude"), default=0.0),
        longitude=_parse_float(request.POST.get("longitude"), default=0.0),
        package_image=request.FILES.get("package_image"),
        ocr_data=parsed_ocr,
        zone=_resolve_zone_name(zone_query),
    )

    return JsonResponse(
        {
            "success": True,
            "message": "Incidencia registrada com sucesso!",
            "data": incidence_dict(incidence),
        },
        status=201,
    )


@require_http_methods(["GET"])
@app_token_required
def incidences_history(request):
    from .models import IncidencePacket

    is_admin = _can_use_admin_features(request.driver_profile)
    if is_admin:
        qs = IncidencePacket.objects.select_related("driver_profile", "driver_profile__access").all()
    else:
        qs = IncidencePacket.objects.select_related("driver_profile", "driver_profile__access").filter(
            driver_profile=request.driver_profile,
        )

    exact_date = (request.GET.get("date") or "").strip()
    if exact_date:
        qs = qs.filter(scanned_at__date=exact_date)

    start_date = (request.GET.get("start_date") or "").strip()
    if start_date:
        qs = qs.filter(scanned_at__gte=start_date)

    end_date = (request.GET.get("end_date") or "").strip()
    if end_date:
        qs = qs.filter(scanned_at__lte=end_date)

    if is_admin:
        user_id = (request.GET.get("user_id") or "").strip()
        if user_id.isdigit():
            qs = qs.filter(driver_profile_id=int(user_id))

        user_ids = (request.GET.get("user_ids") or "").strip()
        if user_ids:
            parsed_ids = [int(v.strip()) for v in user_ids.split(",") if v.strip().isdigit()]
            if parsed_ids:
                qs = qs.filter(driver_profile_id__in=parsed_ids)

        username = (request.GET.get("username") or "").strip()
        if username:
            qs = qs.filter(driver_profile__access__username=username)

        usernames = (request.GET.get("usernames") or "").strip()
        if usernames:
            parsed_usernames = [v.strip() for v in usernames.split(",") if v.strip()]
            if parsed_usernames:
                qs = qs.filter(driver_profile__access__username__in=parsed_usernames)

    qs = qs.order_by("-scanned_at")
    data = [incidence_dict(item) for item in qs]
    return JsonResponse(
        {
            "success": True,
            "message": "Incidencias recuperadas com sucesso",
            "data": data,
            "count": len(data),
        },
    )


@require_http_methods(["GET"])
@app_token_required
def incidences_drivers(request):
    from drivers_app.models import DriverProfile

    if _can_use_admin_features(request.driver_profile):
        qs = DriverProfile.objects.filter(is_active=True).select_related("access").order_by("nome_completo")
    else:
        qs = DriverProfile.objects.filter(id=request.driver_profile.id).select_related("access")

    data = [driver_option_dict(profile) for profile in qs]
    return JsonResponse({"success": True, "data": data, "count": len(data)})


@csrf_exempt
@require_http_methods(["POST"])
@app_token_required
def incidences_process_scan(request):
    from .models import IncidencePacket, OcrScanAttempt

    qr_code = (request.POST.get("qr_code") or "").strip()
    package_image = request.FILES.get("package_image")
    if not qr_code:
        return JsonResponse(
            {"success": False, "status": "error", "message": "QR Code nao foi enviado"},
            status=400,
        )
    if not package_image:
        return JsonResponse(
            {"success": False, "status": "error", "message": "Imagem nao foi enviada"},
            status=400,
        )

    if IncidencePacket.objects.filter(barcode=qr_code).exists():
        return JsonResponse(
            {
                "success": False,
                "status": "duplicate",
                "message": "Pacote ja foi registrado",
                "data": {"qr_code": qr_code},
            },
            status=200,
        )

    temp_path = default_storage.save(f"temp/{timezone.now().strftime('%Y%m%d_%H%M%S')}_{package_image.name}", package_image)
    local_raw_text = request.POST.get("local_ocr_raw_text", "")
    local_blocks = _parse_json_payload(request.POST.get("local_ocr_blocks"), default=[])

    recipient_name = (request.POST.get("local_candidate_recipient_name") or "").strip()
    address = (request.POST.get("local_candidate_address") or "").strip()
    city = (request.POST.get("local_candidate_city") or "").strip()
    state = (request.POST.get("local_candidate_state") or "").strip()
    country = (request.POST.get("local_candidate_country") or "").strip()
    postal_code = (request.POST.get("local_candidate_postal_code") or "").strip()

    confidence = {
        "qr_code": 1.0,
        "package_code": 1.0,
        "recipient_name": 0.65 if recipient_name else 0.0,
        "address": 0.65 if address else 0.0,
        "city": 0.6 if city else 0.0,
        "state": 0.58 if state else 0.0,
        "country": 0.7 if country else 0.0,
        "postal_code": 0.62 if postal_code else 0.0,
    }

    fields_requiring_review = []
    for field_name in ["recipient_name", "address", "postal_code"]:
        if not locals().get(field_name) or confidence[field_name] < 0.75:
            fields_requiring_review.append(field_name)

    response_data = {
        "qr_code": qr_code,
        "package_code": qr_code,
        "operation_code": None,
        "recipient_name": recipient_name or None,
        "address": address or None,
        "city": city or None,
        "state": state or None,
        "country": country or None,
        "postal_code": postal_code or None,
        "image_url": request.build_absolute_uri(default_storage.url(temp_path)),
        "image_path": temp_path,
        "confidence": confidence,
        "fields_requiring_review": fields_requiring_review,
        "local_ocr": {
            "raw_text": local_raw_text,
            "blocks": local_blocks,
            "candidate_recipient_name": recipient_name,
            "candidate_address": address,
            "candidate_city": city,
            "candidate_state": state,
            "candidate_country": country,
            "candidate_postal_code": postal_code,
        },
        "zone": _resolve_zone_name(postal_code or qr_code),
    }

    scan_attempt = OcrScanAttempt.objects.create(
        driver_profile=request.driver_profile,
        qr_code=qr_code,
        image=package_image,
        local_raw_text=local_raw_text,
        server_raw_text="",
        detected_data={"local_blocks": local_blocks},
        confidence=confidence,
    )
    response_data["scan_id"] = scan_attempt.id

    if not recipient_name and not address:
        return JsonResponse(
            {
                "success": False,
                "status": "unreadable",
                "message": "Nao foi possivel ler as informacoes da etiqueta",
                "data": response_data,
            },
            status=200,
        )

    status_name = "review_required"
    if not recipient_name or not address:
        status_name = "missing_fields"

    return JsonResponse(
        {
            "success": True,
            "status": status_name,
            "message": "Confira as informacoes detectadas",
            "data": response_data,
        },
        status=200,
    )


@csrf_exempt
@require_http_methods(["POST"])
@app_token_required
def incidences_complete(request):
    from .models import IncidencePacket

    data = _json_body(request)
    qr_code = (data.get("qr_code") or "").strip()
    recipient_name = (data.get("recipient_name") or "").strip()
    address = (data.get("address") or "").strip()
    image_path = (data.get("image_path") or "").strip()

    if not qr_code:
        return JsonResponse(
            {"success": False, "status": "validation_error", "message": "QR Code e obrigatorio"},
            status=400,
        )
    if not recipient_name:
        return JsonResponse(
            {"success": False, "status": "validation_error", "message": "Nome do destinatario e obrigatorio"},
            status=400,
        )
    if not address:
        return JsonResponse(
            {"success": False, "status": "validation_error", "message": "Endereco e obrigatorio"},
            status=400,
        )

    if IncidencePacket.objects.filter(barcode=qr_code).exists():
        return JsonResponse(
            {
                "success": False,
                "status": "duplicate",
                "message": "Pacote ja foi registrado",
                "data": {"qr_code": qr_code},
            },
            status=200,
        )

    assigned_driver_id = data.get("assigned_user_id")
    target_profile = _resolve_target_driver_profile(request, assigned_driver_id)
    if target_profile is None:
        return JsonResponse(
            {"success": False, "status": "validation_error", "message": "Utilizador de atribuicao invalido"},
            status=400,
        )

    image_field = None
    if image_path and default_storage.exists(image_path):
        with default_storage.open(image_path, "rb") as temp_file:
            file_content = ContentFile(temp_file.read())
            image_field = default_storage.save(
                f"incidences/{qr_code}_{target_profile.id}.jpg",
                file_content,
            )
        default_storage.delete(image_path)

    zone_query = data.get("postal_code") or qr_code

    incidence = IncidencePacket.objects.create(
        driver_profile=target_profile,
        barcode=qr_code,
        tracking_number=qr_code,
        client_name=recipient_name,
        address=address,
        latitude=_parse_float(data.get("latitude"), default=0.0),
        longitude=_parse_float(data.get("longitude"), default=0.0),
        package_image=image_field,
        ocr_data={
            "qr_code": qr_code,
            "package_code": qr_code,
            "operation_code": data.get("operation_code"),
            "recipient_name": recipient_name,
            "address": address,
            "city": data.get("city"),
            "state": data.get("state"),
            "country": data.get("country"),
            "postal_code": data.get("postal_code"),
            "manual_completion": True,
        },
        zone=_resolve_zone_name(zone_query),
    )

    return JsonResponse(
        {
            "success": True,
            "status": "completed",
            "message": "Incidencia registrada com sucesso",
            "data": incidence_dict(incidence),
        },
        status=201,
    )


@csrf_exempt
@require_http_methods(["POST"])
@app_token_required
def incidences_confirm_ocr(request):
    from .models import IncidencePacket, OcrScanAttempt

    data = _json_body(request)
    qr_code = (data.get("qr_code") or "").strip()
    ocr_detected = data.get("ocr_detected") or {}
    user_confirmed = data.get("user_confirmed") or {}
    scan_id = data.get("scan_id")
    image_path = (data.get("image_path") or "").strip()

    if not qr_code:
        return JsonResponse(
            {"success": False, "status": "validation_error", "message": "QR Code e obrigatorio"},
            status=400,
        )
    if not isinstance(user_confirmed, dict) or not user_confirmed:
        return JsonResponse(
            {"success": False, "status": "validation_error", "message": "Dados confirmados sao obrigatorios"},
            status=400,
        )

    if IncidencePacket.objects.filter(barcode=qr_code).exists():
        return JsonResponse(
            {"success": False, "status": "duplicate", "message": "Pacote ja foi registrado"},
            status=200,
        )

    assigned_driver_id = data.get("assigned_user_id")
    target_profile = _resolve_target_driver_profile(request, assigned_driver_id)
    if target_profile is None:
        return JsonResponse(
            {"success": False, "status": "validation_error", "message": "Utilizador de atribuicao invalido"},
            status=400,
        )

    image_field = None
    if image_path and default_storage.exists(image_path):
        with default_storage.open(image_path, "rb") as temp_file:
            file_content = ContentFile(temp_file.read())
            image_field = default_storage.save(
                f"incidences/{qr_code}_{target_profile.id}.jpg",
                file_content,
            )
        default_storage.delete(image_path)

    zone_query = (user_confirmed or {}).get("postal_code") or qr_code

    incidence = IncidencePacket.objects.create(
        driver_profile=target_profile,
        barcode=qr_code,
        tracking_number=qr_code,
        client_name=str(user_confirmed.get("recipient_name") or "").strip() or "Sem nome",
        address=str(user_confirmed.get("address") or "").strip() or "Sem endereco",
        latitude=_parse_float(data.get("latitude"), default=0.0),
        longitude=_parse_float(data.get("longitude"), default=0.0),
        package_image=image_field,
        ocr_data={
            "qr_code": qr_code,
            "package_code": qr_code,
            "ocr_detected": ocr_detected,
            "user_confirmed": user_confirmed,
            "ocr_learning": True,
        },
        zone=_resolve_zone_name(zone_query),
    )

    fields_to_learn = [
        "recipient_name",
        "address",
        "package_code",
        "operation_code",
        "city",
        "state",
        "country",
        "postal_code",
    ]
    learning_summary = []
    for field_name in fields_to_learn:
        ocr_value = (ocr_detected or {}).get(field_name)
        user_value = (user_confirmed or {}).get(field_name)
        if not ocr_value or not user_value:
            continue
        same_value = _normalize_for_learning(ocr_value) == _normalize_for_learning(user_value)
        _save_ocr_learning(
            field_name=field_name,
            original_value=ocr_value,
            corrected_value=user_value,
            was_confirmed=same_value,
            incidence=incidence,
        )
        if same_value:
            learning_summary.append(f"{field_name}: confirmado")
        else:
            learning_summary.append(f"{field_name}: corrigido")

    if scan_id:
        try:
            attempt = OcrScanAttempt.objects.filter(
                id=int(scan_id),
                driver_profile=request.driver_profile,
            ).first()
            if attempt:
                attempt.confirmed_data = user_confirmed
                attempt.was_edited = any("corrigido" in item for item in learning_summary)
                attempt.save(update_fields=["confirmed_data", "was_edited"])
        except (TypeError, ValueError):
            pass

    return JsonResponse(
        {
            "success": True,
            "status": "completed",
            "message": "Incidencia registrada com sucesso",
            "data": incidence_dict(incidence),
            "learning_summary": learning_summary,
        },
        status=201,
    )

