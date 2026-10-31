import json
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounting.services_pf_gaps import find_drivers_without_pf
from core.models import Partner
from drivers_app.models import DriverProfile
from settlements.models import (
    CainiaoOperationTask, CourierNameAlias,
    DriverPreInvoice,
)

DAY = date(2026, 10, 10)
PERIOD = {"periodo_inicio": "2026-10-01", "periodo_fim": "2026-10-31"}


class PreInvoiceOwnershipTests(TestCase):
    """Linha com o ID de um motorista e o nome de outro: é do outro."""

    def setUp(self):
        self.user = User.objects.create_superuser("adm", "a@a.pt", "x")
        self.client.force_login(self.user)
        self.partner = Partner.objects.create(
            name="CAINIAO", nif="500000000", contact_email="c@a.pt",
        )
        self.luis = self._driver("Luis", "ID-LUIS")
        self.fabio = self._driver("Fabio", "ID-FABIO")
        self._task("W1", "Luis", "ID-LUIS")
        self._task("W2", "Fabio", "ID-LUIS")
        self._task("W3", "Fabio", "ID-FABIO")

    def _driver(self, apelido, courier_id):
        return DriverProfile.objects.create(
            nif=courier_id, nome_completo=apelido, telefone="9",
            email=f"{apelido}@a.pt", apelido=apelido,
            courier_id_cainiao=courier_id, price_per_package=Decimal("1.00"),
            status="ATIVO", is_active=True,
        )

    def _task(self, waybill, name, courier_id):
        return CainiaoOperationTask.objects.create(
            task_date=DAY, waybill_number=waybill,
            task_status="Delivered", courier_name=name,
            courier_id_cainiao=courier_id,
            detailed_address=waybill, zip_code="4480-001",
        )

    def _create_pf(self, driver):
        url = reverse("pre-invoice-create", args=[driver.pk])
        res = self.client.post(
            url, json.dumps(PERIOD), content_type="application/json",
        )
        self.assertEqual(res.status_code, 200, res.content)
        return DriverPreInvoice.objects.get(driver=driver)

    def _packages(self, pf):
        return sum(line.total_pacotes for line in pf.linhas.all())

    def test_other_driver_name_is_out_of_the_pf(self):
        self.assertEqual(self._packages(self._create_pf(self.luis)), 1)

    def test_delivery_is_counted_for_the_name_owner(self):
        self.assertEqual(self._packages(self._create_pf(self.fabio)), 2)

    def test_alias_counts_in_the_pf(self):
        CourierNameAlias.objects.create(
            partner=self.partner, courier_id="ID-LUIS",
            courier_name="Luis Antigo",
        )
        self._task("W4", "Luis Antigo", "OUTRO")
        self.assertEqual(self._packages(self._create_pf(self.luis)), 2)

    def test_gaps_follow_the_same_rule(self):
        found = {
            row["driver_id"]: row
            for row in find_drivers_without_pf(
                date(2026, 10, 1), date(2026, 10, 31), min_gap_days=0,
            )
        }
        self.assertEqual(found[self.luis.pk]["delivered_count"], 1)
        self.assertEqual(found[self.fabio.pk]["delivered_count"], 2)
