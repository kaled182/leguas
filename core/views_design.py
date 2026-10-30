"""Página interna do sistema de design, só para staff."""
from django.core.paginator import Paginator
from django.shortcuts import render
from django.utils import timezone

from core.templatetags.ui import eur, pct, pt_int

COLOR_TOKENS = (
    "--brand-purple", "--brand-purple-night", "--brand-purple-wing",
    "--brand-orange", "--brand-orange-dark", "--brand-lilac", "--brand-cream",
    "--ink", "--muted", "--line", "--success", "--danger", "--warning", "--neutral",
)
STATUSES = ("Delivered", "Attempt Failure", "Driver_received", "Assigned", "Wrong HUB", "Exception")
DEMO_DRIVERS = (
    ("Ana Silva", "Fão", 1284), ("Bruno Costa", "Válega", 1102), ("Carla Sousa", "Fão", 998),
    ("Diogo Pinto", "Válega", 876), ("Eva Moreira", "Fão", 754), ("Filipe Rocha", "Válega", 702),
)


def _demo_rows():
    rows = []
    for name, hub, deliveries in DEMO_DRIVERS:
        rows.append({
            "cells": [
                {"text": name}, {"text": hub},
                {"text": pt_int(deliveries), "numeric": True},
                {"text": eur(deliveries * 1.15), "numeric": True},
            ],
            "action_url": "#",
        })
    return rows


def design_system(request):
    page = Paginator(_demo_rows(), 5).get_page(request.GET.get("page"))
    context = {
        "today": timezone.localdate(),
        "hubs": ["Fão", "Válega"],
        "color_tokens": COLOR_TOKENS,
        "statuses": STATUSES,
        "demo": {
            "volume": pt_int(3692), "delivered": pt_int(3501),
            "rate": pct(94.8), "money": eur(1234.56),
        },
        "nav_groups": [
            {"label": "Hoje", "items": [
                {"label": "Painel do dia", "url": "/", "icon": "layout-dashboard", "active": True},
                {"label": "Precisa de atenção", "url": "#", "icon": "bell", "count": 34},
            ]},
            {"label": "Operação", "items": [
                {"label": "Pacotes", "url": "#", "icon": "package"},
                {"label": "Motoristas", "url": "#", "icon": "users"},
            ]},
            {"label": "Finanças", "items": [
                {"label": "Visão geral", "url": "#", "icon": "wallet"},
            ]},
        ],
        "filter_fields": [
            {"kind": "text", "name": "q", "label": "Pesquisa", "value": request.GET.get("q", "")},
            {"kind": "select", "name": "hub", "label": "Hub", "value": request.GET.get("hub", ""),
             "options": [{"value": "", "label": "Todos"}, {"value": "fao", "label": "Fão"}]},
            {"kind": "date", "name": "date", "label": "Data", "value": request.GET.get("date", "")},
        ],
        "table_columns": [
            {"key": "name", "label": "Motorista", "sortable": True},
            {"key": "hub", "label": "Hub", "sortable": True},
            {"key": "deliveries", "label": "Entregas", "numeric": True, "sortable": True},
            {"key": "value", "label": "A pagar", "numeric": True},
        ],
        "table_rows": page.object_list,
        "table_page": page,
        "table_total": page.paginator.count,
        "empty_rows": [],
    }
    return render(request, "design/index.html", context)
