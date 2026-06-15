"""
Ingestão de códigos postais a partir da GeoAPI, por prefixo CP4.

Fluxo: 1 chamada /cp/{CP4} → cria/atualiza todos os CodigoPostal do prefixo com
localidade, designação postal e concelho. Opcionalmente, um segundo passo enriquece
cada CP com coordenadas (centroide) via /cp/{CP4-CP3}.
"""

from collections import defaultdict

from django.db import transaction

from ..models import AreaCP4, CodigoPostal, Concelho, Freguesia, Localidade
from .geoapi import GeoAPIClient


def atribuir_freguesias(cp4s):
    """Atribui a cada CP (com GPS) a freguesia que o contém (point-in-polygon).
    Permite mostrar no mapa só as freguesias que pertencem ao CP4."""
    from shapely.geometry import Point, shape
    cps = list(
        CodigoPostal.objects.filter(
            cp4__in=cp4s, latitude__isnull=False, longitude__isnull=False,
        ).only("id", "latitude", "longitude", "concelho_id")
    )
    if not cps:
        return 0
    concelho_ids = {c.concelho_id for c in cps if c.concelho_id}
    shapes = []
    for f in Freguesia.objects.filter(
        concelho_id__in=concelho_ids,
    ).exclude(geojson__isnull=True):
        try:
            shapes.append((f.id, shape(f.geojson)))
        except Exception:
            continue
    if not shapes:
        return 0
    por_freguesia = defaultdict(list)
    for cp in cps:
        pt = Point(float(cp.longitude), float(cp.latitude))
        for fid, geom in shapes:
            if geom.contains(pt):
                por_freguesia[fid].append(cp.id)
                break
    n = 0
    for fid, ids in por_freguesia.items():
        CodigoPostal.objects.filter(id__in=ids).update(freguesia_id=fid)
        n += len(ids)
    return n

# Chaves (com acentos) tal como vêm da GeoAPI
_K_DESIGNACAO = "Designação Postal"
_K_LOCALIDADE = "Localidade"
_K_ARTERIA = "Artéria"
_K_CP3 = "CP3"


def _primeiro(valor):
    """Normaliza um campo da GeoAPI que pode vir como str ou lista.

    Um prefixo CP4 que abrange vários concelhos devolve `Concelho`/`Distrito`
    como lista (ex.: ['Barcelos', 'Esposende']). Devolvemos o 1º como string.
    """
    if isinstance(valor, list):
        return str(valor[0]).strip() if valor else ""
    return str(valor or "").strip()


def _get_concelho(nome, distrito, codigo_ine, cache):
    """get_or_create de Concelho com cache local (evita queries repetidas)."""
    if not nome:
        return None
    if nome not in cache:
        obj, _ = Concelho.objects.update_or_create(
            nome=nome,
            defaults={"distrito": distrito, "codigo_ine": codigo_ine},
        )
        cache[nome] = obj
    return cache[nome]


def _poligono_geojson(dados):
    """Converte o `poligono` da GeoAPI ([[lat,lng],...]) num GeoJSON Polygon
    (coords [lng,lat], anel fechado). Devolve None se não houver/for inválido.
    """
    pol = dados.get("poligono")
    if not isinstance(pol, list) or len(pol) < 3:
        return None
    ring = []
    for p in pol:
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            try:
                ring.append([float(p[1]), float(p[0])])  # [lng, lat]
            except (TypeError, ValueError):
                continue
    if len(ring) < 3:
        return None
    if ring[0] != ring[-1]:
        ring.append(ring[0])  # fecha o anel
    return {"type": "Polygon", "coordinates": [ring]}


