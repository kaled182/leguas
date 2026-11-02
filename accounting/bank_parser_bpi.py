"""Leitor do extracto de conta em PDF do BPI (BPI Net Empresas).

O PDF tem colunas em posições fixas: data do movimento (só aparece
quando muda), data-valor, descrição, valor e saldo. Cada linha é
verificada pelo saldo: saldo anterior + valor = saldo da linha.
"""
import hashlib
import re
from datetime import date
from decimal import Decimal

# Limites das colunas (x0, em pontos) medidos nos extractos de 2026.
_X_VAL_DATE = 80
_X_DESC = 110
_X_AMOUNT = 425
_X_BALANCE = 540

_DATE = re.compile(r"^\d{2}/\d{2}$")
_AMOUNT = re.compile(r"^-?\d{1,3}(?: \d{3})*,\d{2}$")
_IBAN_IN_DESC = re.compile(r"\b([A-Z]{2}\d{2}[A-Z0-9]{10,30})\b")


class BpiStatementError(ValueError):
    """O PDF não é um extracto BPI ou os saldos não conferem."""


def _amount(text):
    text = text.strip()
    if not _AMOUNT.match(text):
        return None
    return Decimal(text.replace(" ", "").replace(",", "."))


def _lines(page):
    """Agrupa as palavras da página por linha (tolerância de 3 pontos)."""
    rows = []
    for w in sorted(page.extract_words(), key=lambda w: (w["top"], w["x0"])):
        if rows and abs(rows[-1][0] - w["top"]) <= 3:
            rows[-1][1].append(w)
        else:
            rows.append([w["top"], [w]])
    return [sorted(ws, key=lambda w: w["x0"]) for _, ws in rows]


def _columns(words):
    cols = {"mov": [], "val": [], "desc": [], "amount": [], "balance": []}
    for w in words:
        x = w["x0"]
        if x < _X_VAL_DATE:
            key = "mov"
        elif x < _X_DESC:
            key = "val"
        elif x < _X_AMOUNT:
            key = "desc"
        elif x < _X_BALANCE:
            key = "amount"
        else:
            key = "balance"
        cols[key].append(w["text"])
    return {k: " ".join(v) for k, v in cols.items()}


def _full_date(ddmm, period_from, period_to):
    day, month = (int(x) for x in ddmm.split("/"))
    year = period_to.year
    # Extracto de dezembro com movimentos de janeiro, ou o contrário.
    if period_from.year != period_to.year and month >= period_from.month:
        year = period_from.year
    return date(year, month, day)


def _external_id(account, mov_date, desc, amount, balance):
    raw = f"{account}|{mov_date:%Y-%m-%d}|{desc}|{amount}|{balance}"
    return "bpi:" + hashlib.sha1(raw.encode()).hexdigest()[:24]


def parse_bpi_pdf(fileobj):
    """Lê o PDF e devolve o cabeçalho e os movimentos.

    Levanta BpiStatementError quando o ficheiro não é um extracto BPI
    ou quando um saldo não confere.
    """
    import pdfplumber

    head = {}
    rows = []
    balance = None
    closing = None
    mov_date = None
    pending = None  # data-valor numa linha sozinha (linha partida)

    with pdfplumber.open(fileobj) as pdf:
        text = pdf.pages[0].extract_text() or ""
        if "EXTRACTO DE CONTA" not in text or "BPI" not in text:
            raise BpiStatementError("O ficheiro não é um extracto de conta BPI.")
        m = re.search(r"Conta (\d-\d{7}-\d{3}-\d{3})", text)
        head["account_number"] = m.group(1) if m else ""
        m = re.search(r"IBAN: ([A-Z]{2}[\d ]+)", text)
        head["iban"] = m.group(1).replace(" ", "") if m else ""
        m = re.search(r"Período De (\d{2}/\d{2}/\d{4}) a (\d{2}/\d{2}/\d{4})", text)
        if not m:
            raise BpiStatementError("Período do extracto não encontrado.")
        d1, d2 = (
            date(int(s[6:]), int(s[3:5]), int(s[:2])) for s in m.groups()
        )
        head["period_from"], head["period_to"] = d1, d2

        for page in pdf.pages:
            for words in _lines(page):
                c = _columns(words)
                desc = c["desc"]
                if desc.startswith("SALDO ANTERIOR"):
                    balance = _amount(c["balance"])
                    head["opening_balance"] = balance
                    continue
                if desc.startswith("SALDO ACTUAL CONTABILISTICO"):
                    closing = _amount(c["balance"])
                    continue
                if desc.startswith("SALDO ACTUAL DISPONIVEL"):
                    head["available_balance"] = _amount(c["balance"])
                    continue
                if _DATE.match(c["mov"]):
                    mov_date = c["mov"]
                if c["val"] and not desc and _DATE.match(c["val"]):
                    pending = c["val"]
                    continue
                amount = _amount(c["amount"])
                new_balance = _amount(c["balance"])
                if amount is None or new_balance is None:
                    continue
                if balance is None:
                    raise BpiStatementError("Saldo anterior não encontrado.")
                if balance + amount != new_balance:
                    raise BpiStatementError(
                        f"O saldo não confere na linha '{desc[:60]}': "
                        f"{balance} + {amount} ≠ {new_balance}."
                    )
                val_date = c["val"] if _DATE.match(c["val"]) else pending
                pending = None
                md = _full_date(mov_date or val_date, d1, d2)
                vd = _full_date(val_date, d1, d2) if val_date else md
                iban = _IBAN_IN_DESC.search(desc)
                rows.append({
                    "date": md,
                    "value_date": vd,
                    "description": desc[:300],
                    "amount": abs(amount),
                    "direction": "DEBIT" if amount < 0 else "CREDIT",
                    "balance_after": new_balance,
                    "counterparty_iban": iban.group(1) if iban else "",
                    "external_id": _external_id(
                        head["account_number"], md, desc, amount, new_balance,
                    ),
                })
                balance = new_balance

    if closing is None or balance != closing:
        raise BpiStatementError(
            f"O saldo final não confere: movimentos dão {balance}, "
            f"o extracto diz {closing}."
        )
    head["closing_balance"] = closing
    return head, rows
