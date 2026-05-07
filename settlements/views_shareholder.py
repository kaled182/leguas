"""Endpoints para gestão de Sócios (Shareholder) e Reembolsos a Terceiros
(ThirdPartyReimbursement).

A entrada do fluxo é o modal do motorista, onde se pode escolher quem
adiantou o dinheiro de um lançamento (Empresa vs Sócio). Quando é Sócio,
um ThirdPartyReimbursement PENDENTE é criado automaticamente.
"""
import json
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_http_methods

from .models import Shareholder, ThirdPartyReimbursement


def _to_dec(val, default="0.00"):
    try:
        return Decimal(str(val))
    except (InvalidOperation, TypeError):
        return Decimal(default)


# ── Sócios ──────────────────────────────────────────────────────────────

@login_required
def shareholder_list_api(request):
    """Lista de sócios — usado pelo modal do motorista (autocomplete) e
    pela página de gestão.

    Query params:
      ativo=1 (default) → só ativos
      q=texto → filtro por nome (icontains)
    """
    only_active = request.GET.get("ativo", "1") != "0"
    q = (request.GET.get("q") or "").strip()
    qs = Shareholder.objects.all()
    if only_active:
        qs = qs.filter(ativo=True)
    if q:
        qs = qs.filter(nome__icontains=q)

    rows = []
    for s in qs.order_by("nome"):
        pendente = (
            ThirdPartyReimbursement.objects
            .filter(lender=s, status="PENDENTE")
            .aggregate(total=Sum("valor"))["total"] or Decimal("0.00")
        )
        rows.append({
            "id": s.id,
            "nome": s.nome,
            "iban": s.iban,
            "telefone": s.telefone,
            "ativo": s.ativo,
            "saldo_pendente": str(pendente),
        })
    return JsonResponse({"shareholders": rows})


@login_required
@require_http_methods(["POST"])
def shareholder_create(request):
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        body = request.POST.dict()

    nome = (body.get("nome") or "").strip()
    if not nome:
        return JsonResponse(
            {"success": False, "error": "Nome é obrigatório"}, status=400,
        )

    s = Shareholder.objects.create(
        nome=nome,
        iban=(body.get("iban") or "").strip(),
        telefone=(body.get("telefone") or "").strip(),
        observacoes=(body.get("observacoes") or "").strip(),
        ativo=bool(body.get("ativo", True)),
    )
    return JsonResponse({"success": True, "id": s.id})


@login_required
@require_http_methods(["POST"])
def shareholder_update(request, shareholder_id):
    s = get_object_or_404(Shareholder, id=shareholder_id)
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        body = request.POST.dict()

    if "nome" in body:
        nome = (body["nome"] or "").strip()
        if nome:
            s.nome = nome
    if "iban" in body:
        s.iban = (body["iban"] or "").strip()
    if "telefone" in body:
        s.telefone = (body["telefone"] or "").strip()
    if "observacoes" in body:
        s.observacoes = (body["observacoes"] or "").strip()
    if "ativo" in body:
        s.ativo = bool(body["ativo"])
    s.save()
    return JsonResponse({"success": True})


@login_required
@require_http_methods(["POST"])
def shareholder_delete(request, shareholder_id):
    """Desativa o sócio (soft delete). Apaga só se não tiver reembolsos."""
    s = get_object_or_404(Shareholder, id=shareholder_id)
    has_reimbursements = s.reembolsos.exists() or s.advances_pagas.exists()
    if has_reimbursements:
        s.ativo = False
        s.save(update_fields=["ativo"])
        return JsonResponse(
            {"success": True, "deleted": False, "deactivated": True},
        )
    s.delete()
    return JsonResponse(
        {"success": True, "deleted": True, "deactivated": False},
    )


# ── Reembolsos a Terceiros ─────────────────────────────────────────────