def _ingest_freguesias(concelho_nome, client, forcar=False):
    """Guarda as freguesias (com polígono GeoJSON) de um concelho. 1 chamada
    à GeoAPI; salta se já existirem (poupa tokens) salvo `forcar`."""
    concelho_nome = (concelho_nome or "").strip()
    if not concelho_nome:
        return 0
    cobj, _ = Concelho.objects.get_or_create(nome=concelho_nome)
    if not forcar and Freguesia.objects.filter(
        concelho=cobj,
    ).exclude(geojson__isnull=True).exists():
        return 0
    feats = client.consultar_freguesias(concelho_nome)
    n = 0
    for f in feats or []:
        props = f.get("properties") or {}
        nome = (
            props.get("freguesia") or props.get("nome")
            or props.get("Freguesia") or ""
        ).strip()
        if not nome:
            continue
        Freguesia.objects.update_or_create(
            concelho=cobj,
            nome=nome,
            defaults={
                "codigo_ine": (props.get("dtmnfr") or "")[:12],
                "geojson": f.get("geometry"),
            },
        )
        n += 1
    return n


def _mapa_cp3(dados):
    """A partir de `partes`, devolve {cp3: {'localidade', 'designacao', 'arterias'}}."""
    mapa = {}
    for parte in dados.get("partes", []) or []:
        cp3 = str(parte.get(_K_CP3, "")).strip()
        if not cp3:
            continue
        info = mapa.setdefault(
            cp3, {"localidade": "", "designacao": "", "arterias": []}
        )
        if not info["localidade"]:
            info["localidade"] = str(parte.get(_K_LOCALIDADE, "") or "").strip()
        if not info["designacao"]:
            info["designacao"] = str(parte.get(_K_DESIGNACAO, "") or "").strip()
        arteria = str(parte.get(_K_ARTERIA, "") or "").strip()
        if arteria and arteria not in info["arterias"]:
            info["arterias"].append(arteria)
    return mapa


