"""Extractos BPI em PDF: leitura, importação e reconciliação."""
import io
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from reportlab.pdfgen import canvas

from drivers_app.models import DriverProfile
from settlements.models import DriverPreInvoice, PreInvoiceAdvance

from .bank_parser_bpi import BpiStatementError, parse_bpi_pdf
from .models import BankPayee, BankStatement, BankTransaction
from .services_bank_import import StatementImportError, import_statement
from .views_reconciliation import _candidates_for

OWN_IBAN = "PT50 0010 0000 1111 2220 0025 2"
SISTER_IBAN = "PT50001000001111222000349"
DRIVER_IBAN = "PT50000700000012345678923"

ROWS = [
    # (mov, val, descrição, valor, saldo)
    ("08/10", "08/10", "TRF CR SEPA+ 0000001 DE CLIENTE EXEMPLO LDA", "31 677,01", "26 677,66"),
    ("", "08/10", f"TRF CR INTRAB 970 P/ {SISTER_IBAN} COBERTURA DE", "-300,00", "26 377,66"),
    ("", "08/10", f"TRF SEPA+ INST 988 P/ {DRIVER_IBAN} ANA, PAG", "-211,54", "26 166,12"),
    ("12/10", "10/10", "10/10 COMPRA EL-E 0000000/11 POSTO EXEMPLO LDA", "-1 030,00", "25 136,12"),
    ("", "12/10", "TRF CR INTRAB 815 DE LEGUAS FRANZINAS - UNIPESSOAL LDA", "150,00", "25 286,12"),
]


