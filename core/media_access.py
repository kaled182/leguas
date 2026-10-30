"""Autorização de ficheiros em /media/.

O Caddy chama media_auth antes de servir cada ficheiro (forward_auth).
Regras em docs/seguranca/media-privada.md.
"""
import posixpath
from urllib.parse import quote, unquote, urlsplit

from django.apps import apps
from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.core.files.storage import default_storage
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.http import HttpResponse

from .permissions import is_gestao

SIGNED_URL_MAX_AGE = 24 * 60 * 60
PUBLIC_PREFIXES = ("company/", "system_config/logos/")
OPERATOR_PREFIXES = (
    "driver_documents/", "vehicle_documents/", "complaints/", "ticket_imports/",
    "incidences/", "ocr_attempts/", "drivers/profile_pictures/", "contracts/",
)
# (pasta, modelo, campo do ficheiro, filtro do dono)
DRIVER_FILES = (
    ("driver_documents/", "drivers_app.DriverDocument", "arquivo", "motorista_id"),
    ("vehicle_documents/", "drivers_app.VehicleDocument", "arquivo", "veiculo__motorista_id"),
    ("complaints/", "drivers_app.CustomerComplaintAttachment", "ficheiro", "complaint__driver_id"),
    ("claims/evidence/", "settlements.DriverClaim", "evidence_file", "driver_id"),
    ("pre_invoices/comprovativos/", "settlements.DriverPreInvoice", "comprovante_pagamento", "driver_id"),
    ("pre_invoices/faturas/", "settlements.DriverPreInvoice", "fatura_ficheiro", "driver_id"),
    ("settlements/pdfs/", "settlements.DriverSettlement", "pdf_file", "driver_id"),
    ("contracts/signed/", "contracts.DriverContract", "pdf_file", "driver_id"),
    ("contracts/generated/", "contracts.GeneratedContract", "signed_file", "driver_id"),
)
COMPANY_FILES = (
    ("fleet_documents/", "settlements.FleetDocument", "file", "empresa_id"),
    ("fleet_contracts/", "settlements.FleetContract", "file", "empresa_id"),
    ("fleet_invoices/", "settlements.FleetInvoiceAttachment", "file", "fleet_invoice__empresa_id"),
    ("empresa_lancamentos/comprovativos/", "drivers_app.EmpresaParceiraLancamento", "comprovante_pagamento", "empresa_id"),
)

signer = TimestampSigner(salt="core.media")


def signed_media_url(name):
    """URL temporário para a app do motorista, que não envia sessão."""
    signature = signer.sign(name)[len(name) + 1:]
    return f"{default_storage.url(name)}?sig={quote(signature)}"


def has_valid_signature(name, signature):
    try:
        signer.unsign(f"{name}:{signature}", max_age=SIGNED_URL_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return False
    return True


def owns_file(name, rules, owner_id):
    for prefix, label, field, owner in rules:
        if name.startswith(prefix):
            model = apps.get_model(label)
            if model.objects.filter(**{field: name, owner: owner_id}).exists():
                return True
    return False


def company_id(request):
    from customauth.models import EmpresaAccess

    return (
        EmpresaAccess.objects.filter(
            id=request.session.get("empresa_access_id"), is_active=True,
        )
        .values_list("empresa_id", flat=True)
        .first()
    )


def can_read(request, name):
    if name.startswith(PUBLIC_PREFIXES):
        return True
    user = request.user
    if is_gestao(user):
        return True
    if user.is_authenticated and user.is_staff and name.startswith(OPERATOR_PREFIXES):
        return True
    if request.session.get("is_driver_authenticated"):
        driver_id = request.session.get("driver_profile_id")
        if owns_file(name, DRIVER_FILES, driver_id):
            return True
    if request.session.get("is_empresa_authenticated"):
        if owns_file(name, COMPANY_FILES, company_id(request)):
            return True
    return False


def media_name(uri):
    parts = urlsplit(uri)
    path = unquote(parts.path)
    if not path.startswith("/media/"):
        return None, parts
    name = posixpath.normpath(path[len("/media/"):])
    if name.startswith(("..", "/")) or name == ".":
        return None, parts
    return name, parts


def media_auth(request):
    uri = request.META.get("HTTP_X_FORWARDED_URI", "")
    name, parts = media_name(uri)
    if name is None:
        return HttpResponse(status=403)
    if not settings.PERMISSIONS_ENFORCE or can_read(request, name):
        return HttpResponse(status=204)
    query = dict(p.split("=", 1) for p in parts.query.split("&") if "=" in p)
    if "sig" in query and has_valid_signature(name, unquote(query["sig"])):
        return HttpResponse(status=204)
    if not request.user.is_authenticated and not request.session.get(
        "is_driver_authenticated"
    ) and not request.session.get("is_empresa_authenticated"):
        return redirect_to_login(uri)
    return HttpResponse(status=403)
