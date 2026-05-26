"""Auditoria centralizada — timeline cross-modelo dos eventos financeiros.

Reaproveita os timestamps já existentes (`created_at`, `paid_date`,
`approved_at`, `matched_at`, `deleted_at`, etc.) para construir uma
linha temporal unificada sem precisar de tabela de logs nova.

Filtros: tipo de entidade, sentido (entrada/saída), data range, actor.
"""
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone

from .models import Bill, BankTransaction, Imposto


# Tipos de evento — pill colors no template
EVENT_TYPES = [
    ("bill_created", "Bill criada"),
    ("bill_paid", "Bill paga"),
    ("bill_deleted", "Bill removida"),
    ("partner_created", "Fatura parceiro criada"),
    ("partner_approved", "Fatura parceiro aprovada"),
    ("partner_paid", "Fatura parceiro recebida"),
    ("imposto_created", "Imposto criado"),
    ("imposto_paid", "Imposto pago"),
    ("bank_matched", "Match bancário"),
    ("pf_paid", "PF motorista paga"),
]


def _make_dt(d):
    """Converte date → datetime aware (meio-dia) para ordenar
    junto com timestamps reais."""
    if isinstance(d, datetime):
        if timezone.is_naive(d):
            return timezone.make_aware(d)
        return d
    if isinstance(d, date):
        return timezone.make_aware(datetime.combine(d, time(12, 0)))
    return None


