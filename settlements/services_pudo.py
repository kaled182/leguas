"""Helpers para regras PUDO (Pickup & Drop-Off).

Contém:
- `pudo_key(task)`: chave única do PUDO para agregação.
- `haversine_meters(lat1, lng1, lat2, lng2)`: distância entre pontos.
- `is_fake_delivery_suspect(task, tolerance_m)`: True se receiver vs
  actual coords excedem a tolerância.
- `compute_pudo_payment(n, partner)`: 1ª + (N-1) × adicional.
- `aggregate_pudo_packages(tasks_qs)`: agrupa tasks PUDO por chave e
  devolve {pudo_key: [tasks...]}.
- `_PudoTaskLite_dict_to_obj(d)`: helper para converter dict do
  .values() em namedtuple compatível com pudo_key/etc.
"""
from __future__ import annotations

import math
from collections import defaultdict, namedtuple
from decimal import Decimal


# Tipo leve para passar tasks PUDO entre módulos sem precisar de
# CainiaoOperationTask completo. Compatível com as funções
# pudo_key/is_fake_delivery_suspect que só lêem estes atributos.
_PudoTaskLite = namedtuple("_PudoTaskLite", [
    "id", "waybill_number", "task_date",
    "receiver_latitude", "receiver_longitude",
    "actual_latitude", "actual_longitude",
    "zip_code", "detailed_address",
])


def _PudoTaskLite_dict_to_obj(d):
    """Converte um dict (ex: do .values() do queryset) em
    _PudoTaskLite. Tolerante a chaves em falta.
    """
    return _PudoTaskLite(
        id=d.get("id"),
        waybill_number=d.get("waybill_number") or "",
        task_date=d.get("task_date"),
        receiver_latitude=d.get("receiver_latitude") or "",
        receiver_longitude=d.get("receiver_longitude") or "",
        actual_latitude=d.get("actual_latitude") or "",
        actual_longitude=d.get("actual_longitude") or "",
        zip_code=d.get("zip_code") or "",
        detailed_address=d.get("detailed_address") or "",
    )


def haversine_meters(lat1, lng1, lat2, lng2):
    """Distância em metros entre 2 coordenadas (haversine)."""
    try:
        lat1 = float(lat1)
        lng1 = float(lng1)
        lat2 = float(lat2)
        lng2 = float(lng2)
    except (TypeError, ValueError):
        return None
    R = 6371000.0  # raio da Terra em metros
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _norm_coord(s):
    """Arredonda string lat/lng a 4 decimais (≈11m precisão)."""
    if not s:
        return None
    try:
        return round(float(s), 4)
    except (TypeError, ValueError):
        return None


def pudo_key(task):
    """Devolve chave estável que identifica o PUDO da task.

    Prioridade:
      1. (receiver_lat, receiver_lng) arredondado a 4 decimais — mais
         preciso e robusto contra variações de digitação da morada.
      2. (zip_code, detailed_address normalizado) como fallback se
         coordenadas indisponíveis.
      3. None se não há dados suficientes (task não agregável).
    """
    lat = _norm_coord(task.receiver_latitude)
    lng = _norm_coord(task.receiver_longitude)
    if lat is not None and lng is not None:
        return ("geo", lat, lng)
    addr = (task.detailed_address or "").strip().lower()
    zc = (task.zip_code or "").strip()
    if addr:
        return ("addr", zc, addr)
    return None


def is_fake_delivery_suspect(task, tolerance_m):
    """True se o local de entrega real (actual_*) está a > tolerance_m
    do receiver_*. Devolve (suspeita: bool, distance_m: float|None).
    """
    if not (task.actual_latitude and task.actual_longitude
            and task.receiver_latitude and task.receiver_longitude):
        return False, None
    d = haversine_meters(
        task.receiver_latitude, task.receiver_longitude,
        task.actual_latitude, task.actual_longitude,
    )
    if d is None:
        return False, None
    return d > tolerance_m, d


def compute_pudo_payment(n, partner):
    """Pagamento total para N pacotes entregues no MESMO PUDO.

    Fórmula: 1ª + (N-1) × adicional. Mínimo 1 pacote = preço da 1ª.
    """
    if n <= 0:
        return Decimal("0")
    first = (
        partner.pudo_first_delivery_price
        if partner else Decimal("1.00")
    )
    extra = (
        partner.pudo_additional_delivery_price
        if partner else Decimal("0.20")
    )
    if n == 1:
        return first
    return first + (n - 1) * extra


