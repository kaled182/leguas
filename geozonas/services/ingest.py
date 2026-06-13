"""
Ingestão de códigos postais a partir da GeoAPI, por prefixo CP4.

Fluxo: 1 chamada /cp/{CP4} → cria/atualiza todos os CodigoPostal do prefixo com
localidade, designação postal e concelho. Opcionalmente, um segundo passo enriquece
cada CP com coordenadas (centroide) via /cp/{CP4-CP3}.
"""

import time

from django.db import transaction

from ..models import CodigoPostal, Concelho, Localidade
from .geoapi import GeoAPIClient

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


def ingest_cp4(cp4, com_coordenadas=False, delay_coords=0.2, client=None, job=None):
    """
    Importa/atualiza todos os CPs do prefixo `cp4`.

    Args:
        cp4: prefixo de 4 dígitos (ex.: "4990").
        com_coordenadas: se True, faz um 2º passo por CP3 para obter o centroide GPS.
        delay_coords: pausa entre chamadas de detalhe (respeitar rate limit).
        client: GeoAPIClient (injetável para testes).
        job: IngestJob opcional, atualizado com o progresso ao longo da ingestão.

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

    mapa = _mapa_cp3(dados)
    lista_cp3 = [str(c).strip() for c in (dados.get("CP3") or []) if str(c).strip()]
    # Garante que CP3 presentes só em `partes` também entram
    lista_cp3 = sorted(set(lista_cp3) | set(mapa.keys()))

    if job:
        job.status = "A_CORRER"
        job.concelho = concelho_nome
        job.total = len(lista_cp3)
        job.coords_total = len(lista_cp3) if com_coordenadas else 0
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
        stats["com_coordenadas"] = _enriquecer_coordenadas(
            cp4, lista_cp3, client, delay_coords, cache_concelhos, job=job
        )

    if job:
        job.status = "CONCLUIDO"
        job.save(update_fields=["status", "updated_at"])

    return stats


def _enriquecer_coordenadas(cp4, lista_cp3, client, delay, cache_concelhos, job=None):
    """
    2º passo: obtém centroide GPS de cada CP via /cp/{CP4-CP3}.

    Também corrige o concelho de cada CP individualmente (importa quando um
    prefixo CP4 abrange vários concelhos — o detalhe dá o concelho exato do CP3).

    Resiliente: um erro numa chamada NÃO interrompe o resto — conta a falha
    e continua. Atualiza o `job` periodicamente para acompanhamento na UI.
    """
    feitas, falhadas = 0, 0
    total = len(lista_cp3)

    for i, cp3 in enumerate(lista_cp3):
        try:
            detalhe = client.consultar_cp(f"{cp4}-{cp3}")
            if detalhe:
                updates = {}
                centroide = detalhe.get("centroide") or detalhe.get("centroDeMassa")
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
                    CodigoPostal.objects.filter(cp4=cp4, cp3=cp3).update(**updates)
                    if "latitude" in updates:
                        feitas += 1
                    else:
                        falhadas += 1
                else:
                    falhadas += 1
            else:
                falhadas += 1
        except Exception:
            # Não deixa um CP3 problemático matar a importação inteira.
            falhadas += 1

        # Atualiza o job a cada 5 CP3 (e no fim) para não martelar a BD.
        if job and (i % 5 == 0 or i == total - 1):
            job.coords_feitas = feitas
            job.coords_falhadas = falhadas
            job.save(
                update_fields=["coords_feitas", "coords_falhadas", "updated_at"]
            )

        if i < total - 1:
            time.sleep(delay)

    return feitas
