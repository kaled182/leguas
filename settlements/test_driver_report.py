"""Relatório de motoristas por hub (dados inventados)."""
import io
import zipfile
from datetime import date, datetime, timezone
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse
from openpyxl import load_workbook

from core.models import Partner
from drivers_app.models import DriverProfile, EmpresaParceira

from .models import CainiaoHub, CainiaoHubCP4, CainiaoOperationTask, DriverPreInvoice
from .services_driver_breakdown import driver_breakdown
from .services_driver_report import build, collect, driver_detail

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
D1, D2 = date(2026, 10, 16), date(2026, 10, 31)


def _task(wb, courier, zc, addr, status="Delivered", dtype="TO_DOOR", day=D1, lat="41.1"):
    return CainiaoOperationTask.objects.create(
        waybill_number=wb, task_date=day, task_status=status, courier_name=courier,
        delivery_type=dtype, detailed_address=addr, zip_code=zc, task_group_order="-1",
        receiver_latitude=lat, receiver_longitude="-8.1",
        delivery_time=datetime(2026, 10, 16, 10, 0, tzinfo=timezone.utc),
    )


@override_settings(CACHES=LOCMEM)
class DriverReportTests(TestCase):
    def setUp(self):
        self.partner = Partner.objects.create(
            name="CAINIAO", nif="514154411", contact_email="c@x.pt",
            same_door_enabled=True, same_door_additional_price=Decimal("0.30"), pudo_enabled=True,
        )
        north = CainiaoHub.objects.create(name="Norte")
        south = CainiaoHub.objects.create(name="Sul")
        CainiaoHubCP4.objects.create(hub=north, cp4="4740")
        CainiaoHubCP4.objects.create(hub=south, cp4="3800")
        self.fleet = EmpresaParceira.objects.create(nome="Frota Teste")
        self.rui = DriverProfile.objects.create(
            nif="123456789", nome_completo="Rui Teste", telefone="910000000", email="rui@x.pt",
            apelido="Rui_LF", price_per_package=Decimal("1.10"), vat_regime="normal",
        )
        self.ana = DriverProfile.objects.create(
            nif="223456789", nome_completo="Ana Teste", telefone="920000000", email="ana@x.pt",
            apelido="Ana_LF", price_per_package=Decimal("1.00"), empresa_parceira=self.fleet,
        )
        _task("R1", "Rui_LF", "4740-013", "Rua A 10")
        _task("R2", "Rui_LF", "4740-013", "Rua A 10")              # mesma porta
        _task("R3", "Rui_LF", "3800-100", "Rua S 1")               # outro hub
        _task("R4", "Rui_LF", "4740-013", "Rua B 2", status="Attempt Failure")
        _task("R5", "Rui_LF", "9999-000", "Rua X 9")               # CP4 sem hub
        _task("A1", "Ana_LF", "3800-100", "Rua S 2")
        _task("A2", "Ana_LF", "3800-100", "PUDO 1", dtype="PUDO", lat="41.3")
        _task("O1", "Sem_Ficha", "4740-013", "Rua Z 1")            # login sem ficha
        self.user = User.objects.create_superuser("adm", "a@a.pt", "x")

    def test_valores_iguais_ao_breakdown_e_divididos_por_hub(self):
        data, alerts = collect(D1, D2)
        for dd in data:
            bd = driver_breakdown(dd.driver, D1, D2, self.partner)
            self.assertEqual(sum(l["amount"] for l in dd.lines), bd["amounts"]["total"])
        rui = next(dd for dd in data if dd.driver == self.rui)
        self.assertEqual(sorted(rui.by_hub), ["Norte", "Sem hub", "Sul"])
        self.assertEqual((alerts["orphans_n"], alerts["orphans"][0][0]), (1, ("Sem_Ficha", "Norte")))

        north = build(D1, D2, hub="Norte", collected=(data, alerts))
        row = north["rows"][0]
        self.assertEqual((row["driver"], row["delivered"], row["door_normal"], row["same_door"], row["failures"]),
                         (self.rui, 2, 1, 1, 1))
        self.assertEqual(row["amount"], Decimal("1.40"))
        self.assertEqual((row["vat"], row["with_vat"]), (Decimal("0.32"), Decimal("1.72")))
        self.assertEqual(row["other_hubs"], ["Sem hub", "Sul"])
        detail = driver_detail(rui, D1, D2)
        self.assertEqual([(g["n"], g["waybills"]) for g in detail["same_door"]], [(1, ["R1", "R2"])])
        self.assertEqual([h["hub"] for h in detail["hubs"]], ["Norte", "Sem hub", "Sul"])

    def test_frota_agrupa_e_isento_sem_iva(self):
        rep = build(D1, D2, hub="Sul")
        self.assertEqual([g["fleet"] for g in rep["groups"]], [None, self.fleet])
        ana = rep["groups"][1]["rows"][0]
        self.assertEqual((ana["pudo"], ana["vat"]), (1, Decimal("0.00")))
        self.assertEqual(rep["total"]["drivers"], 2)
        self.assertEqual(build(D1, D2, fleet_id="none")["total"]["drivers"], 1)

    def test_diferenca_para_a_pf_do_mesmo_periodo(self):
        DriverPreInvoice.objects.create(
            driver=self.ana, periodo_inicio=D1, periodo_fim=D2, base_entregas=Decimal("1.00"),
        )
        row = next(r for r in build(D1, D2)["rows"] if r["driver"] == self.ana)
        self.assertEqual(row["pf_diff"], row["amount"] - Decimal("1.00"))

    def test_pagina_pdf_excel_e_zip(self):
        self.client.force_login(self.user)
        q = "?hub=Norte&from=2026-10-16&to=2026-10-31"
        r = self.client.get(reverse("driver-report") + q)
        self.assertContains(r, "Rui Teste")
        self.assertContains(r, "Sem_Ficha")
        self.assertNotContains(r, "Ana Teste")
        pdf = self.client.get(reverse("driver-report-hub-pdf") + q)
        self.assertEqual((pdf["Content-Type"], pdf.content[:4]), ("application/pdf", b"%PDF"))
        one = self.client.get(reverse("driver-report-driver-pdf", args=[self.rui.id]) + q)
        self.assertEqual(one.content[:4], b"%PDF")
        self.assertEqual(self.client.get(reverse("driver-report-driver-pdf", args=[999]) + q).status_code, 404)
        wb = load_workbook(io.BytesIO(self.client.get(reverse("driver-report-xlsx") + q).content), read_only=True)
        self.assertEqual(wb.sheetnames, ["Resumo", "Entregas"])
        self.assertEqual(len(list(wb["Entregas"].iter_rows())), 4)   # cabeçalho + R1, R2, R4
        z = zipfile.ZipFile(io.BytesIO(self.client.get(reverse("driver-report-zip") + q).content))
        self.assertEqual(len([n for n in z.namelist() if n.startswith("motoristas/")]), 1)

    def test_filtros_invalidos_usam_a_omissao(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse("driver-report") + "?hub=Lisboa&from=xx&to=2020-01-01")
        self.assertEqual(r.status_code, 200)

    def test_operador_nao_ve_o_relatorio(self):
        op = User.objects.create_user("op", "o@a.pt", "x")
        Group.objects.get_or_create(name="Operador")
        self.client.force_login(op)
        r = self.client.get(reverse("driver-report"))
        self.assertNotEqual(r.status_code, 200)
