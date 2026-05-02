"""Parsers para extractos bancários CSV e OFX."""
import csv
import io
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation


def _parse_amount(s):
    """Converte string numérica europeia/americana em Decimal positivo
    + direction. Retorna (amount, direction) ou (None, None) em erro."""
    if s is None:
        return None, None
    s = str(s).strip()
    if not s:
        return None, None
    is_negative = s.startswith("-")
    s = s.lstrip("+-").replace("€", "").replace(" ", "").replace(" ", "")
    # Normalizar formato europeu (1.234,56) → (1234.56)
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        amt = Decimal(s)
    except (InvalidOperation, ValueError):
        return None, None
    if amt < 0 or is_negative:
        return abs(amt), "DEBIT"
    return amt, "CREDIT"


def _parse_date(s):
    """Tenta vários formatos comuns. Retorna date ou None."""
    if not s:
        return None
    s = str(s).strip()
    for fmt in (
        "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d",
        "%d.%m.%Y", "%Y%m%d",
    ):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            pass
    return None


def parse_csv(file_bytes):
    """Parse CSV genérico. Tenta detectar colunas por palavras-chave nos
    headers: data, descrição, valor (ou débito/crédito separados).
    Retorna lista de dicts {date, description, amount, direction, external_id}.
    """
    text = file_bytes.decode("utf-8-sig", errors="ignore")
    # Detectar separador (auto)
    sample = text[:2000]
    sep = ","
    for s in [";", "\t", "|", ","]:
        if sample.count(s) > sample.count(sep):
            sep = s
    reader = csv.reader(io.StringIO(text), delimiter=sep)
    rows = list(reader)
    if not rows:
        return []
    # Encontrar cabeçalho — primeira row com pelo menos uma palavra-chave
    keywords_date = ("data", "date", "fecha")
    keywords_desc = ("descri", "descr", "memo", "histori", "movimento")
    keywords_amount = ("valor", "amount", "montante", "importe")
    keywords_debit = ("débito", "debito", "debit")
    keywords_credit = ("crédito", "credito", "credit")

    header_idx = 0
    header = rows[0]
    for i, row in enumerate(rows[:10]):
        low = [c.lower() for c in row]
        if any(any(k in c for k in keywords_date) for c in low):
            header = row
            header_idx = i
            break

    low = [c.lower() for c in header]

    def find(keys):
        for j, c in enumerate(low):
            if any(k in c for k in keys):
                return j
        return None

    ci_date = find(keywords_date)
    ci_desc = find(keywords_desc)
    ci_amount = find(keywords_amount)
    ci_debit = find(keywords_debit)
    ci_credit = find(keywords_credit)
    ci_id = find(("ref", "id", "número", "numero"))

    if ci_date is None:
        return []

    out = []
    for row in rows[header_idx + 1:]:
        if not row or len(row) <= ci_date:
            continue
        d = _parse_date(row[ci_date])
        if not d:
            continue
        desc = row[ci_desc] if ci_desc is not None and ci_desc < len(row) else ""
        amount = None
        direction = None
        if ci_amount is not None and ci_amount < len(row):
            amount, direction = _parse_amount(row[ci_amount])
        elif ci_debit is not None or ci_credit is not None:
            db = (
                _parse_amount(row[ci_debit])[0]
                if ci_debit is not None and ci_debit < len(row) else None
            )
            cr = (
                _parse_amount(row[ci_credit])[0]
                if ci_credit is not None and ci_credit < len(row) else None
            )
            if db:
                amount, direction = db, "DEBIT"
            elif cr:
                amount, direction = cr, "CREDIT"
        if amount is None:
            continue
        ext_id = (
            row[ci_id] if ci_id is not None and ci_id < len(row) else ""
        )
        out.append({
            "date": d,
            "description": (desc or "").strip()[:300],
            "amount": amount,
            "direction": direction,
            "external_id": (ext_id or "").strip()[:80],
        })
    return out


def parse_ofx(file_bytes):
    """Parse OFX simples por regex (não depende de libs externas).
    Reconhece blocos <STMTTRN>...</STMTTRN>."""
    text = file_bytes.decode("utf-8", errors="ignore")
    blocks = re.findall(
        r"<STMTTRN>(.*?)</STMTTRN>", text, re.DOTALL | re.IGNORECASE,
    )
    out = []
    for b in blocks:
        def get(tag):
            m = re.search(
                rf"<{tag}>([^<\r\n]+)", b, re.IGNORECASE,
            )
            return m.group(1).strip() if m else ""
        dt = get("DTPOSTED")[:8]  # YYYYMMDD
        d = _parse_date(dt) if len(dt) == 8 else None
        if not d:
            continue
        amt_raw = get("TRNAMT")
        amt, direction = _parse_amount(amt_raw)
        if amt is None:
            continue
        memo = get("MEMO") or get("NAME")
        fitid = get("FITID")
        out.append({
            "date": d,
            "description": memo[:300],
            "amount": amt,
            "direction": direction,
            "external_id": fitid[:80],
        })
    return out


def parse_statement(filename, file_bytes):
    """Detecta tipo pelo nome/conteúdo e devolve lista de transacções."""
    name = (filename or "").lower()
    head = file_bytes[:200].lower()
    if name.endswith(".ofx") or b"<ofx" in head or b"<stmttrn" in head:
        return parse_ofx(file_bytes)
    return parse_csv(file_bytes)
