from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import Partner, PartnerIntegration


class PartnerModelTest(TestCase):
    """Testes para o modelo Partner"""

    def test_create_partner(self):
        """Teste criação básica de Partner"""
        partner = Partner.objects.create(
            name="Test Partner",
            nif="123456789",
            contact_email="test@partner.com",
        )

        self.assertEqual(partner.name, "Test Partner")
        self.assertEqual(partner.nif, "PT123456789")  # NIF normalizado
        self.assertTrue(partner.is_active)

    def test_nif_normalization(self):
        """Teste normalização de NIF"""
        partner = Partner.objects.create(
            name="Test",
            nif="  123456789  ",  # Com espaços
            contact_email="test@test.com",
        )

        self.assertEqual(partner.nif, "PT123456789")

    def test_nif_unique(self):
        """Teste unicidade de NIF"""
        Partner.objects.create(
            name="Partner 1",
            nif="123456789",
            contact_email="p1@test.com",
        )

        with self.assertRaises(Exception):  # IntegrityError
            Partner.objects.create(
                name="Partner 2",
                nif="PT123456789",  # Mesmo NIF
                contact_email="p2@test.com",
            )

    def test_invalid_email(self):
        """Teste validação de email inválido"""
        partner = Partner(
            name="Test",
            nif="123456789",
            contact_email="invalid-email",
        )

        with self.assertRaises(ValidationError):
            partner.clean()


class PartnerIntegrationModelTest(TestCase):
    """Testes para o modelo PartnerIntegration"""

    def setUp(self):
        self.partner = Partner.objects.create(
            name="Test Partner",
            nif="123456789",
            contact_email="test@partner.com",
        )

    def test_create_integration(self):
        """Teste criação de integração"""
        integration = PartnerIntegration.objects.create(
            partner=self.partner,
            integration_type="API",
            endpoint_url="https://api.partner.com",
            sync_frequency_minutes=15,
        )

        self.assertEqual(integration.partner, self.partner)
        self.assertEqual(integration.integration_type, "API")
        self.assertTrue(integration.is_active)

    def test_mark_sync_success(self):
        """Teste marcar sincronização como sucesso"""
        integration = PartnerIntegration.objects.create(
            partner=self.partner,
            integration_type="API",
        )

        integration.mark_sync_success("Importados 10 pedidos")
        integration.refresh_from_db()

        self.assertEqual(integration.last_sync_status, "SUCCESS")
        self.assertIsNotNone(integration.last_sync_at)
        self.assertIn("10 pedidos", integration.last_sync_message)

    def test_is_sync_overdue(self):
        """Teste detecção de sincronização atrasada"""
        from datetime import timedelta

        from django.utils import timezone

        integration = PartnerIntegration.objects.create(
            partner=self.partner,
            integration_type="API",
            sync_frequency_minutes=15,
        )

        # Sem sincronização = atrasada
        self.assertTrue(integration.is_sync_overdue)

        # Sincronização recente = OK
        integration.last_sync_at = timezone.now()
        integration.save()
        self.assertFalse(integration.is_sync_overdue)

        # Sincronização antiga = atrasada
        integration.last_sync_at = timezone.now() - timedelta(minutes=60)
        integration.save()
        self.assertTrue(integration.is_sync_overdue)


class ToggleStatusSecurityTests(TestCase):
    """Ativar/desativar só por POST."""

    def setUp(self):
        self.user = User.objects.create_user("u", password="x", is_staff=True)
        self.client.force_login(self.user)
        self.partner = Partner.objects.create(
            name="P", nif="517307243", contact_email="p@example.test",
        )
        self.integration = PartnerIntegration.objects.create(
            partner=self.partner, integration_type="API",
            endpoint_url="https://example.test",
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

    def test_partner_toggle_rejects_get(self):
        self.assert_post_only("core:partner-toggle-status", self.partner)

    def test_integration_toggle_rejects_get(self):
        self.assert_post_only("core:integration-toggle-status", self.integration)
