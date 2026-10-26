"""Ficha do motorista (admin): cada bloco aparece só para leitura e tem
o seu botão Editar → Guardar / Cancelar. Grava só os campos desse bloco
e regista quem mudou o quê."""
from datetime import timedelta

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import (
    DriverHubAssignment, DriverPaymentRegimeChange, DriverProfile,
    DriverProfileEditLog,
)
from .services_hubs import (
    contract_completeness, driver_hub_suggestions, hub_options,
    is_placeholder_email, is_placeholder_phone,
)


def _is_admin(u):
    return u.is_authenticated and (u.is_staff or u.is_superuser)


admin_required = user_passes_test(_is_admin, login_url="/auth/login/")

# (chave, título, ícone, campos)
SECTIONS = [
    ("identificacao", "Identificação", "user-circle", [
        "nome_completo", "apelido", "courier_id_cainiao", "nif", "niss",
        "data_nascimento", "nacionalidade",
    ]),
    ("contacto", "Contacto", "phone", [
        "telefone", "email", "endereco_residencia", "codigo_postal", "cidade",
    ]),
    ("documentos", "Documentos e seguros", "id-card", [
        "provider_type", "company_rep_name", "company_rep_nif",
        "id_doc_type", "id_doc_number", "id_doc_expiry",
        "driving_license_number", "driving_license_country", "driving_license_expiry",
        "insurance_work_policy", "insurance_auto_policy",
    ]),
    ("vinculo", "Vínculo", "briefcase", [
        "tipo_vinculo", "empresa_parceira", "nome_frota",
    ]),
    ("financeiro", "Financeiro e regime", "wallet", [
        "payment_regime", "payment_regime_since", "iban",
        "price_per_package", "advance_monthly_limit", "daily_capacity",
        "bonus_performance_enabled", "vat_regime", "irs_retention_pct",
    ]),
    ("estado", "Estado do cadastro", "shield-check", [
        "status", "is_active", "observacoes",
    ]),
]
SECTION_FIELDS = {k: f for k, _t, _i, f in SECTIONS}

INPUT_CSS = (
    "w-full px-3 py-2 text-sm bg-gray-50 dark:bg-gray-700 border border-gray-300 "
    "dark:border-gray-600 rounded-lg text-gray-900 dark:text-white"
)
DATE_FIELDS = {"data_nascimento", "id_doc_expiry", "driving_license_expiry", "payment_regime_since"}
MONO_FIELDS = {"nif", "niss", "courier_id_cainiao", "iban", "company_rep_nif", "telefone"}


def _section_form(section, data=None, instance=None):
    fields = SECTION_FIELDS[section]
    widgets = {}
    for f in fields:
        if f in DATE_FIELDS:
            widgets[f] = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
        elif f == "observacoes":
            widgets[f] = forms.Textarea(attrs={"rows": 3})
    Form = forms.modelform_factory(DriverProfile, fields=fields, widgets=widgets)
    form = Form(data=data, instance=instance, prefix=section)
    for name, field in form.fields.items():
        if isinstance(field.widget, forms.CheckboxInput):
            field.widget.attrs["class"] = "w-4 h-4 rounded"
            continue
        css = INPUT_CSS + (" font-mono" if name in MONO_FIELDS else "")
        field.widget.attrs["class"] = css
    if "empresa_parceira" in form.fields:
        from .models import EmpresaParceira
        form.fields["empresa_parceira"].queryset = EmpresaParceira.objects.filter(
            ativo=True,
        ).order_by("nome")
        form.fields["empresa_parceira"].empty_label = "— Independente —"
    return form


def _display(driver, name):
    """Valor legível de um campo para o modo leitura."""
    field = DriverProfile._meta.get_field(name)
    value = getattr(driver, name)
    if field.choices and value not in (None, ""):
        return getattr(driver, f"get_{name}_display")()
    if isinstance(value, bool):
        return "Sim" if value else "Não"
    if value in (None, ""):
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%d/%m/%Y")
    return str(value)


def _next_cycle_start(regime, today):
    """Mudança de regime vale no ciclo seguinte: semanal → próxima
    segunda; mensal → dia 1 do mês seguinte."""
    if regime == "SEMANAL":
        return today + timedelta(days=7 - today.weekday())
    first_next = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
    return first_next


def _save_hubs(request, driver):
    """Grava hubs/CP a partir do POST do bloco 'hubs'."""
    from settlements.models import CainiaoHub

    primary = request.POST.get("primary_hub", "")
    keep = set()
    before = {a.hub_id: (sorted(a.cp4s), a.is_primary) for a in driver.hub_assignments.all()}
    for hub in CainiaoHub.objects.all():
        cps = sorted(set(request.POST.getlist(f"cp_{hub.id}")))
        if not cps and request.POST.get(f"hub_{hub.id}") != "on":
            continue
        keep.add(hub.id)
        DriverHubAssignment.objects.update_or_create(
            driver=driver, hub=hub,
            defaults={"cp4s": cps, "is_primary": str(hub.id) == primary},
        )
    driver.hub_assignments.exclude(hub_id__in=keep).delete()
    if keep and not driver.hub_assignments.filter(is_primary=True).exists():
        first = driver.hub_assignments.order_by("hub__name").first()
        first.is_primary = True
        first.save(update_fields=["is_primary"])
    after = {a.hub_id: (sorted(a.cp4s), a.is_primary) for a in driver.hub_assignments.all()}
    if before != after:
        names = dict(CainiaoHub.objects.values_list("id", "name"))
        fmt = lambda d: "; ".join(  # noqa: E731
            f"{names.get(h, h)}{' (principal)' if p else ''}: {','.join(c) or '—'}"
            for h, (c, p) in sorted(d.items())
        )
        DriverProfileEditLog.objects.create(
            driver=driver, user=request.user, section="hubs",
            changes={"hubs": [fmt(before), fmt(after)]},
        )
    return before != after


