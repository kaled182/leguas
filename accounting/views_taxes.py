"""Endpoints do módulo de Impostos.

Cobre:
  - CRUD de Imposto (list, create, edit, mark_paid, anular)
  - Geração automática de N prestações para modalidade PARCELADO
  - Criação automática de Bill espelho ao marcar como PAGO
    (entra no DRE / Fluxo de Caixa do mês de pagamento)
  - KPIs por status, tipo e modalidade
"""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from calendar import monthrange

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .forms import ImpostoForm
from .models import (
    Bill, CostCenter, ExpenseCategory, Fornecedor, Imposto,
)


def _add_months(d: date, months: int) -> date:
    """Soma `months` a uma data preservando dia (ajusta no fim do mês)."""
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    last_day = monthrange(y, m)[1]
    return date(y, m, min(d.day, last_day))


def _split_evenly(total: Decimal, n: int):
    """Divide total em N parcelas iguais (a última absorve o resto
    para garantir soma exacta)."""
    base = (total / n).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    parcelas = [base] * n
    diff = total - (base * n)
    parcelas[-1] = (parcelas[-1] + diff).quantize(Decimal("0.01"))
    return parcelas


@login_required
def imposto_list(request):
    """Lista de impostos com filtros e KPIs.

    Por defeito mostra os pais (PARCELADO + MENSAL_VIGENTE + PONTUAL),
    mas inclui as prestações quando o filtro `?modo=parcelas`.
    """
    qs = Imposto.objects.select_related("fornecedor", "parent")

    modo = (request.GET.get("modo") or "principais").strip()
    if modo == "parcelas":
        qs = qs.filter(parent__isnull=False)
    elif modo == "todos":
        pass
    else:  # principais
        qs = qs.filter(parent__isnull=True)

    tipo = (request.GET.get("tipo") or "").strip()
    if tipo:
        qs = qs.filter(tipo=tipo)
    status = (request.GET.get("status") or "").strip()
    if status:
        qs = qs.filter(status=status)
    ano = (request.GET.get("ano") or "").strip()
    if ano.isdigit():
        qs = qs.filter(periodo_ano=int(ano))

    qs = qs.order_by("-data_vencimento", "-id")

    # KPIs (todos os impostos do ano corrente, ignorando filtros)
    today = timezone.localdate()
    base_kpi = Imposto.objects.filter(
        parent__isnull=True,  # só pais para não duplicar
        periodo_ano=today.year,
    )
    agg = base_kpi.aggregate(
        total_pendente=Sum(
            "valor", filter=Q(status=Imposto.STATUS_PENDENTE),
        ),
        total_pago=Sum("valor", filter=Q(status=Imposto.STATUS_PAGO)),
        total_atraso=Sum(
            "valor", filter=Q(status=Imposto.STATUS_EM_ATRASO),
        ),
        n_pendente=Count("id", filter=Q(status=Imposto.STATUS_PENDENTE)),
        n_pago=Count("id", filter=Q(status=Imposto.STATUS_PAGO)),
        n_atraso=Count("id", filter=Q(status=Imposto.STATUS_EM_ATRASO)),
    )
    kpis = {
        "total_pendente": agg["total_pendente"] or Decimal("0"),
        "total_pago": agg["total_pago"] or Decimal("0"),
        "total_atraso": agg["total_atraso"] or Decimal("0"),
        "n_pendente": agg["n_pendente"] or 0,
        "n_pago": agg["n_pago"] or 0,
        "n_atraso": agg["n_atraso"] or 0,
    }

    return render(request, "accounting/imposto_list.html", {
        "impostos": qs,
        "kpis": kpis,
        "filters": {
            "modo": modo, "tipo": tipo, "status": status, "ano": ano or today.year,
        },
        "tipo_choices": Imposto.TIPO_CHOICES,
        "status_choices": Imposto.STATUS_CHOICES,
    })


