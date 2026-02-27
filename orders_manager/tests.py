from django.test import TestCase
from django.utils import timezone
from datetime import date, timedelta
from core.models import Partner
from drivers_app.models import DriverProfile
from django.contrib.auth.models import User
from .models import Order, OrderStatusHistory, OrderIncident


class OrderModelTest(TestCase):
    """Testes para o modelo Order"""
    
    def setUp(self):
        # Criar parceiro de teste
        self.partner = Partner.objects.create(
            name='Test Partner',
            nif='123456789',
            contact_email='test@partner.com',
        )
        
        # Criar usuário e motorista de teste
        self.user = User.objects.create_user(
            username='driver_test',
            first_name='João',
            last_name='Silva',
        )
        self.driver = DriverProfile.objects.create(
            user=self.user,
            phone='912345678',
            license_number='PT123456',
        )
    
    def test_create_order(self):
        """Teste criação básica de Order"""
        order = Order.objects.create(
            partner=self.partner,
            external_reference='TEST-001',
            recipient_name='Carlos Silva',
            recipient_address='Rua de teste, 123',
            postal_code='1000-001',
            declared_value=50.00,
        )
        
        self.assertEqual(order.partner, self.partner)
        self.assertEqual(order.current_status, 'PENDING')
        self.assertIsNotNone(order.created_at)
    
    def test_unique_reference_per_partner(self):
        """Teste unicidade de referência por parceiro"""
        Order.objects.create(
            partner=self.partner,
            external_reference='TEST-001',
            recipient_name='Carlos Silva',
            recipient_address='Rua de teste, 123',
            postal_code='1000-001',
        )
        
        # Deveria falhar (duplicate)
        with self.assertRaises(Exception):
            Order.objects.create(
                partner=self.partner,
                external_reference='TEST-001',  # Mesma referência
                recipient_name='Outro Cliente',
                recipient_address='Outra rua',
                postal_code='2000-001',
            )
    
    def test_assign_to_driver(self):
        """Teste atribuição de pedido a motorista"""
        order = Order.objects.create(
            partner=self.partner,
            external_reference='TEST-002',
            recipient_name='Maria Santos',
            recipient_address='Av. Principal, 456',
            postal_code='1100-001',
        )
        
        order.assign_to_driver(self.driver)
        order.refresh_from_db()
        
        self.assertEqual(order.assigned_driver, self.driver)
        self.assertEqual(order.current_status, 'ASSIGNED')
        self.assertIsNotNone(order.assigned_at)
        
        # Verificar que histórico foi criado
        self.assertTrue(
            order.status_history.filter(status='ASSIGNED').exists()
        )
    
    def test_mark_as_delivered(self):
        """Teste marcação como entregue"""
        order = Order.objects.create(
            partner=self.partner,
            external_reference='TEST-003',
            recipient_name='Pedro Costa',
            recipient_address='Praça Central, 789',
            postal_code='1200-001',
        )
        
        proof = {'signature': 'Pedro Costa', 'photo_url': 'http://example.com/photo.jpg'}
        order.mark_as_delivered(proof=proof)
        order.refresh_from_db()
        
        self.assertEqual(order.current_status, 'DELIVERED')
        self.assertIsNotNone(order.delivered_at)
        self.assertEqual(order.delivery_proof, proof)
    
    def test_is_overdue(self):
        """Teste detecção de pedido atrasado"""
        # Pedido com entrega agendada para ontem
        order_overdue = Order.objects.create(
            partner=self.partner,
            external_reference='TEST-004',
            recipient_name='Ana Oliveira',
            recipient_address='Rua das Flores, 111',
            postal_code='1300-001',
            scheduled_delivery=date.today() - timedelta(days=1),
        )
        
        self.assertTrue(order_overdue.is_overdue)
        
        # Pedido com entrega agendada para amanhã
        order_ok = Order.objects.create(
            partner=self.partner,
            external_reference='TEST-005',
            recipient_name='Rui Ferreira',
            recipient_address='Praça da República, 222',
            postal_code='1400-001',
            scheduled_delivery=date.today() + timedelta(days=1),
        )
        
        self.assertFalse(order_ok.is_overdue)


class OrderIncidentModelTest(TestCase):
    """Testes para o modelo OrderIncident"""
    
    def setUp(self):
        self.partner = Partner.objects.create(
            name='Test Partner',
            nif='123456789',
            contact_email='test@partner.com',
        )
        
        self.order = Order.objects.create(
            partner=self.partner,
            external_reference='TEST-INC-001',
            recipient_name='Cliente Teste',
            recipient_address='Rua Teste',
            postal_code='1000-001',
        )
    
    def test_create_incident(self):
        """Teste criação de incidente"""
        incident = OrderIncident.objects.create(
            order=self.order,
            incident_type='DAMAGED',
            description='Encomenda danificada durante transporte',
            driver_responsible=True,
            claim_amount=25.00,
        )
        
        self.assertFalse(incident.resolved)
        self.assertEqual(incident.incident_type, 'DAMAGED')
        self.assertEqual(incident.claim_amount, 25.00)
    
    def test_mark_as_resolved(self):
        """Teste marcação de incidente como resolvido"""
        incident = OrderIncident.objects.create(
            order=self.order,
            incident_type='LOST',
            description='Encomenda extraviada',
        )
        
        incident.mark_as_resolved('Encomenda encontrada e entregue')
        incident.refresh_from_db()
        
        self.assertTrue(incident.resolved)
        self.assertIsNotNone(incident.resolved_at)
        self.assertIn('encontrada', incident.resolution_notes)
