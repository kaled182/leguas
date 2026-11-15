"""Regra "vários pacotes na mesma porta" (Cainiao "Modelo AA").

Quando o motorista entrega mais do que um pacote à porta (não-PUDO) na
mesma morada no mesmo dia, o 1º pacote é pago ao preço normal e cada
adicional a `partner.same_door_additional_price`.

Chave do grupo: dia (task_date) + login Cainiao (courier_name) +
morada normalizada `CP7|rua|número da porta` (`address_key`).

O número de paragem (Stop Number / Task Group Order) NÃO entra na
chave. A Cainiao numera cada leva de tarefas desde o 1, por isso o
mesmo número aparece em moradas diferentes no mesmo dia.

Salvaguardas pelas coordenadas do destinatário:
  - com número de porta: se dois pacotes do grupo ficam a mais de
    300 m, o grupo não junta e fica para revisão;
  - sem número de porta: só junta se todos os pacotes têm coordenadas
    e ficam a menos de 50 m uns dos outros.

- `address_key(task)`: chave da morada (ou None).
- `same_door_extra_ids(task_ids, partner)`: ids dos pacotes adicionais
  (todos menos o 1º entregue de cada grupo).
- `same_door_review_groups(tasks)`: grupos que não juntaram por causa
  da distância (para revisão).
"""
from __future__ import annotations

import math
import re
from collections import defaultdict

from unidecode import unidecode

MAX_SPREAD_WITH_NUMBER_M = 300
MAX_SPREAD_WITHOUT_NUMBER_M = 50

_CP7_TEXT_RE = re.compile(r"\b(\d{4})\s*[-–]\s*(\d{3})\b")
_WAYBILL_CP7_RE = re.compile(r"^[A-Z]{2}[A-Z]{3}(\d{7})")
# Separa letras de números colados ("no670" → "no 670", "23a" → "23 a")
_ALNUM_SPLIT_RE = re.compile(r"(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])")

_ABBREV = {
    "r": "rua", "rua": "rua",
    "av": "avenida", "avd": "avenida", "avda": "avenida", "avenida": "avenida",
    "tv": "travessa", "trav": "travessa", "tr": "travessa", "travessa": "travessa",
    "lg": "largo", "lgo": "largo", "largo": "largo",
    "pc": "praca", "pca": "praca", "pr": "praca", "praca": "praca",
    "al": "alameda", "alam": "alameda", "alameda": "alameda",
    "est": "estrada", "estr": "estrada", "estrada": "estrada",
    "cc": "calcada", "calc": "calcada", "calcada": "calcada",
    "bc": "beco", "beco": "beco",
    "lug": "lugar", "lugar": "lugar",
    "urb": "urbanizacao", "urbanizacao": "urbanizacao",
    "qta": "quinta", "qt": "quinta", "quinta": "quinta",
    "bro": "bairro", "b": "bairro", "bairro": "bairro",
    "lot": "loteamento", "loteamento": "loteamento",
    "pct": "praceta", "praceta": "praceta",
    "estr": "estrada", "en": "estrada nacional",
    "s": "sao", "sto": "santo", "sta": "santa", "dr": "doutor", "eng": "engenheiro",
}
# Tipo de via: entra na normalização, mas não na chave ("Rua Igreja" → "igreja").
_STREET_TYPES = {
    "rua", "avenida", "travessa", "largo", "praca", "alameda", "estrada",
    "calcada", "beco", "lugar", "praceta", "nacional", "caminho", "via",
}
_STOPWORDS = {"de", "da", "do", "das", "dos", "e", "a", "o", "em", "na", "nas", "nos", "ao"}
# Marcas de número de porta: o número a seguir é a porta.
_NUM_MARKERS = {"n", "no", "nr", "num", "numero", "lote", "lt", "porta"}
# Fração/andar: a palavra e o número a seguir não contam.
_FLOOR_WORDS = {
    "rc", "esq", "esquerdo", "esquerda", "dto", "dt", "dta", "direito", "direita",
    "andar", "piso", "fracao", "frac", "fr", "bloco", "bl", "loja", "lj",
    "cave", "sub", "res", "chao", "apartamento", "apart", "apt", "apto", "hab", "habitacao",
    "frente", "tras", "trs", "esc", "escritorio", "sala",
}
_POBOX_WORDS = {"cx", "caixa", "apartado"}
_MONTHS = {
    "janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho",
    "agosto", "setembro", "outubro", "novembro", "dezembro",
}


def is_same_door_active(partner):
    return bool(partner and getattr(partner, "same_door_enabled", False))


