"""Export das ZonaGeo em GeoJSON para o ReliableMaps.

O formato é um contrato lido pelo ReliableMaps: não renomear campos.
`codigo` é a chave estável (o ReliableMaps atualiza a mesma zona por ele).
"""

from django.utils import timezone

from ..models import AreaCP4, ZonaGeo


def _geometria(poligono):
    """Extrai a geometry GeoJSON (Polygon/MultiPolygon) do que estiver guardado."""
    g = poligono
    if isinstance(g, dict) and g.get("type") == "FeatureCollection":
        feats = g.get("features") or []
        g = feats[0] if feats else None
    if isinstance(g, dict) and g.get("type") == "Feature":
        g = g.get("geometry")
    if isinstance(g, dict) and g.get("type") in ("Polygon", "MultiPolygon"):
        return g
    return None


def _shape(geometry):
    from shapely.geometry import shape
    try:
        return shape(geometry)
    except Exception:
        return None


def _login_cainiao(driver, cainiao):
    if driver is None:
        return None
    if driver.apelido:
        return driver.apelido
    if cainiao is not None:
        m = driver.courier_mappings.filter(partner=cainiao).exclude(courier_name="").first()
        if m:
            return m.courier_name
    return None


def _iso(dt):
    return timezone.localtime(dt).isoformat() if dt else None


def exportar_zonas(desde=None):
    """Devolve (FeatureCollection, números para conferir)."""
    from core.models import Partner
    from settlements.models import CainiaoHub

    cainiao = Partner.objects.filter(name__iexact="CAINIAO").first()
    hubs = [
        (h.name, set(h.cp4_list()))
        for h in CainiaoHub.objects.prefetch_related("cp4_codes").order_by("name")
    ]
    areas = [
        (a.cp4, s)
        for a in AreaCP4.objects.exclude(poligono=None).order_by("cp4")
        for s in [_shape(a.poligono)]
        if s is not None
    ]

    qs = ZonaGeo.objects.select_related("motorista_default").order_by("codigo")
    todas = list(qs)
    zonas = [z for z in todas if desde is None or z.updated_at >= desde]

    features, invalidas = [], []
    for z in zonas:
        geometry = _geometria(z.poligono) if z.poligono else None
        cp4s = []
        if geometry:
            zs = _shape(geometry)
            if zs is None or not zs.is_valid:
                invalidas.append(z.codigo)
            if zs is not None:
                if not zs.is_valid:
                    zs = zs.buffer(0)
                cp4s = [cp4 for cp4, s in areas if zs.intersects(s)]
        features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "codigo": z.codigo,
                "nome": z.nome,
                "cor": z.cor,
                "ativa": z.is_active,
                "hubs": [nome for nome, hcp4 in hubs if hcp4 & set(cp4s)],
                "cp4s": cp4s,
                "motorista_default": _login_cainiao(z.motorista_default, cainiao),
                "atualizada_em": _iso(z.updated_at),
            },
        })

    fc = {
        "type": "FeatureCollection",
        "exportado_em": _iso(timezone.now()),
        "features": features,
        # A gestão não regista zonas apagadas: o ReliableMaps compara a lista inteira.
        "apagadas": None,
    }
    numeros = {
        "total": len(todas),
        "ativas": sum(1 for z in todas if z.is_active),
        "inativas": sum(1 for z in todas if not z.is_active),
        "sem_poligono": sum(1 for z in todas if not _geometria(z.poligono)),
        "invalidas": invalidas,
        "hubs": [{"name": nome, "cp4s": sorted(hcp4)} for nome, hcp4 in hubs],
    }
    return fc, numeros
