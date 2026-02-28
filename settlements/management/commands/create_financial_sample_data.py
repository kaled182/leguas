"""
Management command para criar dados fictícios do sistema financeiro
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta
import random

from settlements.models import PartnerInvoice, DriverSettlement, DriverClaim
from core.models import Partner
from drivers_app.models import DriverProfile


class Command(BaseCommand):
    help = 'Cria dados fictícios para o sistema financeiro (faturas, liquidações, reclamações)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--invoices',
            type=int,
            default=15,
            help='Número de faturas a criar'
        )
        parser.add_argument(
            '--settlements',
            type=int,
            default=20,
            help='Número de liquidações a criar'
        )
        parser.add_argument(
            '--claims',
            type=int,
            default=10,
            help='Número de reclamações a criar'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Criando dados fictícios para o sistema financeiro...'))
        
        # Get or create partners
        partners = self._ensure_partners()
        drivers = list(DriverProfile.objects.all()[:10])
        
        if not drivers:
            self.stdout.write(self.style.ERROR('Nenhum motorista encontrado. Crie motoristas primeiro.'))
            return
        
        # Create invoices
        invoices_count = options['invoices']
        self.stdout.write(f'Criando {invoices_count} faturas...')
        for i in range(invoices_count):
            self._create_invoice(partners, i)
        
        # Create settlements
        settlements_count = options['settlements']
        self.stdout.write(f'Criando {settlements_count} liquidações...')
        for i in range(settlements_count):
            self._create_settlement(partners, drivers, i)
        
        # Create claims
        claims_count = options['claims']
        self.stdout.write(f'Criando {claims_count} reclamações...')
        settlements = list(DriverSettlement.objects.all()[:5])
        for i in range(claims_count):
            self._create_claim(drivers, settlements, i)
        
        self.stdout.write(self.style.SUCCESS('✅ Dados fictícios criados com sucesso!'))
        self.stdout.write(f'   {invoices_count} faturas')
        self.stdout.write(f'   {settlements_count} liquidações')
        self.stdout.write(f'   {claims_count} reclamações')

    def _ensure_partners(self):
        """Garante que há partners criados"""
        partner_data = [
            {'name': 'Paack', 'nif': '501234567', 'email': 'paack@example.com'},
            {'name': 'Amazon', 'nif': '502345678', 'email': 'amazon@example.com'},
            {'name': 'DPD', 'nif': '503456789', 'email': 'dpd@example.com'},
            {'name': 'Glovo', 'nif': '504567890', 'email': 'glovo@example.com'},
            {'name': 'Delnext', 'nif': '505678901', 'email': 'delnext@example.com'},
        ]
        partners = []
        
        for data in partner_data:
            partner, created = Partner.objects.get_or_create(
                name=data['name'],
                defaults={
                    'nif': data['nif'],
                    'contact_email': data['email'],
                    'is_active': True,
                }
            )
            partners.append(partner)
            if created:
                self.stdout.write(f'   Partner criado: {data["name"]}')
        
        return partners

    def _create_invoice(self, partners, index):
        """Cria uma fatura fictícia"""
        partner = random.choice(partners)
        today = timezone.now().date()
        
        # Período: últimos 3 meses
        days_ago = random.randint(1, 90)
        period_end = today - timedelta(days=days_ago)
        period_start = period_end - timedelta(days=random.choice([7, 14, 30]))
        
        # Valores
        gross_amount = Decimal(random.uniform(5000, 50000)).quantize(Decimal('0.01'))
        tax_amount = (gross_amount * Decimal('0.23')).quantize(Decimal('0.01'))  # IVA 23%
        net_amount = gross_amount + tax_amount
        
        # Status aleatório
        statuses = ['DRAFT', 'PENDING', 'PAID', 'OVERDUE', 'CANCELLED']
        weights = [0.1, 0.3, 0.4, 0.15, 0.05]
        status = random.choices(statuses, weights=weights)[0]
        
        # Datas
        issue_date = period_end + timedelta(days=random.randint(1, 5))
        due_date = issue_date + timedelta(days=30)
        paid_date = None
        paid_amount = None
        if status == 'PAID':
            paid_date = due_date - timedelta(days=random.randint(0, 10))
            paid_amount = net_amount
        
        invoice_number = f'{partner.name.upper()}-2026-{index+1:03d}'
        
        try:
            PartnerInvoice.objects.create(
                partner=partner,
                invoice_number=invoice_number,
                external_reference=f'EXT-{random.randint(10000, 99999)}',
                period_start=period_start,
                period_end=period_end,
                gross_amount=gross_amount,
                tax_amount=tax_amount,
                net_amount=net_amount,
                status=status,
                issue_date=issue_date,
                due_date=due_date,
                paid_date=paid_date,
                paid_amount=paid_amount,
                total_orders=random.randint(100, 500),
                total_delivered=random.randint(80, 450),
                notes=f'Fatura de teste #{index+1}' if random.random() > 0.7 else ''
            )
            self.stdout.write(f'   ✓ Fatura {invoice_number} - {status} - €{net_amount}')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'   ⚠ Erro ao criar fatura {invoice_number}: {e}'))

    def _create_settlement(self, partners, drivers, index):
        """Cria uma liquidação fictícia"""
        driver = random.choice(drivers)
        partner = random.choice(partners)
        today = timezone.now().date()
        
        # Período: últimas 8 semanas
        weeks_ago = random.randint(0, 8)
        period_end = today - timedelta(weeks=weeks_ago)
        period_start = period_end - timedelta(days=6)  # 1 semana
        
        # Estatísticas
        total_orders = random.randint(80, 250)
        delivered_orders = int(total_orders * random.uniform(0.75, 0.95))
        failed_orders = total_orders - delivered_orders
        success_rate = Decimal((delivered_orders / total_orders * 100) if total_orders > 0 else 0).quantize(Decimal('0.01'))
        
        # Valores
        gross_amount = Decimal(random.uniform(400, 1200)).quantize(Decimal('0.01'))
        bonus_amount = Decimal(random.uniform(0, 100)).quantize(Decimal('0.01'))
        fuel_deduction = Decimal(random.uniform(50, 150)).quantize(Decimal('0.01'))
        other_deductions = Decimal(random.uniform(0, 100)).quantize(Decimal('0.01'))
        net_amount = gross_amount + bonus_amount - fuel_deduction - other_deductions
        
        # Status
        statuses = ['DRAFT', 'CALCULATED', 'APPROVED', 'PAID', 'DISPUTED']
        weights = [0.1, 0.2, 0.3, 0.35, 0.05]
        status = random.choices(statuses, weights=weights)[0]
        
        paid_at = None
        if status == 'PAID':
            paid_at = timezone.now() - timedelta(days=random.randint(0, 14))
        
        try:
            DriverSettlement.objects.create(
                driver=driver,
                partner=partner,
                period_type='WEEKLY',
                week_number=period_end.isocalendar()[1],
                year=period_end.year,
                period_start=period_start,
                period_end=period_end,
                total_orders=total_orders,
                delivered_orders=delivered_orders,
                failed_orders=failed_orders,
                success_rate=success_rate,
                gross_amount=gross_amount,
                bonus_amount=bonus_amount,
                fuel_deduction=fuel_deduction,
                other_deductions=other_deductions,
                net_amount=net_amount,
                status=status,
                paid_at=paid_at,
                notes=f'Liquidação semanal de teste #{index+1}' if random.random() > 0.7 else ''
            )
            self.stdout.write(f'   ✓ Liquidação {driver.nome_completo} - {status} - €{net_amount}')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'   ⚠ Erro ao criar liquidação: {e}'))

    def _create_claim(self, drivers, settlements, index):
        """Cria uma reclamação fictícia"""
        driver = random.choice(drivers)
        
        claim_types = [
            'ORDER_LOSS',
            'ORDER_DAMAGE',
            'VEHICLE_FINE',
            'VEHICLE_DAMAGE',
            'FUEL_EXCESS',
            'MISSING_POD',
            'LATE_DELIVERY',
            'CUSTOMER_COMPLAINT',
            'OTHER'
        ]
        
        statuses = ['PENDING', 'APPROVED', 'REJECTED', 'APPEALED']
        weights = [0.35, 0.35, 0.2, 0.1]
        status = random.choices(statuses, weights=weights)[0]
        
        amount = Decimal(random.uniform(20, 500)).quantize(Decimal('0.01'))
        
        reviewed_at = None
        if status in ['APPROVED', 'REJECTED']:
            reviewed_at = timezone.now() - timedelta(days=random.randint(1, 10))
        
        descriptions = [
            'Perda de pacote durante a entrega',
            'Dano em pacote reportado pelo cliente',
            'Multa de trânsito durante expedição',
            'Entrega realizada fora do prazo',
            'Reclamação formal do cliente',
            'Falta de comprovante de entrega',
        ]
        
        justifications = [
            'Pedido já foi resolvido com cliente',
            'Não foi culpa do motorista',
            'Situação fora de controle',
            '',
        ]
        
        try:
            DriverClaim.objects.create(
                driver=driver,
                settlement=random.choice(settlements) if settlements and random.random() > 0.3 else None,
                claim_type=random.choice(claim_types),
                amount=amount,
                status=status,
                description=random.choice(descriptions),
                justification=random.choice(justifications) if status == 'APPEALED' else '',
                review_notes=f'Análise administrativa #{index+1}' if status != 'PENDING' else '',
                reviewed_at=reviewed_at
            )
            self.stdout.write(f'   ✓ Reclamação {driver.nome_completo} - {status} - €{amount}')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'   ⚠ Erro ao criar reclamação: {e}'))
