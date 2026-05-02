"""Endpoints da Conta-Corrente do Motorista (PreInvoiceAdvance).

Cobre 3 famílias de uso:
  1. CRUD individual: criar, editar, cancelar lançamentos.
  2. Bulk: criar N lançamentos do dia numa única transação (planilha).
  3. Integração com PF: listar pendentes do período e anexar à PF.

Regras-chave:
- Editar só permitido se status == PENDENTE (Fase 5 do plano).
- Cancelar permitido em qualquer estado; se INCLUIDO_PF, recalcula a PF.
- Sócios (terceiros): mantém comportamento existente — `_sync_reimbursement`
  no `save()` cria `ThirdPartyReimbursement` PENDENTE no acto do lançamento.
"""
import json
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_http_methods

from drivers_app.models import DriverProfile

from .cash_entry_services import (
    attach_entries_to_pf,
    cancel_entry,
    pending_entries_for_driver,
    pending_total_for_driver,
)
from .models import (
    DriverPreInvoice,
    PreInvoiceAdvance,
    Shareholder,
)


# ── Helpers internos ───────────────────────────────────────────────────

def _to_dec(val, default="0.00"):
    try:
        return Decimal(str(val))
    except (InvalidOperation, TypeError):
        return Decimal(default)


VALID_TIPOS = {"ADIANTAMENTO", "COMBUSTIVEL", "ABASTECIMENTO", "OUTRO"}
VALID_PAID_BY = {"EMPRESA", "TERCEIRO"}


def _validate_paid_by(paid_by_source, paid_by_lender_id):
    """Valida par (source, lender_id). Devolve (lender_obj_or_None, error_or_None)."""
    if paid_by_source not in VALID_PAID_BY:
        return None, "paid_by_source inválido"
    if paid_by_source != "TERCEIRO":
        return None, None
    if not paid_by_lender_id:
        return None, "paid_by_lender_id é obrigatório quando TERCEIRO"
    lender = Shareholder.objects.filter(
        id=paid_by_lender_id, ativo=True,
    ).first()
    if not lender:
        return None, "Sócio inválido ou inativo"
    return lender, None


def _serialize_entry(e):
    pf = e.pre_invoice
    return {
        "id": e.id,
        "driver_id": e.driver_id,
        "driver_nome": e.driver.nome_completo,
        "data": e.data.strftime("%Y-%m-%d") if e.data else "",
        "data_pt": e.data.strftime("%d/%m/%Y") if e.data else "",
        "tipo": e.tipo,
        "tipo_display": e.get_tipo_display(),
        "descricao": e.descricao,
        "valor": str(e.valor),
        "documento_referencia": e.documento_referencia,
        "paid_by_source": e.paid_by_source,
        "paid_by_lender_id": e.paid_by_lender_id,
        "paid_by_lender_nome": (
            e.paid_by_lender.nome if e.paid_by_lender_id else ""
        ),
        "status": e.status,
        "status_display": e.get_status_display(),
        "pre_invoice_id": e.pre_invoice_id,
        "pre_invoice_numero": pf.numero if pf else "",
        "pre_invoice_status": pf.status if pf else "",
        "created_at": e.created_at.strftime("%Y-%m-%d %H:%M"),
    }


# ── CRUD individual ────────────────────────────────────────────────────

@login_required
@require_http_methods(["POST"])
def cash_entry_create(request):
    """Cria um lançamento (sempre PENDENTE, sem PF)."""
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        body = request.POST.dict()

    driver_id = body.get("driver_id")
    if not driver_id:
        return JsonResponse(
            {"success": False, "error": "driver_id é obrigatório"},
            status=400,
        )
    driver = DriverProfile.objects.filter(id=driver_id).first()
    if not driver:
        return JsonResponse(
            {"success": False, "error": "Motorista não encontrado"},
            status=400,
        )

    tipo = body.get("tipo", "ADIANTAMENTO")
    if tipo not in VALID_TIPOS:
        return JsonResponse(
            {"success": False, "error": "tipo inválido"}, status=400,
        )

    valor = _to_dec(body.get("valor", 0))
    if valor <= 0:
        return JsonResponse(
            {"success": False, "error": "valor deve ser > 0"}, status=400,
        )

    paid_by_source = body.get("paid_by_source", "EMPRESA")
    lender, err = _validate_paid_by(
        paid_by_source, body.get("paid_by_lender_id"),
    )
    if err:
        return JsonResponse({"success": False, "error": err}, status=400)

    e = PreInvoiceAdvance.objects.create(
        driver=driver,
        pre_invoice=None,  # nasce sem PF
        status="PENDENTE",
        data=parse_date(body.get("data") or "") or None,
        tipo=tipo,
        descricao=(body.get("descricao") or "")[:300],
        valor=valor,
        documento_referencia=(body.get("documento_referencia") or "")[:300],
        paid_by_source=paid_by_source,
        paid_by_lender=lender,
    )
    return JsonResponse({
        "success": True,
        "id": e.id,
        "entry": _serialize_entry(e),
    })


