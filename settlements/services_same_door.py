"""Regra "vários pacotes na mesma porta" (Cainiao "Modelo AA").

Quando o motorista entrega mais do que um pacote à porta (não-PUDO) na
mesma morada no mesmo dia, o 1º pacote é pago ao preço normal e cada
adicional a `partner.same_door_additional_price`.

Duas tasks do mesmo dia estão na mesma porta quando:
  - têm a mesma morada normalizada + CP (`door_key`), OU
  - têm a mesma paragem na rota da Cainiao (`stop_key`: driver +
    Stop Number). Apanha a mesma morada escrita de formas diferentes.

- `door_key(task)` / `stop_key(task)`: chaves de agrupamento.
- `same_door_extra_ids(task_ids, partner)`: ids das tasks que são
  pacotes adicionais (todas menos a 1ª de cada grupo (dia, porta)).
"""
from __future__ import annotations

import re
from collections import defaultdict

from unidecode import unidecode

_ZIP_RE = re.compile(r"\b\d{4}\s*-\s*\d{3}\b")
# "nº", "n.º", "no", "nr", "numero" antes do número da porta
_NUM_WORD_RE = re.compile(r"\b(?:n o|numero|num|nr|no|n)\b")
# Separa letras de números colados ("no670" → "no 670")
_ALNUM_SPLIT_RE = re.compile(r"(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])")


def is_same_door_active(partner):
    return bool(partner and getattr(partner, "same_door_enabled", False))


def normalize_address(text):
    """Morada comparável: minúsculas sem acentos, sem CP no texto, sem
    "nº" e sem repetições ("58 58", "Rua X 10 Rua X 10")."""
    s = unidecode(text or "").lower()
    s = _ZIP_RE.sub(" ", s)
    s = re.sub(r"[^\w]+", " ", s)
    s = _ALNUM_SPLIT_RE.sub(" ", s)
    s = _NUM_WORD_RE.sub(" ", s)
    tokens = s.split()
    # Tokens repetidos seguidos ("58 58")
    tokens = [t for i, t in enumerate(tokens) if i == 0 or t != tokens[i - 1]]
    # Morada inteira repetida ("rua x 10 rua x 10")
    half = len(tokens) // 2
    if half and len(tokens) % 2 == 0 and tokens[:half] == tokens[half:]:
        tokens = tokens[:half]
    return " ".join(tokens)


def door_key(task):
    """Chave da porta pela morada.

    Usa a morada completa normalizada (inclui andar/porta) + CP, para
    não juntar apartamentos diferentes do mesmo prédio. Sem morada,
    cai para as coordenadas exactas do destinatário. None se não há
    dados suficientes.
    """
    addr = normalize_address(task.detailed_address)
    zc = re.sub(r"\s+", "", task.zip_code or "")
    if addr:
        return ("addr", zc, addr)
    lat = (task.receiver_latitude or "").strip()
    lng = (task.receiver_longitude or "").strip()
    if lat and lng:
        return ("geo", lat, lng)
    return None


def stop_key(task):
    """Chave da paragem na rota da Cainiao (Stop Number). None se a
    task não tem paragem ("-1" ou vazio)."""
    stop = (getattr(task, "task_group_order", "") or "").strip()
    if not stop or stop == "-1":
        return None
    return ("stop", (task.courier_name or "").strip(), stop)


def group_same_door(tasks):
    """Agrupa tasks em portas (mesmo dia + door_key OU stop_key).

    Devolve lista de grupos (listas de tasks), só com grupos de 2 ou mais.
    """
    parent = {}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    by_id = {}
    first_by_key = {}
    for t in tasks:
        by_id[t.id] = t
        parent[t.id] = t.id
        for k in (door_key(t), stop_key(t)):
            if k is None:
                continue
            kk = (t.task_date, k)
            if kk in first_by_key:
                union(first_by_key[kk], t.id)
            else:
                first_by_key[kk] = t.id

    groups = defaultdict(list)
    for tid in by_id:
        groups[find(tid)].append(by_id[tid])
    return [g for g in groups.values() if len(g) > 1]


def sorted_same_door_groups(tasks):
    """Portas com 2+ pacotes; em cada grupo o 1º é o primeiro entregue
    (fallback: id mais baixo). Grupos ordenados por dia."""
    groups = group_same_door(tasks)
    for g in groups:
        g.sort(key=lambda t: (t.delivery_time is None, t.delivery_time or 0, t.id))
    groups.sort(key=lambda g: (g[0].task_date, g[0].id))
    return groups


def extra_ids_from_tasks(tasks):
    """Ids dos pacotes adicionais (todos menos o 1º entregue de cada porta)."""
    return {t.id for g in sorted_same_door_groups(tasks) for t in g[1:]}


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
        "courier_name", "task_group_order",
    )
    return extra_ids_from_tasks(list(rows))