# ---------------------------------------------------------------- CP7

def task_cp7(task):
    """CP7 `NNNN-NNN` do Zip Code. Se o Zip Code só tem o CP4, usa o CP7
    do número da guia (CNPRT4740141… → 4740-141). "" se não há."""
    digits = re.sub(r"\D", "", getattr(task, "zip_code", "") or "")
    if len(digits) == 7:
        return f"{digits[:4]}-{digits[4:]}"
    m = _WAYBILL_CP7_RE.match((getattr(task, "waybill_number", "") or "").upper())
    if m and (not digits or m.group(1).startswith(digits[:4])):
        d = m.group(1)
        return f"{d[:4]}-{d[4:]}"
    return digits[:4]


# ------------------------------------------------------------ morada

_ORD_RE = re.compile(r"(?<=\d)\s*[\u00ba\u00b0\u00aa]")
_NUM_SIGN_RE = re.compile(r"\bn\s*\.?\s*[\u00ba\u00b0]", re.IGNORECASE)
_RC_RE = re.compile(r"\b(?:r\s*/\s*c(?:hao)?|r\s*/\s*ch|res\s+do\s+chao)\b")
# Depois de "1º"/"2a": se vem uma destas, o número é o andar.
_SIDE_WORDS = {
    "andar", "piso", "esq", "esquerdo", "esquerda", "dto", "dt", "dta",
    "direito", "direita", "frente", "tras", "trs",
}


def _tokens(text, cp7=""):
    s = text or ""
    s = _NUM_SIGN_RE.sub(" n ", s)          # "n.º 23", "n° 23" → "n 23"
    s = _ORD_RE.sub(" ord ", s)             # "1º", "2°", "3ª" → "1 ord"
    s = unidecode(s).lower()
    s = _RC_RE.sub(" rc ", s)               # "r/c", "r/chão" → "rc"
    s = _CP7_TEXT_RE.sub(" ", s)
    if cp7 and len(cp7) == 8:
        s = re.sub(rf"\b{cp7[:4]}\s?{cp7[5:]}\b", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = _ALNUM_SPLIT_RE.sub(" ", s)
    out = []
    for t in s.split():
        out.extend(_ABBREV.get(t, t).split())
    return out


def parse_address(text, cp7=""):
    """Devolve (rua, número) da morada.

    rua: palavras antes do número da porta, sem tipo de via, sem
    palavras vazias e sem fração/andar. Sem número de porta: todas as
    palavras que sobram.
    número: o 1º número de porta reconhecido (depois de "nº", "n",
    "nr", "lote", ou o número solto a seguir ao nome da rua). Uma caixa
    postal ("cx 490") conta se não há outro número. "" se não há.
    """
    toks = _tokens(text, cp7)
    street, number, pobox, lead = [], "", "", ""
    i, n = 0, len(toks)
    while i < n:
        t = toks[i]
        nxt = toks[i + 1] if i + 1 < n else ""
        if t == "ord":
            i += 1
            continue
        if t in _FLOOR_WORDS:
            # "andar 2", "bloco 3", "loja 4": o número é da fração.
            # "esq", "dto", "rc" ficam depois do número: não o consomem.
            i += 2 if nxt.isdigit() and t not in _SIDE_WORDS | {"rc"} else 1
            continue
        if t in _POBOX_WORDS and nxt.isdigit():
            pobox = pobox or nxt
            i += 2
            continue
        if t in _NUM_MARKERS:
            # "n 23", "no 23", "n o 23", "lote 5"
            j = i + 1
            if j < n and toks[j] == "o" and t == "n":
                j += 1
            if j < n and toks[j].isdigit():
                if not street and i > 0 and toks[i - 1] in _STREET_TYPES:
                    # "Estrada Nacional n 1": o número é o nome da via
                    street.append(toks[j])
                    i = j + 1
                    continue
                number = toks[j]
                break
            i += 1
            continue
        if t.isdigit():
            ordinal = nxt == "ord" or (
                nxt in ("o", "a") and i + 2 < n and toks[i + 2] in _SIDE_WORDS)
            # "Rua 25 de Abril", "Rua 1º de Maio": o número é do nome da rua
            k = i + 2 if ordinal or nxt in ("o", "a") else i + 1
            if k + 1 < n and toks[k] in _STOPWORDS and toks[k + 1] in _MONTHS:
                street.append(t)
                i = k
                continue
            # "EN 13": o número a seguir ao tipo de via é o nome da via
            if not street and i > 0 and toks[i - 1] in _STREET_TYPES:
                street.append(t)
                i += 1
                continue
            # "1º esq", "2a dto", "2 andar": é o andar ("77 rc" é porta)
            if ordinal:
                i += 2
                continue
            if nxt in ("andar", "piso"):
                i += 1
                continue
            if street:
                number = t
                break
            # "185 Rua da Caldeira": número antes da rua
            lead = lead or t
            i += 1
            continue
        if t in _STOPWORDS or t in _STREET_TYPES:
            i += 1
            continue
        street.append(t)
        i += 1
    if not number:
        number = lead or pobox
    return " ".join(street), number


def normalize_address(text, cp7=""):
    """Morada comparável `rua|número` (sem CP)."""
    street, number = parse_address(text, cp7)
    return f"{street}|{number}"


def address_key(task):
    """Chave `CP7|rua|número`. None se não há rua nem número."""
    cp7 = task_cp7(task)
    street, number = parse_address(getattr(task, "detailed_address", ""), cp7)
    if not street and not number:
        return None
    return f"{cp7}|{street}|{number}"


# ------------------------------------------------------- coordenadas

def _coord(task):
    try:
        lat = float((task.receiver_latitude or "").strip())
        lng = float((task.receiver_longitude or "").strip())
    except (TypeError, ValueError, AttributeError):
        return None
    if lat == 0 and lng == 0:
        return None
    return lat, lng


def _dist_m(a, b):
    lat1, lng1 = map(math.radians, a)
    lat2, lng2 = map(math.radians, b)
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2)
    return 2 * 6371000 * math.asin(math.sqrt(h))


