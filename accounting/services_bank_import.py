"""Importação de extractos bancários (PDF BPI, CSV, OFX)."""
from django.db import transaction

from .bank_parser import parse_statement
from .bank_parser_bpi import BpiStatementError, parse_bpi_pdf
from .models import BankStatement, BankTransaction

# Banco + balcão + número de cliente: as contas do mesmo cliente BPI
# partilham estes 19 caracteres do IBAN.
_CLIENT_IBAN_PREFIX = 19

COMPANY_NAME = "LEGUAS FRANZINAS"


class StatementImportError(ValueError):
    pass


def _is_internal(row, own_prefixes):
    iban = row.get("counterparty_iban") or ""
    if iban and iban[:_CLIENT_IBAN_PREFIX] in own_prefixes:
        return True
    return f"DE {COMPANY_NAME}" in (row.get("description") or "")


def import_statement(uploaded, user, name=""):
    """Grava o extracto e os movimentos novos.

    Devolve (statement, n_novos, n_repetidos). Levanta
    StatementImportError quando o ficheiro não se lê ou já foi importado.
    """
    filename = uploaded.name or ""
    head = {}
    if filename.lower().endswith(".pdf"):
        try:
            head, rows = parse_bpi_pdf(uploaded)
        except BpiStatementError as e:
            raise StatementImportError(str(e)) from e
    else:
        rows = parse_statement(filename, uploaded.read())
    if not rows:
        raise StatementImportError(
            "Não foi possível extrair movimentos do ficheiro."
        )

    account = head.get("account_number", "")
    existing = set(
        BankTransaction.objects.filter(
            statement__account_number=account,
            external_id__in=[r["external_id"] for r in rows if r.get("external_id")],
        ).values_list("external_id", flat=True)
    )
    new_rows = [r for r in rows if not r.get("external_id") or r["external_id"] not in existing]
    if not new_rows:
        raise StatementImportError(
            "Este extracto já foi importado: todos os movimentos já existem."
        )

    own_prefixes = {
        iban[:_CLIENT_IBAN_PREFIX]
        for iban in BankStatement.objects.exclude(iban="").values_list("iban", flat=True)
    }
    if head.get("iban"):
        own_prefixes.add(head["iban"][:_CLIENT_IBAN_PREFIX])

    period_from = head.get("period_from") or min(r["date"] for r in rows)
    period_to = head.get("period_to") or max(r["date"] for r in rows)
    if not name:
        name = (
            f"BPI {account[-3:]} · {period_to:%m/%Y}" if account else filename
        )

    uploaded.seek(0)
    with transaction.atomic():
        statement = BankStatement.objects.create(
            name=name[:80],
            period_from=period_from,
            period_to=period_to,
            file=uploaded,
            n_transactions=len(new_rows),
            account_number=account,
            iban=head.get("iban", ""),
            opening_balance=head.get("opening_balance"),
            closing_balance=head.get("closing_balance"),
            uploaded_by=user,
        )
        BankTransaction.objects.bulk_create([
            BankTransaction(
                statement=statement,
                date=r["date"],
                value_date=r.get("value_date"),
                description=r["description"],
                direction=r["direction"],
                amount=r["amount"],
                balance_after=r.get("balance_after"),
                counterparty_iban=r.get("counterparty_iban", ""),
                is_internal=_is_internal(r, own_prefixes),
                external_id=r.get("external_id", ""),
            )
            for r in new_rows
        ])
    return statement, len(new_rows), len(rows) - len(new_rows)