@admin_required
@require_http_methods(["GET", "POST"])
def driver_ficha(request, driver_id):
    driver = get_object_or_404(
        DriverProfile.objects.select_related("empresa_parceira"), pk=driver_id,
    )
    error_section = None
    bound = {}

    if request.method == "POST":
        section = request.POST.get("section", "")
        if section == "hubs":
            with transaction.atomic():
                changed = _save_hubs(request, driver)
            messages.success(request, "Hubs e CP guardados." if changed else "Sem alterações.")
            return redirect(f"{request.path}#hubs")

        if section in SECTION_FIELDS:
            old_vat = driver.vat_regime
            old_regime = driver.payment_regime
            form = _section_form(section, data=request.POST, instance=driver)
            if form.is_valid():
                # is_valid() já alterou `driver`: os valores antigos vêm da BD.
                before = DriverProfile.objects.get(pk=driver.pk)
                changes = {name: [_display(before, name), None] for name in form.changed_data}
                with transaction.atomic():
                    obj = form.save(commit=False)
                    if "payment_regime" in form.changed_data:
                        today = timezone.localdate()
                        if (not obj.payment_regime_since
                                or "payment_regime_since" not in form.changed_data):
                            obj.payment_regime_since = (
                                _next_cycle_start(obj.payment_regime, today)
                                if old_regime else today
                            )
                        DriverPaymentRegimeChange.objects.create(
                            driver=obj, old_regime=old_regime,
                            new_regime=obj.payment_regime,
                            effective_from=obj.payment_regime_since,
                            changed_by=request.user,
                        )
                    obj.save()
                    for name in changes:
                        changes[name][1] = _display(obj, name)
                    if changes:
                        DriverProfileEditLog.objects.create(
                            driver=obj, user=request.user, section=section,
                            changes=changes,
                        )
                if changes:
                    messages.success(request, f"Guardado: {len(changes)} campo(s) alterado(s).")
                else:
                    messages.info(request, "Sem alterações.")
                if old_vat != obj.vat_regime:
                    _recalc_open_pfs(request, obj)
                return redirect(f"{request.path}#{section}")
            error_section = section
            bound[section] = form
            messages.error(request, "Há campos inválidos. Corrija e guarde de novo.")

    sections = []
    for key, title, icon, fields in SECTIONS:
        form = bound.get(key) or _section_form(key, instance=driver)
        rows = []
        for name in fields:
            value = _display(driver, name)
            flag = ""
            if name == "telefone" and is_placeholder_phone(driver.telefone):
                flag = "dado de importação"
            elif name == "email" and is_placeholder_email(driver.email):
                flag = "dado de importação"
            rows.append({
                "name": name,
                "label": DriverProfile._meta.get_field(name).verbose_name,
                "value": value,
                "flag": flag,
                "bound": form[name],
                "wide": name in ("endereco_residencia", "observacoes", "nome_completo"),
            })
        sections.append({
            "key": key, "title": title, "icon": icon, "rows": rows,
            "form": form, "editing": key == error_section,
        })

    pct, missing = contract_completeness(driver)
    assignments = {a.hub_id: a for a in driver.hub_assignments.select_related("hub")}
    options = hub_options()
    for opt in options:
        a = assignments.get(opt["hub"].id)
        opt["assigned"] = a is not None
        opt["primary"] = bool(a and a.is_primary)
        selected = set(a.cp4s) if a else set()
        for cp in opt["cps"]:
            cp["checked"] = cp["cp4"] in selected
    suggestions = driver_hub_suggestions(driver)

    from contracts.models import GeneratedContract

    return render(request, "drivers_app/portal/admin_ficha.html", {
        "driver": driver,
        "sections": sections,
        "completeness_pct": pct,
        "completeness_missing": missing,
        "hub_options": options,
        "assignments": list(assignments.values()),
        "suggestions": suggestions,
        "regime_changes": driver.regime_changes.select_related("changed_by")[:10],
        "edit_logs": driver.edit_logs.select_related("user")[:15],
        "contracts": GeneratedContract.objects.filter(driver=driver)[:10],
        "documents_contract": driver.documents.filter(tipo_documento="CONTRATO"),
    })


def _recalc_open_pfs(request, driver):
    """vat_regime mudou: recalcula PF em CALCULADO (como na edição antiga)."""
    from settlements.models import DriverPreInvoice

    n = 0
    for pf in DriverPreInvoice.objects.filter(driver=driver, status="CALCULADO"):
        pf.recalcular()
        pf.save()
        n += 1
    if n:
        messages.info(
            request,
            f"Recalculadas {n} pré-fatura(s) em CALCULADO com o novo regime de IVA "
            f"({driver.get_vat_regime_display()}).",
        )