def ingest_cp4(
    cp4, com_coordenadas=False, delay_coords=0.2, client=None, job=None,
    forcar_coords=False,
):
    """
    Importa/atualiza todos os CPs do prefixo `cp4`.

    Args:
        cp4: prefixo de 4 dígitos (ex.: "4990").
        com_coordenadas: se True, faz um 2º passo por CP3 para obter o centroide GPS.
        delay_coords: (legado, ignorado — as chamadas são paralelas).
        client: GeoAPIClient (injetável para testes).
        job: IngestJob opcional, atualizado com o progresso ao longo da ingestão.
        forcar_coords: se False (default), o passo de coordenadas só vai buscar
            os CP3 que ainda NÃO têm GPS — poupa tokens ao re-importar. Se True,
            re-busca todos.

    Returns:
        dict com estatísticas da ingestão.
    """
    cp4 = str(cp4).strip()
    client = client or GeoAPIClient()

    dados = client.consultar_cp4(cp4)
    if not dados:
        if job:
            job.status = "ERRO"
            job.erro = "CP4 não encontrado na GeoAPI"
            job.save(update_fields=["status", "erro", "updated_at"])
        return {"cp4": cp4, "ok": False, "erro": "CP4 não encontrado", "total": 0}

    concelho_nome = _primeiro(dados.get("Concelho"))
    distrito = _primeiro(dados.get("Distrito"))
    codigo_ine = _primeiro(dados.get("codigoineMunicipio"))

    cache_concelhos = {}
    concelho_obj = _get_concelho(
        concelho_nome, distrito, codigo_ine, cache_concelhos
    )

    # Guarda o contorno (divisas) da área do CP4 para desenhar no mapa.
    centroide = dados.get("centroide") or dados.get("centroDeMassa")
    AreaCP4.objects.update_or_create(
        cp4=cp4,
        defaults={
            "concelho_nome": concelho_nome,
            "distrito": distrito,
            "poligono": _poligono_geojson(dados),
            "centro_lat": (
                centroide[0] if centroide and len(centroide) == 2 else None
            ),
            "centro_lng": (
                centroide[1] if centroide and len(centroide) == 2 else None
            ),
        },
    )

    # Freguesias (divisas finas) do(s) concelho(s) do CP4 — 1 chamada por
    # concelho, saltada se já existirem (poupa tokens). Não-fatal.
    concelhos_raw = dados.get("Concelho")
    nomes_concelho = (
        concelhos_raw if isinstance(concelhos_raw, list) else [concelhos_raw]
    )
    for cnome in {str(c).strip() for c in nomes_concelho if str(c).strip()}:
        try:
            _ingest_freguesias(cnome, client, forcar=forcar_coords)
        except Exception:
            pass

    mapa = _mapa_cp3(dados)
    lista_cp3 = [str(c).strip() for c in (dados.get("CP3") or []) if str(c).strip()]
    # Garante que CP3 presentes só em `partes` também entram
    lista_cp3 = sorted(set(lista_cp3) | set(mapa.keys()))

    if job:
        job.status = "A_CORRER"
        job.concelho = concelho_nome
        job.total = len(lista_cp3)
        job.coords_total = 0  # definido após saber quantos faltam
        job.save(
            update_fields=[
                "status", "concelho", "total", "coords_total", "updated_at"
            ]
        )

    criados, atualizados = 0, 0
    cache_localidades = {}

    with transaction.atomic():
        for cp3 in lista_cp3:
            info = mapa.get(cp3, {})
            loc_nome = info.get("localidade", "")
            localidade_obj = None
            if loc_nome:
                if loc_nome not in cache_localidades:
                    localidade_obj, _ = Localidade.objects.get_or_create(nome=loc_nome)
                    cache_localidades[loc_nome] = localidade_obj
                localidade_obj = cache_localidades[loc_nome]

            _, criado = CodigoPostal.objects.update_or_create(
                cp4=cp4,
                cp3=cp3,
                defaults={
                    "designacao_postal": info.get("designacao", ""),
                    "localidade": localidade_obj,
                    "concelho": concelho_obj,
                    "arterias": info.get("arterias") or None,
                    "fonte": "geoapi",
                },
            )
            if criado:
                criados += 1
            else:
                atualizados += 1

    if job:
        job.processados = len(lista_cp3)
        job.save(update_fields=["processados", "updated_at"])

    stats = {
        "cp4": cp4,
        "ok": True,
        "concelho": concelho_nome,
        "distrito": distrito,
        "total": len(lista_cp3),
        "criados": criados,
        "atualizados": atualizados,
        "com_coordenadas": 0,
    }

    if com_coordenadas:
        if forcar_coords:
            cp3_coords = lista_cp3
        else:
            # Só os CP3 que ainda não têm GPS — re-import não desperdiça tokens.
            cp3_coords = list(
                CodigoPostal.objects.filter(
                    cp4=cp4, cp3__in=lista_cp3, latitude__isnull=True,
                ).values_list("cp3", flat=True)
            )
        stats["coords_em_falta"] = len(cp3_coords)
        if job:
            job.coords_total = len(cp3_coords)
            job.save(update_fields=["coords_total", "updated_at"])
        stats["com_coordenadas"] = _enriquecer_coordenadas(
            cp4, cp3_coords, client, delay_coords, cache_concelhos, job=job
        )
        # Garante freguesias de TODOS os concelhos reais dos CPs deste CP4
        # (apanha o caso multi-concelho, ex.: 4740 = Barcelos + Esposende).
        nomes_reais = (
            CodigoPostal.objects.filter(cp4=cp4, concelho__isnull=False)
            .values_list("concelho__nome", flat=True).distinct()
        )
        for cnome in set(nomes_reais):
            try:
                _ingest_freguesias(cnome, client, forcar=forcar_coords)
            except Exception:
                pass
        # Liga cada CP à sua freguesia (point-in-polygon) — não-fatal.
        try:
            atribuir_freguesias([cp4])
        except Exception:
            pass

    if job:
        job.status = "CONCLUIDO"
        job.save(update_fields=["status", "updated_at"])

    return stats


