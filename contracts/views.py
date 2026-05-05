"""Views: portal driver (visualizar/assinar) + admin (gestão templates)."""
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from drivers_app.models import DriverProfile

from .models import ContractTemplate, DriverContract


# ─── Helpers ────────────────────────────────────────────────────────

def _get_client_ip(request):
    """Extrai IP do request (considerando reverse proxy)."""
    fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _is_admin(u):
    return u.is_authenticated and (u.is_staff or u.is_superuser)


admin_required = user_passes_test(_is_admin, login_url="/auth/login/")


def portal_access_required(view_func):
    """Acesso ao portal: admin OU driver autenticado a ver o seu próprio."""
    @wraps(view_func)
    def wrapper(request, driver_id, *args, **kwargs):
        if request.user.is_authenticated and (
            request.user.is_staff or request.user.is_superuser
        ):
            return view_func(request, driver_id, *args, **kwargs)
        if request.session.get("is_driver_authenticated"):
            session_pid = request.session.get("driver_profile_id")
            if session_pid and int(session_pid) == int(driver_id):
                return view_func(request, driver_id, *args, **kwargs)
            messages.warning(request, "Só podes aceder aos teus próprios contratos.")
            return redirect("drivers_app:driver_portal", driver_id=session_pid)
        return redirect("customauth:driver_login")
    return wrapper


def _applicable_templates_for_driver(driver):
    """Templates activos aplicáveis a este driver (por scope)."""
    scope_filter = Q(scope="all")
    if driver.empresa_parceira:
        scope_filter |= Q(scope="fleet")
    else:
        scope_filter |= Q(scope="independent")

    qs = ContractTemplate.objects.filter(is_active=True).filter(scope_filter)
    today = timezone.now().date()
    qs = qs.filter(effective_from__lte=today).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gte=today)
    )
    return qs


# ─── Driver Portal: Contratos ───────────────────────────────────────

@portal_access_required
def driver_contracts(request, driver_id):
    """Lista de contratos do driver — assinados + pendentes."""
    driver = get_object_or_404(DriverProfile, pk=driver_id)

    # Contratos assinados (não revogados)
    signed = (
        DriverContract.objects
        .filter(driver=driver, revoked_at__isnull=True)
        .select_related("template")
        .order_by("-signed_at")
    )
    signed_template_ids = set(signed.values_list("template_id", flat=True))

    # Templates aplicáveis ainda não assinados
    pending = []
    for tmpl in _applicable_templates_for_driver(driver):
        if tmpl.id not in signed_template_ids:
            pending.append(tmpl)

    return render(request, "contracts/driver_contracts.html", {
        "driver": driver,
        "signed": signed,
        "pending": pending,
    })


@portal_access_required
@require_http_methods(["GET", "POST"])
def driver_contract_sign(request, driver_id, template_id):
    """Página de assinatura: mostra contrato + aceitar/recusar."""
    driver = get_object_or_404(DriverProfile, pk=driver_id)
    template = get_object_or_404(
        ContractTemplate, pk=template_id, is_active=True,
    )

    # Já assinou?
    existing = DriverContract.objects.filter(
        driver=driver, template=template, revoked_at__isnull=True,
    ).first()
    if existing:
        messages.info(request, "Este contrato já foi assinado.")
        return redirect("contracts:driver_contracts", driver_id=driver.id)

    # Verifica scope
    if template not in _applicable_templates_for_driver(driver):
        messages.error(request, "Este contrato não se aplica a ti.")
        return redirect("contracts:driver_contracts", driver_id=driver.id)

    if request.method == "POST":
        agreed = request.POST.get("agreed") == "yes"
        if not agreed:
            messages.error(request, "Tens de marcar a caixa de aceitação para assinar.")
            return redirect("contracts:driver_contract_sign",
                            driver_id=driver.id, template_id=template.id)

        contract = DriverContract.objects.create(
            driver=driver,
            template=template,
            content_snapshot=template.content,
            ip_address=_get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:1000],
            signature_text=request.POST.get(
                "signature_text", "Li e aceito os termos.",
            )[:200],
        )
        messages.success(
            request,
            f"Contrato '{template.name}' assinado com sucesso.",
        )
        return redirect("contracts:driver_contract_view",
                        driver_id=driver.id, contract_id=contract.id)

    return render(request, "contracts/driver_contract_sign.html", {
        "driver": driver,
        "template": template,
    })


@portal_access_required
def driver_contract_view(request, driver_id, contract_id):
    """Ver contrato já assinado."""
    driver = get_object_or_404(DriverProfile, pk=driver_id)
    contract = get_object_or_404(
        DriverContract, pk=contract_id, driver=driver,
    )
    return render(request, "contracts/driver_contract_view.html", {
        "driver": driver,
        "contract": contract,
    })


# ─── Admin: Gestão de Templates ─────────────────────────────────────

