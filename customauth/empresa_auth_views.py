"""Login dedicado para EmpresaParceira (frota) + admin de credenciais."""
import secrets
import string
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from customauth.models import EmpresaAccess
from drivers_app.models import EmpresaParceira


# ─── Decorator de sessão da empresa ─────────────────────────────────
def empresa_login_required(view_func):
    """Decorator: aceita admin OU sessão de empresa autenticada.

    Quando o utilizador é admin, o request continua normalmente.
    Quando é sessão de empresa, expõe `request.empresa_access` e
    `request.empresa` e bloqueia acesso a empresas que não a sua.
    """
    @wraps(view_func)
    def wrapper(request, empresa_id=None, *args, **kwargs):
        # 1. Sessão de empresa
        if request.session.get("is_empresa_authenticated"):
            access_id = request.session.get("empresa_access_id")
            try:
                access = EmpresaAccess.objects.select_related("empresa").get(
                    id=access_id, is_active=True,
                )
                request.empresa_access = access
                request.empresa = access.empresa
                # Bloqueia acesso cruzado entre empresas
                if empresa_id is not None and int(empresa_id) != access.empresa.id:
                    return redirect(
                        "empresa-portal-dashboard", empresa_id=access.empresa.id,
                    )
                return view_func(request, empresa_id=empresa_id, *args, **kwargs)
            except EmpresaAccess.DoesNotExist:
                pass
        # 2. Admin Django
        if request.user.is_authenticated and (
            request.user.is_staff or request.user.is_superuser
        ):
            request.empresa_access = None
            request.empresa = None
            return view_func(request, empresa_id=empresa_id, *args, **kwargs)
        # 3. Sem sessão → login
        return redirect("customauth:empresa_login")
    return wrapper


# ─── Login / Logout ─────────────────────────────────────────────────
@require_http_methods(["GET", "POST"])
def empresa_login(request):
    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""
        if not username or not password:
            messages.error(request, "Username e password obrigatórios.")
            return render(request, "customauth/empresa_login.html")

        access = EmpresaAccess.objects.filter(
            username__iexact=username, is_active=True,
        ).select_related("empresa").first()
        if not access:
            access = EmpresaAccess.objects.filter(
                email__iexact=username, is_active=True,
            ).select_related("empresa").first()
        if not access or not access.check_password(password):
            messages.error(request, "Credenciais inválidas.")
            return render(request, "customauth/empresa_login.html")

        access.last_login = timezone.now()
        access.save(update_fields=["last_login"])
        request.session["is_empresa_authenticated"] = True
        request.session["empresa_access_id"] = access.id
        request.session["empresa_id"] = access.empresa.id
        request.session["empresa_nome"] = access.empresa.nome

        messages.success(request, f"Bem-vindo, {access.empresa.nome}!")
        return redirect("empresa-portal-dashboard", empresa_id=access.empresa.id)

    return render(request, "customauth/empresa_login.html")


def empresa_logout(request):
    for k in (
        "is_empresa_authenticated", "empresa_access_id",
        "empresa_id", "empresa_nome",
    ):
        request.session.pop(k, None)
    messages.success(request, "Sessão terminada.")
    return redirect("customauth:empresa_login")


# ─── Admin: gerir credenciais de empresa ────────────────────────────
def _is_admin(u):
    return u.is_authenticated and (u.is_staff or u.is_superuser)


def _gen_password(length=12):
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


@user_passes_test(_is_admin)
@require_http_methods(["GET", "POST"])
def admin_empresa_credentials(request, empresa_id):
    """Admin gere/cria credenciais para uma empresa parceira."""
    empresa = get_object_or_404(EmpresaParceira, id=empresa_id)
    access = EmpresaAccess.objects.filter(empresa=empresa).first()
    new_password = None

    if request.method == "POST":
        action = request.POST.get("action") or ""
        if action == "create":
            username = (request.POST.get("username") or "").strip().lower()
            email = (request.POST.get("email") or empresa.email or "").strip()
            if not username:
                messages.error(request, "Username obrigatório.")
            elif EmpresaAccess.objects.filter(username__iexact=username).exists():
                messages.error(request, "Username já existe.")
            else:
                pw = _gen_password()
                access = EmpresaAccess.objects.create(
                    empresa=empresa, username=username,
                    email=email, is_active=True,
                    created_by=request.user,
                )
                access.set_password(pw)
                access.save()
                new_password = pw
                messages.success(request, f"Credenciais criadas. Username: {username}")
        elif action == "reset_password" and access:
            pw = _gen_password()
            access.set_password(pw)
            access.save(update_fields=["password", "updated_at"])
            new_password = pw
            messages.success(request, "Password redefinida.")
        elif action == "toggle_active" and access:
            access.is_active = not access.is_active
            access.save(update_fields=["is_active", "updated_at"])
            messages.success(
                request,
                "Acesso reactivado." if access.is_active else "Acesso desactivado.",
            )
        elif action == "delete" and access:
            access.delete()
            access = None
            messages.success(request, "Credenciais removidas.")

    return render(request, "customauth/admin_empresa_credentials.html", {
        "empresa": empresa,
        "access": access,
        "new_password": new_password,
    })