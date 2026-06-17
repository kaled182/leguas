"""Serviço de Triagem — resolve a zona de entrega de um CP ou waybill.

Dado um código postal (4990-008 / 7 dígitos / só CP4) ou uma etiqueta
(waybill), devolve a zona desenhada (ZonaGeo) que contém o ponto, mais
as coordenadas e a localização. Partilhado entre o Modo Triagem web
(geozonas/mapa) e a API da app do motorista.
"""
import re

from geozonas.models import CodigoPostal, ZonaGeo


def resolver_triagem(q):
    """Devolve um dict com a zona de entrega para `q` (CP ou waybill).

    Estrutura: {ok, encontrado, q, cp, waybill, localidade, concelho,
    freguesia, lat, lng, zona{id,nome,cor,motorista}}.
    """
    from shapely.geometry import Point, shape

    from settlements.models import CainiaoOperationTask

    s = (q or "").strip().upper()
    cp = None
    cp_str = ""
    waybill = ""
    lat = lng = None
    localidade = concelho = ""

    m = re.match(r"^(\d{4})-?(\d{3})$", s)
    if m:  # CP completo (XXXX-XXX ou 7 dígitos)
        cp = CodigoPostal.objects.filter(
            cp4=m.group(1), cp3=m.group(2)
        ).select_related("localidade", "concelho").first()
    elif re.match(r"^\d{4}$", s):  # só CP4
        cp = CodigoPostal.objects.filter(
            cp4=s, latitude__isnull=False
        ).select_related("localidade", "concelho").first()
    else:  # waybill / etiqueta
        waybill = s
        # O CP vem no início do waybill: prefixo de letras + 7 dígitos.
        # Ex.: CNPRT45255041234... → 4525504 → 4525-504.
        gm = re.match(r"^[A-Z]+(\d{4})(\d{3})", s)
        if gm:
            cp_str = f"{gm.group(1)}-{gm.group(2)}"
            cp = CodigoPostal.objects.filter(
                cp4=gm.group(1), cp3=gm.group(2)
            ).select_related("localidade", "concelho").first()
        # Fallback: a task real dá coordenadas precisas (se o CP não estiver
        # importado, ou para etiquetas sem o CP no início).
        if cp is None or cp.latitude is None:
            task = (
                CainiaoOperationTask.objects.filter(waybill_number=s)
                .order_by("-task_date").first()
            )
            if task:
                localidade = task.destination_city or ""
                for la, lo in [
                    (task.receiver_latitude, task.receiver_longitude),
                    (task.actual_latitude, task.actual_longitude),
                ]:
                    try:
                        if la and lo:
                            lat, lng = float(la), float(lo)
                            break
                    except (TypeError, ValueError):
                        pass
                if cp is None:
                    zm = re.match(
                        r"^(\d{4})-?(\d{3})", (task.zip_code or "").strip()
                    )
                    if zm:
                        cp = CodigoPostal.objects.filter(
                            cp4=zm.group(1), cp3=zm.group(2)
                        ).select_related("localidade", "concelho").first()
                        cp_str = f"{zm.group(1)}-{zm.group(2)}"

    freguesia = ""
    if cp:
        cp_str = cp.codigo_postal
        if lat is None and cp.latitude is not None:
            lat, lng = float(cp.latitude), float(cp.longitude)
        localidade = localidade or (cp.localidade.nome if cp.localidade else "")
        concelho = cp.concelho.nome if cp.concelho else ""
        if cp.freguesia_id:
            freguesia = cp.freguesia.nome

    if lat is None or lng is None:
        return {
            "ok": True, "encontrado": False, "q": q, "cp": cp_str,
            "waybill": waybill,
        }

    pt = Point(lng, lat)
    zona = None
    for z in (
        ZonaGeo.objects.filter(is_active=True)
        .exclude(poligono__isnull=True)
        .select_related("motorista_default")
    ):
        try:
            if shape(z.poligono).contains(pt):
                mot = ""
                if z.motorista_default_id:
                    md = z.motorista_default
                    mot = md.nome_completo or md.apelido or ""
                zona = {
                    "id": z.id, "nome": z.nome, "cor": z.cor,
                    "motorista": mot,
                }
                break
        except Exception:  # noqa: BLE001 — polígono inválido, ignora
            continue

    return {
        "ok": True, "encontrado": True, "q": q, "cp": cp_str,
        "waybill": waybill, "localidade": localidade, "concelho": concelho,
        "freguesia": freguesia, "lat": lat, "lng": lng, "zona": zona,
    }
