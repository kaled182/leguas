"""Pesquisa global da topbar: só leitura, com as regras de acesso do perfil."""
import re

from django.http import JsonResponse
from django.urls import reverse

from .permissions import is_gestao, operator_can_access

LIMIT = 5


def packages(q):
    from settlements.models import CainiaoOperationTask

    waybills = (
        CainiaoOperationTask.objects.filter(waybill_number__istartswith=q)
        .values_list("waybill_number", flat=True).distinct()[:LIMIT]
    )
    return [
        {"label": waybill, "url": reverse("package-360", args=[waybill])}
        for waybill in waybills
    ]


def drivers(q):
    from drivers_app.central_views import _driver_search_q
    from drivers_app.models import DriverProfile

    found = DriverProfile.objects.filter(_driver_search_q(q)).distinct()[:LIMIT]
    return [
        {
            "label": driver.nome_completo, "note": driver.apelido or "",
            "url": reverse("drivers_app:driver_portal", args=[driver.id]),
        }
        for driver in found
    ]


def postal_codes(q):
    if not re.fullmatch(r"\d{4}", q):
        return []
    return [{"label": q, "url": f"{reverse('cainiao-packages-page')}?cp4={q}"}]


def partners(q):
    from core.models import Partner

    found = Partner.objects.filter(name__icontains=q)[:LIMIT]
    return [
        {"label": partner.name, "url": reverse("core:partner-detail", args=[partner.id])}
        for partner in found
    ]


def contracts(q):
    from contracts.models import GeneratedContract

    found = (
        GeneratedContract.objects.filter(driver__nome_completo__icontains=q)
        .select_related("driver")[:LIMIT]
    )
    return [
        {
            "label": contract.driver.nome_completo,
            "url": reverse("contracts:generated_contract_view", args=[contract.pk]),
        }
        for contract in found
    ]


SOURCES = (
    ("Pacotes", packages), ("Motoristas", drivers), ("CP4", postal_codes),
    ("Clientes e plataformas", partners), ("Contratos", contracts),
)


def global_search(request):
    q = request.GET.get("q", "").strip()
    if len(q) < 2:
        return JsonResponse({"groups": []})
    gestao = is_gestao(request.user)
    groups = []
    for label, source in SOURCES:
        results = [
            result for result in source(q)
            if gestao or operator_can_access(result["url"].split("?")[0])
        ]
        if results:
            groups.append({"label": label, "results": results})
    return JsonResponse({"groups": groups})
