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


def ingest_cp4(cp4, com_coordenadas=False, delay_coords=0.3, client=None):
    """
    Importa/atualiza todos os CPs do prefixo `cp4`.

    Args:
        cp4: prefixo de 4 dígitos (ex.: "4990").
        com_coordenadas: se True, faz um 2º passo por CP3 para obter o centroide GPS.
        delay_coords: pausa entre chamadas de detalhe (respeitar rate limit).
        client: GeoAPIClient (injetável para testes).

    Returns:
        dict com estatísticas da ingestão.
    """
    cp4 = str(cp4).strip()
    client = client or GeoAPIClient()

    dados = client.consultar_cp4(cp4)
    if not dados:
        return {"cp4": cp4, "ok": False, "erro": "CP4 não encontrado", "total": 0}

    concelho_nome = str(dados.get("Concelho", "") or "").strip()
    distrito = str(dados.get("Distrito", "") or "").strip()
    codigo_ine = str(dados.get("codigoineMunicipio", "") or "").strip()

    concelho_obj = None
    if concelho_nome:
        concelho_obj, _ = Concelho.objects.update_or_create(
            nome=concelho_nome,
            defaults={"distrito": distrito, "codigo_ine": codigo_ine},
        )

    mapa = _mapa_cp3(dados)
    lista_cp3 = [str(c).strip() for c in (dados.get("CP3") or []) if str(c).strip()]
    # Garante que CP3 presentes só em `partes` também entram
    lista_cp3 = sorted(set(lista_cp3) | set(mapa.keys()))

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
            cp4, lista_cp3, client, delay_coords
        )

    return stats


def _enriquecer_coordenadas(cp4, lista_cp3, client, delay):
    """2º passo: obtém centroide GPS de cada CP via /cp/{CP4-CP3}."""
    atualizados = 0
    for i, cp3 in enumerate(lista_cp3):
        detalhe = client.consultar_cp(f"{cp4}-{cp3}")
        if detalhe:
            centroide = detalhe.get("centroide") or detalhe.get("centroDeMassa")
            if centroide and len(centroide) == 2:
                CodigoPostal.objects.filter(cp4=cp4, cp3=cp3).update(
                    latitude=centroide[0], longitude=centroide[1]
                )
                atualizados += 1
        if i < len(lista_cp3) - 1:
            time.sleep(delay)
    return atualizados