@login_required
def imposto_create(request):
    if request.method == "POST":
        form = ImpostoForm(request.POST, request.FILES)
        if form.is_valid():
            imposto = form.save(commit=False)
            imposto.created_by = request.user
            with transaction.atomic():
                imposto.save()
                # PARCELADO: gerar N filhos
                if imposto.modalidade == Imposto.MODALIDADE_PARCELADO:
                    n = form.cleaned_data["n_prestacoes"]
                    primeira = form.cleaned_data["primeira_prestacao_em"]
                    parcelas = _split_evenly(imposto.valor, n)
                    for i, valor_parcela in enumerate(parcelas, start=1):
                        venc = _add_months(primeira, i - 1)
                        Imposto.objects.create(
                            nome=f"{imposto.nome} — {i}/{n}",
                            tipo=imposto.tipo,
                            modalidade=Imposto.MODALIDADE_PARCELADO,
                            fornecedor=imposto.fornecedor,
                            periodo_ano=venc.year,
                            periodo_mes=venc.month,
                            valor=valor_parcela,
                            mb_entidade=imposto.mb_entidade,
                            mb_referencia=imposto.mb_referencia,
                            data_vencimento=venc,
                            status=Imposto.STATUS_PENDENTE,
                            parent=imposto,
                            parcela_numero=i,
                            parcela_total=n,
                            created_by=request.user,
                        )
                    imposto.parcela_total = n
                    imposto.save(update_fields=["parcela_total", "updated_at"])
                    messages.success(
                        request,
                        f"Imposto criado com {n} prestações.",
                    )
                else:
                    messages.success(
                        request, f"Imposto '{imposto.nome}' criado.",
                    )
            return redirect("accounting:imposto_list")
    else:
        form = ImpostoForm(initial={
            "periodo_ano": timezone.localdate().year,
            "periodo_mes": timezone.localdate().month,
        })
    return render(request, "accounting/imposto_form.html", {
        "form": form, "is_create": True,
    })


@login_required
def imposto_edit(request, pk):
    imposto = get_object_or_404(Imposto, pk=pk)
    if request.method == "POST":
        form = ImpostoForm(request.POST, request.FILES, instance=imposto)
        if form.is_valid():
            form.save()
            # Se actualizámos uma prestação, recalcula status do pai
            if imposto.parent_id:
                imposto.parent.update_status_from_parcelas()
            messages.success(request, "Imposto actualizado.")
            return redirect("accounting:imposto_list")
    else:
        form = ImpostoForm(instance=imposto)
    return render(request, "accounting/imposto_form.html", {
        "form": form, "imposto": imposto, "is_create": False,
    })


@login_required
@require_http_methods(["POST"])
def imposto_mark_paid(request, pk):
    """Marca imposto como PAGO + cria Bill espelho para entrar no
    fluxo de caixa do mês."""
    imposto = get_object_or_404(Imposto, pk=pk)
    today = timezone.localdate()
    if imposto.status == Imposto.STATUS_PAGO:
        messages.info(request, "Imposto já estava marcado como pago.")
        return redirect("accounting:imposto_list")
    if imposto.is_parent and imposto.parcelas.exists():
        messages.error(
            request,
            "Não marca o pai PARCELADO directamente — paga prestação por "
            "prestação. O pai actualiza-se sozinho.",
        )
        return redirect("accounting:imposto_list")

    with transaction.atomic():
        imposto.status = Imposto.STATUS_PAGO
        imposto.data_pagamento = today
        imposto.save(update_fields=[
            "status", "data_pagamento", "updated_at",
        ])
        # Bill espelho — só cria se ainda não existe
        if not imposto.bill_espelho_id:
            cat, _ = ExpenseCategory.objects.get_or_create(
                code="IMP",
                defaults={
                    "name": "Impostos e Contribuições",
                    "nature": ExpenseCategory.NATURE_FIXO,
                    "icon": "landmark",
                    "sort_order": 50,
                },
            )
            cc = CostCenter.objects.filter(
                type=CostCenter.TYPE_ADMIN,
            ).first()
            if not cc:
                cc, _ = CostCenter.objects.get_or_create(
                    code="ADMIN",
                    defaults={
                        "name": "Administrativo",
                        "type": CostCenter.TYPE_ADMIN,
                    },
                )
            if cat and cc:
                bill = Bill.objects.create(
                    description=f"[Imposto] {imposto.nome}",
                    fornecedor=imposto.fornecedor,
                    supplier=(
                        imposto.fornecedor.name
                        if imposto.fornecedor
                        else f"AT — {imposto.get_tipo_display()}"
                    ),
                    supplier_nif=(
                        imposto.fornecedor.nif if imposto.fornecedor else ""
                    ),
                    category=cat,
                    cost_center=cc,
                    amount_net=imposto.valor,
                    iva_rate=Decimal("0"),
                    amount_total=imposto.valor,
                    issue_date=imposto.data_vencimento,
                    due_date=imposto.data_vencimento,
                    paid_date=today,
                    paid_amount=imposto.valor,
                    status=Bill.STATUS_PAID,
                    recurrence=Bill.RECURRENCE_NONE,
                    notes=(
                        f"Bill espelho gerada automaticamente do imposto "
                        f"#{imposto.pk}"
                    ),
                    created_by=request.user,
                )
                imposto.bill_espelho = bill
                imposto.save(update_fields=["bill_espelho", "updated_at"])
        # Se for prestação, recalcula estado do pai
        if imposto.parent_id:
            imposto.parent.update_status_from_parcelas()

    messages.success(
        request,
        f"Imposto '{imposto.nome}' marcado como PAGO. "
        f"Bill #{imposto.bill_espelho_id or '?'} criada.",
    )
    return redirect("accounting:imposto_list")