@login_required
@require_http_methods(["POST"])
def cash_entry_update(request, entry_id):
    """Edita um lançamento PENDENTE. Bloqueado se INCLUIDO_PF/CANCELADO."""
    e = get_object_or_404(PreInvoiceAdvance, id=entry_id)
    if e.status != "PENDENTE":
        return JsonResponse(
            {"success": False,
             "error": f"Não é possível editar — status={e.status}. "
                      "Apenas lançamentos PENDENTE são editáveis. "
                      "Para alterar um lançamento já incluído numa PF, "
                      "cancele-o e crie um novo."},
            status=400,
        )

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        body = request.POST.dict()

    if "tipo" in body:
        if body["tipo"] not in VALID_TIPOS:
            return JsonResponse(
                {"success": False, "error": "tipo inválido"}, status=400,
            )
        e.tipo = body["tipo"]
    if "valor" in body:
        v = _to_dec(body["valor"])
        if v <= 0:
            return JsonResponse(
                {"success": False, "error": "valor deve ser > 0"},
                status=400,
            )
        e.valor = v
    if "data" in body:
        e.data = parse_date(body["data"] or "") or None
    if "descricao" in body:
        e.descricao = (body["descricao"] or "")[:300]
    if "documento_referencia" in body:
        e.documento_referencia = (
            body["documento_referencia"] or ""
        )[:300]
    if "paid_by_source" in body:
        lender, err = _validate_paid_by(
            body["paid_by_source"],
            body.get("paid_by_lender_id", e.paid_by_lender_id),
        )
        if err:
            return JsonResponse(
                {"success": False, "error": err}, status=400,
            )
        e.paid_by_source = body["paid_by_source"]
        e.paid_by_lender = lender

    e.save()
    return JsonResponse({"success": True, "entry": _serialize_entry(e)})


@login_required
@require_http_methods(["POST"])
def cash_entry_cancel(request, entry_id):
    """Cancela um lançamento. Se INCLUIDO_PF, recalcula a PF."""
    e = get_object_or_404(PreInvoiceAdvance, id=entry_id)
    if e.status == "CANCELADO":
        return JsonResponse(
            {"success": False, "error": "Já está cancelado"},
            status=400,
        )
    pf_id = e.pre_invoice_id
    cancel_entry(e)
    return JsonResponse({
        "success": True,
        "entry_id": e.id,
        "recalculated_pf_id": pf_id,
    })


# ── Listagem ───────────────────────────────────────────────────────────

