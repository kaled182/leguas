from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from core.models import Partner

from .models import PartnerTariff, PostalZone


class PostalZoneModelTest(TestCase):
    """Testes para o modelo PostalZone"""

    def test_create_postal_zone(self):
        """Teste criação básica de PostalZone"""
        zone = PostalZone.objects.create(
            name="Lisboa Centro",
            code="LIS-CENTRO",
            postal_code_pattern="^11\\d{2}",
            region="LISBOA",
        )

        self.assertEqual(zone.name, "Lisboa Centro")
        self.assertTrue(zone.is_active)

    def test_matches_postal_code(self):
        """Teste matching de código postal"""
        zone = PostalZone.objects.create(
            name="Lisboa",
            code="LISBOA",
            postal_code_pattern="^11\\d{2}",
        )

        # Deve fazer match
        self.assertTrue(zone.matches_postal_code("1100-001"))
        self.assertTrue(zone.matches_postal_code("1150-200"))

        # Não deve fazer match
        self.assertFalse(zone.matches_postal_code("2000-001"))

    def test_find_zone_for_postal_code(self):
        """Teste encontrar zona para código postal"""
        PostalZone.objects.create(
            name="Lisboa",
            code="LISBOA",
            postal_code_pattern="^11\\d{2}",
        )

        zone = PostalZone.find_zone_for_postal_code("1100-001")

        self.assertIsNotNone(zone)
        self.assertEqual(zone.code, "LISBOA")


class PartnerTariffModelTest(TestCase):
    """Testes para o modelo PartnerTariff"""

    def setUp(self):
        self.partner = Partner.objects.create(
            name="Test Partner",
            nif="123456789",
            contact_email="test@partner.com",
        )

        self.zone = PostalZone.objects.create(
            name="Test Zone",
            code="TEST",
            postal_code_pattern="^10\\d{2}",
        )

    def test_create_tariff(self):
        """Teste criação de tarifa"""
        tariff = PartnerTariff.objects.create(
            partner=self.partner,
            postal_zone=self.zone,
            base_price=2.50,
            success_bonus=0.50,
            valid_from=date.today(),
        )

        self.assertEqual(tariff.partner, self.partner)
        self.assertEqual(tariff.postal_zone, self.zone)
        self.assertTrue(tariff.is_active)

    def test_is_valid_on_date(self):
        """Teste validação de data"""
        tariff = PartnerTariff.objects.create(
            partner=self.partner,
            postal_zone=self.zone,
            base_price=2.50,
            valid_from=date.today() - timedelta(days=10),
            valid_until=date.today() + timedelta(days=10),
        )

        # Dentro do período
        self.assertTrue(tariff.is_valid_on_date(date.today()))

        # Antes do período
        self.assertFalse(tariff.is_valid_on_date(date.today() - timedelta(days=20)))

        # Depois do período
        self.assertFalse(tariff.is_valid_on_date(date.today() + timedelta(days=20)))

    def test_calculate_price(self):
        """Teste cálculo de preço"""
        tariff = PartnerTariff.objects.create(
            partner=self.partner,
            postal_zone=self.zone,
            base_price=2.00,
            success_bonus=0.50,
            weekend_multiplier=1.5,
            valid_from=date.today(),
        )

        # Preço normal
        price = tariff.calculate_price(is_weekend=False)
        self.assertEqual(price, 2.50)

        # Preço com multiplicador de fim de semana
        price_weekend = tariff.calculate_price(is_weekend=True)
        self.assertEqual(price_weekend, 3.75)  # 2.50 * 1.5


class ToggleStatusSecurityTests(TestCase):
    """Ativar/desativar só por POST."""

    def setUp(self):
        self.user = User.objects.create_user("u", password="x", is_staff=True, is_superuser=True)
        self.client.force_login(self.user)
        self.zone = PostalZone.objects.create(
            name="Zona", code="Z1", postal_code_pattern="^4740",
        )
        self.partner = Partner.objects.create(
            name="P", nif="517307243", contact_email="p@example.test",
        )
        self.tariff = PartnerTariff.objects.create(
            partner=self.partner, postal_zone=self.zone, base_price=1,
            valid_from=date(2026, 1, 1),
        )

    def assert_post_only(self, url_name, obj):
        url = reverse(url_name, args=[obj.pk])
        before = obj.is_active
        self.assertEqual(self.client.get(url).status_code, 405)
        obj.refresh_from_db()
        self.assertEqual(obj.is_active, before)
        self.assertEqual(self.client.post(url).status_code, 302)
        obj.refresh_from_db()
        self.assertNotEqual(obj.is_active, before)

    def test_zone_toggle_rejects_get(self):
        self.assert_post_only("pricing:zone-toggle-status", self.zone)

    def test_tariff_toggle_rejects_get(self):
        self.assert_post_only("pricing:tariff-toggle-status", self.tariff)

    def test_toggle_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        url = reverse("pricing:zone-toggle-status", args=[self.zone.pk])
        self.assertEqual(client.post(url).status_code, 403)
