"""Regra "vários pacotes na mesma porta" (Cainiao "Modelo AA").

Quando o motorista entrega mais do que um pacote à porta (não-PUDO) na
mesma morada no mesmo dia, o 1º pacote é pago ao preço normal e cada
adicional a `partner.same_door_additional_price`.

- `door_key(task)`: chave da "porta" (morada normalizada + CP; fallback
  coordenadas exactas do destinatário).
- `same_door_extra_ids(task_ids, partner)`: ids das tasks que são
  pacotes adicionais (todas menos a 1ª de cada (dia, porta)).
"""
from __future__ import annotations

import re
from collections import defaultdict


def is_same_door_active(partner):
    return bool(partner and getattr(partner, "same_door_enabled", False))


def door_key(task):
    """Chave que identifica a porta de entrega.

    Usa a morada completa normalizada (inclui andar/porta) + CP, para
    não juntar apartamentos diferentes do mesmo prédio. Sem morada,
    cai para as coordenadas exactas do destinatário. None se não há
    dados suficientes (a task conta como porta isolada).
    """
    addr = re.sub(r"[^\w]+", " ", (task.detailed_address or "").lower()).strip()
    zc = re.sub(r"\s+", "", task.zip_code or "")
    if addr:
        return ("addr", zc, addr)
    lat = (task.receiver_latitude or "").strip()
    lng = (task.receiver_longitude or "").strip()
    if lat and lng:
        return ("geo", lat, lng)
    return None


def same_door_extra_ids(task_ids, partner):
    """Devolve o set de ids de tasks que são pacotes ADICIONAIS na
    mesma porta (a 1ª de cada (dia, porta) fica de fora).

    Vazio se a regra não está activa no parceiro. Respeita
    `same_door_start_date` e ignora PUDO quando as regras PUDO estão
    activas (essas têm fórmula própria).
    """
    if not is_same_door_active(partner) or not task_ids:
        return set()
    from .models import CainiaoOperationTask

    qs = CainiaoOperationTask.objects.filter(id__in=list(task_ids))
    start = getattr(partner, "same_door_start_date", None)
    if start:
        qs = qs.filter(task_date__gte=start)
    if getattr(partner, "pudo_enabled", False):
        qs = qs.exclude(delivery_type__iexact="PUDO")
    rows = qs.only(
        "id", "task_date", "delivery_time", "detailed_address",
        "zip_code", "receiver_latitude", "receiver_longitude",
    )

    groups = defaultdict(list)
    for t in rows:
        k = door_key(t)
        if k is None:
            continue
        groups[(t.task_date, k)].append(t)

    extras = set()
    for tasks in groups.values():
        if len(tasks) < 2:
            continue
        # 1º pacote = o primeiro entregue (fallback: id mais baixo)
        tasks.sort(key=lambda t: (t.delivery_time is None, t.delivery_time or 0, t.id))
        extras.update(t.id for t in tasks[1:])
    return extras