def _collect_events(date_from, date_to, type_filter=None):
    """Recolhe eventos dos vários modelos no intervalo dado e devolve
    lista de dicts ordenada por timestamp descendente.
    """
    dt_from = timezone.make_aware(datetime.combine(date_from, time.min))
    dt_to = timezone.make_aware(datetime.combine(date_to, time.max))
    events = []

    def want(t):
        return not type_filter or t in type_filter

    # ── Bills ─────────────────────────────────────────────────────
    bill_qs = Bill.all_objects.select_related("fornecedor", "created_by", "deleted_by")
    if want("bill_created"):
        for b in bill_qs.filter(
            created_at__gte=dt_from, created_at__lte=dt_to,
        )[:300]:
            events.append({
                "ts": b.created_at,
                "type": "bill_created",
                "actor": b.created_by,
                "amount": b.amount_total,
                "sign": "out",
                "label": (
                    f"{b.fornecedor.name if b.fornecedor_id else b.supplier or 'Fornecedor'} · "
                    f"{b.description}"
                ),
                "url": f"/accounting/contas-a-pagar/{b.id}/",
            })
    if want("bill_paid"):
        for b in bill_qs.filter(
            paid_date__gte=date_from, paid_date__lte=date_to,
            status=Bill.STATUS_PAID,
        )[:300]:
            events.append({
                "ts": _make_dt(b.paid_date),
                "type": "bill_paid",
                "actor": None,
                "amount": b.paid_amount or b.amount_total,
                "sign": "out",
                "label": (
                    f"{b.fornecedor.name if b.fornecedor_id else b.supplier or 'Fornecedor'} · "
                    f"{b.description}"
                ),
                "url": f"/accounting/contas-a-pagar/{b.id}/",
            })
    if want("bill_deleted"):
        for b in bill_qs.filter(
            deleted_at__gte=dt_from, deleted_at__lte=dt_to,
            is_deleted=True,
        )[:200]:
            events.append({
                "ts": b.deleted_at,
                "type": "bill_deleted",
                "actor": b.deleted_by,
                "amount": b.amount_total,
                "sign": "out",
                "label": (
                    f"{b.fornecedor.name if b.fornecedor_id else b.supplier or 'Fornecedor'} · "
                    f"{b.description}  ({b.delete_reason or 'sem motivo'})"
                ),
                "url": f"/accounting/contas-a-pagar/{b.id}/",
            })

    # ── PartnerInvoice ────────────────────────────────────────────
    try:
        from settlements.models import PartnerInvoice
        pi_qs = PartnerInvoice.objects.select_related(
            "partner", "created_by", "approved_by",
        )
        if want("partner_created"):
            for p in pi_qs.filter(
                created_at__gte=dt_from, created_at__lte=dt_to,
            )[:300]:
                events.append({
                    "ts": p.created_at,
                    "type": "partner_created",
                    "actor": p.created_by,
                    "amount": p.gross_amount,
                    "sign": "in",
                    "label": (
                        f"{p.partner.name if p.partner_id else 'Parceiro'} · "
                        f"{p.invoice_number}"
                    ),
                    "url": f"/settlements/invoices/{p.id}/",
                })
        if want("partner_approved"):
            for p in pi_qs.filter(
                approved_at__gte=dt_from, approved_at__lte=dt_to,
            )[:200]:
                events.append({
                    "ts": p.approved_at,
                    "type": "partner_approved",
                    "actor": p.approved_by,
                    "amount": p.gross_amount,
                    "sign": "in",
                    "label": (
                        f"{p.partner.name if p.partner_id else 'Parceiro'} · "
                        f"{p.invoice_number}"
                    ),
                    "url": f"/settlements/invoices/{p.id}/",
                })
        if want("partner_paid"):
            for p in pi_qs.filter(
                paid_date__gte=date_from, paid_date__lte=date_to,
                status="PAID",
            )[:200]:
                events.append({
                    "ts": _make_dt(p.paid_date),
                    "type": "partner_paid",
                    "actor": None,
                    "amount": p.gross_amount,
                    "sign": "in",
                    "label": (
                        f"{p.partner.name if p.partner_id else 'Parceiro'} · "
                        f"{p.invoice_number}"
                    ),
                    "url": f"/settlements/invoices/{p.id}/",
                })
    except Exception:
        pass

    # ── Impostos ──────────────────────────────────────────────────
    imp_qs = Imposto.objects.select_related("fornecedor", "created_by", "parent")
    if want("imposto_created"):
        for i in imp_qs.filter(
            created_at__gte=dt_from, created_at__lte=dt_to,
        )[:200]:
            events.append({
                "ts": i.created_at,
                "type": "imposto_created",
                "actor": i.created_by,
                "amount": i.valor,
                "sign": "out",
                "label": (
                    f"{i.get_tipo_display()} · {i.nome}"
                    + (f"  (parcela {i.parcela_numero}/{i.parcela_total})"
                       if i.parent_id else "")
                ),
                "url": (
                    f"/accounting/impostos/planos/{i.parent_id}/"
                    if i.parent_id
                    else f"/accounting/impostos/{i.id}/editar/"
                ),
            })
    if want("imposto_paid"):
        for i in imp_qs.filter(
            data_pagamento__gte=date_from, data_pagamento__lte=date_to,
            status=Imposto.STATUS_PAGO,
        )[:200]:
            events.append({
                "ts": _make_dt(i.data_pagamento),
                "type": "imposto_paid",
                "actor": None,
                "amount": i.valor,
                "sign": "out",
                "label": (
                    f"{i.get_tipo_display()} · {i.nome}"
                    + (f"  (parcela {i.parcela_numero}/{i.parcela_total})"
                       if i.parent_id else "")
                ),
                "url": (
                    f"/accounting/impostos/planos/{i.parent_id}/"
                    if i.parent_id
                    else f"/accounting/impostos/{i.id}/editar/"
                ),
            })

    # ── BankTransaction matched ───────────────────────────────────
    if want("bank_matched"):
        for tx in BankTransaction.objects.filter(
            matched_at__gte=dt_from, matched_at__lte=dt_to,
        ).select_related("matched_by", "matched_bill")[:200]:
            target = "Bill" if tx.matched_bill_id else (
                "Fatura parceiro" if tx.matched_partner_invoice_id
                else "PF" if tx.matched_pf_id else "?"
            )
            events.append({
                "ts": tx.matched_at,
                "type": "bank_matched",
                "actor": tx.matched_by,
                "amount": tx.amount,
                "sign": "in" if tx.direction == "CREDIT" else "out",
                "label": (
                    f"{tx.date:%d/%m} {target} · "
                    f"{(tx.description or '')[:60]}"
                ),
                "url": "/accounting/reconciliacao-bancaria/?matched=1",
            })

    # ── DriverPreInvoice ──────────────────────────────────────────
    if want("pf_paid"):
        try:
            from settlements.models import DriverPreInvoice
            for pf in DriverPreInvoice.objects.filter(
                data_pagamento__gte=date_from, data_pagamento__lte=date_to,
                status="PAGO",
            ).select_related("driver")[:200]:
                events.append({
                    "ts": _make_dt(pf.data_pagamento),
                    "type": "pf_paid",
                    "actor": None,
                    "amount": pf.total_a_receber,
                    "sign": "out",
                    "label": (
                        f"PF {pf.numero} · "
                        f"{pf.driver.nome_completo if pf.driver_id else '?'}"
                    ),
                    "url": f"/settlements/pre-invoices/{pf.id}/",
                })
        except Exception:
            pass

    events.sort(key=lambda e: e["ts"] or timezone.now(), reverse=True)
    return events


@login_required
def audit_timeline(request):
    """Timeline cross-modelo dos últimos eventos financeiros."""
    today = timezone.localdate()
    days = int(request.GET.get("days") or 30)
    if days < 1:
        days = 30
    if days > 365:
        days = 365
    date_from = today - timedelta(days=days)
    date_to = today

    type_filter = request.GET.getlist("type") or None

    events = _collect_events(date_from, date_to, type_filter=type_filter)
    events = events[:300]

    # KPIs por tipo
    type_counts = {}
    for e in events:
        type_counts[e["type"]] = type_counts.get(e["type"], 0) + 1

    return render(request, "accounting/audit_timeline.html", {
        "events": events,
        "type_counts": type_counts,
        "type_choices": EVENT_TYPES,
        "filters": {
            "days": days,
            "types": type_filter or [],
        },
        "date_from": date_from,
        "date_to": date_to,
    })
