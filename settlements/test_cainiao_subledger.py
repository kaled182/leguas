"""Pré-fatura Cainiao a partir do sub-ledger do portal CES (dados inventados)."""
import io
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from drivers_app.models import DriverProfile

from .models import CainiaoBill, CainiaoBillCharge, CainiaoOperationTask
from .services_cainiao_subledger import (
    SubledgerError, charges_for, checks, create_pre_invoice, documents,
    dynamic, export_xlsx, import_subledger,
)

HEADER = (
    "Settlement ID,Settlement ID,Billing Time,Bill Item,Business Node Time,"
    "Logistics Product,Bill Amount,Charging currency,Service Product,"
    "Logistics Treasure Order Number,User Nickname,Employee ID,Weight (g),"
    "AAmodel First Order,International Postal Codes,Calculate,AAModel code,"
    "Business Appraisal Remarks,Comments on Liability for Complaints,The bill ID"
)


def line(sid, item, when, amount, lp, employee="900001", bill="'500000000001",
         formula="1.3*1.23", claim="", first="Y", cp="4900"):
    return ",".join([
        f"1{sid}", f"2{sid}", when, item, when, "DSP", amount, "EUR", "PT",
        f"'{lp}", "dsp-teste", employee, "500.0", first, cp, formula, "", "",
        claim, bill,
    ])


def csv_file(lines, name="Consolidated_Bill_teste.csv"):
    body = "﻿" + HEADER + "\n" + "\n".join(lines) + "\n"
    return SimpleUploadedFile(name, body.encode("utf-8"), "text/csv")


LINES = [
    line(1, "末端配送费", "2026-10-16 10:00:00", "1.6", "LP0001"),
    line(2, "末端配送费", "2026-10-17 11:00:00", "1.72", "LP0002", formula="1.4*1.23"),
    line(3, "末端配送费", "2026-10-17 11:05:00", "0.43", "LP0003", formula="0.35*1.23", first="N"),
    line(4, "挂号服务费", "2026-09-10 09:00:00", "0.46", "LP0004", bill="'500000000002"),
    line(5, "货值赔付", "2026-10-20 12:00:00", "-30.0", "LP0005", employee="",
         bill="'500000000003", formula="", claim="LM-F7 sem resposta"),
    line(6, "APP使用费", "2026-10-29 00:00:00", "-24.6", "appfee", employee="",
         bill="'500000000004", formula="-20.0*1.23"),
]


class ImportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("adm", "a@a.pt", "x")

    def test_importa_linhas_e_faturas(self):
        imp, n_new, n_dup, bills = import_subledger(csv_file(LINES), self.user)
        self.assertEqual((n_new, n_dup, len(bills)), (6, 0, 4))
        self.assertEqual(imp.total_amount, Decimal("-50.39"))
        bill = CainiaoBill.objects.get(bill_id="500000000001")
        self.assertEqual((bill.n_lines, bill.total_amount, bill.main_item), (3, Decimal("3.75"), "LASTMILE"))
        c = CainiaoBillCharge.objects.get(lp_number="LP0003")
        self.assertEqual((c.first_order, c.weight_g, c.postal_code), ("N", 500, "4900"))
        self.assertEqual(CainiaoBillCharge.objects.get(lp_number="LP0005").claim_comment, "LM-F7 sem resposta")

    def test_reimportar_ignora_linhas_repetidas(self):
        import_subledger(csv_file(LINES), self.user)
        _, n_new, n_dup, _ = import_subledger(csv_file(LINES + [
            line(7, "末端配送费", "2026-10-18 10:00:00", "1.6", "LP0007"),
        ]), self.user)
        self.assertEqual((n_new, n_dup), (1, 6))
        self.assertEqual(CainiaoBill.objects.get(bill_id="500000000001").n_lines, 4)

    def test_recusa_ficheiro_que_nao_e_sub_ledger(self):
        with self.assertRaises(SubledgerError):
            import_subledger(SimpleUploadedFile("x.csv", b"a,b,c\n1,2,3\n"), self.user)


class PreInvoiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("adm", "a@a.pt", "x")
        import_subledger(csv_file(LINES), self.user)
        self.pre = create_pre_invoice(
            ["500000000001", "500000000002", "500000000003", "500000000004"],
            date(2026, 10, 16), date(2026, 10, 31), self.user,
        )

    def test_documentos_iguais_a_folha(self):
        docs = documents(charges_for(self.pre))
        inv = {l["code"]: l for l in docs["invoice"]}
        self.assertEqual((inv["001"]["qty"], inv["001"]["gross"]), (3, Decimal("3.75")))
        self.assertEqual(inv["001"]["base"], Decimal("3.05"))
        self.assertEqual(inv["002"]["gross"], Decimal("0.46"))
        cred = {l["label"]: l for l in docs["credit"]}
        self.assertEqual((cred["app fee"]["base"], cred["app fee"]["vat"]), (Decimal("20.00"), Decimal("4.60")))
        self.assertEqual((cred["compensacion (claims)"]["base"], cred["compensacion (claims)"]["vat"]),
                         (Decimal("30.00"), Decimal("0.00")))
        self.assertEqual(docs["net"]["gross"], Decimal("-50.39"))
        self.assertEqual(docs["control"], Decimal("0"))

    def test_separa_acerto_retroativo(self):
        dyn = dynamic(charges_for(self.pre), self.pre.period_from, self.pre.period_to)
        periods = {p["label"]: p["n"] for p in dyn["periods"]}
        self.assertEqual(periods, {"No período": 5, "Antes do período": 1})
        self.assertEqual(len(dyn["compensations"]), 1)
        self.assertEqual({t["amount"]: t["n"] for t in dyn["by_tariff"]}[Decimal("1.60")], 1)

    def test_fatura_so_entra_numa_pre_fatura(self):
        with self.assertRaises(SubledgerError):
            create_pre_invoice(["500000000001"], date(2026, 10, 16), date(2026, 10, 31), self.user)

    def test_excel_tem_as_4_folhas(self):
        wb = load_workbook(io.BytesIO(export_xlsx(self.pre)), read_only=True)
        self.assertEqual(wb.sheetnames, ["Faturacao", "Dinamica", "Compensacoes", "Linhas"])
        self.assertEqual(len(list(wb["Linhas"].iter_rows())), 7)

    def test_paginas_abrem(self):
        self.client.force_login(self.user)
        for name, args in (("cainiao-subledger-list", []), ("cainiao-preinvoice-detail", [self.pre.pk]),
                           ("cainiao-preinvoice-checks", [self.pre.pk])):
            r = self.client.get(reverse(name, args=args))
            self.assertEqual(r.status_code, 200, name)
        r = self.client.get(reverse("cainiao-preinvoice-export", args=[self.pre.pk]))
        self.assertEqual(r["Content-Type"].split(";")[0],
                         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    def test_marcar_emitida_e_eliminar_so_em_rascunho(self):
        self.client.force_login(self.user)
        url = reverse("cainiao-preinvoice-update", args=[self.pre.pk])
        self.client.post(url, {"action": "issue", "toconline_invoice": "FT 2026/123",
                               "toconline_credit_note": "NC 2026/9", "issued_at": "2026-11-02"})
        self.pre.refresh_from_db()
        self.assertEqual((self.pre.status, self.pre.toconline_invoice), ("EMITIDA", "FT 2026/123"))
        self.client.post(reverse("cainiao-preinvoice-delete", args=[self.pre.pk]))
        self.assertTrue(type(self.pre).objects.filter(pk=self.pre.pk).exists())

    def test_upload_pela_pagina(self):
        self.client.force_login(self.user)
        r = self.client.post(reverse("cainiao-subledger-upload"), {"file": csv_file([
            line(9, "末端配送费", "2026-11-02 10:00:00", "1.6", "LP0009", bill="'500000000009"),
        ])})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(CainiaoBill.objects.filter(bill_id="500000000009", pre_invoice=None).exists())


class ChecksTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("adm", "a@a.pt", "x")
        DriverProfile.objects.create(
            nif="123456789", nome_completo="Ana Teste", telefone="9", email="a@t.pt",
            apelido="Ana_LF", courier_id_cainiao="900001", status="ATIVO", is_active=True,
        )

        def task(lp, day, status="Delivered", courier="900001"):
            CainiaoOperationTask.objects.create(
                task_date=day, waybill_number=f"CN{lp}", lp_number=lp, task_status=status,
                courier_name="Ana_LF", courier_id_cainiao=courier, zip_code="4900-001",
            )

        task("LP0001", date(2026, 10, 16))
        task("LP0002", date(2026, 10, 17), courier="900777")
        task("LP0003", date(2026, 10, 17), status="Attempt Failure")
        task("LP0099", date(2026, 10, 18))
        import_subledger(csv_file(LINES), self.user)
        self.pre = create_pre_invoice(
            ["500000000001"], date(2026, 10, 16), date(2026, 10, 31), self.user,
        )

    def test_conferencias(self):
        c = checks(self.pre)
        self.assertEqual(c["n_billed"], 3)
        self.assertEqual(c["unbilled_n"], 1)
        self.assertEqual(c["unbilled_sample"][0]["lp_number"], "LP0099")
        self.assertEqual(c["not_delivered_n"], 1)
        self.assertEqual(c["not_delivered_status"], [("Attempt Failure", 1)])
        self.assertEqual(c["mismatch_n"], 1)
        row = c["mismatch_rows"][0]
        self.assertEqual((row["our_id"], row["billed_id"], row["billed_driver"].nome_completo),
                         ("900777", "900001", "Ana Teste"))
        self.assertEqual(c["unknown_ids"], [])


class CompensationOwnerTests(TestCase):
    def setUp(self):
        from .models import DriverClaim
        self.user = User.objects.create_superuser("adm", "a@a.pt", "x")
        self.ana = DriverProfile.objects.create(
            nif="123456789", nome_completo="Ana Teste", telefone="9", email="a@t.pt",
            apelido="Ana_LF", courier_id_cainiao="900001", status="ATIVO", is_active=True,
        )
        CainiaoOperationTask.objects.create(
            task_date=date(2026, 10, 19), waybill_number="CNLP0005", lp_number="LP0005",
            task_status="Delivered", courier_name="Ana_LF", courier_id_cainiao="900001",
        )
        DriverClaim.objects.create(
            driver=self.ana, claim_type=DriverClaim.CLAIM_TYPES[0][0], amount=Decimal("50"),
            description="teste", waybill_number="CNLP0005", status="APPROVED",
        )
        import_subledger(csv_file(LINES + [
            line(8, "货值赔付", "2026-10-21 12:00:00", "-30.0", "AP0008", employee="",
                 bill="'500000000003", formula=""),
        ]), self.user)
        self.pre = create_pre_invoice(["500000000003"], date(2026, 10, 16), date(2026, 10, 31), self.user)

    def test_compensacao_mostra_dono_e_desconto(self):
        dyn = dynamic(charges_for(self.pre), self.pre.period_from, self.pre.period_to)
        comp = {c.lp_number: c for c in dyn["compensations"]}
        self.assertEqual(comp["LP0005"].owner["driver"], self.ana)
        self.assertEqual(comp["LP0005"].owner["waybill"], "CNLP0005")
        self.assertEqual([cl.amount for cl in comp["LP0005"].claims], [Decimal("50.00")])
        self.assertIsNone(comp["AP0008"].owner)
        owners = dict(dyn["compensations_by_owner"])
        self.assertEqual(owners["Ana Teste"]["claimed"], 1)
        self.assertEqual(owners["Sem dono identificado"]["n"], 1)
        self.client.force_login(self.user)
        r = self.client.get(reverse("cainiao-preinvoice-detail", args=[self.pre.pk]))
        self.assertContains(r, "Sem dono identificado")
        self.assertContains(r, "CNLP0005")
