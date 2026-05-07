"""View do Dashboard de Tesouraria."""
import json
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .services_treasury import cash_projection_30d, treasury_snapshot
from .services_pt_tax_calendar import (
    irc_payment_dates, irs_declaracao_dates,
)


def _decimal_default(o):
    if isinstance(o, Decimal):
        return float(o)
    raise TypeError(f"Tipo não serializável: {type(o)}")


@login_required
def treasury_dashboard(request):
    snap = treasury_snapshot()
    proj = cash_projection_30d()

    # Datas do calendário fiscal anual (informativas)
    today = snap["today"]
    irc_dates = irc_payment_dates(today.year)
    irs_dates = irs_declaracao_dates(today.year)

    # Datasets para Chart.js
    chart_labels = [d["date"].strftime("%d/%m") for d in proj["days"]]
    chart_balance = [float(d["balance"]) for d in proj["days"]]
    chart_in = [float(d["in_amount"]) for d in proj["days"]]
    chart_out = [float(-d["out_amount"]) for d in proj["days"]]  # negativo no gráfico

    context = {
        "snap": snap,
        "proj": proj,
        "irc_dates": irc_dates,
        "irs_dates": irs_dates,
        "chart_labels_json": json.dumps(chart_labels),
        "chart_balance_json": json.dumps(chart_balance),
        "chart_in_json": json.dumps(chart_in),
        "chart_out_json": json.dumps(chart_out),
    }
    return render(request, "accounting/treasury_dashboard.html", context)
