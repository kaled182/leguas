"""Gerador de contrato único / aditivo a partir da ficha do motorista.

Fluxo: gerar (pré-visualização + PDF pelo browser) → registar
(snapshot + hash, estado GERADO) → enviado → assinado (anexo do PDF
assinado) ou anulado.
"""
import json

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from drivers_app.models import DriverProfile
from drivers_app.services_hubs import is_placeholder_phone

from .models import ContractSettings, GeneratedContract


def _is_admin(u):
    return u.is_authenticated and (u.is_staff or u.is_superuser)


admin_required = user_passes_test(_is_admin, login_url="/auth/login/")


def _ficha_url(driver_id):
    return reverse("drivers_app:driver_admin_edit", args=[driver_id]) + "#contrato"


def _hub_payload(driver):
    from drivers_app.services_hubs import driver_cp_selection, hub_options

    options = hub_options()
    chosen, negotiated = driver_cp_selection(driver)
    shown = {opt["hub"].id for opt in options}
    primary = next(
        (a.hub_id for a in driver.hub_assignments.all() if a.is_primary and a.hub_id in shown),
        None,
    )
    hubs = []
    for opt in options:
        hub, terms = opt["hub"], opt["terms"]
        if primary is None and chosen & {cp["cp4"] for cp in opt["cps"]}:
            primary = hub.id
        hubs.append({
            "id": hub.id,
            "name": hub.name,
            "address": hub.address,
            "has_terms": terms is not None,
            "signing_place": terms.signing_place if terms else "",
            "allows_monthly": terms.allows_monthly if terms else True,
            "allows_weekly": terms.allows_weekly if terms else False,
            "monthly_mode": terms.monthly_payment_mode if terms else "DAYS_AFTER_CLOSE",
            "monthly_value": terms.monthly_payment_value if terms else 30,
            "monthly_text": terms.monthly_payment_text() if terms else "",
            "weekly_payday": terms.weekly_payday if terms else 1,
            "weekly_lag_weeks": terms.weekly_lag_weeks if terms else 4,
            "min_fare": terms.min_fare_enabled if terms else False,
            "cps": [_cp_payload(cp, chosen, negotiated) for cp in opt["cps"]],
        })
    return hubs, primary


def _cp_payload(cp, chosen, negotiated):
    """Linha do Anexo I: valor negociado (só CP selecionados) substitui a
    tarifa padrão nas duas colunas."""
    neg = negotiated.get(cp["cp4"]) if cp["cp4"] in chosen else None
    p = cp["price_monthly"]
    s = cp["price_weekly"]
    if neg:
        p = s = neg
    return {
        "cp": cp["cp4"], "z": cp["zone"], "esc": cp["tier"],
        "p": float(p) if p is not None else None,
        "s": float(s) if s is not None else None,
        "neg": bool(neg),
        "checked": cp["cp4"] in chosen and p is not None,
    }


@admin_required
def contract_generator(request, driver_id):
    driver = get_object_or_404(DriverProfile, pk=driver_id)
    kind = request.GET.get("kind", "CONTRATO")
    if kind not in ("CONTRATO", "ADITIVO"):
        kind = "CONTRATO"
    settings = ContractSettings.get()
    hubs, primary = _hub_payload(driver)
    primary_hub = next((h for h in hubs if h["id"] == primary), hubs[0] if hubs else None)
    plates = ", ".join(
        v.matricula for v in driver.vehicles.filter(is_active=True) if v.matricula
    ) if hasattr(driver, "vehicles") else ""
    regime = driver.payment_regime or (
        "MENSAL" if not primary_hub or primary_hub["allows_monthly"] else "SEMANAL"
    )
    gen = {
        "kind": kind,
        "logo": request.build_absolute_uri(static("contracts/logo-leguas.png")),
        "hubs": hubs,
        "primary_hub_id": primary,
        "driver": {"regime": driver.payment_regime},
    }
    return render(request, "contracts/generator.html", {
        "driver": driver,
        "kind": kind,
        "settings": settings,
        "gen": gen,
        "regime": regime,
        "plates": plates,
        "signing_place": (primary_hub or {}).get("signing_place") or "Esposende",
        "primary_hub_id": primary,
        "hubs": hubs,
        "min_fare_default": any(h["min_fare"] for h in hubs if h["id"] == primary),
        "today": timezone.localdate(),
        "ficha_url": _ficha_url(driver.id),
        "tel": "" if is_placeholder_phone(driver.telefone) else driver.telefone,
        "morada": ", ".join(
            x for x in [driver.endereco_residencia, " ".join(
                y for y in [driver.codigo_postal, driver.cidade] if y)] if x
        ),
        "id_doc_choices": DriverProfile.ID_DOC_CHOICES,
    })


@admin_required
@require_POST
def contract_generator_save(request, driver_id):
    driver = get_object_or_404(DriverProfile, pk=driver_id)
    kind = request.POST.get("kind", "CONTRATO")
    html = request.POST.get("html", "")
    try:
        hubs = json.loads(request.POST.get("hubs") or "[]")
        params = json.loads(request.POST.get("params") or "{}")
    except ValueError:
        messages.error(request, "Dados do contrato inválidos. Gere de novo.")
        return redirect(_ficha_url(driver.id))
    if kind not in ("CONTRATO", "ADITIVO") or not html:
        messages.error(request, "Contrato vazio. Gere de novo.")
        return redirect(_ficha_url(driver.id))
    dorig = params.get("dorig") or None
    c = GeneratedContract.objects.create(
        driver=driver, kind=kind, regime=request.POST.get("regime", "")[:10],
        hubs=hubs, params=params, content_snapshot=html,
        original_contract_date=dorig if kind == "ADITIVO" else None,
        generated_by=request.user,
    )
    messages.success(
        request,
        f"{c.get_kind_display()} registado (n.º {c.id}). Imprima, assine e anexe o PDF assinado.",
    )
    return redirect(_ficha_url(driver.id))


@admin_required
def generated_contract_view(request, pk):
    c = get_object_or_404(GeneratedContract.objects.select_related("driver"), pk=pk)
    return render(request, "contracts/generated_view.html", {
        "c": c, "ficha_url": _ficha_url(c.driver_id),
    })


@admin_required
@require_POST
def generated_contract_action(request, pk):
    c = get_object_or_404(GeneratedContract, pk=pk)
    action = request.POST.get("action", "")
    now = timezone.now()
    if action == "sent" and c.status == "GERADO":
        c.status, c.sent_at = "ENVIADO", now
        c.save(update_fields=["status", "sent_at"])
        messages.success(request, "Marcado como enviado ao motorista.")
    elif action == "signed" and c.status in ("GERADO", "ENVIADO"):
        f = request.FILES.get("signed_file")
        if not f:
            messages.error(request, "Anexe o PDF ou a imagem do contrato assinado.")
        else:
            c.status, c.signed_at, c.signed_file = "ASSINADO", now, f
            c.save(update_fields=["status", "signed_at", "signed_file"])
            messages.success(request, "Contrato assinado registado.")
    elif action == "cancel" and c.status != "ANULADO":
        c.status = "ANULADO"
        c.notes = (c.notes + f"\nAnulado por {request.user.username} em {now:%d/%m/%Y %H:%M}").strip()
        c.save(update_fields=["status", "notes"])
        messages.success(request, "Contrato anulado.")
    else:
        messages.error(request, "Acção não permitida neste estado.")
    return redirect(_ficha_url(c.driver_id))
