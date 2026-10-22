import io
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings
from openpyxl import Workbook

from core.models import Partner
from drivers_app.models import DriverProfile

from .models import CainiaoOperationTask
from .services_driver_breakdown import driver_breakdown
from .services_same_door import normalize_address, same_door_extra_ids

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
D1 = date(2026, 10, 2)


def _task(wb, addr="Rua A 10", zc="4740-013", stop="-1", status="Delivered",
          dtype="TO_DOOR", day=D1, courier="Rui_LF", hour=10, lat="41.1", lng="-8.1"):
    return CainiaoOperationTask.objects.create(
        waybill_number=wb, task_date=day, task_status=status, courier_name=courier,
        delivery_type=dtype, detailed_address=addr, zip_code=zc, task_group_order=stop,
        receiver_latitude=lat, receiver_longitude=lng,
        delivery_time=datetime(2026, 10, 2, hour, 0, tzinfo=timezone.utc),
    )


class NormalizeAddressTests(TestCase):
    def test_variantes_da_mesma_morada_ficam_iguais(self):
        self.assertEqual(normalize_address("Rua porto carreiro n 25"),
                         normalize_address("rua porto carreiro n 25 4740-013"))
        self.assertEqual(normalize_address("Rua Pereira Azurara, 58 58"),
                         normalize_address("Rua Pereira Azurara, 58"))
        self.assertEqual(normalize_address("Rua de cassufas nº670 Rua de cassufas nº670"),
                         normalize_address("Rua de Cassufas 670"))

    def test_andares_diferentes_nao_juntam(self):
        self.assertNotEqual(normalize_address("Rua X 10 1 esq"), normalize_address("Rua X 10 2 esq"))


@override_settings(CACHES=LOCMEM)
class SameDoorTests(TestCase):
    def setUp(self):
        self.p = Partner.objects.create(
            name="CAINIAO", nif="514154411", contact_email="c@x.pt",
            same_door_enabled=True, same_door_additional_price=Decimal("0.30"),
            pudo_enabled=True,
        )

    def test_morada_escrita_diferente_conta_como_mesma_porta(self):
        a = _task("W1", addr="Rua porto carreiro n 25", hour=9)
        b = _task("W2", addr="rua porto carreiro n 25 4740-013", hour=10)
        self.assertEqual(same_door_extra_ids([a.id, b.id], self.p), {b.id})

    def test_mesma_paragem_cainiao_junta_moradas_diferentes(self):
        a = _task("W1", addr="Av Poveiros 265 R/C", stop="12.0", hour=9)
        b = _task("W2", addr="Avenida Poveiros 265", stop="12.0", hour=10)
        c = _task("W3", addr="Outra rua 1", stop="13.0", hour=11)
        self.assertEqual(same_door_extra_ids([a.id, b.id, c.id], self.p), {b.id})

    def test_paragem_de_outro_motorista_nao_junta(self):
        a = _task("W1", addr="Rua 1", stop="5.0")
        b = _task("W2", addr="Rua 2", stop="5.0", courier="Ana_LF")
        self.assertEqual(same_door_extra_ids([a.id, b.id], self.p), set())

    def test_dias_diferentes_e_pudo_nao_contam(self):
        a = _task("W1")
        b = _task("W2", day=date(2026, 10, 3))
        c = _task("W3", dtype="PUDO")
        self.assertEqual(same_door_extra_ids([a.id, b.id, c.id], self.p), set())


@override_settings(CACHES=LOCMEM)
class DriverBreakdownTests(TestCase):
    def setUp(self):
        self.p = Partner.objects.create(
            name="CAINIAO", nif="514154411", contact_email="c@x.pt",
            same_door_enabled=True, same_door_additional_price=Decimal("0.30"),
            pudo_enabled=True,
        )
        self.d = DriverProfile.objects.create(
            nif="123456789", nome_completo="Rui", telefone="910000000",
            email="rui@x.pt", apelido="Rui_LF", price_per_package=Decimal("1.10"),
        )

    def test_total_primeiro_depois_divisao_e_valor(self):
        _task("W1", hour=9)
        _task("W2", hour=10)                       # mesma porta
        _task("W3", addr="Rua B 2")                # porta normal
        _task("W4", dtype="PUDO", lat="41.2")      # PUDO
        _task("W5", status="Attempt Failure", addr="Rua C 3")
        bd = driver_breakdown(self.d, D1, D1)
        t = bd["totals"]
        self.assertEqual((t["delivered"], t["door_normal"], t["same_door"], t["pudo"], t["failures"]),
                         (4, 2, 1, 1, 1))
        self.assertEqual(t["delivered"], t["door_normal"] + t["same_door"] + t["pudo"])
        # 2 × 1,10 + 1 × 0,30 + PUDO 1ª entrega (1,00)
        self.assertEqual(bd["amounts"]["total"], Decimal("2.20") + Decimal("0.30") + Decimal("1.00"))
        self.assertEqual(bd["days"][0]["delivered"], 4)


