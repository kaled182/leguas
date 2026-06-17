"""Login dedicado para motoristas (DriverAccess) + criação de credenciais."""
import re
import secrets
import string
from datetime import timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from customauth.models import DriverAccess, DriverLoginOTP
from drivers_app.models import DriverProfile


# ─── Decorators de sessão de driver ─────────────────────────────────

def driver_login_required(view_func):
    """Decorator: requer sessão de driver autenticado."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.session.get("is_driver_authenticated"):
            access_id = request.session.get("driver_access_id")
            try:
                access = DriverAccess.objects.select_related("driver_profile").get(
                    id=access_id, is_active=True,
                )
                request.driver_access = access
                request.driver_profile = access.driver_profile
                return view_func(request, *args, **kwargs)
            except DriverAccess.DoesNotExist:
                pass
        # Fallback: admin loggado pode ver
        if request.user.is_authenticated and (
            request.user.is_staff or request.user.is_superuser
        ):
            request.driver_access = None
            request.driver_profile = None
            return view_func(request, *args, **kwargs)
        return redirect("customauth:driver_login")
    return wrapper


# ─── Login / Logout ─────────────────────────────────────────────────

@require_http_methods(["GET", "POST"])
def driver_login(request):
    """Login para motorista usando DriverAccess."""
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        if not username or not password:
            messages.error(request, "Username e password são obrigatórios.")
            return render(request, "customauth/driver_login.html")

        # Busca por username OU email
        access = DriverAccess.objects.filter(
            username__iexact=username, is_active=True,
        ).first()
        if not access:
            access = DriverAccess.objects.filter(
                email__iexact=username, is_active=True,
            ).first()

        if not access or not access.check_password(password):
            messages.error(request, "Credenciais inválidas.")
            return render(request, "customauth/driver_login.html")

        if not access.driver_profile:
            messages.error(request, "Conta sem perfil de motorista associado. Contacta o administrador.")
            return render(request, "customauth/driver_login.html")

        # Login OK
        access.last_login = timezone.now()
        access.save(update_fields=["last_login"])
        request.session["is_driver_authenticated"] = True
        request.session["driver_access_id"] = access.id
        request.session["driver_profile_id"] = access.driver_profile.id
        request.session["driver_name"] = access.full_name

        messages.success(request, f"Bem-vindo, {access.first_name}!")
        return redirect("drivers_app:driver_portal", driver_id=access.driver_profile.id)

    return render(request, "customauth/driver_login.html")


def driver_logout(request):
    """Logout do motorista."""
    for k in ("is_driver_authenticated", "driver_access_id", "driver_profile_id", "driver_name"):
        request.session.pop(k, None)
    messages.success(request, "Sessão terminada.")
    return redirect("customauth:driver_login")


# ─── Login por telemóvel + código WhatsApp (OTP) ────────────────────

def _normalize_phone(raw):
    """Mantém apenas os dígitos do número."""
    return re.sub(r"\D", "", raw or "")


def _mask_phone(phone):
    """Mascara o número para mostrar ao motorista (ex: ••• ••• 678)."""
    d = _normalize_phone(phone)
    if len(d) <= 3:
        return "•••"
    return "••• ••• " + d[-3:]


def _resolve_driver_by_phone(raw_phone):
    """Encontra um DriverProfile pelo telefone, robusto a +351/formatação:
    compara pelos últimos 9 dígitos (telemóvel PT).

    Devolve (profile, erro). profile=None quando há erro.
    """
    digits = _normalize_phone(raw_phone)
    if len(digits) < 9:
        return None, "Número de telemóvel inválido."
    tail = digits[-9:]
    candidatos = DriverProfile.objects.filter(telefone__endswith=tail)
    matches = [
        p for p in candidatos
        if _normalize_phone(p.telefone).endswith(tail)
    ]
    if not matches:
        return None, "Não encontrámos nenhum motorista com este número."
    if len(matches) > 1:
        exatos = [p for p in matches if _normalize_phone(p.telefone) == digits]
        if len(exatos) == 1:
            return exatos[0], None
        return None, (
            "Vários motoristas com este número. Usa username e password."
        )
    return matches[0], None


@require_http_methods(["POST"])
def driver_login_send_code(request):
    """Gera um código OTP e envia-o por WhatsApp para o telemóvel do
    motorista. Resposta JSON (AJAX)."""
    raw_phone = (request.POST.get("phone") or "").strip()
    profile, erro = _resolve_driver_by_phone(raw_phone)
    if erro:
        return JsonResponse({"success": False, "error": erro}, status=400)

    if not (profile.telefone or "").strip():
        return JsonResponse(
            {"success": False, "error": "Motorista sem telefone registado."},
            status=400,
        )

    # Anti-spam: no máximo 1 código por 60s
    recente = DriverLoginOTP.objects.filter(
        driver_profile=profile,
        created_at__gte=timezone.now() - timedelta(seconds=60),
    ).exists()
    if recente:
        return JsonResponse(
            {"success": False,
             "error": "Já enviámos um código há instantes. Aguarda um pouco."},
            status=429,
        )

    # invalida códigos anteriores ainda não usados (garante 1 ativo)
    DriverLoginOTP.objects.filter(
        driver_profile=profile, used_at__isnull=True,
    ).update(used_at=timezone.now())

    code = DriverLoginOTP.generate_code()
    otp = DriverLoginOTP.objects.create(
        driver_profile=profile,
        phone=profile.telefone,
        code=code,
        expires_at=timezone.now() + timedelta(minutes=5),
    )

    try:
        from system_config.whatsapp_helper import WhatsAppWPPConnectAPI
        api = WhatsAppWPPConnectAPI.from_config()
        nome = (profile.nome_completo or profile.apelido or "").split(" ")[0]
        saudacao = f"Olá {nome}! " if nome else "Olá! "
        msg = (
            f"{saudacao}O teu código de acesso ao Portal do Motorista é:\n\n"
            f"*{code}*\n\n"
            f"Válido por 5 minutos. Não partilhes este código com ninguém."
        )
        api.send_text(profile.telefone, msg)
    except Exception as exc:  # noqa: BLE001 — erro amigável
        otp.delete()
        return JsonResponse(
            {"success": False,
             "error": f"Não foi possível enviar o código por WhatsApp: {exc}"},
            status=502,
        )

    return JsonResponse({"success": True, "masked_phone": _mask_phone(profile.telefone)})


@require_http_methods(["POST"])
def driver_login_verify_code(request):
    """Valida o código OTP e inicia a sessão do motorista. JSON (AJAX)."""
    raw_phone = (request.POST.get("phone") or "").strip()
    code = (request.POST.get("code") or "").strip()
    profile, erro = _resolve_driver_by_phone(raw_phone)
    if erro:
        return JsonResponse({"success": False, "error": erro}, status=400)
    if not code:
        return JsonResponse(
            {"success": False, "error": "Indica o código recebido."},
            status=400,
        )

    otp = DriverLoginOTP.objects.filter(
        driver_profile=profile, used_at__isnull=True,
    ).order_by("-created_at").first()
    if not otp or otp.is_expired:
        return JsonResponse(
            {"success": False, "error": "Código expirado. Pede um novo."},
            status=400,
        )
    if otp.attempts >= DriverLoginOTP.MAX_ATTEMPTS:
        return JsonResponse(
            {"success": False,
             "error": "Demasiadas tentativas. Pede um novo código."},
            status=429,
        )

    if otp.code != code:
        otp.attempts += 1
        otp.save(update_fields=["attempts"])
        restantes = max(0, DriverLoginOTP.MAX_ATTEMPTS - otp.attempts)
        return JsonResponse(
            {"success": False,
             "error": f"Código incorreto. {restantes} tentativa(s) restante(s)."},
            status=400,
        )

    # Código válido → inicia sessão
    otp.used_at = timezone.now()
    otp.save(update_fields=["used_at"])

    request.session["is_driver_authenticated"] = True
    request.session["driver_profile_id"] = profile.id
    request.session["driver_name"] = (
        profile.nome_completo or profile.apelido or "Motorista"
    )
    access = DriverAccess.objects.filter(
        driver_profile=profile, is_active=True,
    ).first()
    if access:
        request.session["driver_access_id"] = access.id
        access.last_login = timezone.now()
        access.save(update_fields=["last_login"])

    redirect_url = reverse(
        "drivers_app:driver_portal", kwargs={"driver_id": profile.id},
    )
    return JsonResponse({"success": True, "redirect": redirect_url})


# ─── Admin: gerir credenciais de driver ─────────────────────────────

def _is_admin(u):
    return u.is_authenticated and (u.is_staff or u.is_superuser)

admin_required = user_passes_test(_is_admin, login_url="/auth/login/")


def _generate_password(length=10):
    """Gera password aleatória legível."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


