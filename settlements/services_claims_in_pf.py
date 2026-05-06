"""Auto-inclusão de DriverClaim aprovados na DriverPreInvoice.

Regra de negócio:
  - Quando uma DriverPreInvoice é criada/recalculada, todos os
    DriverClaim em status APPROVED do driver, com data dentro do
    período da PF, e que ainda não foram incluídos noutra PF, são
    automaticamente convertidos em PreInvoiceLostPackage e somados
    a total_pacotes_perdidos.

  - Idempotência: usa numero_pacote=claim.waybill_number e
    api_source="auto:driver_claim:<claim_id>" como chave estável.

  - Status APPEALED ou PENDING NÃO são incluídos — o operador deve
    primeiro decidir.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def auto_include_approved_claims(pre_invoice):
    """Para um DriverPreInvoice, cria PreInvoiceLostPackage para cada
    DriverClaim APPROVED do mesmo driver no período.

    Devolve dict com contadores:
      - included: número de claims novos incluídos nesta chamada
      - already: número de claims que já tinham sido incluídos
      - skipped: número de claims com status diferente de APPROVED
        no período
    """
    from .models import DriverClaim, PreInvoiceLostPackage

    if not pre_invoice or not pre_invoice.driver_id:
        return {"included": 0, "already": 0, "skipped": 0}

    # Claims APPROVED no período (occurred_at OU operation_task_date)
    qs = DriverClaim.objects.filter(
        driver_id=pre_invoice.driver_id,
        status="APPROVED",
    ).filter(
        # qualquer um dos dois campos cair no período
        # operation_task_date é mais preciso (data da entrega Cainiao)
        # mas é nullable; fallback para occurred_at.
    )

    period_start = pre_invoice.periodo_inicio
    period_end = pre_invoice.periodo_fim

    included = already = skipped = 0
    for claim in qs:
        ref_date = (
            claim.operation_task_date
            or (claim.occurred_at.date() if claim.occurred_at else None)
        )
        if ref_date is None:
            skipped += 1
            continue
        if not (period_start <= ref_date <= period_end):
            skipped += 1
            continue

        # Idempotência por claim id
        marker = f"auto:driver_claim:{claim.id}"
        existing = PreInvoiceLostPackage.objects.filter(
            pre_invoice=pre_invoice,
            api_source=marker,
        ).first()
        if existing:
            already += 1
            continue

        PreInvoiceLostPackage.objects.create(
            pre_invoice=pre_invoice,
            data=ref_date,
            numero_pacote=claim.waybill_number or f"claim-{claim.id}",
            descricao=(claim.description or "")[:300],
            valor=claim.amount,
            api_source=marker,
            observacoes=(
                f"Auto-incluído de DriverClaim #{claim.id} "
                f"({claim.get_claim_type_display()})"
            )[:300],
        )
        included += 1
        log.info(
            "DriverClaim #%s incluído em PF %s (€%s)",
            claim.id, pre_invoice.numero, claim.amount,
        )

    return {
        "included": included,
        "already": already,
        "skipped": skipped,
    }