def aggregate_pudo_packages(tasks):
    """Agrupa tasks PUDO por pudo_key. Tasks sem chave caem em
    bucket "_unkeyed" (cada uma conta como 1 PUDO isolado, garante
    pelo menos 1ª entrega).
    """
    grouped = defaultdict(list)
    for t in tasks:
        k = pudo_key(t)
        if k is None:
            grouped[("solo", t.id)].append(t)
        else:
            grouped[k].append(t)
    return grouped


def split_pudo_and_door_tasks(tasks_iterable):
    """Separa tasks num par (pudo_tasks, door_tasks) com base em
    delivery_type. Aceita queryset ou lista.
    """
    pudo, door = [], []
    for t in tasks_iterable:
        if (t.delivery_type or "").upper().strip() == "PUDO":
            pudo.append(t)
        else:
            door.append(t)
    return pudo, door


def find_fake_delivery_suspects(date_from, date_to, partner):
    """Lista CainiaoOperationTask que são suspeitas de Fake Delivery.

    Critérios:
      - delivery_type=PUDO
      - task_status=Delivered
      - receiver_lat/lng e actual_lat/lng preenchidos
      - distância haversine > partner.pudo_geo_tolerance_meters
      - sem DriverClaim já confirmado para este waybill
        (claim_type=FAKE_DELIVERY ou waybill_number match)

    Devolve queryset annotated + helper para distância calculada
    em Python (não SQL — haversine não é trivial em SQL puro).

    Cada elemento retornado é um dict com:
      - id, waybill_number, task_date, courier_name, driver
      - receiver_lat/lng, actual_lat/lng
      - distance_m
      - existing_claim_id (None se não há claim vinculado)
    """
    from .models import CainiaoOperationTask, DriverClaim

    if not partner or not getattr(partner, "pudo_enabled", False):
        return []

    tolerance = partner.pudo_geo_tolerance_meters or 200

    qs = CainiaoOperationTask.objects.filter(
        delivery_type__iexact="PUDO",
        task_status="Delivered",
        task_date__range=(date_from, date_to),
    ).exclude(receiver_latitude="").exclude(
        receiver_longitude="",
    ).exclude(actual_latitude="").exclude(actual_longitude="")

    # Pré-buscar DriverClaims existentes para evitar mostrar
    # suspeitas já tratadas
    existing_claims_by_wb = {}
    waybills = list(qs.values_list("waybill_number", flat=True))
    if waybills:
        for c in DriverClaim.objects.filter(
            waybill_number__in=waybills,
        ).values("id", "waybill_number", "claim_type", "status"):
            wb = c["waybill_number"]
            if wb and wb not in existing_claims_by_wb:
                existing_claims_by_wb[wb] = c

    suspects = []
    for t in qs:
        d = haversine_meters(
            t.receiver_latitude, t.receiver_longitude,
            t.actual_latitude, t.actual_longitude,
        )
        if d is None or d <= tolerance:
            continue
        existing = existing_claims_by_wb.get(t.waybill_number)
        suspects.append({
            "task": t,
            "id": t.id,
            "waybill_number": t.waybill_number,
            "task_date": t.task_date,
            "courier_name": t.courier_name,
            "courier_id_cainiao": t.courier_id_cainiao,
            "receiver_latitude": t.receiver_latitude,
            "receiver_longitude": t.receiver_longitude,
            "actual_latitude": t.actual_latitude,
            "actual_longitude": t.actual_longitude,
            "destination_city": t.destination_city,
            "detailed_address": t.detailed_address,
            "distance_m": int(d),
            "existing_claim_id": (
                existing["id"] if existing else None
            ),
            "existing_claim_status": (
                existing["status"] if existing else None
            ),
        })
    suspects.sort(key=lambda s: -s["distance_m"])
    return suspects


def compute_pudo_total_for_driver(pudo_tasks, partner):
    """Calcula o total de pagamento para uma lista de tasks PUDO de
    um driver, agrupando por PUDO e aplicando a fórmula.

    Devolve: (total_amount Decimal, n_pudos_distintos int, breakdown
    list[{pudo_key, n_packages, amount}]).
    """
    grouped = aggregate_pudo_packages(pudo_tasks)
    total = Decimal("0.00")
    breakdown = []
    for k, tasks_in_pudo in grouped.items():
        n = len(tasks_in_pudo)
        amt = compute_pudo_payment(n, partner)
        total += amt
        breakdown.append({
            "pudo_key": k,
            "n_packages": n,
            "amount": amt,
        })
    return total, len(grouped), breakdown