@login_required
def cash_entry_list(request):
    """Lista lançamentos com filtros + KPIs.

    Query params:
      driver_id=<id>
      status=PENDENTE|INCLUIDO_PF|CANCELADO  (multi)
      tipo=ADIANTAMENTO|...                  (multi)
      paid_by_source=EMPRESA|TERCEIRO
      lender_id=<id>
      from=YYYY-MM-DD  (data >=)
      to=YYYY-MM-DD    (data <=)
      page=N&page_size=M  (default page_size=50, max 200)
    """
    qs = PreInvoiceAdvance.objects.select_related(
        "driver", "pre_invoice", "paid_by_lender",
    )

    driver_id = request.GET.get("driver_id")
    if driver_id:
        qs = qs.filter(driver_id=driver_id)

    statuses = request.GET.getlist("status")
    if statuses:
        qs = qs.filter(status__in=statuses)

    tipos = request.GET.getlist("tipo")
    if tipos:
        qs = qs.filter(tipo__in=tipos)

    paid_by = request.GET.get("paid_by_source")
    if paid_by:
        qs = qs.filter(paid_by_source=paid_by)

    lender_id = request.GET.get("lender_id")
    if lender_id:
        qs = qs.filter(paid_by_lender_id=lender_id)

    date_from = parse_date(request.GET.get("from") or "")
    date_to = parse_date(request.GET.get("to") or "")
    if date_from:
        qs = qs.filter(data__gte=date_from)
    if date_to:
        qs = qs.filter(data__lte=date_to)

    qs = qs.order_by("-data", "-id")

    # Paginação simples
    try:
        page = max(1, int(request.GET.get("page") or 1))
        page_size = min(
            200, max(10, int(request.GET.get("page_size") or 50)),
        )
    except (TypeError, ValueError):
        page, page_size = 1, 50
    total = qs.count()
    start = (page - 1) * page_size
    rows = [_serialize_entry(e) for e in qs[start:start + page_size]]

    # KPIs sobre o queryset filtrado
    aggs = qs.aggregate(
        total_pendente=Sum(
            "valor", filter=Q(status="PENDENTE"),
        ),
        total_incluido=Sum(
            "valor", filter=Q(status="INCLUIDO_PF"),
        ),
        total_cancelado=Sum(
            "valor", filter=Q(status="CANCELADO"),
        ),
    )
    kpis = {
        "n_pendente": qs.filter(status="PENDENTE").count(),
        "n_incluido": qs.filter(status="INCLUIDO_PF").count(),
        "n_cancelado": qs.filter(status="CANCELADO").count(),
        "total_pendente": str(aggs["total_pendente"] or Decimal("0.00")),
        "total_incluido": str(aggs["total_incluido"] or Decimal("0.00")),
        "total_cancelado": str(aggs["total_cancelado"] or Decimal("0.00")),
    }

    # Top 10 motoristas com maior saldo pendente (geral, não filtrado)
    top_pending = list(
        PreInvoiceAdvance.objects
        .filter(status="PENDENTE")
        .values("driver_id", "driver__nome_completo")
        .annotate(total=Sum("valor"))
        .order_by("-total")[:10]
    )
    top_pending_rows = [
        {
            "driver_id": r["driver_id"],
            "driver_nome": r["driver__nome_completo"],
            "total": str(r["total"]),
        }
        for r in top_pending
    ]

    return JsonResponse({
        "entries": rows,
        "page": page,
        "page_size": page_size,
        "total": total,
        "kpis": kpis,
        "top_pending": top_pending_rows,
    })


# ── Bulk: lançamento do dia ────────────────────────────────────────────

@login_required
@require_http_methods(["POST"])
def cash_entry_bulk_create(request):
    """Cria N lançamentos numa transação. Body:

    {
        "data": "2026-05-01",
        "tipo": "COMBUSTIVEL",
        "paid_by_source": "EMPRESA" | "TERCEIRO",  # default para entries
        "paid_by_lender_id": <id|null>,             # default para entries
        "entries": [
            # Cada entry pode override paid_by_source/paid_by_lender_id;
            # se omitido, usa o default global do body.
            {
                "driver_id": 1, "valor": "20.00", "descricao": "...",
                "paid_by_source": "TERCEIRO",
                "paid_by_lender_id": 5,
            },
            ...
        ]
    }

    Ignora silenciosamente entries com valor <= 0, driver inválido, ou
    sócio inválido (quando TERCEIRO) — devolve relatório do que foi
    criado e do que foi descartado, com `reason`.
    """
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse(
            {"success": False, "error": "JSON inválido"}, status=400,
        )

    common_data = parse_date(body.get("data") or "") or None
    tipo = body.get("tipo", "ADIANTAMENTO")
    if tipo not in VALID_TIPOS:
        return JsonResponse(
            {"success": False, "error": "tipo inválido"}, status=400,
        )

    # Defaults globais (usados quando uma entry não traz os seus próprios)
    default_source = body.get("paid_by_source", "EMPRESA")
    default_lender_id = body.get("paid_by_lender_id")
    # Se default é TERCEIRO, valida o sócio default — mas não falha aqui,
    # porque entries podem ter o seu próprio TERCEIRO/EMPRESA.
    default_lender = None
    if default_source == "TERCEIRO" and default_lender_id:
        default_lender = Shareholder.objects.filter(
            id=default_lender_id, ativo=True,
        ).first()

    entries = body.get("entries") or []
    if not isinstance(entries, list) or not entries:
        return JsonResponse(
            {"success": False, "error": "entries vazio"}, status=400,
        )

    created, skipped = [], []
    with transaction.atomic():
        for raw in entries:
            driver_id = raw.get("driver_id")
            valor = _to_dec(raw.get("valor", 0))
            if valor <= 0 or not driver_id:
                skipped.append({
                    "driver_id": driver_id,
                    "reason": "valor<=0 ou driver_id ausente",
                })
                continue
            drv = DriverProfile.objects.filter(id=driver_id).first()
            if not drv:
                skipped.append({
                    "driver_id": driver_id,
                    "reason": "driver não encontrado",
                })
                continue

            # Resolver pago_por desta linha (override > default)
            row_source = raw.get("paid_by_source", default_source)
            if row_source not in VALID_PAID_BY:
                skipped.append({
                    "driver_id": driver_id,
                    "reason": f"paid_by_source inválido ({row_source})",
                })
                continue
            row_lender = None
            if row_source == "TERCEIRO":
                row_lender_id = raw.get(
                    "paid_by_lender_id", default_lender_id,
                )
                if not row_lender_id:
                    skipped.append({
                        "driver_id": driver_id,
                        "reason": "TERCEIRO sem paid_by_lender_id",
                    })
                    continue
                row_lender = Shareholder.objects.filter(
                    id=row_lender_id, ativo=True,
                ).first()
                if not row_lender:
                    skipped.append({
                        "driver_id": driver_id,
                        "reason": f"sócio inválido ({row_lender_id})",
                    })
                    continue

            e = PreInvoiceAdvance.objects.create(
                driver=drv,
                pre_invoice=None,
                status="PENDENTE",
                data=common_data,
                tipo=tipo,
                descricao=(raw.get("descricao") or "")[:300],
                valor=valor,
                documento_referencia=(
                    raw.get("documento_referencia") or ""
                )[:300],
                paid_by_source=row_source,
                paid_by_lender=row_lender,
            )
            created.append({"id": e.id, "driver_id": drv.id})

    return JsonResponse({
        "success": True,
        "created_count": len(created),
        "skipped_count": len(skipped),
        "created": created,
        "skipped": skipped,
    })