@admin_required
def admin_templates_list(request):
    """Lista templates com filtros."""
    qs = ContractTemplate.objects.all().order_by("-is_active", "name", "-version")
    counts = {
        "total": ContractTemplate.objects.count(),
        "active": ContractTemplate.objects.filter(is_active=True).count(),
        "inactive": ContractTemplate.objects.filter(is_active=False).count(),
    }
    # Total assinaturas por template
    sig_counts = {
        s["template_id"]: s["c"]
        for s in DriverContract.objects
            .filter(revoked_at__isnull=True)
            .values("template_id").annotate(c=Count("id"))
    }
    rows = []
    for t in qs:
        rows.append({"t": t, "signed_count": sig_counts.get(t.id, 0)})

    return render(request, "contracts/admin_templates_list.html", {
        "rows": rows,
        "counts": counts,
    })


@admin_required
@require_http_methods(["GET", "POST"])
def admin_template_create(request):
    """Criar novo template."""
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        version = request.POST.get("version", "").strip() or "1.0"
        scope = request.POST.get("scope", "all")
        content = request.POST.get("content", "").strip()
        effective_from = request.POST.get("effective_from", "")
        expires_at = request.POST.get("expires_at", "") or None

        if not name or not content:
            messages.error(request, "Nome e conteúdo são obrigatórios.")
        else:
            t = ContractTemplate(
                name=name, version=version, scope=scope, content=content,
                created_by=request.user,
            )
            if effective_from:
                t.effective_from = effective_from
            if expires_at:
                t.expires_at = expires_at
            t.save()
            messages.success(request, f"Template '{t}' criado.")
            return redirect("contracts:admin_templates_list")

    return render(request, "contracts/admin_template_form.html", {
        "template": None,
        "is_create": True,
    })


@admin_required
@require_http_methods(["GET", "POST"])
def admin_template_edit(request, pk):
    """Editar template existente. Atenção: só nome/versão/scope/datas — conteúdo
    NÃO se altera depois de assinaturas existirem."""
    t = get_object_or_404(ContractTemplate, pk=pk)
    has_signatures = DriverContract.objects.filter(template=t).exists()

    if request.method == "POST":
        t.name = request.POST.get("name", "").strip() or t.name
        t.version = request.POST.get("version", "").strip() or t.version
        t.scope = request.POST.get("scope", t.scope)
        if not has_signatures:
            t.content = request.POST.get("content", t.content)
        ef = request.POST.get("effective_from", "")
        if ef:
            t.effective_from = ef
        ex = request.POST.get("expires_at", "")
        t.expires_at = ex or None
        t.is_active = request.POST.get("is_active") == "on"
        t.save()
        messages.success(request, f"Template '{t}' actualizado.")
        return redirect("contracts:admin_templates_list")

    return render(request, "contracts/admin_template_form.html", {
        "template": t,
        "is_create": False,
        "has_signatures": has_signatures,
    })


@admin_required
def admin_signed_contracts(request):
    """Lista todos os contratos assinados."""
    qs = DriverContract.objects.select_related(
        "driver", "template",
    ).order_by("-signed_at")

    template_id = request.GET.get("template")
    if template_id:
        qs = qs.filter(template_id=template_id)

    show_revoked = request.GET.get("revoked") == "1"
    if not show_revoked:
        qs = qs.filter(revoked_at__isnull=True)

    return render(request, "contracts/admin_signed_list.html", {
        "contracts": qs[:300],
        "templates": ContractTemplate.objects.all(),
        "selected_template_id": int(template_id) if template_id else None,
        "show_revoked": show_revoked,
    })


@admin_required
def admin_missing_contracts(request):
    """Drivers que não têm o(s) contrato(s) aplicáveis."""
    today = timezone.now().date()
    active_templates = ContractTemplate.objects.filter(is_active=True).filter(
        effective_from__lte=today,
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gte=today)
    )

    drivers = DriverProfile.objects.all()
    rows = []
    for d in drivers:
        applicable = []
        for t in active_templates:
            if t.scope == "all":
                applicable.append(t)
            elif t.scope == "fleet" and d.empresa_parceira:
                applicable.append(t)
            elif t.scope == "independent" and not d.empresa_parceira:
                applicable.append(t)

        signed_ids = set(
            DriverContract.objects.filter(
                driver=d, revoked_at__isnull=True,
            ).values_list("template_id", flat=True)
        )
        missing = [t for t in applicable if t.id not in signed_ids]
        if missing:
            rows.append({
                "driver": d,
                "missing": missing,
                "applicable_count": len(applicable),
                "missing_count": len(missing),
            })

    rows.sort(key=lambda r: -r["missing_count"])

    return render(request, "contracts/admin_missing_list.html", {
        "rows": rows,
        "total_drivers": drivers.count(),
        "drivers_missing": len(rows),
        "active_templates_count": active_templates.count(),
    })


@admin_required
@require_http_methods(["POST"])
def admin_revoke_contract(request, pk):
    """Revogar um contrato assinado (não apaga, marca como revogado)."""
    contract = get_object_or_404(DriverContract, pk=pk, revoked_at__isnull=True)
    reason = request.POST.get("reason", "").strip() or "Revogado pelo administrador."
    contract.revoked_at = timezone.now()
    contract.revoked_by = request.user
    contract.revoked_reason = reason
    contract.save()
    messages.success(request, "Contrato revogado.")
    return redirect("contracts:admin_signed_contracts")