def preencher_coordenadas_em_falta(cp4, client=None, job=None):
    """
    Vai buscar coordenadas SÓ aos CP3 do prefixo que ainda não têm GPS.

    Não faz a chamada bulk /cp/{CP4} (poupa ainda mais tokens) — usa o que já
    está no catálogo. Ideal para completar um CP4 já importado.
    """
    cp4 = str(cp4).strip()
    client = client or GeoAPIClient()

    faltam = list(
        CodigoPostal.objects.filter(
            cp4=cp4, latitude__isnull=True,
        ).values_list("cp3", flat=True)
    )
    total = len(faltam)
    if job:
        job.status = "A_CORRER"
        job.total = total
        job.coords_total = total
        job.save(update_fields=[
            "status", "total", "coords_total", "updated_at",
        ])

    feitas = 0
    if faltam:
        feitas = _enriquecer_coordenadas(
            cp4, faltam, client, 0, {}, job=job
        )
        try:
            atribuir_freguesias([cp4])
        except Exception:
            pass

    if job:
        job.status = "CONCLUIDO"
        job.save(update_fields=["status", "updated_at"])

    return {"cp4": cp4, "ok": True, "faltavam": total, "feitas": feitas}


def _enriquecer_coordenadas(cp4, lista_cp3, client, delay, cache_concelhos, job=None):
    """
    2º passo: obtém centroide GPS de cada CP via /cp/{CP4-CP3}.

    Também corrige o concelho de cada CP individualmente (importa quando um
    prefixo CP4 abrange vários concelhos — o detalhe dá o concelho exato do CP3).

    Resiliente: um erro numa chamada NÃO interrompe o resto — conta a falha
    e continua. Atualiza o `job` periodicamente para acompanhamento na UI.
    """
    # As chamadas de detalhe (1 por CP3) são o passo lento. Paralelizamos a
    # parte de REDE com um pool de threads; as escritas na BD ficam na thread
    # principal (no laço as_completed), evitando problemas de ligações Django
    # entre threads. `delay` deixa de ser usado (a concorrência regula o ritmo).
    from concurrent.futures import ThreadPoolExecutor, as_completed

    feitas, falhadas = 0, 0
    total = len(lista_cp3)
    processados = 0

    def _fetch(cp3):
        try:
            return cp3, client.consultar_cp(f"{cp4}-{cp3}")
        except Exception:
            return cp3, None

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(_fetch, cp3) for cp3 in lista_cp3]
        for fut in as_completed(futures):
            cp3, detalhe = fut.result()
            tem_coords = False
            if detalhe:
                updates = {}
                centroide = (
                    detalhe.get("centroide") or detalhe.get("centroDeMassa")
                )
                if centroide and len(centroide) == 2:
                    updates["latitude"] = centroide[0]
                    updates["longitude"] = centroide[1]

                c_nome = _primeiro(detalhe.get("Concelho"))
                if c_nome:
                    concelho_obj = _get_concelho(
                        c_nome,
                        _primeiro(detalhe.get("Distrito")),
                        _primeiro(detalhe.get("codigoineMunicipio")),
                        cache_concelhos,
                    )
                    if concelho_obj:
                        updates["concelho"] = concelho_obj

                if updates:
                    CodigoPostal.objects.filter(
                        cp4=cp4, cp3=cp3,
                    ).update(**updates)
                    tem_coords = "latitude" in updates

            if tem_coords:
                feitas += 1
            else:
                falhadas += 1

            processados += 1
            # Atualiza o job a cada 8 CP3 (e no fim) para mostrar progresso.
            if job and (processados % 8 == 0 or processados == total):
                job.coords_feitas = feitas
                job.coords_falhadas = falhadas
                job.save(update_fields=[
                    "coords_feitas", "coords_falhadas", "updated_at",
                ])

    return feitas
