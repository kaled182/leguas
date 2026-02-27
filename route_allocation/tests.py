from django.test import TestCase
from datetime import date, time
from django.contrib.auth.models import User
from drivers_app.models import DriverProfile
from pricing.models import PostalZone
from .models import DriverShift


class DriverShiftModelTest(TestCase):
    """Testes para o modelo DriverShift"""
    
    def setUp(self):
        # Criar usuário e motorista
        self.user = User.objects.create_user(
            username='test_driver',
            first_name='João',
            last_name='Silva',
        )
        self.driver = DriverProfile.objects.create(
            user=self.user,
            phone='912345678',
            license_number='PT123456',
        )
        
        # Criar zona postal
        self.zone = PostalZone.objects.create(
            name='Lisboa Centro',
            code='LIS-CENTRO',
            postal_code_pattern='^11\\d{2}',
        )
    
    def test_create_shift(self):
        """Teste criação básica de turno"""
        shift = DriverShift.objects.create(
            driver=self.driver,
            date=date.today(),
            start_time=time(9, 0),
            end_time=time(18, 0),
        )
        
        self.assertEqual(shift.driver, self.driver)
        self.assertEqual(shift.status, 'SCHEDULED')
        self.assertEqual(shift.total_deliveries, 0)
    
    def test_unique_shift_per_day(self):
        """Teste unicidade de turno por motorista por dia"""
        DriverShift.objects.create(
            driver=self.driver,
            date=date.today(),
        )
        
        # Deveria falhar (duplicate)
        with self.assertRaises(Exception):
            DriverShift.objects.create(
                driver=self.driver,
                date=date.today(),
            )
    
    def test_start_end_shift(self):
        """Teste início e fim de turno"""
        shift = DriverShift.objects.create(
            driver=self.driver,
            date=date.today(),
        )
        
        # Iniciar turno
        shift.start_shift()
        shift.refresh_from_db()
        
        self.assertEqual(shift.status, 'IN_PROGRESS')
        self.assertIsNotNone(shift.actual_start_time)
        
        # Finalizar turno
        shift.end_shift()
        shift.refresh_from_db()
        
        self.assertEqual(shift.status, 'COMPLETED')
        self.assertIsNotNone(shift.actual_end_time)
    
    def test_success_rate(self):
        """Teste cálculo de taxa de sucesso"""
        shift = DriverShift.objects.create(
            driver=self.driver,
            date=date.today(),
            total_deliveries=10,
            successful_deliveries=8,
            failed_deliveries=2,
        )
        
        self.assertEqual(shift.success_rate, 80.0)
