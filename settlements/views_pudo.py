"""Endpoints para gestão de PUDO — Suspeitas de Fake Delivery.

A "Fake Delivery" é um pacote PUDO marcado como Delivered onde a
distância haversine entre `receiver_*` e `actual_*` excede a tolerância
configurada no parceiro (`pudo_geo_tolerance_meters`). O operador
revê cada suspeita e confirma para gerar o desconto na pré-fatura.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_http_methods

from core.models import Partner
from drivers_app.models import DriverProfile

from .models import CainiaoOperationTask, DriverClaim
from .services_pudo import find_fake_delivery_suspects


def _resolve_driver_for_task(task):
    """Resolve DriverProfile a partir de courier_id ou courier_name."""
    if task.courier_id_cainiao:
        d = DriverProfile.objects.filter(
            courier_id_cainiao=task.courier_id_cainiao,
        ).first()
        if d:
            return d
    if task.courier_name:
        d = DriverProfile.objects.filter(
            apelido__iexact=task.courier_name.strip(),
        ).first()
        if d:
            return d
        d = DriverProfile.objects.filter(
            nome_completo__iexact=task.courier_name.strip(),
        ).first()
        if d:
            return d
    return None


@login_required
def fake_delivery_suspects(request):
    """Lista suspeitas de Fake Delivery (PUDO) para revisão."""
    partner = Partner.objects.filter(name__iexact="CAINIAO").first()

    today = timezone.localdate()
    default_from = today - timedelta(days=30)

    df = parse_date(request.GET.get("date_from", "") or "") or default_from
    dt = parse_date(request.GET.get("date_to", "") or "") or today

    suspects = []
    if partner and getattr(partner, "pudo_enabled", False):
        suspects = find_fake_delivery_suspects(df, dt, partner)
        # Adicionar driver resolvido a cada suspeita
        for s in suspects:
            s["driver"] = _resolve_driver_for_task(s["task"])

    context = {
        "partner": partner,
        "pudo_enabled": bool(partner and partner.pudo_enabled),
        "tolerance_m": (
            partner.pudo_geo_tolerance_meters
            if partner else 200
        ),
        "penalty": (
            partner.pudo_fake_delivery_penalty
            if partner else Decimal("1.30")
        ),
        "date_from": df,
        "date_to": dt,
        "suspects": suspects,
        "n_total": len(suspects),
        "n_pending": sum(
            1 for s in suspects if not s.get("existing_claim_id")
        ),
    }
    return render(
        request, "settlements/pudo_fake_delivery_suspects.html", context,
    )


@login_required
@require_http_methods(["POST"])
def confirm_fake_delivery(request, task_id):
    """Confirma um Fake Delivery e cria DriverClaim com a penalty.

    Idempotente: se já existir DriverClaim FAKE_DELIVERY para a mesma
    waybill, não cria outro.
    """
    task = get_object_or_404(CainiaoOperationTask, id=task_id)
    partner = Partner.objects.filter(name__iexact="CAINIAO").first()

    if not partner or not getattr(partner, "pudo_enabled", False):
        messages.error(request, "PUDO não está activo no parceiro CAINIAO.")
        return redirect("pudo-fake-delivery-suspects")

    driver = _resolve_driver_for_task(task)
    if not driver:
        messages.error(
            request,
            f"Não foi possível resolver o motorista para "
            f"courier='{task.courier_name}' "
            f"(courier_id={task.courier_id_cainiao}).",
        )
        return redirect("pudo-fake-delivery-suspects")

    existing = DriverClaim.objects.filter(
        waybill_number=task.waybill_number,
        claim_type="FAKE_DELIVERY",
    ).first()
    if existing:
        messages.warning(
            request,
            f"Já existe Fake Delivery #{existing.id} "
            f"para waybill {task.waybill_number}.",
        )
        return redirect("pudo-fake-delivery-suspects")

    distance_m = None
    try:
        from .services_pudo import haversine_meters
        d = haversine_meters(
            task.receiver_latitude, task.receiver_longitude,
            task.actual_latitude, task.actual_longitude,
        )
        if d is not None:
            distance_m = int(d)
    except Exception:
        pass

    description = (
        f"Fake Delivery PUDO — entrega a {distance_m}m do destino "
        f"(tolerância {partner.pudo_geo_tolerance_meters}m).\n"
        f"Waybill: {task.waybill_number}\n"
        f"Data: {task.task_date}\n"
        f"Endereço destino: {task.detailed_address}\n"
        f"Receiver coords: ({task.receiver_latitude}, "
        f"{task.receiver_longitude})\n"
        f"Actual coords: ({task.actual_latitude}, "
        f"{task.actual_longitude})"
    )

    claim = DriverClaim.objects.create(
        driver=driver,
        claim_type="FAKE_DELIVERY",
        amount=partner.pudo_fake_delivery_penalty,
        description=description,
        occurred_at=task.delivery_time or timezone.now(),
        waybill_number=task.waybill_number,
        operation_task_date=task.task_date,
        status="PENDING",
        created_by=request.user,
        auto_detected=False,
    )
    messages.success(
        request,
        f"Fake Delivery confirmado — Reclamação #{claim.id} "
        f"criada para {driver.nome_completo} "
        f"(€{partner.pudo_fake_delivery_penalty}).",
    )
    return redirect("pudo-fake-delivery-suspects")
