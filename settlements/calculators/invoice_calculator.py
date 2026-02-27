"""
InvoiceCalculator: Calculador de faturas de partners.
Gera faturas baseadas em pedidos entregues.
"""
from decimal import Decimal
from datetime import datetime, timedelta
from django.db.models import Count, Sum, Q
from django.utils import timezone


class InvoiceCalculator:
    """
    Calcula faturas para partners baseado em:
    - Pedidos entregues no período
    - Tarifas acordadas
    - Performance (SLA, taxa de sucesso)
    """
    
    def __init__(self):
        self.debug = []
    
    def calculate_partner_invoice(self, partner, period_start, period_end, created_by=None):
        """
        Calcula fatura para um partner em um período.
        
        Args:
            partner: Partner instance
            period_start: date
            period_end: date
            created_by: User instance
        
        Returns:
            PartnerInvoice instance (salvo)
        """
        from settlements.models import PartnerInvoice
        from orders_manager.models import Order
        from pricing.models import PartnerTariff
        
        self.debug.append(f"Calculando invoice: {partner.name} ({period_start} → {period_end})")
        
        # Gerar número de invoice
        invoice_number = self._generate_invoice_number(partner, period_start)
        
        # Buscar pedidos do partner no período
        orders = Order.objects.filter(
            partner=partner,
            created_at__date__gte=period_start,
            created_at__date__lte=period_end
        ).select_related('partner')
        
        total_orders = orders.count()
        delivered_orders = orders.filter(current_status='DELIVERED').count()
        
        self.debug.append(f"Pedidos: {total_orders} (Entregues: {delivered_orders})")
        
        # Calcular valor bruto
        gross_amount = Decimal('0.00')
        
        for order in orders:
            order_value = self._calculate_order_value(order)
            gross_amount += order_value
        
        self.debug.append(f"Valor bruto: €{gross_amount}")
        
        # Calcular IVA
        tax_amount = gross_amount * Decimal('0.23')  # IVA 23%
        net_amount = gross_amount + tax_amount
        
        # Calcular data de vencimento (30 dias)
        due_date = period_end + timedelta(days=30)
        
        # Criar invoice
        invoice = PartnerInvoice.objects.create(
            partner=partner,
            invoice_number=invoice_number,
            period_start=period_start,
            period_end=period_end,
            gross_amount=gross_amount,
            tax_amount=tax_amount,
            net_amount=net_amount,
            total_orders=total_orders,
            total_delivered=delivered_orders,
            status='PENDING',
            issue_date=timezone.now().date(),
            due_date=due_date,
            created_by=created_by
        )
        
        self.debug.append(f"Invoice criado: {invoice_number} - €{net_amount}")
        
        return invoice
    
    def calculate_monthly_invoices_all_partners(self, year, month):
        """
        Calcula invoices mensais para todos os partners ativos.
        
        Args:
            year: int
            month: int (1-12)
        
        Returns:
            list of PartnerInvoice instances
        """
        from core.models import Partner
        from calendar import monthrange
        
        # Calcular datas do mês
        period_start = datetime(year, month, 1).date()
        last_day = monthrange(year, month)[1]
        period_end = datetime(year, month, last_day).date()
        
        active_partners = Partner.objects.filter(is_active=True)
        invoices_created = []
        
        for partner in active_partners:
            try:
                # Verificar se já existe invoice
                from settlements.models import PartnerInvoice
                existing = PartnerInvoice.objects.filter(
                    partner=partner,
                    period_start=period_start,
                    period_end=period_end
                ).first()
                
                if existing:
                    self.debug.append(f"Invoice já existe para {partner.name}")
                    continue
                
                # Calcular invoice
                invoice = self.calculate_partner_invoice(partner, period_start, period_end)
                
                # Salvar apenas se houver pedidos
                if invoice.total_orders > 0:
                    invoices_created.append(invoice)
                    self.debug.append(f"✅ Invoice criado para {partner.name}")
                else:
                    invoice.delete()
                    self.debug.append(f"⊘ Nenhum pedido para {partner.name}")
                
            except Exception as e:
                self.debug.append(f"❌ Erro calculando {partner.name}: {e}")
        
        return invoices_created
    
    def _generate_invoice_number(self, partner, period_start):
        """
        Gera número único de invoice.
        Formato: PARTNER-YYYY-MMDD-###
        """
        from settlements.models import PartnerInvoice
        
        prefix = partner.name.upper().replace(' ', '')[:8]
        date_str = period_start.strftime('%Y-%m%d')
        
        # Contar invoices do mesmo período
        count = PartnerInvoice.objects.filter(
            partner=partner,
            invoice_number__startswith=f"{prefix}-{date_str}"
        ).count()
        
        sequence = count + 1
        
        return f"{prefix}-{date_str}-{sequence:03d}"
    
    def _calculate_order_value(self, order):
        """Calcula valor faturável de um pedido"""
        from pricing.models import PartnerTariff
        
        try:
            # Buscar tarifa aplicável
            postal_code_prefix = order.postal_code[:4] if order.postal_code else '0000'
            
            tariff = PartnerTariff.objects.filter(
                partner=order.partner,
                postal_zone__code=postal_code_prefix,
                valid_from__lte=order.created_at.date(),
                valid_until__gte=order.created_at.date()
            ).first()
            
            if tariff:
                if order.current_status == 'DELIVERED':
                    return tariff.base_price + tariff.success_bonus
                else:
                    return tariff.base_price - tariff.failure_penalty
            
        except Exception as e:
            self.debug.append(f"Erro calculando order {order.id}: {e}")
        
        # Fallback
        return Decimal('5.00') if order.current_status == 'DELIVERED' else Decimal('2.00')
    
    def reconcile_invoice(self, invoice, paid_amount, paid_date=None):
        """
        Reconcilia invoice com pagamento recebido.
        
        Args:
            invoice: PartnerInvoice instance
            paid_amount: Decimal
            paid_date: date ou None
        """
        if invoice.status == 'PAID':
            raise ValueError("Invoice já está pago")
        
        invoice.mark_as_paid(paid_amount, paid_date)
        
        # Verificar diferença
        difference = paid_amount - invoice.net_amount
        
        if abs(difference) > Decimal('0.01'):
            self.debug.append(
                f"⚠️ Diferença encontrada: Esperado €{invoice.net_amount}, "
                f"Recebido €{paid_amount} (Diferença: €{difference})"
            )
        else:
            self.debug.append(f"✅ Invoice pago corretamente: {invoice.invoice_number}")
        
        return invoice
    
    def check_overdue_invoices(self):
        """
        Verifica invoices atrasados e atualiza status.
        
        Returns:
            list of PartnerInvoice instances atrasados
        """
        from settlements.models import PartnerInvoice
        
        overdue_invoices = PartnerInvoice.objects.filter(
            status='PENDING',
            due_date__lt=timezone.now().date()
        )
        
        for invoice in overdue_invoices:
            invoice.check_overdue()
            self.debug.append(f"⚠️ Invoice atrasado: {invoice.invoice_number} (Vencimento: {invoice.due_date})")
        
        return list(overdue_invoices)
    
    def get_partner_financial_summary(self, partner, year=None):
        """
        Retorna resumo financeiro de um partner.
        
        Returns:
            dict com estatísticas
        """
        from settlements.models import PartnerInvoice
        
        invoices_query = PartnerInvoice.objects.filter(partner=partner)
        
        if year:
            invoices_query = invoices_query.filter(period_start__year=year)
        
        summary = {
            'total_invoices': invoices_query.count(),
            'paid_invoices': invoices_query.filter(status='PAID').count(),
            'pending_invoices': invoices_query.filter(status='PENDING').count(),
            'overdue_invoices': invoices_query.filter(status='OVERDUE').count(),
            'total_billed': invoices_query.aggregate(
                total=Sum('net_amount')
            )['total'] or Decimal('0.00'),
            'total_paid': invoices_query.filter(status='PAID').aggregate(
                total=Sum('paid_amount')
            )['total'] or Decimal('0.00'),
            'total_pending': invoices_query.filter(status__in=['PENDING', 'OVERDUE']).aggregate(
                total=Sum('net_amount')
            )['total'] or Decimal('0.00'),
            'total_orders': invoices_query.aggregate(
                total=Sum('total_orders')
            )['total'] or 0,
            'total_delivered': invoices_query.aggregate(
                total=Sum('total_delivered')
            )['total'] or 0,
        }
        
        # Calcular taxa de entrega
        if summary['total_orders'] > 0:
            summary['delivery_rate'] = (
                Decimal(summary['total_delivered']) / Decimal(summary['total_orders'])
            ) * Decimal('100.00')
        else:
            summary['delivery_rate'] = Decimal('0.00')
        
        return summary
    
    def get_debug_log(self):
        """Retorna log de debug"""
        return '\n'.join(self.debug)
