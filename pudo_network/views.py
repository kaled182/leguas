"""Portal do lojista (PUDO) — login/logout + dashboard placeholder.

Espelha o padrão de `customauth.empresa_auth_views` (sessão própria, fora do
`User` Django). A operação real (custódia, receção, POD) entra nas Fases 1-2;
por agora o dashboard é um placeholder autenticado.
"""
import uuid as uuid_lib
from functools import wraps

from django.contrib import messages
from django.db.models import Count, Sum
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import (
    PudoAccess,
    PudoCustodyPackage,
    PudoStoreBillingLine,
    PudoTransaction,
)
from .services import (
    PudoServiceError,
    deliver_with_doc,
    deliver_with_otp,
    mark_for_return,
    process_handshake,
    process_signed_handshake,
    send_pickup_otp,
)


def pudo_login_required(view_func):
    """Aceita sessão de PUDO autenticada OU admin Django.

    Expõe `request.pudo_access` e `request.pudo_store` na view.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.session.get("is_pudo_authenticated"):
            access = (
                PudoAccess.objects.select_related("store")
                .filter(id=request.session.get("pudo_access_id"), is_active=True)
                .first()
            )
            if access:
                request.pudo_access = access
                request.pudo_store = access.store
                return view_func(request, *args, **kwargs)
        if request.user.is_authenticated and (
            request.user.is_staff or request.user.is_superuser
        ):
            request.pudo_access = None
            request.pudo_store = None
            return view_func(request, *args, **kwargs)
        return redirect("pudo_network:login")
    return wrapper


@require_http_methods(["GET", "POST"])
def pudo_login(request):
    if request.session.get("is_pudo_authenticated"):
        return redirect("pudo_network:dashboard")

    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""
        if not username or not password:
            messages.error(request, "Username e password obrigatórios.")
            return render(request, "pudo_network/login.html")

        access = (
            PudoAccess.objects.select_related("store")
            .filter(username__iexact=username, is_active=True)
            .first()
        )
        if not access or not access.check_password(password):
            messages.error(request, "Credenciais inválidas.")
            return render(request, "pudo_network/login.html")

        access.last_login = timezone.now()
        access.save(update_fields=["last_login"])
        request.session["is_pudo_authenticated"] = True
        request.session["pudo_access_id"] = access.id
        request.session["pudo_store_id"] = access.store_id
        request.session["pudo_store_numero"] = access.store.numero
        request.session["pudo_papel"] = access.papel

        messages.success(request, f"Bem-vindo, {access.store.nome}!")
        return redirect("pudo_network:dashboard")

    return render(request, "pudo_network/login.html")


def pudo_logout(request):
    for k in (
        "is_pudo_authenticated", "pudo_access_id", "pudo_store_id",
        "pudo_store_numero", "pudo_papel",
    ):
        request.session.pop(k, None)
    messages.success(request, "Sessão terminada.")
    return redirect("pudo_network:login")


@pudo_login_required
def pudo_dashboard(request):
    store = request.pudo_store
    ctx = {
        "store": store, "access": request.pudo_access,
        "em_stock": 0, "expirados": 0, "aguarda_dev": 0,
        "ocupacao_pct": None, "ganhos_mes": None,
    }
    if store is not None:
        now = timezone.now()
        counts = dict(
            PudoCustodyPackage.objects.filter(store=store)
            .values_list("status")
            .annotate(n=Count("id"))
        )
        ctx["em_stock"] = counts.get(PudoCustodyPackage.EM_STOCK_PUDO, 0)
        ctx["expirados"] = counts.get(PudoCustodyPackage.EXPIRADO, 0)
        ctx["aguarda_dev"] = counts.get(
            PudoCustodyPackage.AGUARDA_DEVOLUCAO, 0,
        )
        if store.capacidade_max:
            ctx["ocupacao_pct"] = round(
                100 * ctx["em_stock"] / store.capacidade_max,
            )
        access = request.pudo_access
        if access is None or access.pode_ver_financeiro:
            ctx["ganhos_mes"] = (
                PudoStoreBillingLine.objects
                .filter(store=store, emitted_at__year=now.year,
                        emitted_at__month=now.month)
                .aggregate(t=Sum("valor"))["t"] or 0
            )
    return render(request, "pudo_network/dashboard.html", ctx)


def _actor(request):
    """Identidade do actor para o evento de custódia."""
    if getattr(request, "pudo_access", None):
        return request.pudo_access.username, "PUDO"
    return (request.user.get_username() if request.user.is_authenticated
            else "web"), "ADMIN"


@pudo_login_required
def pudo_reception(request):
    """Receção de pacotes no balcão (leitor de código de barras = teclado).

    GET  → ecrã de receção (input com foco, Alpine trata o loop de scans).
    POST → 1 scan = 1 handshake idempotente (uuid do browser). Devolve JSON.
    """
    store = request.pudo_store
    if store is None:
        # Sessão admin sem loja associada não tem balcão próprio.
        messages.info(request, "Selecione um PUDO no admin para rececionar.")
        return redirect("pudo_network:dashboard")

    if request.method == "POST":
        tracking_ref = (request.POST.get("tracking_ref") or "").strip()
        client_uuid = (request.POST.get("uuid") or "").strip()
        if not tracking_ref:
            return JsonResponse(
                {"success": False, "error": "Código vazio."}, status=400,
            )
        actor, actor_type = _actor(request)
        result = process_handshake(
            uuid=client_uuid or uuid_lib.uuid4(),
            tipo=PudoTransaction.Tipo.ENTREGA,
            store=store, tracking_ref=tracking_ref,
            origin=PudoTransaction.Origin.PUDO_WEB,
            actor=actor, actor_type=actor_type, payload={"origin": "portal"},
        )
        pkg = result.package
        return JsonResponse({
            "success": True,
            "idempotent": result.idempotent,
            "tracking_ref": pkg.tracking_ref if pkg else tracking_ref,
            "status": pkg.status if pkg else None,
        }, status=200)

    return render(request, "pudo_network/reception.html", {
        "store": store,
        "access": request.pudo_access,
    })


def _require_store(request):
    store = request.pudo_store
    if store is None:
        raise Http404("Sessão sem PUDO associado.")
    return store


def _get_package(request, pk):
    store = _require_store(request)
    return get_object_or_404(PudoCustodyPackage, pk=pk, store=store)


@pudo_login_required
def pudo_stock(request):
    """Lista de pacotes em stock no PUDO (prontos para levantamento)."""
    store = _require_store(request)
    packages = (
        PudoCustodyPackage.objects
        .filter(store=store, status=PudoCustodyPackage.EM_STOCK_PUDO)
        .order_by("aging_deadline", "-received_at")
    )
    return render(request, "pudo_network/stock.html", {
        "store": store, "access": request.pudo_access,
        "packages": packages, "now": timezone.now(),
    })


@pudo_login_required
def pudo_pickup(request, pk):
    """Detalhe/POD de um pacote. POST com `action` devolve JSON (Alpine)."""
    package = _get_package(request, pk)
    actor, actor_type = _actor(request)

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        try:
            if action == "send_otp":
                otp = send_pickup_otp(
                    package, actor=actor, actor_type=actor_type,
                )
                return JsonResponse({"success": True, "sent_to": otp.phone})
            if action == "deliver_otp":
                deliver_with_otp(
                    package, request.POST.get("code", ""),
                    levantador_nome=request.POST.get("nome", ""),
                    actor=actor, actor_type=actor_type,
                )
                return JsonResponse({"success": True, "status": package.status})
            if action == "deliver_doc":
                deliver_with_doc(
                    package, request.POST.get("doc", ""),
                    levantador_nome=request.POST.get("nome", ""),
                    terceiro=request.POST.get("terceiro") == "1",
                    actor=actor, actor_type=actor_type,
                )
                return JsonResponse({"success": True, "status": package.status})
            if action == "return":
                mark_for_return(
                    package, request.POST.get("motivo", ""),
                    actor=actor, actor_type=actor_type,
                )
                return JsonResponse({"success": True, "status": package.status})
        except PudoServiceError as exc:
            return JsonResponse(
                {"success": False, "error": exc.message}, status=exc.status,
            )
        return JsonResponse(
            {"success": False, "error": "Ação desconhecida."}, status=400,
        )

    return render(request, "pudo_network/pickup.html", {
        "store": package.store, "access": request.pudo_access,
        "package": package,
        "motivos": PudoCustodyPackage.MotivoDevolucao.choices,
    })


@pudo_login_required
def pudo_billing(request):
    """Extrato do lojista — LÊ o ledger imutável. Só o papel DONO vê valores."""
    store = _require_store(request)
    access = request.pudo_access
    if access is not None and not access.pode_ver_financeiro:
        messages.error(request, "Sem permissão para ver o financeiro.")
        return redirect("pudo_network:dashboard")

    lines = PudoStoreBillingLine.objects.filter(store=store)
    desde = (request.GET.get("desde") or "").strip()
    ate = (request.GET.get("ate") or "").strip()
    if desde:
        lines = lines.filter(emitted_at__date__gte=desde)
    if ate:
        lines = lines.filter(emitted_at__date__lte=ate)

    agg = lines.aggregate(total=Sum("valor"), n=Count("id"))
    return render(request, "pudo_network/billing.html", {
        "store": store, "access": access,
        "lines": lines.order_by("-emitted_at")[:500],
        "total": agg["total"] or 0, "n": agg["n"] or 0,
        "desde": desde, "ate": ate,
    })


@pudo_login_required
def pudo_scan_offline(request):
    """Receção de um QR offline ASSINADO pelo estafeta (redundância/sem rede).

    O PUDO lê o QR (que o estafeta gerou offline) e submete o JSON. O servidor
    verifica assinatura + TTL + nonce (uso-único) e processa. O estafeta é
    identificado pelo próprio payload (o PUDO não tem o token dele).

    GET  → ecrã de leitura.
    POST → verifica e processa; devolve JSON.
    """
    store = _require_store(request)
    if request.method == "POST":
        import json as _json
        raw = (request.POST.get("payload") or "").strip()
        try:
            data = _json.loads(raw) if raw else {}
        except ValueError:
            return JsonResponse(
                {"success": False, "error": "QR inválido (JSON)."}, status=400,
            )
        # O PUDO só pode rececionar para a SUA loja.
        if str(data.get("pudo") or "").strip() not in (
            store.numero, str(store.id),
        ):
            return JsonResponse(
                {"success": False, "error": "QR destinado a outro PUDO."},
                status=409,
            )
        try:
            res = process_signed_handshake(
                data, origin=PudoTransaction.Origin.PUDO_WEB,
            )
        except PudoServiceError as exc:
            return JsonResponse(
                {"success": False, "error": exc.message}, status=exc.status,
            )
        return JsonResponse({
            "success": True, "idempotent": res.idempotent,
            "tracking_ref": res.package.tracking_ref if res.package else None,
            "status": res.package.status if res.package else None,
        }, status=200)

    return render(request, "pudo_network/scan_offline.html", {
        "store": store, "access": request.pudo_access,
    })