@override_settings(CACHES=LOCMEM)
class RecoverEpodMissingTests(TestCase):
    def _xlsx(self, tmp_path_rows):
        wb = Workbook()
        ws = wb.active
        ws.append(["Waybill Number", "Task Date", "Task Status", "Driver"])
        for r in tmp_path_rows:
            ws.append(r)
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    def test_dry_run_lista_so_o_que_falta_e_apply_importa_so_esses(self):
        CainiaoOperationTask.objects.create(
            waybill_number="OK1", task_date=date(2026, 9, 23), task_status="Delivered", courier_name="Rui_LF",
        )
        content = self._xlsx([
            ["OK1", "2026-09-23", "Delivered", "Rui_LF"],
            ["MISS1", "2026-09-23", "Delivered", "Rui_LF"],
            ["FAIL1", "2026-09-23", "Attempt Failure", "Rui_LF"],
        ])
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".xlsx") as f:
            f.write(content)
            f.flush()
            out = io.StringIO()
            call_command("recover_epod_missing", f.name, stdout=out)
            self.assertIn("1 em falta", out.getvalue())
            with mock.patch("settlements.cainiao_views.import_operation_file",
                            return_value=({"success": True, "total_novos": 1, "total_atualizados": 0,
                                           "date_range": "2026-09-23"}, 200)) as imp:
                call_command("recover_epod_missing", f.name, "--apply", stdout=io.StringIO())
        sent = imp.call_args[0][0]
        from openpyxl import load_workbook
        rows = list(load_workbook(io.BytesIO(sent)).active.iter_rows(values_only=True))
        self.assertEqual([r[0] for r in rows[1:]], ["MISS1"])


@override_settings(CACHES=LOCMEM, SECURE_SSL_REDIRECT=False)
class BreakdownPagesTests(TestCase):
    """As 4 páginas mostram o total do motorista e a divisão."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        from .models import DriverPreInvoice, PreInvoiceLine

        self.p = Partner.objects.create(
            name="CAINIAO", nif="514154411", contact_email="c@x.pt",
            same_door_enabled=True, same_door_additional_price=Decimal("0.30"), pudo_enabled=True,
        )
        self.d = DriverProfile.objects.create(
            nif="123456789", nome_completo="Rui", telefone="910000000",
            email="rui@x.pt", apelido="Rui_LF", price_per_package=Decimal("1.10"),
        )
        today = date.today()
        for i, (addr, dtype) in enumerate([("Rua A 1", "TO_DOOR"), ("Rua A 1", "TO_DOOR"), ("Rua B 2", "PUDO")]):
            CainiaoOperationTask.objects.create(
                waybill_number=f"W{i}", task_date=today, task_status="Delivered", courier_name="Rui_LF",
                delivery_type=dtype, detailed_address=addr, zip_code="4740-013",
            )
        self.pf = DriverPreInvoice.objects.create(
            driver=self.d, periodo_inicio=today, periodo_fim=today, status="CALCULADO",
        )
        PreInvoiceLine.objects.create(pre_invoice=self.pf, parceiro=self.p, total_pacotes=2,
                                      taxa_por_entrega=Decimal("1.10"))
        self.client.force_login(get_user_model().objects.create_superuser("adm", "a@x.pt", "x"))

    def test_paginas_mostram_total_e_divisao(self):
        from django.urls import reverse
        urls = [
            reverse("drivers_app:driver_portal", args=[self.d.id]),
            reverse("drivers_app:driver_portal_invoices", args=[self.d.id]),
            reverse("drivers_app:driver_pre_invoice_detail", args=[self.d.id, self.pf.id]),
        ]
        for url in urls:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, url)
            self.assertContains(r, "Total entregue pelo motorista")
            self.assertContains(r, "Mesma porta")
        r = self.client.get(reverse("drivers_app:driver_pre_invoice_detail", args=[self.d.id, self.pf.id]))
        self.assertContains(r, "Pré-fatura não confere")  # PF tem 2, sistema tem 3
        r = self.client.get(reverse("core:partner-detail", args=[self.p.id]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Mesma porta")


@override_settings(CACHES=LOCMEM)
class RecoverAmbiguousTests(TestCase):
    def test_cancel_depois_da_entrega_nao_e_importado(self):
        import tempfile
        wb = Workbook()
        ws = wb.active
        ws.append(["Waybill Number", "Task Date", "Task Status", "Driver"])
        ws.append(["AMB1", "2026-09-13", "Delivered", "Gus_LF"])
        ws.append(["AMB1", "2026-09-14", "Cancel", "Gus_LF"])
        with tempfile.NamedTemporaryFile(suffix=".xlsx") as f:
            wb.save(f.name)
            out = io.StringIO()
            with mock.patch("settlements.cainiao_views.import_operation_file") as imp:
                call_command("recover_epod_missing", f.name, "--apply", stdout=out)
        imp.assert_not_called()
        self.assertIn("revisão manual", out.getvalue())
        self.assertIn("0 em falta", out.getvalue())
