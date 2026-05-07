"""Endpoints de Fornecedor e FornecedorTag.

Cobre:
  - CRUD de Fornecedor (list, create, edit, delete soft via is_active)
  - CRUD ligeiro de FornecedorTag
  - Endpoint JSON para autocomplete na Nova Conta a Pagar
  - Endpoint JSON de detalhe (devolve campos para auto-fill no Bill form)
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .forms import FornecedorForm, FornecedorTagForm
from .models import Bill, Fornecedor, FornecedorTag


@login_required
def fornecedor_list(request):
    """Lista de fornecedores com filtros (nome/NIF, tag, ativo) e KPIs."""
    qs = (
        Fornecedor.objects
        .prefetch_related("tags")
        .annotate(
            n_bills=Count("bills"),
            total_pago=Sum(
                "bills__amount_total",
                filter=Q(bills__status=Bill.STATUS_PAID),
            ),
        )
    )

    # Filtros
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(nif__icontains=q))

    tag_slug = (request.GET.get("tag") or "").strip()
    if tag_slug:
        qs = qs.filter(tags__slug=tag_slug)

    show = (request.GET.get("show") or "active").strip()
    if show == "active":
        qs = qs.filter(is_active=True)
    elif show == "inactive":
        qs = qs.filter(is_active=False)

    qs = qs.order_by("name")

    # KPIs (sobre todos, não só filtrados — overview rápido)
    total_active = Fornecedor.objects.filter(is_active=True).count()
    total_inactive = Fornecedor.objects.filter(is_active=False).count()
    total_with_iva_dedutivel = Fornecedor.objects.filter(
        is_active=True, iva_dedutivel=True,
    ).count()

    context = {
        "fornecedores": qs,
        "tags": FornecedorTag.objects.filter(is_active=True),
        "filters": {"q": q, "tag": tag_slug, "show": show},
        "kpis": {
            "active": total_active,
            "inactive": total_inactive,
            "iva_dedutivel": total_with_iva_dedutivel,
        },
    }
    return render(request, "accounting/fornecedor_list.html", context)


@login_required
def fornecedor_create(request):
    if request.method == "POST":
        form = FornecedorForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.created_by = request.user
            obj.save()
            form.save_m2m()
            messages.success(
                request, f"Fornecedor '{obj.name}' criado com sucesso.",
            )
            # Se veio de uma sugestão OCR (?from=ocr), volta para a Bill
            if request.GET.get("from") == "ocr":
                return redirect("accounting:bill_create")
            return redirect("accounting:fornecedor_list")
    else:
        # Pré-preenche a partir de query params (ex: vindo do OCR no Bill form)
        initial = {}
        for key in ("name", "nif", "default_iva_rate"):
            v = (request.GET.get(key) or "").strip()
            if v:
                initial[key] = v
        if request.GET.get("iva_dedutivel") in ("1", "true", "True"):
            initial["iva_dedutivel"] = True
        form = FornecedorForm(initial=initial)
    return render(request, "accounting/fornecedor_form.html", {
        "form": form, "is_create": True,
        "from_ocr": request.GET.get("from") == "ocr",
    })


@login_required
def fornecedor_edit(request, pk):
    obj = get_object_or_404(Fornecedor, pk=pk)
    if request.method == "POST":
        form = FornecedorForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Fornecedor atualizado.")
            return redirect("accounting:fornecedor_list")
    else:
        form = FornecedorForm(instance=obj)
    return render(request, "accounting/fornecedor_form.html", {
        "form": form, "fornecedor": obj, "is_create": False,
    })


@login_required
@require_http_methods(["POST"])
def fornecedor_toggle_active(request, pk):
    """Soft-delete: alterna is_active. Bloqueado se houver Bills PROTECT."""
    obj = get_object_or_404(Fornecedor, pk=pk)
    obj.is_active = not obj.is_active
    obj.save(update_fields=["is_active", "updated_at"])
    state = "ativado" if obj.is_active else "desativado"
    messages.success(request, f"Fornecedor '{obj.name}' {state}.")
    return redirect("accounting:fornecedor_list")


# ── Tags ─────────────────────────────────────────────────────────────────

@login_required
def fornecedor_tag_list(request):
    tags = FornecedorTag.objects.annotate(
        n_fornecedores=Count("fornecedores"),
    ).order_by("name")
    if request.method == "POST":
        form = FornecedorTagForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Tag criada.")
            return redirect("accounting:fornecedor_tag_list")
    else:
        form = FornecedorTagForm()
    return render(request, "accounting/fornecedor_tag_list.html", {
        "tags": tags, "form": form,
    })


@login_required
@require_http_methods(["POST"])
def fornecedor_tag_delete(request, pk):
    tag = get_object_or_404(FornecedorTag, pk=pk)
    tag.delete()
    messages.success(request, f"Tag '{tag.name}' apagada.")
    return redirect("accounting:fornecedor_tag_list")


# ── APIs JSON ────────────────────────────────────────────────────────────

@login_required
def fornecedor_search_api(request):
    """Autocomplete: ?q=texto → top 20 matches por nome/NIF."""
    q = (request.GET.get("q") or "").strip()
    qs = Fornecedor.objects.filter(is_active=True)
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(nif__icontains=q))
    results = [
        {
            "id": f.id,
            "name": f.name,
            "nif": f.nif,
            "label": f"{f.name}" + (f" · NIF {f.nif}" if f.nif else ""),
        }
        for f in qs.order_by("name")[:20]
    ]
    return JsonResponse({"results": results})


@login_required
def fornecedor_detail_api(request, pk):
    """Detalhes para auto-fill do Bill form. Só campos que pré-preenchem."""
    f = get_object_or_404(
        Fornecedor.objects.select_related(
            "default_categoria", "default_centro_custo",
        ),
        pk=pk,
    )
    return JsonResponse({
        "id": f.id,
        "name": f.name,
        "nif": f.nif,
        "iva_rate": str(f.default_iva_rate),
        "iva_dedutivel": f.iva_dedutivel,
        "categoria_id": f.default_categoria_id,
        "centro_custo_id": f.default_centro_custo_id,
        "recorrencia": f.recorrencia_default,
        "forma_pagamento": f.forma_pagamento,
        "iban": f.iban,
        "mb_entidade": f.mb_entidade,
        "mb_referencia": f.mb_referencia,
        "dia_vencimento": f.dia_vencimento,
    })
