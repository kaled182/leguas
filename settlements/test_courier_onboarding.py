import json
from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from core.models import Partner
from drivers_app.models import DriverProfile

from .models import (
    CainiaoDriverStat, CainiaoDriverStatBatch, CainiaoOperationTask, CourierNameAlias, DriverCourierMapping,
)
from .services_courier_onboarding import (
    OnboardingError, create_driver_for_courier_name, lookup_courier_id, suggested_full_name,
)

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


def _task(waybill, courier_name, courier_id=""):
    return CainiaoOperationTask.objects.create(
        waybill_number=waybill, task_date=date(2026, 9, 28), task_status="Delivered",
        courier_name=courier_name, courier_id_cainiao=courier_id,
    )


@override_settings(CACHES=LOCMEM)
class CreateDriverTests(TestCase):
    def setUp(self):
        self.partner = Partner.objects.create(name="CAINIAO", nif="514154411", contact_email="c@x.pt")

    def test_cria_pendente_ligado_ao_login_exacto_e_marca_so_as_desse_login(self):
        _task("WB1", "Josuel Lobato_LF")
        _task("WB2", "Josuel Lobato_LF")
        _task("WB3", "Josuel_Lobato_LF")  # outro login: outro Courier ID, nunca se mistura
        _task("WB4", "Josuel Lobato_LF", courier_id="999")  # já tinha ID: não se toca

        r = create_driver_for_courier_name("Josuel Lobato_LF", "1576538726968")

        self.assertEqual(r["updated"], 2)
        driver = DriverProfile.objects.get(pk=r["driver_id"])
        self.assertEqual((driver.status, driver.is_active), ("PENDENTE", False))
        self.assertEqual((driver.nome_completo, driver.apelido, driver.courier_id_cainiao),
                         ("Josuel Lobato", "Josuel Lobato_LF", "1576538726968"))
        m = DriverCourierMapping.objects.get(partner=self.partner, courier_id="1576538726968")
        self.assertEqual((m.courier_name, m.driver_id), ("Josuel Lobato_LF", driver.id))
        self.assertEqual(CourierNameAlias.objects.get(courier_name="Josuel Lobato_LF").courier_id, "1576538726968")
        self.assertEqual(CainiaoOperationTask.objects.get(waybill_number="WB3").courier_id_cainiao, "")
        self.assertEqual(CainiaoOperationTask.objects.get(waybill_number="WB4").courier_id_cainiao, "999")

    def test_courier_id_de_outro_motorista_e_recusado_sem_criar_nada(self):
        create_driver_for_courier_name("Ana_LF", "1576538000001")
        with self.assertRaisesMessage(OnboardingError, "já pertence"):
            create_driver_for_courier_name("Outra_LF", "1576538000001")
        self.assertEqual(DriverProfile.objects.count(), 1)

    def test_courier_id_invalido(self):
        with self.assertRaisesMessage(OnboardingError, "Courier ID inválido"):
            create_driver_for_courier_name("Ana_LF", "Ana_LF")

    def test_nome_sugerido(self):
        self.assertEqual(suggested_full_name("Gustavo Guedes-LF"), "Gustavo Guedes")
        self.assertEqual(suggested_full_name("Matteo Ferreira_LF"), "Matteo Ferreira")


@override_settings(CACHES=LOCMEM)
class LookupTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def test_driver_statistic_primeiro_e_so_login_exacto(self):
        batch = CainiaoDriverStatBatch.objects.create(filename="COURIER_DELIVERY_STATISTIC.xlsx")
        CainiaoDriverStat.objects.create(batch=batch, courier_id="1576538726968", courier_name="Alex Serafim_LF")
        with mock.patch("settlements.services_courier_onboarding._ces_users", return_value=[]):
            self.assertEqual(lookup_courier_id("Alex Serafim_LF")["courier_id"], "1576538726968")
            self.assertIsNone(lookup_courier_id("Alexserafim_APOIO"), "outro login, outro Courier ID")

    def test_user_list_do_ces_so_login_exacto(self):
        users = [
            {"login": "Donovan_silva_LF", "courier_id": "111", "tipo": "COURIER", "principal": "", "hub": "porto"},
            {"login": "Donovan silva LF", "courier_id": "222", "tipo": "COURIER_HELPER", "principal": "Rui_LF", "hub": "porto"},
        ]
        with mock.patch("settlements.services_courier_onboarding._ces_users", return_value=users):
            f = lookup_courier_id("Donovan silva LF")
            self.assertEqual((f["courier_id"], f["source"], f["tipo"], f["principal"]), ("222", "ces", "COURIER_HELPER", "Rui_LF"))
            self.assertIsNone(lookup_courier_id("donovan silva lf"))

    def test_ces_indisponivel_nao_parte(self):
        with mock.patch("settlements.services_courier_onboarding._config", return_value=(True, "https://r.test", "k")), \
             mock.patch("settlements.services_reliable_sync.requests.get", return_value=mock.Mock(status_code=404)):
            self.assertIsNone(lookup_courier_id("Ana_LF"))


@override_settings(CACHES=LOCMEM)
class ViewsTests(TestCase):
    def setUp(self):
        Partner.objects.create(name="CAINIAO", nif="514154411", contact_email="c@x.pt")
        self.user = get_user_model().objects.create_user("operador", password="x")

    def test_login_obrigatorio(self):
        self.assertEqual(self.client.get("/settlements/cainiao/unmapped/lookup/?courier_name=A", secure=True).status_code, 302)
        self.assertEqual(self.client.post("/settlements/cainiao/unmapped/create-driver/", "{}",
                                          content_type="application/json", secure=True).status_code, 302)

    def test_cria_pela_view(self):
        _task("WB1", "Matteo Ferreira_LF")
        self.client.force_login(self.user)
        d = self.client.post("/settlements/cainiao/unmapped/create-driver/", json.dumps({
            "old_courier_name": "Matteo Ferreira_LF", "courier_id": "1576538111111", "nome": "Matteo Ferreira",
        }), content_type="application/json", secure=True).json()
        self.assertTrue(d["success"], d)
        self.assertEqual(d["updated"], 1)
        self.assertIn("operador", DriverProfile.objects.get(pk=d["driver_id"]).observacoes)

        d = self.client.post("/settlements/cainiao/unmapped/create-driver/", json.dumps({
            "old_courier_name": "X_LF", "courier_id": "1576538111111",
        }), content_type="application/json", secure=True)
        self.assertEqual(d.status_code, 400)


@override_settings(CACHES=LOCMEM)
class PartnerPageRendersTests(TestCase):
    """A página do parceiro renderiza o painel (os {% url %} só falham ao renderizar)."""

    def test_pagina_do_parceiro_abre(self):
        partner = Partner.objects.create(name="CAINIAO", nif="514154411", contact_email="c@x.pt")
        admin = get_user_model().objects.create_superuser("admin", "a@x.pt", "x")
        self.client.force_login(admin)
        r = self.client.get(f"/core/partners/{partner.id}/", secure=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "_unmToggleNewDriver")