def max_spread_m(tasks):
    """Maior distância (m) entre 2 pacotes com coordenadas. 0 se < 2."""
    pts = [c for c in (_coord(t) for t in tasks) if c]
    best = 0.0
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            best = max(best, _dist_m(pts[i], pts[j]))
    return best


# --------------------------------------------------------- agrupar

def _candidate_groups(tasks):
    by_key = defaultdict(list)
    for t in tasks:
        k = address_key(t)
        if k is None:
            continue
        by_key[(t.task_date, (t.courier_name or "").strip(), k)].append(t)
    return [(k, g) for k, g in by_key.items() if len(g) > 1]


def classify_groups(tasks):
    """Devolve (grupos_que_juntam, grupos_para_revisão).

    Um grupo é a lista de tasks com a mesma (dia, login, address_key).
    """
    joined, review = [], []
    for (_day, _login, key), g in _candidate_groups(tasks):
        has_number = not key.endswith("|")
        if has_number:
            if max_spread_m(g) > MAX_SPREAD_WITH_NUMBER_M:
                review.append(g)
            else:
                joined.append(g)
        else:
            all_coords = all(_coord(t) for t in g)
            if all_coords and max_spread_m(g) < MAX_SPREAD_WITHOUT_NUMBER_M:
                joined.append(g)
    return joined, review


def group_same_door(tasks):
    """Portas com 2 ou mais pacotes (só os grupos que juntam)."""
    return classify_groups(tasks)[0]


def same_door_review_groups(tasks):
    """Grupos com a mesma morada mas pacotes a mais de 300 m: não
    juntam e ficam para revisão."""
    return classify_groups(tasks)[1]


def _sort_group(g):
    g.sort(key=lambda t: (t.delivery_time is None, t.delivery_time or 0, t.id))
    return g


def sorted_same_door_groups(tasks):
    """Portas com 2+ pacotes; em cada grupo o 1º é o primeiro entregue
    (fallback: id mais baixo). Grupos ordenados por dia."""
    groups = [_sort_group(g) for g in group_same_door(tasks)]
    groups.sort(key=lambda g: (g[0].task_date, g[0].id))
    return groups


def extra_ids_from_tasks(tasks):
    """Ids dos pacotes adicionais (todos menos o 1º entregue de cada porta)."""
    return {t.id for g in sorted_same_door_groups(tasks) for t in g[1:]}


SAME_DOOR_FIELDS = (
    "id", "waybill_number", "task_date", "delivery_time", "detailed_address",
    "zip_code", "receiver_latitude", "receiver_longitude", "courier_name",
)


def same_door_extra_ids(task_ids, partner):
    """Devolve o set de ids de tasks que são pacotes ADICIONAIS na
    mesma porta (a 1ª de cada (dia, login, morada) fica de fora).

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
    return extra_ids_from_tasks(list(qs.only(*SAME_DOOR_FIELDS)))
