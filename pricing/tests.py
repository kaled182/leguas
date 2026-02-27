from django.test import TestCase
from datetime import date, timedelta
from core.models import Partner
from .models import PostalZone, PartnerTariff


class PostalZoneModelTest(TestCase):
    """Testes para o modelo PostalZone"""
    
    def test_create_postal_zone(self):
        """Teste criação básica de PostalZone"""
        zone = PostalZone.objects.create(
            name='Lisboa Centro',
            code='LIS-CENTRO',
            postal_code_pattern='^11\\d{2}',
            region='LISBOA',
        )
        
        self.assertEqual(zone.name, 'Lisboa Centro')
        self.assertTrue(zone.is_active)
    
    def test_matches_postal_code(self):
        """Teste matching de código postal"""
        zone = PostalZone.objects.create(
            name='Lisboa',
            code='LISBOA',
            postal_code_pattern='^11\\d{2}',
        )
        
        # Deve fazer match
        self.assertTrue(zone.matches_postal_code('1100-001'))
        self.assertTrue(zone.matches_postal_code('1150-200'))
        
        # Não deve fazer match
        self.assertFalse(zone.matches_postal_code('2000-001'))
    
    def test_find_zone_for_postal_code(self):
        """Teste encontrar zona para código postal"""
        PostalZone.objects.create(
            name='Lisboa',
            code='LISBOA',
            postal_code_pattern='^11\\d{2}',
        )
        
        zone = PostalZone.find_zone_for_postal_code('1100-001')
        
        self.assertIsNotNone(zone)
        self.assertEqual(zone.code, 'LISBOA')


class PartnerTariffModelTest(TestCase):
    """Testes para o modelo PartnerTariff"""
    
    def setUp(self):
        self.partner = Partner.objects.create(
            name='Test Partner',
            nif='123456789',
            contact_email='test@partner.com',
        )
        
        self.zone = PostalZone.objects.create(
            name='Test Zone',
            code='TEST',
            postal_code_pattern='^10\\d{2}',
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
