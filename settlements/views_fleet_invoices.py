"""Lista global das faturas de frotas subcontratadas, só de leitura."""
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render
from django.urls import reverse

from core.templatetags.ui import eur
from drivers_app.models import EmpresaParceira

from .models import FleetInvoice

PAGE_SIZE = 25
STATUS_TONES = {
    "RASCUNHO": "neutral", "CALCULADO": "brand", "APROVADO": "warning",
    "PAGO": "success", "CANCELADO": "danger",
}
COLUMNS = [
    {"key": "numero", "label": "Número"},
    {"key": "empresa", "label": "Frota"},
    {"key": "periodo", "label": "Período"},
    {"key": "estado", "label": "Estado"},
    {"key": "total", "label": "Total", "numeric": True},
]


def filtered_invoices(params):
    invoices = FleetInvoice.objects.select_related("empresa").order_by("-periodo_fim", "-id")
    if params.get("empresa", "").isdigit():
        invoices = invoices.filter(empresa_id=params["empresa"])
    if params.get("estado"):
        invoices = invoices.filter(status=params["estado"])
    if params.get("de"):
        invoices = invoices.filter(periodo_fim__gte=params["de"])
    if params.get("ate"):
        invoices = invoices.filter(periodo_inicio__lte=params["ate"])
    return invoices


def invoice_row(invoice):
    return {
        "cells": [
            {"text": invoice.numero},
            {"text": invoice.empresa.nome},
            {"text": f"{invoice.periodo_inicio:%d/%m/%Y} a {invoice.periodo_fim:%d/%m/%Y}"},
            {"text": invoice.get_status_display(), "tone": STATUS_TONES.get(invoice.status, "neutral")},
            {"text": eur(invoice.total_com_iva), "numeric": True},
        ],
        "action_url": reverse("fleet-invoice-pdf", args=[invoice.id]),
        "action_label": "PDF",
    }


@login_required
def fleet_invoice_list(request):
    params = request.GET
    page = Paginator(filtered_invoices(params), PAGE_SIZE).get_page(params.get("page"))
    empresas = EmpresaParceira.objects.order_by("nome").values_list("id", "nome")
    filters = [
        {
            "kind": "select", "name": "empresa", "label": "Frota", "value": params.get("empresa", ""),
            "options": [{"value": "", "label": "Todas"}] + [
                {"value": str(pk), "label": nome} for pk, nome in empresas
            ],
        },
        {
            "kind": "select", "name": "estado", "label": "Estado", "value": params.get("estado", ""),
            "options": [{"value": "", "label": "Todos"}] + [
                {"value": value, "label": label} for value, label in FleetInvoice.STATUS_CHOICES
            ],
        },
        {"kind": "date", "name": "de", "label": "De", "value": params.get("de", "")},
        {"kind": "date", "name": "ate", "label": "Até", "value": params.get("ate", "")},
    ]
    return render(request, "settlements/fleet_invoice_list.html", {
        "filters": filters, "columns": COLUMNS, "page": page,
        "rows": [invoice_row(invoice) for invoice in page.object_list],
        "total": page.paginator.count,
    })
