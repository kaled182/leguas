"""
Operações espaciais do módulo GeoZonas, em Python puro (shapely).

Usado para o fluxo "desenha uma área no mapa → que códigos postais caem lá dentro".
GeoJSON usa a ordem [longitude, latitude]; o shapely Point também é (x=lon, y=lat).
"""

from shapely.geometry import Point, shape


def cps_dentro_poligono(geometry_geojson, cps):
    """
    Filtra os CPs cujo ponto (lat/lng) cai dentro da geometria GeoJSON.

    Args:
        geometry_geojson: dict GeoJSON de um Polygon/MultiPolygon
            (o campo "geometry" de uma Feature do Leaflet.draw).
        cps: iterável de CodigoPostal (com latitude/longitude preenchidos).

    Returns:
        Lista de CodigoPostal contidos no polígono.
    """
    poligono = shape(geometry_geojson)
    dentro = []
    for cp in cps:
        if cp.latitude is None or cp.longitude is None:
            continue
        ponto = Point(float(cp.longitude), float(cp.latitude))
        if poligono.contains(ponto):
            dentro.append(cp)
    return dentro