@login_required
def reimbursement_list_api(request):
    """Lista reembolsos, com filtros e KPIs.

    Query params:
      status=PENDENTE | PAGO | CANCELADO  (multi)
      lender_id=<id>
      from=YYYY-MM-DD  (data_emprestimo >=)
      to=YYYY-MM-DD    (data_emprestimo <=)
    """
    qs = ThirdPartyReimbursement.objects.select_related(
        "lender", "origem_advance__pre_invoice__driver",
        "origem_bill__fornecedor",
        "pago_por", "created_by",
    )
    statuses = request.GET.getlist("status")
    if statuses:
        qs = qs.filter(status__in=statuses)
    lender_id = request.GET.get("lender_id")
    if lender_id:
        qs = qs.filter(lender_id=lender_id)
    date_from = parse_date(request.GET.get("from") or "")
    date_to = parse_date(request.GET.get("to") or "")
    if date_from:
        qs = qs.filter(data_emprestimo__gte=date_from)
    if date_to:
        qs = qs.filter(data_emprestimo__lte=date_to)

    rows = []
    for r in qs.order_by("status", "-data_emprestimo", "-id"):
        adv = r.origem_advance
        bill = r.origem_bill
        driver_nome = ""
        pf_numero = ""
        bill_supplier = ""
        bill_id = None
        if adv and adv.pre_invoice_id:
            driver_nome = adv.pre_invoice.driver.nome_completo
            pf_numero = adv.pre_invoice.numero
        elif bill:
            bill_supplier = (
                bill.fornecedor.name if bill.fornecedor_id
                else (bill.supplier or "")
            )
            bill_id = bill.id
        rows.append({
            "id": r.id,
            "lender_id": r.lender_id,
            "lender_nome": r.lender.nome,
            "valor": str(r.valor),
            "data_emprestimo": r.data_emprestimo.strftime("%Y-%m-%d"),
            "descricao": r.descricao,
            "status": r.status,
            "status_display": r.get_status_display(),
            "data_pagamento": (
                r.data_pagamento.strftime("%Y-%m-%d")
                if r.data_pagamento else ""
            ),
            "referencia_pagamento": r.referencia_pagamento,
            "pago_por_nome": (
                r.pago_por.get_full_name() or r.pago_por.username
            ) if r.pago_por_id else "",
            "origem_advance_id": r.origem_advance_id,
            "origem_bill_id": bill_id,
            "driver_nome": driver_nome,
            "pf_numero": pf_numero,
            "bill_supplier": bill_supplier,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M"),
        })

    # KPIs
    pend = ThirdPartyReimbursement.objects.filter(status="PENDENTE")
    if lender_id:
        pend = pend.filter(lender_id=lender_id)
    total_pendente = (
        pend.aggregate(t=Sum("valor"))["t"] or Decimal("0.00")
    )
    pago = ThirdPartyReimbursement.objects.filter(status="PAGO")
    if lender_id:
        pago = pago.filter(lender_id=lender_id)
    total_pago = pago.aggregate(t=Sum("valor"))["t"] or Decimal("0.00")

    # Saldo pendente por sócio
    by_lender = []
    pend_by_lender = (
        ThirdPartyReimbursement.objects
        .filter(status="PENDENTE")
        .values("lender_id", "lender__nome")
        .annotate(total=Sum("valor"))
        .order_by("-total")
    )
    for row in pend_by_lender:
        by_lender.append({
            "lender_id": row["lender_id"],
            "lender_nome": row["lender__nome"],
            "total_pendente": str(row["total"]),
        })

    return JsonResponse({
        "reimbursements": rows,
        "kpis": {
            "total_pendente": str(total_pendente),
            "total_pago": str(total_pago),
            "n_pendente": pend.count(),
            "n_pago": pago.count(),
        },
        "by_lender": by_lender,
    })


@login_required
@require_http_methods(["POST"])
def reimbursement_create(request):
    """Cria reembolso manual (sem advance ligado — ex.: peça de veículo
    paga pelo sócio sem entrar como adiantamento de motorista)."""
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        body = request.POST.dict()

    lender_id = body.get("lender_id")
    if not lender_id:
        return JsonResponse(
            {"success": False, "error": "lender_id é obrigatório"},
            status=400,
        )
    lender = Shareholder.objects.filter(id=lender_id).first()
    if not lender:
        return JsonResponse(
            {"success": False, "error": "Sócio não encontrado"}, status=400,
        )
    valor = _to_dec(body.get("valor", 0))
    if valor <= 0:
        return JsonResponse(
            {"success": False, "error": "Valor deve ser > 0"}, status=400,
        )
    data_emp = parse_date(body.get("data_emprestimo") or "")
    if not data_emp:
        data_emp = timezone.now().date()

    r = ThirdPartyReimbursement.objects.create(
        lender=lender,
        valor=valor,
        data_emprestimo=data_emp,
        descricao=(body.get("descricao") or "")[:300],
        status="PENDENTE",
        created_by=request.user if request.user.is_authenticated else None,
    )
    return JsonResponse({"success": True, "id": r.id})


@login_required
@require_http_methods(["POST"])
def reimbursement_mark_paid(request, reimbursement_id):
    r = get_object_or_404(ThirdPartyReimbursement, id=reimbursement_id)
    if r.status == "PAGO":
        return JsonResponse(
            {"success": False, "error": "Já está marcado como pago"},
            status=400,
        )
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        body = request.POST.dict()

    data_pag = parse_date(body.get("data_pagamento") or "")
    if not data_pag:
        data_pag = timezone.now().date()
    r.status = "PAGO"
    r.data_pagamento = data_pag
    r.referencia_pagamento = (
        body.get("referencia_pagamento") or ""
    )[:200]
    r.pago_por = (
        request.user if request.user.is_authenticated else None
    )
    r.save()
    return JsonResponse({"success": True})


@login_required
@require_http_methods(["POST"])
def reimbursement_cancel(request, reimbursement_id):
    r = get_object_or_404(ThirdPartyReimbursement, id=reimbursement_id)
    if r.status == "CANCELADO":
        return JsonResponse(
            {"success": False, "error": "Já está cancelado"}, status=400,
        )
    r.status = "CANCELADO"
    r.save(update_fields=["status"])
    return JsonResponse({"success": True})


@login_required
@require_http_methods(["POST"])
def reimbursement_bulk_mark_paid(request):
    """Marca várias linhas como pagas (via lista de IDs)."""
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        body = request.POST.dict()
    ids = body.get("ids") or []
    if not isinstance(ids, list):
        ids = []
    data_pag = parse_date(body.get("data_pagamento") or "")
    if not data_pag:
        data_pag = timezone.now().date()
    ref = (body.get("referencia_pagamento") or "")[:200]

    qs = ThirdPartyReimbursement.objects.filter(
        id__in=ids, status="PENDENTE",
    )
    n = qs.count()
    qs.update(
        status="PAGO",
        data_pagamento=data_pag,
        referencia_pagamento=ref,
        pago_por=(request.user if request.user.is_authenticated else None),
    )
    return JsonResponse({"success": True, "marked": n})


# ── Página HTML ────────────────────────────────────────────────────────

@login_required
def shareholder_dashboard(request):
    """Página HTML para gestão de sócios e reembolsos."""
    return render(request, "settlements/shareholder_dashboard.html")
