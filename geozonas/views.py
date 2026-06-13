import json

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.db.utils import OperationalError, ProgrammingError
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_POST

from .models import CodigoPostal, IngestJob, ZonaGeo
from .services.espacial import cps_dentro_poligono
from .tasks import ingest_cp4_task


def _feature(cp):
    """Serializa um CodigoPostal como Feature GeoJSON (ponto)."""
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [float(cp.longitude), float(cp.latitude)],
        },
        "properties": {
            "cp": cp.codigo_postal,
            "localidade": cp.localidade.nome if cp.localidade else "",
            "concelho": cp.concelho.nome if cp.concelho else "",
        },
    }


# ───────────────────────── Páginas ─────────────────────────


@login_required
def mapa(request):
    """Mapa de Códigos Postais: cadastrar áreas (CP4), ver pontos e desenhar zonas."""
    context = {"map_center": [39.5, -8.0], "map_zoom": 7, "cp4s": [], "zonas_json": []}
    try:
        context["cp4s"] = list(
            CodigoPostal.objects.order_by("cp4")
            .values_list("cp4", flat=True)
            .distinct()
        )
        context["zonas_json"] = [
            {"nome": z.nome, "cor": z.cor, "poligono": z.poligono}
            for z in ZonaGeo.objects.filter(is_active=True)
        ]
    except (OperationalError, ProgrammingError):
        # Tabelas ainda não migradas — mostra o mapa vazio sem rebentar.
        context["nao_migrado"] = True
    return render(request, "geozonas/mapa.html", context)


@login_required
def catalogo(request):
    """Pesquisa: insere um CP (ou CP4, ou localidade) e identifica a zona."""
    q = (request.GET.get("q") or "").strip()
    resultados = []
    if q:
        qs = CodigoPostal.objects.select_related(
            "concelho", "localidade", "freguesia"
        )
        digitos = q.replace("-", "").replace(" ", "")
        if len(digitos) >= 7 and digitos[:7].isdigit():
            qs = qs.filter(cp4=digitos[:4], cp3=digitos[4:7])
        elif len(digitos) == 4 and digitos.isdigit():
            qs = qs.filter(cp4=digitos)
        else:
            qs = qs.filter(
                Q(localidade__nome__icontains=q)
                | Q(designacao_postal__icontains=q)
            )
        resultados = list(qs[:500])
    return render(
        request, "geozonas/catalogo.html", {"q": q, "resultados": resultados}
    )


# ───────────────────────── APIs JSON ─────────────────────────


@login_required
@require_GET
def api_cps(request):
    """Pontos dos CPs (GeoJSON) para o mapa. Filtra por ?cp4=4990 se indicado."""
    cp4 = request.GET.get("cp4")
    qs = CodigoPostal.objects.filter(
        latitude__isnull=False, longitude__isnull=False
    ).select_related("localidade", "concelho")
    if cp4:
        qs = qs.filter(cp4=cp4)
    features = [_feature(cp) for cp in qs[:8000]]
    return JsonResponse({"type": "FeatureCollection", "features": features})


@login_required
@require_POST
def api_selecionar(request):
    """Recebe a geometria desenhada e devolve os CPs que caem lá dentro."""
    try:
        data = json.loads(request.body or "{}")
    except ValueError:
        return JsonResponse({"erro": "JSON inválido"}, status=400)

    geometry = data.get("geometry")
    if not geometry:
        return JsonResponse({"erro": "Falta a geometria"}, status=400)

    qs = CodigoPostal.objects.filter(
        latitude__isnull=False, longitude__isnull=False
    ).select_related("localidade", "concelho")
    cp4 = data.get("cp4")
    if cp4:
        qs = qs.filter(cp4=cp4)

    dentro = cps_dentro_poligono(geometry, qs)
    return JsonResponse(
        {
            "count": len(dentro),
            "cps": [cp.codigo_postal for cp in dentro],
            "features": [_feature(cp) for cp in dentro],
        }
    )


@login_required
@require_POST
def api_criar_zona(request):
    """Cria/atualiza uma ZonaGeo a partir do polígono desenhado."""
    try:
        data = json.loads(request.body or "{}")
    except ValueError:
        return JsonResponse({"ok": False, "erro": "JSON inválido"}, status=400)

    nome = (data.get("nome") or "").strip()
    cor = (data.get("cor") or "#2563eb").strip()
    geometry = data.get("geometry")
    if not nome or not geometry:
        return JsonResponse(
            {"ok": False, "erro": "Nome e geometria são obrigatórios"}, status=400
        )

    codigo = slugify(nome)[:40] or slugify(f"zona-{nome}")[:40]
    zona, criada = ZonaGeo.objects.update_or_create(
        codigo=codigo,
        defaults={"nome": nome, "cor": cor, "poligono": geometry},
    )

    qs = CodigoPostal.objects.filter(
        latitude__isnull=False, longitude__isnull=False
    )
    dentro = cps_dentro_poligono(geometry, qs)
    return JsonResponse(
        {
            "ok": True,
            "id": zona.id,
            "nome": zona.nome,
            "codigo": zona.codigo,
            "cor": zona.cor,
            "criada": criada,
            "count": len(dentro),
        }
    )


@login_required
@require_POST
def api_ingest(request):
    """Dispara a ingestão de um prefixo CP4 via Celery."""
    try:
        data = json.loads(request.body or "{}")
    except ValueError:
        return JsonResponse({"ok": False, "erro": "JSON inválido"}, status=400)

    cp4 = (data.get("cp4") or "").strip()
    com_coords = bool(data.get("coords"))
    if not (cp4.isdigit() and len(cp4) == 4):
        return JsonResponse(
            {"ok": False, "erro": "CP4 inválido (4 dígitos)"}, status=400
        )

    job = IngestJob.objects.create(cp4=cp4, com_coordenadas=com_coords)
    ingest_cp4_task.delay(cp4, com_coords, job_id=job.id)
    return JsonResponse(
        {"ok": True, "queued": cp4, "coords": com_coords, "job_id": job.id}
    )


@login_required
@require_GET
def api_jobs_active(request):
    """Lista importações ainda a decorrer (para reatar as barras no load)."""
    jobs = IngestJob.objects.filter(
        status__in=["PENDENTE", "A_CORRER"]
    ).order_by("-created_at")[:20]
    return JsonResponse(
        {
            "jobs": [
                {"id": j.id, "cp4": j.cp4, "status": j.status, "percent": j.percent}
                for j in jobs
            ]
        }
    )


@login_required
@require_GET
def api_job_status(request):
    """Estado/progresso de uma importação (polling pela UI)."""
    job_id = request.GET.get("id")
    job = IngestJob.objects.filter(id=job_id).first()
    if not job:
        return JsonResponse({"erro": "Job não encontrado"}, status=404)
    return JsonResponse(
        {
            "id": job.id,
            "cp4": job.cp4,
            "status": job.status,
            "percent": job.percent,
            "concelho": job.concelho,
            "total": job.total,
            "processados": job.processados,
            "coords_total": job.coords_total,
            "coords_feitas": job.coords_feitas,
            "coords_falhadas": job.coords_falhadas,
            "erro": job.erro,
        }
    )
