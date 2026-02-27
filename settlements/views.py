from datetime import datetime
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum
from django.utils.dateparse import parse_date
from django.shortcuts import render
import csv

from .models import SettlementRun
from .services import compute_payouts

def _parse_dates(request):
    dfrom = parse_date(request.GET.get("date_from")) if request.GET.get("date_from") else None
    dto   = parse_date(request.GET.get("date_to"))   if request.GET.get("date_to")   else None
    return dfrom, dto

def summary(request):
    dfrom, dto = _parse_dates(request)
    qs = SettlementRun.objects.all()
    if dfrom: qs = qs.filter(run_date__gte=dfrom)
    if dto:   qs = qs.filter(run_date__lte=dto)
    if request.GET.get("driver"): qs = qs.filter(driver__name=request.GET["driver"])
    if request.GET.get("client"): qs = qs.filter(client=request.GET["client"])

    agg = qs.aggregate(
        runs=Sum(1),
        qtd_pact=Sum("qtd_pact"),
        qtd_entregue=Sum("qtd_entregue"),
        bruto=Sum("total_pct"),
        gasoleo=Sum("gasoleo"),
        desconto_tickets=Sum("desconto_tickets"),
        rec_liq_tickets=Sum("rec_liq_tickets"),
        outros=Sum("outros"),
        liquido=Sum("vl_final"),
    )
    qtd_pact = float(agg.get("qtd_pact") or 0)
    qtd_ent  = float(agg.get("qtd_entregue") or 0)
    taxa = round((qtd_ent / qtd_pact) * 100, 2) if qtd_pact > 0 else 0.0
    media = round((float(agg.get("liquido") or 0) / qtd_ent), 2) if qtd_ent > 0 else 0.0
    
    # Para requisições AJAX, retorna JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            "runs": int(agg.get("runs") or 0),
            "qtd_pact": int(agg.get("qtd_pact") or 0),
            "qtd_entregue": int(agg.get("qtd_entregue") or 0),
            "bruto": float(agg.get("bruto") or 0),
            "gasoleo": float(agg.get("gasoleo") or 0),
            "desconto_tickets": float(agg.get("desconto_tickets") or 0),
            "rec_liq_tickets": float(agg.get("rec_liq_tickets") or 0),
            "outros": float(agg.get("outros") or 0),
            "liquido": float(agg.get("liquido") or 0),
            "taxa_sucesso_pct": taxa,
            "avg_liq_por_pacote": media
        })
    
    # Para requisições normais, renderiza o template
    return render(request, 'settlements/summary.html')

def drivers_rank(request):
    dfrom, dto = _parse_dates(request)
    qs = SettlementRun.objects.all()
    if dfrom: qs = qs.filter(run_date__gte=dfrom)
    if dto:   qs = qs.filter(run_date__lte=dto)

    data = (qs.values("driver__name")
              .annotate(
                  entregues=Sum("qtd_entregue"),
                  qtd_pact=Sum("qtd_pact"),
                  liquido=Sum("vl_final"),
              ))
    result = []
    for row in data:
        entregues = int(row["entregues"] or 0)
        pact = int(row["qtd_pact"] or 0)
        taxa = round((entregues / pact) * 100, 2) if pact else 0.0
        result.append({
            "driver": row["driver__name"],
            "entregues": entregues,
            "taxa_media": taxa,
            "liquido": float(row["liquido"] or 0)
        })
    result.sort(key=lambda r: (-r["liquido"], r["driver"]))
    
    # Para requisições AJAX, retorna JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(result, safe=False)
    
    # Para requisições normais, renderiza o template
    return render(request, 'settlements/drivers_rank.html')

def runs_list(request):
    dfrom, dto = _parse_dates(request)
    qs = SettlementRun.objects.select_related("driver").all()
    if dfrom: qs = qs.filter(run_date__gte=dfrom)
    if dto:   qs = qs.filter(run_date__lte=dto)
    if request.GET.get("driver"): qs = qs.filter(driver__name=request.GET["driver"])
    if request.GET.get("client"): qs = qs.filter(client=request.GET["client"])
    if request.GET.get("area"):   qs = qs.filter(area_code=request.GET["area"])

    data = list(qs.values(
        "run_date","client","area_code","driver__name",
        "qtd_saida","qtd_pact","qtd_entregue","vl_pct","total_pct",
        "gasoleo","desconto_tickets","rec_liq_tickets","outros","vl_final","notes"
    ).order_by("-run_date")[:1000])
    
    # Para requisições AJAX, retorna JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(data, safe=False)
    
    # Para requisições normais, renderiza o template
    return render(request, 'settlements/runs_list.html')

def payouts(request):
    date_from = request.GET.get("date_from"); date_to = request.GET.get("date_to")
    
    # Para requisições normais sem parâmetros de data, apenas renderiza o template
    if not (date_from and date_to) and request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return render(request, 'settlements/payouts.html')
        
    # Para requisições AJAX, exige os parâmetros de data
    if not (date_from and date_to):
        return JsonResponse({"error":"date_from & date_to são obrigatórios (YYYY-MM-DD)"}, status=400)
        
    client = request.GET.get("client"); area = request.GET.get("area")
    pf = datetime.strptime(date_from, "%Y-%m-%d").date()
    pt = datetime.strptime(date_to, "%Y-%m-%d").date()
    data = compute_payouts(pf, pt, client, area)
    
    # Para requisições AJAX, retorna JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(data, safe=False)
    
    # Para requisições normais, renderiza o template
    return render(request, 'settlements/payouts.html')

def payouts_csv(request):
    date_from = request.GET.get("date_from"); date_to = request.GET.get("date_to")
    if not (date_from and date_to):
        return JsonResponse({"error":"date_from & date_to são obrigatórios (YYYY-MM-DD)"}, status=400)
    client = request.GET.get("client"); area = request.GET.get("area")
    pf = datetime.strptime(date_from, "%Y-%m-%d").date()
    pt = datetime.strptime(date_to, "%Y-%m-%d").date()
    data = compute_payouts(pf, pt, client, area)

    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    filename = f"payouts_{pf}_{pt}.csv"
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    w = csv.writer(resp, delimiter=';')
    w.writerow(["driver","period_from","period_to","entregues","bruto_pkg","bonus","fixo","bruto_total","descontos","liquido","media_liq_por_pacote"])
    for r in data:
        w.writerow([r["driver"], r["period_from"], r["period_to"], r["entregues"], r["bruto_pkg"], r["bonus"], r["fixo"], r["bruto_total"], r["descontos"], r["liquido"], r["media_liq_por_pacote"]])
    return resp
