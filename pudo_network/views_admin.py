"""Gestão interna da Rede PUDO (staff) — no padrão visual do dashboard.

Substitui o uso do Django admin para o fluxo do dia-a-dia: listar/criar/editar
PUDOs e gerir credenciais do lojista. Páginas herdam `paack_dashboard/base.html`.
"""
import secrets
import string

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .forms import PudoStoreForm
from .models import PudoAccess, PudoCustodyPackage, PudoStore, PudoStoreBillingLine


def _gen_password(length=12):
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


@staff_member_required
def gestao_list(request):
    qs = PudoStore.objects.all().order_by("numero")
    estado = (request.GET.get("estado") or "").strip()
    q = (request.GET.get("q") or "").strip()
    if estado:
        qs = qs.filter(status=estado)
    if q:
        qs = qs.filter(Q(nome__icontains=q) | Q(numero__icontains=q))

    # KPIs globais
    stock_por_loja = dict(
        PudoCustodyPackage.objects
        .filter(status=PudoCustodyPackage.EM_STOCK_PUDO)
        .values_list("store").annotate(n=Count("id"))
    )
    stores = list(qs)
    for s in stores:
        s.em_stock = stock_por_loja.get(s.id, 0)

    return render(request, "pudo_network/gestao/list.html", {
        "stores": stores,
        "total": PudoStore.objects.count(),
        "ativos": PudoStore.objects.filter(status=PudoStore.Status.ATIVO).count(),
        "em_stock_total": sum(stock_por_loja.values()),
        "estado": estado, "q": q,
        "status_choices": PudoStore.Status.choices,
    })


@staff_member_required
def gestao_create(request):
    if request.method == "POST":
        form = PudoStoreForm(request.POST)
        if form.is_valid():
            store = form.save()
            messages.success(request, f"PUDO {store.numero} criado.")
            return redirect("pudo_network:gestao_detail", pk=store.pk)
    else:
        form = PudoStoreForm()
    return render(request, "pudo_network/gestao/form.html", {
        "form": form, "modo": "novo",
    })


@staff_member_required
def gestao_edit(request, pk):
    store = get_object_or_404(PudoStore, pk=pk)
    if request.method == "POST":
        form = PudoStoreForm(request.POST, instance=store)
        if form.is_valid():
            form.save()
            messages.success(request, "PUDO atualizado.")
            return redirect("pudo_network:gestao_detail", pk=store.pk)
    else:
        form = PudoStoreForm(instance=store)
    return render(request, "pudo_network/gestao/form.html", {
        "form": form, "modo": "editar", "store": store,
    })


@staff_member_required
def gestao_detail(request, pk):
    store = get_object_or_404(PudoStore, pk=pk)
    now = timezone.now()
    counts = dict(
        PudoCustodyPackage.objects.filter(store=store)
        .values_list("status").annotate(n=Count("id"))
    )
    ganhos_mes = (
        PudoStoreBillingLine.objects
        .filter(store=store, emitted_at__year=now.year, emitted_at__month=now.month)
        .aggregate(t=Sum("valor"))["t"] or 0
    )
    recentes = (
        PudoCustodyPackage.objects.filter(store=store)
        .order_by("-created_at")[:10]
    )
    return render(request, "pudo_network/gestao/detail.html", {
        "store": store,
        "access": getattr(store, "access", None),
        "em_stock": counts.get(PudoCustodyPackage.EM_STOCK_PUDO, 0),
        "entregues": counts.get(PudoCustodyPackage.ENTREGUE_CLIENTE, 0),
        "expirados": counts.get(PudoCustodyPackage.EXPIRADO, 0),
        "aguarda_dev": counts.get(PudoCustodyPackage.AGUARDA_DEVOLUCAO, 0),
        "ganhos_mes": ganhos_mes,
        "recentes": recentes,
        "papeis": PudoAccess.Papel.choices,
    })


@staff_member_required
@require_http_methods(["POST"])
def gestao_access(request, pk):
    """Gere as credenciais do lojista (criar/reset/toggle/remover)."""
    store = get_object_or_404(PudoStore, pk=pk)
    access = getattr(store, "access", None)
    action = (request.POST.get("action") or "").strip()

    if action == "create" and access is None:
        username = (request.POST.get("username") or "").strip().lower()
        papel = request.POST.get("papel") or PudoAccess.Papel.DONO
        if not username:
            messages.error(request, "Username obrigatório.")
        elif PudoAccess.objects.filter(username__iexact=username).exists():
            messages.error(request, "Username já existe.")
        else:
            pw = _gen_password()
            access = PudoAccess(
                store=store, username=username, papel=papel,
                email=store.email or "", created_by=request.user,
            )
            access.set_password(pw)
            access.save()
            messages.success(
                request, f"Acesso criado — username: {username} · password: {pw}",
            )
    elif action == "reset" and access:
        pw = _gen_password()
        access.set_password(pw)
        access.save(update_fields=["password", "updated_at"])
        messages.success(request, f"Nova password de {access.username}: {pw}")
    elif action == "toggle" and access:
        access.is_active = not access.is_active
        access.save(update_fields=["is_active", "updated_at"])
        messages.success(
            request,
            "Acesso reativado." if access.is_active else "Acesso desativado.",
        )
    elif action == "delete" and access:
        access.delete()
        messages.success(request, "Acesso removido.")

    return redirect("pudo_network:gestao_detail", pk=store.pk)
