"""Transferência de um login (DriverCourierMapping) entre motoristas.

Move o login + os dados ATRIBUÍVEIS a esse courier_id (reclamações, claims,
entregas Cainiao) para o motorista destino, mantendo o motorista de origem.

Atribuição: waybill → CainiaoOperationTask.courier_id_cainiao == courier_id.
Só se move o que resolve com certeza para o courier_id; o resto fica na
origem. NÃO toca em pré-faturas (documentos financeiros já calculados).
As CainiaoOperationTask não têm FK ao driver — resolvem-se pelo login, por
isso seguem automaticamente ao reatribuir o DriverCourierMapping.
"""
from __future__ import annotations

import logging

from django.db import transaction

log = logging.getLogger(__name__)


def _courier_waybills(courier_id):
    """Conjunto de waybills atribuídos a este courier_id (via tarefas Cainiao)."""
    from settlements.models import CainiaoOperationTask

    if not courier_id:
        return set()
    return set(
        CainiaoOperationTask.objects
        .filter(courier_id_cainiao=courier_id)
        .exclude(waybill_number="")
        .values_list("waybill_number", flat=True)
    )


def preview_login_transfer(mapping, target):
    """Conta o que seria transferido — sem alterar nada."""
    from drivers_app.models import CustomerComplaint
    from settlements.models import CainiaoDelivery, DriverClaim

    source = mapping.driver
    waybills = _courier_waybills(mapping.courier_id)

    if waybills:
        complaints = CustomerComplaint.objects.filter(
            driver=source, numero_pacote__in=waybills
        ).count()
        claims = DriverClaim.objects.filter(
            driver=source, waybill_number__in=waybills
        ).count()
    else:
        complaints = claims = 0

    deliveries = CainiaoDelivery.objects.filter(
        driver=source, courier_id=mapping.courier_id
    ).count()

    return {
        "waybills": len(waybills),
        "complaints": complaints,
        "claims": claims,
        "deliveries": deliveries,
    }


@transaction.atomic
def transfer_login(mapping, target, user=None, notes=""):
    """Move o login e os dados atribuíveis para `target`. Atómico + auditoria."""
    from drivers_app.models import CustomerComplaint, DriverMergeAudit
    from settlements.models import CainiaoDelivery, DriverClaim

    source = mapping.driver
    if source.pk == target.pk:
        raise ValueError("Origem e destino são o mesmo motorista.")

    waybills = _courier_waybills(mapping.courier_id)
    counts = {"waybills": len(waybills), "complaints": 0, "claims": 0}

    if waybills:
        counts["complaints"] = CustomerComplaint.objects.filter(
            driver=source, numero_pacote__in=waybills
        ).update(driver=target)
        counts["claims"] = DriverClaim.objects.filter(
            driver=source, waybill_number__in=waybills
        ).update(driver=target)

    counts["deliveries"] = CainiaoDelivery.objects.filter(
        driver=source, courier_id=mapping.courier_id
    ).update(driver=target)

    # Reatribui o próprio login
    mapping.driver = target
    mapping.save(update_fields=["driver"])
    counts["mapping"] = 1

    DriverMergeAudit.objects.create(
        source_driver_repr=(
            f"#{source.pk} · {source.nome_completo} · "
            f"login {mapping.partner.name}/{mapping.courier_id}"
        )[:200],
        source_driver_id=source.pk,
        target_driver=target,
        transferred_counts=counts,
        notes=(
            f"[TRANSFERÊNCIA DE LOGIN {mapping.partner.name}/"
            f"{mapping.courier_id}] {notes}"
        ).strip(),
        merged_by=user if (user and getattr(user, "is_authenticated", False)) else None,
    )
    log.info(
        "Login %s/%s transferido de #%s para #%s: %s",
        mapping.partner.name, mapping.courier_id, source.pk, target.pk, counts,
    )
    return counts
