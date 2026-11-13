"""Interruptor da penalização por entrega falsa PUDO (ficha do parceiro)."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Partner
from drivers_app.models import DriverProfile

from .models import CainiaoOperationTask, DriverClaim

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


@override_settings(CACHES=LOCMEM)
class FakeDeliveryToggleTests(TestCase):
    def setUp(self):
        self.p = Partner.objects.create(
            name="CAINIAO", nif="514154411", contact_email="c@x.pt",
            pudo_enabled=True, pudo_fake_delivery_penalty=Decimal("5.00"),
        )
        DriverProfile.objects.create(
            nif="123456789", nome_completo="Rui", telefone="910000000",
            email="rui@x.pt", apelido="Rui_LF",
        )
        self.task = CainiaoOperationTask.objects.create(
            waybill_number="W1", task_date=date(2026, 11, 2), task_status="Delivered",
            courier_name="Rui_LF", delivery_type="PUDO", detailed_address="Rua A 1",
            receiver_latitude="41.10", receiver_longitude="-8.10",
            actual_latitude="41.20", actual_longitude="-8.20",
        )
        admin = get_user_model().objects.create_superuser("admin", "a@x.pt", "x")
        self.client.force_login(admin)
        self.url = reverse("pudo-fake-delivery-confirm", args=[self.task.id])

    def test_por_omissao_a_penalizacao_esta_ligada(self):
        self.assertTrue(Partner.objects.get(pk=self.p.pk).pudo_fake_delivery_enabled)
        self.client.post(self.url)
        claim = DriverClaim.objects.get(waybill_number="W1")
        self.assertEqual((claim.claim_type, claim.amount), ("FAKE_DELIVERY", Decimal("5.00")))

    def test_desligada_nao_cria_desconto(self):
        self.p.pudo_fake_delivery_enabled = False
        self.p.save()
        self.client.post(self.url)
        self.assertEqual(DriverClaim.objects.count(), 0)
        r = self.client.get(reverse("pudo-fake-delivery-suspects"))
        self.assertContains(r, "Penalização por entrega falsa desligada")
        self.assertNotContains(r, "Confirmar Fake")

    def test_gerador_de_contrato_segue_o_interruptor(self):
        from contracts.views_generator import _multi_payload

        self.assertTrue(_multi_payload()["fake_on"])
        self.p.pudo_fake_delivery_enabled = False
        self.p.save()
        self.assertFalse(_multi_payload()["fake_on"])