def bpi_pdf(rows=ROWS, opening="-4 999,35", closing="25 286,12"):
    """PDF com o desenho do extracto BPI (colunas nas mesmas posições)."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(595, 842))
    c.setFont("Helvetica", 7)
    y = 800

    def line(*parts):
        nonlocal y
        for x, text, right in parts:
            if text:
                (c.drawRightString if right else c.drawString)(x, y, text)
        y -= 12

    line((56, "EXTRACTO DE CONTA", False))
    line((56, "Conta 7-1111222-000-002 LEGUAS FRANZINAS - UNIPESSOAL LDA", False))
    line((56, "Período De 01/10/2026 a 31/10/2026", False))
    line((56, "CONTA VALOR BPI NEGOCIOS Nº: 7-1111222-000-002", False))
    line((56, f"IBAN: {OWN_IBAN}", False))
    line((113, "SALDO ANTERIOR CONTABILISTICO", False), (575, opening, True))
    for mov, val, desc, amount, balance in rows:
        line(
            (56, mov, False), (82, val, False), (113, desc, False),
            (520, amount, True), (575, balance, True),
        )
    line((113, "SALDO ACTUAL CONTABILISTICO", False), (575, closing, True))
    c.save()
    return buf.getvalue()


def upload(content=None, name="Extrato_Conta_2026-10-30.pdf"):
    return SimpleUploadedFile(name, content or bpi_pdf(), "application/pdf")


class ParseBpiPdfTests(TestCase):
    def test_le_cabecalho_e_movimentos(self):
        head, rows = parse_bpi_pdf(io.BytesIO(bpi_pdf()))
        self.assertEqual(head["account_number"], "7-1111222-000-002")
        self.assertEqual(head["iban"], "PT50001000001111222000252")
        self.assertEqual(head["opening_balance"], Decimal("-4999.35"))
        self.assertEqual(head["closing_balance"], Decimal("25286.12"))
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0]["direction"], "CREDIT")
        self.assertEqual(rows[0]["amount"], Decimal("31677.01"))
        self.assertEqual(rows[3]["amount"], Decimal("1030.00"))
        self.assertEqual(rows[3]["direction"], "DEBIT")

    def test_data_do_movimento_so_aparece_quando_muda(self):
        _, rows = parse_bpi_pdf(io.BytesIO(bpi_pdf()))
        self.assertEqual(rows[1]["date"], date(2026, 10, 8))
        self.assertEqual(rows[3]["date"], date(2026, 10, 12))
        self.assertEqual(rows[3]["value_date"], date(2026, 10, 10))
        self.assertEqual(rows[4]["date"], date(2026, 10, 12))

    def test_le_o_iban_do_destinatario(self):
        _, rows = parse_bpi_pdf(io.BytesIO(bpi_pdf()))
        self.assertEqual(rows[2]["counterparty_iban"], DRIVER_IBAN)
        self.assertEqual(rows[3]["counterparty_iban"], "")

    def test_recusa_saldo_que_nao_confere(self):
        rows = list(ROWS)
        rows[2] = rows[2][:3] + ("-211,55",) + rows[2][4:]
        with self.assertRaises(BpiStatementError):
            parse_bpi_pdf(io.BytesIO(bpi_pdf(rows)))

    def test_recusa_pdf_que_nao_e_extracto_bpi(self):
        buf = io.BytesIO()
        c = canvas.Canvas(buf)
        c.drawString(56, 800, "Fatura 123")
        c.save()
        with self.assertRaises(BpiStatementError):
            parse_bpi_pdf(io.BytesIO(buf.getvalue()))


class ImportStatementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("op", "o@a.pt", "x")

    def test_grava_extracto_e_marca_contas_proprias(self):
        st, n_new, n_dup = import_statement(upload(), self.user)
        self.assertEqual((n_new, n_dup), (5, 0))
        self.assertEqual(st.account_number, "7-1111222-000-002")
        self.assertEqual(st.closing_balance, Decimal("25286.12"))
        internal = list(
            st.transactions.filter(is_internal=True)
            .order_by("id").values_list("description", flat=True)
        )
        self.assertEqual(len(internal), 2)
        self.assertIn("COBERTURA", internal[0])
        self.assertIn("DE LEGUAS FRANZINAS", internal[1])

    def test_segundo_upload_do_mesmo_extracto_e_recusado(self):
        import_statement(upload(), self.user)
        with self.assertRaises(StatementImportError):
            import_statement(upload(), self.user)
        self.assertEqual(BankTransaction.objects.count(), 5)

    def test_upload_de_varios_ficheiros_pela_pagina(self):
        self.client.force_login(User.objects.create_superuser("adm", "a@a.pt", "x"))
        r = self.client.post(
            reverse("accounting:bank_statement_upload"),
            {"file": [upload(), upload(name="copia.pdf")]},
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(BankStatement.objects.count(), 1)
        self.assertEqual(BankTransaction.objects.count(), 5)


class ReconciliationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("adm", "a@a.pt", "x")
        self.ana = DriverProfile.objects.create(
            nif="123456789", nome_completo="Ana Teste",
            telefone="9", email="j@a.pt", apelido="Ana_LF",
            status="ATIVO", is_active=True,
        )
        self.outro = DriverProfile.objects.create(
            nif="223456789", nome_completo="Rui Exemplo",
            telefone="8", email="r@a.pt", apelido="Rui_LF",
            status="ATIVO", is_active=True,
        )
        import_statement(upload(), self.user)
        self.tx = BankTransaction.objects.get(counterparty_iban=DRIVER_IBAN)

    def _advance(self, driver, valor="211.54", dia=8):
        return PreInvoiceAdvance.objects.create(
            driver=driver, data=date(2026, 10, dia), tipo="ADIANTAMENTO",
            valor=Decimal(valor),
        )

    def test_sugere_adiantamento_com_o_mesmo_valor(self):
        adv = self._advance(self.ana)
        sugs = _candidates_for(self.tx)
        self.assertEqual([(s["type"], s["id"]) for s in sugs], [("advance", adv.pk)])
        self.assertGreaterEqual(sugs[0]["score"], 10)

    def test_contas_proprias_nao_pedem_ligacao(self):
        tx = BankTransaction.objects.filter(is_internal=True).first()
        self.assertEqual(_candidates_for(tx), [])
        self.client.force_login(self.user)
        r = self.client.get(reverse("accounting:bank_reconciliation"))
        self.assertEqual(r.context["total_internal"], 2)
        self.assertEqual(r.context["total_unmatched"], 3)

    def test_confirmar_guarda_o_iban_e_filtra_as_proximas_sugestoes(self):
        adv = self._advance(self.ana)
        self.client.force_login(self.user)
        self.client.post(
            reverse("accounting:bank_match_confirm", args=[self.tx.pk]),
            {"type": "advance", "id": adv.pk},
        )
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.matched_advance, adv)
        self.assertEqual(BankPayee.objects.get(iban=DRIVER_IBAN).driver, self.ana)

        # Novo movimento para o mesmo IBAN: só sugere a Ana.
        tx2 = BankTransaction.objects.create(
            statement=self.tx.statement, date=date(2026, 10, 20),
            description=f"TRF SEPA+ INST 1 P/ {DRIVER_IBAN} PAGAMENTO",
            direction="DEBIT", amount=Decimal("50.00"),
            counterparty_iban=DRIVER_IBAN,
        )
        self._advance(self.outro, "50.00", 20)
        mine = self._advance(self.ana, "50.00", 14)
        sugs = _candidates_for(tx2)
        self.assertEqual([s["id"] for s in sugs], [mine.pk])

    def test_sugere_pf_por_pagar_com_o_valor_a_receber(self):
        pf = DriverPreInvoice.objects.create(
            numero="PF-0600", driver=self.ana,
            periodo_inicio=date(2026, 9, 1), periodo_fim=date(2026, 9, 30),
        )
        DriverPreInvoice.objects.filter(pk=pf.pk).update(
            total_a_receber=Decimal("211.54"),
        )
        sugs = _candidates_for(self.tx)
        self.assertIn(("pf", pf.pk), [(s["type"], s["id"]) for s in sugs])
        label = next(s["label"] for s in sugs if s["type"] == "pf")
        self.assertIn("ainda não marcada paga", label)

    def test_limpar_remove_a_ligacao_ao_adiantamento(self):
        adv = self._advance(self.ana)
        self.client.force_login(self.user)
        self.client.post(
            reverse("accounting:bank_match_confirm", args=[self.tx.pk]),
            {"type": "advance", "id": adv.pk},
        )
        self.client.post(reverse("accounting:bank_match_clear", args=[self.tx.pk]))
        self.tx.refresh_from_db()
        self.assertIsNone(self.tx.matched_advance)

    def test_pagina_da_lista_mostra_saldos(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse("accounting:bank_statement_list"))
        self.assertContains(r, "7-1111222-000-002")
        self.assertEqual(r.context["statements"][0].n_done, 2)
