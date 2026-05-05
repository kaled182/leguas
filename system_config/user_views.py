"""Gestão de utilizadores do sistema (CRUD)."""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

User = get_user_model()


def _is_admin(u):
    """Apenas superuser pode gerir utilizadores."""
    return u.is_authenticated and u.is_superuser


admin_required = user_passes_test(_is_admin, login_url="/auth/login/")


def _role_label(user):
    if user.is_superuser:
        return "Admin"
    if user.is_staff:
        return "Operador"
    return "Visualizador"


@admin_required
def user_list(request):
    """Lista todos os utilizadores do sistema."""
    q = request.GET.get("q", "").strip()
    role_filter = request.GET.get("role", "")

    qs = User.objects.all().order_by("-is_superuser", "-is_staff", "username")

    if q:
        qs = qs.filter(
            Q(username__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(email__icontains=q)
        )

    if role_filter == "admin":
        qs = qs.filter(is_superuser=True)
    elif role_filter == "operator":
        qs = qs.filter(is_staff=True, is_superuser=False)
    elif role_filter == "viewer":
        qs = qs.filter(is_staff=False, is_superuser=False)

    users = []
    for u in qs:
        users.append({
            "id": u.id,
            "username": u.username,
            "full_name": u.get_full_name() or "",
            "email": u.email or "",
            "role": _role_label(u),
            "is_superuser": u.is_superuser,
            "is_staff": u.is_staff,
            "is_active": u.is_active,
            "last_login": u.last_login,
            "date_joined": u.date_joined,
        })

    counts = {
        "total": User.objects.count(),
        "admin": User.objects.filter(is_superuser=True).count(),
        "operator": User.objects.filter(is_staff=True, is_superuser=False).count(),
        "viewer": User.objects.filter(is_staff=False, is_superuser=False).count(),
        "inactive": User.objects.filter(is_active=False).count(),
    }

    return render(request, "system_config/users/list.html", {
        "users": users,
        "counts": counts,
        "q": q,
        "role_filter": role_filter,
    })


@admin_required
@require_http_methods(["GET", "POST"])
def user_create(request):
    """Criar novo utilizador."""
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        password_confirm = request.POST.get("password_confirm", "")
        role = request.POST.get("role", "viewer")

        errors = []
        if not username:
            errors.append("O username é obrigatório.")
        elif User.objects.filter(username__iexact=username).exists():
            errors.append(f"Já existe um utilizador com o username '{username}'.")
        if email and User.objects.filter(email__iexact=email).exists():
            errors.append(f"Já existe um utilizador com o email '{email}'.")
        if not password:
            errors.append("A password é obrigatória.")
        elif len(password) < 6:
            errors.append("A password deve ter pelo menos 6 caracteres.")
        elif password != password_confirm:
            errors.append("As passwords não coincidem.")

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, "system_config/users/form.html", {
                "user_obj": None, "form_data": request.POST,
                "is_create": True,
            })

        u = User(
            username=username, first_name=first_name,
            last_name=last_name, email=email,
        )
        u.set_password(password)
        if role == "admin":
            u.is_superuser = True
            u.is_staff = True
        elif role == "operator":
            u.is_staff = True
        u.save()
        messages.success(request, f"Utilizador '{u.username}' criado.")
        return redirect("system_config:user_list")

    return render(request, "system_config/users/form.html", {
        "user_obj": None, "is_create": True,
    })


@admin_required
@require_http_methods(["GET", "POST"])
def user_edit(request, pk):
    """Editar utilizador existente (sem mexer na password)."""
    u = get_object_or_404(User, pk=pk)

    if request.method == "POST":
        u.first_name = request.POST.get("first_name", "").strip()
        u.last_name = request.POST.get("last_name", "").strip()
        new_email = request.POST.get("email", "").strip()
        if new_email != u.email:
            if new_email and User.objects.filter(email__iexact=new_email).exclude(id=u.id).exists():
                messages.error(request, f"Já existe outro utilizador com o email '{new_email}'.")
                return render(request, "system_config/users/form.html", {
                    "user_obj": u, "form_data": request.POST, "is_create": False,
                })
            u.email = new_email

        # Role — não permitir auto-rebaixamento do último admin
        role = request.POST.get("role", "viewer")
        was_admin = u.is_superuser
        if role == "admin":
            u.is_superuser = True
            u.is_staff = True
        elif role == "operator":
            u.is_superuser = False
            u.is_staff = True
        else:
            u.is_superuser = False
            u.is_staff = False

        # Validação: não pode ficar sem nenhum admin
        if was_admin and not u.is_superuser:
            other_admins = User.objects.filter(is_superuser=True).exclude(id=u.id).count()
            if other_admins == 0:
                messages.error(request, "Não pode rebaixar o último administrador do sistema.")
                u.is_superuser = True
                u.is_staff = True

        u.save()
        messages.success(request, f"Utilizador '{u.username}' actualizado.")
        return redirect("system_config:user_list")

    return render(request, "system_config/users/form.html", {
        "user_obj": u, "is_create": False,
    })


@admin_required
@require_http_methods(["POST"])
def user_delete(request, pk):
    """Eliminar utilizador (não pode auto-eliminar nem eliminar último admin)."""
    u = get_object_or_404(User, pk=pk)
    if u.id == request.user.id:
        messages.error(request, "Não pode eliminar a sua própria conta.")
        return redirect("system_config:user_list")
    if u.is_superuser and User.objects.filter(is_superuser=True).count() <= 1:
        messages.error(request, "Não pode eliminar o último administrador.")
        return redirect("system_config:user_list")
    username = u.username
    u.delete()
    messages.success(request, f"Utilizador '{username}' eliminado.")
    return redirect("system_config:user_list")


@admin_required
@require_http_methods(["POST"])
def user_toggle_active(request, pk):
    """Ativa/desativa utilizador."""
    u = get_object_or_404(User, pk=pk)
    if u.id == request.user.id:
        return JsonResponse({"success": False, "error": "Não pode desativar a sua própria conta."}, status=400)
    if u.is_active and u.is_superuser and User.objects.filter(is_superuser=True, is_active=True).count() <= 1:
        return JsonResponse({"success": False, "error": "Não pode desativar o último admin activo."}, status=400)
    u.is_active = not u.is_active
    u.save(update_fields=["is_active"])
    return JsonResponse({"success": True, "is_active": u.is_active})


@admin_required
@require_http_methods(["POST"])
def user_reset_password(request, pk):
    """Define nova password para o utilizador."""
    u = get_object_or_404(User, pk=pk)
    new_password = request.POST.get("password", "")
    if not new_password or len(new_password) < 6:
        messages.error(request, "A nova password deve ter pelo menos 6 caracteres.")
        return redirect("system_config:user_list")
    u.set_password(new_password)
    u.save()
    messages.success(request, f"Password do utilizador '{u.username}' actualizada.")
    return redirect("system_config:user_list")
