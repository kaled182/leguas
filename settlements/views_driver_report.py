"""Relatório de motoristas por hub: página, PDF do hub, PDF do motorista, Excel e ZIP.

Só Gestão: as rotas não estão em `core.permissions.OPERATOR_PATTERNS`.
"""
import io
import zipfile
from datetime import date

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.utils.text import slugify

from drivers_app.models import DriverProfile, EmpresaParceira

from .models import CainiaoHub, DriverPreInvoice
from .reports.driver_report_pdf import driver_pdf, hub_pdf
from .services_driver_report import NO_HUB, build, collect_cached, driver_detail
from .views_cainiao_subledger import _quinzena


def _date(value, default):
    try:
        return date.fromisoformat(value) if value else default
    except ValueError:
        return default


def _params(request):
    """Filtros do GET. Valores inválidos usam a omissão."""
    g = request.GET
    d_from, d_to = _quinzena(date.today())
    date_from = _date(g.get("from"), d_from)
    date_to = _date(g.get("to"), d_to)
    if date_to < date_from or (date_to - date_from).days > 62:
        date_from, date_to = d_from, d_to
    hub_names = list(CainiaoHub.objects.filter(cp4_codes__isnull=False).distinct()
                     .values_list("name", flat=True))
    hub = g.get("hub", "")
    if hub not in hub_names + [NO_HUB]:
        hub = ""
    return {
        "date_from": date_from, "date_to": date_to, "hub": hub, "hub_names": hub_names,
        "fleet": g.get("fleet", ""), "vat": g.get("vat", ""), "pf": g.get("pf", ""),
        "q": g.get("q", "").strip(),
    }


def _report(request, p):
    collected = collect_cached(p["date_from"], p["date_to"], refresh=request.GET.get("refresh") == "1")
    return build(p["date_from"], p["date_to"], hub=p["hub"] or None, fleet_id=p["fleet"] or None,
                 vat=p["vat"] or None, pf_status=p["pf"] or None, q=p["q"] or None,
                 collected=collected)


def _hub_label(p):
    return p["hub"] or "Todos os hubs"


def _file_stem(p):
    return f"relatorio-motoristas-{slugify(_hub_label(p))}-{p['date_from']:%Y%m%d}-{p['date_to']:%Y%m%d}"


def _attachment(content, name, content_type):
    resp = HttpResponse(content, content_type=content_type)
    resp["Content-Disposition"] = f'attachment; filename="{name}"'
    return resp


@login_required
def driver_report(request):
    p = _params(request)
    report = _report(request, p)
    return render(request, "settlements/driver_report/index.html", {
        **p, "report": report, "query": request.GET.urlencode(),
        "fleets": EmpresaParceira.objects.filter(motoristas__isnull=False).distinct().order_by("nome"),
        "vat_choices": DriverProfile.VAT_REGIME_CHOICES,
        "pf_choices": DriverPreInvoice.STATUS_CHOICES,
        "no_hub": NO_HUB,
    })


@login_required
def driver_report_hub_pdf(request):
    p = _params(request)
    pdf = hub_pdf(_report(request, p), _hub_label(p), p["date_from"], p["date_to"], request.user)
    return _attachment(pdf, f"{_file_stem(p)}.pdf", "application/pdf")


def _driver_data(report, driver_id):
    for dd in report["data"]:
        if dd.driver.id == driver_id:
            return dd
    raise Http404("O motorista não tem tarefas neste período.")


@login_required
def driver_report_driver_pdf(request, driver_id):
    p = _params(request)
    dd = _driver_data(_report(request, p), driver_id)
    pdf = driver_pdf(driver_detail(dd, p["date_from"], p["date_to"]), request.user)
    name = f"relatorio-{slugify(dd.driver.nome_completo)}-{p['date_from']:%Y%m%d}-{p['date_to']:%Y%m%d}.pdf"
    return _attachment(pdf, name, "application/pdf")