@admin_required
def admin_driver_credentials(request, driver_id):
    """Página admin: criar/regenerar credenciais para um driver."""
    driver = get_object_or_404(DriverProfile, pk=driver_id)
    access = DriverAccess.objects.filter(driver_profile=driver).first()

    if request.method == "POST":
        action = request.POST.get("action", "")

        if action == "create" and not access:
            username = request.POST.get("username", "").strip()
            email = request.POST.get("email", "").strip()
            password = request.POST.get("password", "").strip() or _generate_password()

            errors = []
            if not username:
                errors.append("Username é obrigatório.")
            elif DriverAccess.objects.filter(username__iexact=username).exists():
                errors.append(f"Username '{username}' já existe.")
            if email and DriverAccess.objects.filter(email__iexact=email).exists():
                errors.append(f"Email '{email}' já existe.")

            if errors:
                for e in errors:
                    messages.error(request, e)
            else:
                access = DriverAccess(
                    user=request.user,
                    driver_profile=driver,
                    username=username,
                    first_name=(driver.nome_completo or driver.apelido or "").split(" ")[0][:100],
                    last_name=" ".join((driver.nome_completo or driver.apelido or "").split(" ")[1:])[:100] or "",
                    phone=driver.telefone or "",
                    nif=driver.nif or "",
                    email=email or driver.email or f"{username}@leguas.local",
                )
                access.set_password(password)
                access.save()
                messages.success(request, f"Credenciais criadas. Username: {username}, Password: {password}")

        elif action == "regenerate" and access:
            new_password = _generate_password()
            access.set_password(new_password)
            access.save(update_fields=["password", "updated_at"])
            messages.success(request, f"Nova password: {new_password}")

        elif action == "toggle_active" and access:
            access.is_active = not access.is_active
            access.save(update_fields=["is_active", "updated_at"])
            messages.success(request, f"Conta {'activada' if access.is_active else 'desactivada'}.")

        elif action == "delete" and access:
            access.delete()
            messages.success(request, "Acesso eliminado.")
            return redirect("drivers_app:driver_portal", driver_id=driver.id)

        return redirect("customauth:admin_driver_credentials", driver_id=driver.id)

    return render(request, "customauth/admin_driver_credentials.html", {
        "driver": driver,
        "access": access,
    })