@login_required
@require_http_methods(["POST"])
def imposto_anular(request, pk):
    """Anula um imposto (status=ANULADO). Não apaga histórico."""
    imposto = get_object_or_404(Imposto, pk=pk)
    if imposto.status == Imposto.STATUS_PAGO:
        messages.error(
            request, "Não é possível anular um imposto já pago.",
        )
        return redirect("accounting:imposto_list")
    imposto.status = Imposto.STATUS_ANULADO
    imposto.save(update_fields=["status", "updated_at"])
    messages.success(request, f"Imposto '{imposto.nome}' anulado.")
    return redirect("accounting:imposto_list")


@login_required
@require_http_methods(["POST"])
def imposto_ocr_extract(request):
    """OCR de guia de pagamento de imposto (AT, SS, IUC, etc.).

    Recebe 1+ ficheiros em request.FILES.getlist('file').
    Devolve dados extraídos + sugestão de fornecedor (Estado) já
    cadastrado, se houver.
    """
    from .services_ocr_imposto import extract_imposto_data

    files = request.FILES.getlist("file") or []
    if not files:
        return JsonResponse(
            {"success": False, "error": "Sem ficheiro(s)."}, status=400,
        )

    # Para guias usamos apenas o primeiro (cada guia = 1 imposto).
    # Se houver mais, ignoramos os restantes mas dizemos.
    main_file = files[0]
    try:
        data = extract_imposto_data(main_file)
    except Exception as e:
        return JsonResponse(
            {"success": False, "error": str(e)}, status=500,
        )

    # Sugestão de fornecedor (entidade credora — AT, SS, etc.)
    suggested_fornecedor = None
    entidade = (data.get("entidade_credora") or "").strip().upper()
    if entidade:
        match = None
        if entidade in ("AT", "AUTORIDADE TRIBUTÁRIA", "AUTORIDADE TRIBUTARIA"):
            match = Fornecedor.objects.filter(
                Q(name__icontains="Autoridade Tributária") |
                Q(name__icontains="Autoridade Tributaria"),
                tipo="ESTADO",
            ).first()
        elif entidade in ("SS", "SEGURANCA SOCIAL", "SEGURANÇA SOCIAL"):
            match = Fornecedor.objects.filter(
                name__icontains="Segurança Social",
                tipo="ESTADO",
            ).first()
        if not match:
            match = Fornecedor.objects.filter(
                tipo="ESTADO", name__icontains=entidade,
            ).first()
        if match:
            suggested_fornecedor = {"id": match.id, "name": match.name}

    # Sugestão de modalidade — se OCR detectou prestações, é PARCELADO
    suggested_modalidade = None
    pn = data.get("parcela_numero")
    pt = data.get("parcela_total")
    if (pn and pt) or data.get("numero_plano"):
        suggested_modalidade = "PARCELADO"
    elif data.get("periodo_mes"):
        suggested_modalidade = "MENSAL_VIGENTE"
    elif data.get("periodo_ano"):
        suggested_modalidade = "PONTUAL"

    return JsonResponse({
        "success": True,
        "data": data,
        "suggested_fornecedor": suggested_fornecedor,
        "suggested_modalidade": suggested_modalidade,
        "skipped_files": [f.name for f in files[1:]] if len(files) > 1 else [],
    })