def _xlsx(report, p):
    from openpyxl import Workbook

    wb = Workbook(write_only=True)
    ws = wb.create_sheet("Resumo")
    ws.append(["Frota", "Motorista", "NIF", "Regime IVA", "Hubs", "Dias", "Entregues", "Porta",
               "Mesma porta", "PUDO", "Falhas", "Producao", "Claims aprovados", "Claims por decidir",
               "Sem IVA", "IVA", "Com IVA", "Adiantamentos", "A pagar", "Retencao IRS",
               "PF", "Estado PF", "Diferenca vs PF"])
    for r in report["rows"]:
        d, pf = r["driver"], r["pf"]
        ws.append([r["fleet"].nome if r["fleet"] else "Direto", d.nome_completo, d.nif,
                   d.get_vat_regime_display(), ", ".join(r["hubs"]), r["days"], r["delivered"],
                   r["door_normal"], r["same_door"], r["pudo"], r["failures"], float(r["amount"]),
                   float(r["claims_amount"]), r["claims_open_n"], float(r["billable"]), float(r["vat"]), float(r["with_vat"]),
                   float(r["advances_amount"]), float(r["to_pay"]), float(r["irs"]),
                   pf.numero if pf else "", pf.get_status_display() if pf else "",
                   float(r["pf_diff"]) if r["pf_diff"] is not None else None])
    ws = wb.create_sheet("Entregas")
    ws.append(["Hub", "Motorista", "Frota", "Login", "Data", "Guia", "LP", "Estado", "Tipo",
               "CP4", "Codigo postal", "Morada", "Preco", "Valor sem IVA"])
    wanted = {r["driver"].id for r in report["rows"]}
    for dd in report["data"]:
        if dd.driver.id not in wanted:
            continue
        fleet = dd.driver.empresa_parceira.nome if dd.driver.empresa_parceira else "Direto"
        for l in dd.lines:
            if p["hub"] and l["hub"] != p["hub"]:
                continue
            ws.append([l["hub"], dd.driver.nome_completo, fleet, l["login"], l["date"], l["waybill"],
                       l["lp"], l["status"], l["kind"], l["cp4"], l["zip"], l["address"],
                       l["source"], float(l["amount"])])
    ws = wb.create_sheet("Claims")
    ws.append(["Hub", "Motorista", "Data", "Guia", "Tipo", "Estado", "Valor", "Desconta", "Descricao"])
    for dd in report["data"]:
        if dd.driver.id not in wanted:
            continue
        for c in dd.claims:
            if p["hub"] and c["hub"] != p["hub"]:
                continue
            ws.append([c["hub"], dd.driver.nome_completo, c["date"], c["waybill"], c["type"],
                       c["status_label"], float(c["amount"]),
                       "Sim" if c["deducted"] else ("Fatura seguinte" if c["deferred"] else "Nao"),
                       c["description"][:300]])
    ws = wb.create_sheet("Adiantamentos")
    ws.append(["Hub", "Motorista", "Data", "Tipo", "Estado", "Valor", "Desconta", "Descricao"])
    for dd in report["data"]:
        if dd.driver.id not in wanted:
            continue
        for a in dd.advances:
            if p["hub"] and a["hub"] != p["hub"]:
                continue
            ws.append([a["hub"], dd.driver.nome_completo, a["date"], a["type"], a["status_label"],
                       float(a["amount"]), "Sim" if a["deducted"] else "Proxima PF", a["description"][:300]])
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@login_required
def driver_report_xlsx(request):
    p = _params(request)
    return _attachment(_xlsx(_report(request, p), p), f"{_file_stem(p)}.xlsx", XLSX)


@login_required
def driver_report_zip(request):
    """PDF do hub, Excel e um PDF por motorista do filtro."""
    p = _params(request)
    report = _report(request, p)
    by_id = {dd.driver.id: dd for dd in report["data"]}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        stem = _file_stem(p)
        z.writestr(f"{stem}.pdf", hub_pdf(report, _hub_label(p), p["date_from"], p["date_to"], request.user))
        z.writestr(f"{stem}.xlsx", _xlsx(report, p))
        for r in report["rows"]:
            dd = by_id[r["driver"].id]
            pdf = driver_pdf(driver_detail(dd, p["date_from"], p["date_to"]), request.user)
            z.writestr(f"motoristas/{slugify(dd.driver.nome_completo)}-{dd.driver.id}.pdf", pdf)
    return _attachment(buf.getvalue(), f"{stem}.zip", "application/zip")
