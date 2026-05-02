"""Helpers para a conta-corrente do motorista (PreInvoiceAdvance).

Cada lançamento (`PreInvoiceAdvance`) nasce com `status='PENDENTE'` e sem
PF. O operador decide quando anexá-lo a uma PF — manualmente no modal do
motorista ou via prompt no fluxo de criação/recálculo da PF.

Regras invariantes:
- Um lançamento só pode estar em **uma** PF a qualquer momento.
- Editar um lançamento `INCLUIDO_PF` é proibido (apenas cancelar é permitido,
  e cancelar dispara recálculo da PF onde estava).
- Cancelar a PF (REPROVADO/CANCELADO) liberta os lançamentos de volta a
  PENDENTE — não os perde.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import QuerySet, Sum

from .models import PreInvoiceAdvance, DriverPreInvoice


# ── Queries ────────────────────────────────────────────────────────────

def pending_entries_for_driver(driver, start=None, end=None) -> QuerySet:
    """Lançamentos PENDENTES de um motorista. Se `start`/`end` forem
    fornecidos, filtra pelos que caem no período (data >= start
    e data <= end). Datas nulas (data IS NULL) são incluídas — assumimos
    que pertencem ao período mais recente possível."""
    qs = PreInvoiceAdvance.objects.filter(driver=driver, status="PENDENTE")
    if start:
        qs = qs.filter(data__gte=start)
    if end:
        qs = qs.filter(data__lte=end)
    return qs.order_by("data", "id")


def pending_total_for_driver(driver) -> Decimal:
    """Soma de valores PENDENTES (todos, sem filtro de data)."""
    agg = PreInvoiceAdvance.objects.filter(
        driver=driver, status="PENDENTE",
    ).aggregate(t=Sum("valor"))
    return agg["t"] or Decimal("0.00")


# ── Mutations ──────────────────────────────────────────────────────────

@transaction.atomic
def attach_entries_to_pf(entry_ids: list, pf: DriverPreInvoice) -> int:
    """Anexa lançamentos PENDENTE a uma PF, marcando-os como INCLUIDO_PF.

    Retorna o nº de lançamentos efectivamente anexados. Apenas anexa os
    que pertencem ao motorista da PF e estão em status PENDENTE — ignora
    os outros silenciosamente (validação acontece a montante).

    Após anexar, dispara `pf.recalcular()` automaticamente.
    """
    if not entry_ids:
        return 0
    qs = PreInvoiceAdvance.objects.filter(
        id__in=entry_ids,
        driver=pf.driver,
        status="PENDENTE",
    )
    n = qs.update(status="INCLUIDO_PF", pre_invoice=pf)
    if n:
        pf.recalcular()
    return n


@transaction.atomic
def detach_entries_from_pf(pf: DriverPreInvoice) -> int:
    """Liberta os lançamentos INCLUIDO_PF desta PF, voltando-os a PENDENTE.

    Usado quando a PF é REPROVADA ou CANCELADA. Não recalcula a PF (quem
    chamou normalmente está a cancelar, não a manter).
    """
    qs = pf.adiantamentos.filter(status="INCLUIDO_PF")
    return qs.update(status="PENDENTE", pre_invoice=None)


@transaction.atomic
def cancel_entry(entry: PreInvoiceAdvance) -> None:
    """Cancela um lançamento. Se estava INCLUIDO_PF, recalcula a PF para
    remover o seu valor do total. Se já estava CANCELADO, no-op."""
    if entry.status == "CANCELADO":
        return
    pf = entry.pre_invoice
    entry.status = "CANCELADO"
    entry.pre_invoice = None
    entry.save(update_fields=["status", "pre_invoice"])
    if pf and pf.status not in ("PAGO",):
        pf.recalcular()