# ── Integração com PF ──────────────────────────────────────────────────

@login_required
def pre_invoice_pending_entries(request, pre_invoice_id):
    """Lista lançamentos PENDENTES do motorista da PF cuja `data` cai no
    período da PF (incluindo data NULL). Usado pelo prompt "incluir
    pendentes?" no fluxo de criação/recálculo da PF."""
    pf = get_object_or_404(DriverPreInvoice, id=pre_invoice_id)
    qs = pending_entries_for_driver(
        pf.driver, pf.periodo_inicio, pf.periodo_fim,
    )
    rows = [_serialize_entry(e) for e in qs]
    total = sum((Decimal(r["valor"]) for r in rows), Decimal("0.00"))

    # Também devolve o saldo TOTAL (todos pendentes, incl. fora do período)
    total_geral = pending_total_for_driver(pf.driver)

    return JsonResponse({
        "success": True,
        "pre_invoice_id": pf.id,
        "pre_invoice_numero": pf.numero,
        "driver_id": pf.driver_id,
        "driver_nome": pf.driver.nome_completo,
        "periodo_inicio": pf.periodo_inicio.strftime("%Y-%m-%d"),
        "periodo_fim": pf.periodo_fim.strftime("%Y-%m-%d"),
        "entries": rows,
        "total_periodo": str(total),
        "total_geral_pendente": str(total_geral),
        "n_periodo": len(rows),
    })


@login_required
def cash_entries_dashboard(request):
    """Página HTML da Conta-Corrente do Motorista."""
    return render(request, "settlements/cash_entries_dashboard.html")


@login_required
@require_http_methods(["POST"])
def pre_invoice_attach_entries(request, pre_invoice_id):
    """Anexa lançamentos PENDENTE à PF. Body: {"entry_ids": [...]}."""
    pf = get_object_or_404(DriverPreInvoice, id=pre_invoice_id)
    if pf.status in ("PAGO", "REPROVADO"):
        return JsonResponse(
            {"success": False,
             "error": f"PF está {pf.status} — não é possível anexar."},
            status=400,
        )

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        body = request.POST.dict()
    entry_ids = body.get("entry_ids") or []
    if not isinstance(entry_ids, list):
        entry_ids = []
    n = attach_entries_to_pf([int(x) for x in entry_ids if x], pf)
    pf.refresh_from_db()
    return JsonResponse({
        "success": True,
        "attached_count": n,
        "pre_invoice_id": pf.id,
        "total_a_receber": str(pf.total_a_receber),
        "total_adiantamentos": str(pf.total_adiantamentos),
    })
