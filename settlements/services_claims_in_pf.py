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


# PFs onde ainda se pode remover/editar linhas (PAGO e REPROVADO são terminais)
EDITABLE_PF_STATES = ("RASCUNHO", "CALCULADO", "APROVADO", "PENDENTE", "CONTESTADO")


def revert_claim_from_preinvoices(claim):
    """Estorna um DriverClaim das pré-faturas — devolve o valor ao motorista.

    Para cada PreInvoiceLostPackage do claim (marker auto:driver_claim:<id>):
      - PF editável → remove a linha e recalcula (estorno directo);
      - PF já PAGA → cria um crédito (linha negativa) na próxima PF aberta
        do motorista (estorno via crédito), preservando a PF paga intacta.

    Idempotente no crédito (marker auto:driver_claim_credit:<id>).
    """
    from .models import PreInvoiceLostPackage

    removed = credited = paid_blocked = 0
    lines = PreInvoiceLostPackage.objects.filter(
        api_source=f"auto:driver_claim:{claim.id}"
    ).select_related("pre_invoice")

    for line in lines:
        pf = line.pre_invoice
        if pf and pf.status == "PAGO":
            # PF paga é imutável → estorno via crédito na próxima PF aberta
            if _credit_in_next_open_pf(claim, line.valor):
                credited += 1
            else:
                paid_blocked += 1
            continue
        # PF editável → remover a linha e recalcular
        line.delete()
        removed += 1
        if pf:
            pf.recalcular()

    log.info(
        "Estorno claim #%s: removidos=%s creditados=%s sem_pf=%s",
        claim.id, removed, credited, paid_blocked,
    )
    return {"removed": removed, "credited": credited, "paid_blocked": paid_blocked}


def _credit_in_next_open_pf(claim, valor):
    """Cria uma linha de crédito (valor negativo) na próxima PF aberta do
    motorista. Devolve True se creditou (ou já estava creditado)."""
    from django.utils import timezone
    from .models import DriverPreInvoice, PreInvoiceLostPackage

    if not claim.driver_id or not valor:
        return False

    pf = (
        DriverPreInvoice.objects.filter(
            driver_id=claim.driver_id,
            status__in=EDITABLE_PF_STATES,
        )
        .order_by("-periodo_fim")
        .first()
    )
    if not pf:
        return False

    marker = f"auto:driver_claim_credit:{claim.id}"
    if PreInvoiceLostPackage.objects.filter(
        pre_invoice=pf, api_source=marker
    ).exists():
        return True  # já creditado (idempotente)

    PreInvoiceLostPackage.objects.create(
        pre_invoice=pf,
        data=timezone.now().date(),
        numero_pacote=claim.waybill_number or f"claim-{claim.id}",
        descricao=f"Estorno (crédito) do recurso — claim #{claim.id}"[:300],
        valor=-abs(valor),  # negativo → reduz total_pacotes_perdidos
        api_source=marker,
        observacoes=(
            f"Crédito de estorno do DriverClaim #{claim.id} "
            f"(recurso/quarentena)"
        )[:300],
    )
    pf.recalcular()
    log.info("Crédito de estorno do claim #%s em PF %s (€%s)", claim.id, pf.numero, valor)
    return True


def reapply_claim(claim):
    """Re-aplica o desconto (parceiro negou o recurso).

    Remove eventuais créditos de estorno deste claim e re-inclui o claim
    (que deve estar APPROVED) nas PFs abertas do período.
    """
    from .models import DriverPreInvoice, PreInvoiceLostPackage

    # 1) remover créditos de estorno previamente criados
    for cl in PreInvoiceLostPackage.objects.filter(
        api_source=f"auto:driver_claim_credit:{claim.id}"
    ).select_related("pre_invoice"):
        pf = cl.pre_invoice
        if pf and pf.status != "PAGO":
            cl.delete()
            pf.recalcular()

    # 2) re-incluir nas PFs abertas do período (auto_include só age em APPROVED)
    ref_date = (
        claim.operation_task_date
        or (claim.occurred_at.date() if claim.occurred_at else None)
    )
    if not ref_date or not claim.driver_id:
        return {"included": 0}
    open_pfs = DriverPreInvoice.objects.filter(
        driver_id=claim.driver_id,
        periodo_inicio__lte=ref_date,
        periodo_fim__gte=ref_date,
        status__in=["CALCULADO", "APROVADO", "PENDENTE"],
    )
    total = 0
    for pf in open_pfs:
        r = auto_include_approved_claims(pf)
        if r["included"]:
            pf.recalcular()
            total += r["included"]
    return {"included": total}
