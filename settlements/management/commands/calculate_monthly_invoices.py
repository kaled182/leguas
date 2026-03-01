"""
Management command para calcular invoices mensais de partners.
Execução: python manage.py calculate_monthly_invoices --month 2 --year 2026
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from settlements.calculators import InvoiceCalculator


class Command(BaseCommand):
    help = "Calcula invoices mensais para todos os partners ativos"

    def add_arguments(self, parser):
        parser.add_argument(
            "--month",
            type=int,
            help="Mês (1-12). Se não informado, usa mês anterior",
        )
        parser.add_argument(
            "--year", type=int, help="Ano. Se não informado, usa ano atual"
        )
        parser.add_argument(
            "--partner-id",
            type=int,
            help="ID do partner específico. Se não informado, calcula para todos",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Executa sem salvar no banco (teste)",
        )

    def handle(self, *args, **options):
        # Determinar mês e ano
        now = timezone.now()
        year = options["year"] or now.year

        # Se não informado, usa mês anterior
        if options["month"]:
            month = options["month"]
        else:
            # Mês anterior
            if now.month == 1:
                month = 12
                year = now.year - 1
            else:
                month = now.month - 1

        partner_id = options["partner_id"]
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(
                self.style.WARNING("🔍 Modo DRY RUN - Nenhuma alteração será salva\n")
            )

        self.stdout.write(
            self.style.SUCCESS(f"🧾 Calculando invoices - {month:02d}/{year}\n")
        )

        # Criar calculator
        calculator = InvoiceCalculator()

        if partner_id:
            # Calcular para partner específico
            from calendar import monthrange
            from datetime import datetime

            from core.models import Partner

            try:
                partner = Partner.objects.get(id=partner_id)
                self.stdout.write(f"Processando partner: {partner.name}")

                # Calcular datas do mês
                period_start = datetime(year, month, 1).date()
                last_day = monthrange(year, month)[1]
                period_end = datetime(year, month, last_day).date()

                invoice = calculator.calculate_partner_invoice(
                    partner, period_start, period_end
                )

                if not dry_run:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✅ Invoice criado: {invoice.invoice_number} - "
                            f"€{invoice.net_amount} ({invoice.total_orders} pedidos)"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"[DRY RUN] Invoice: {invoice.invoice_number} - "
                            f"€{invoice.net_amount} ({invoice.total_orders} pedidos)"
                        )
                    )
                    if not dry_run:
                        invoice.delete()  # Remover se dry run

                # Mostrar debug
                self.stdout.write("\n📋 Detalhes do cálculo:")
                self.stdout.write(calculator.get_debug_log())

            except Partner.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"❌ Partner com ID {partner_id} não encontrado")
                )
                return

        else:
            # Calcular para todos os partners
            if not dry_run:
                invoices = calculator.calculate_monthly_invoices_all_partners(
                    year, month
                )

                self.stdout.write("\n" + "=" * 60)
                self.stdout.write(
                    self.style.SUCCESS(f"✅ {len(invoices)} invoices criados")
                )

                # Estatísticas
                total_amount = sum(inv.net_amount for inv in invoices)
                total_orders = sum(inv.total_orders for inv in invoices)

                self.stdout.write(f"Total a receber: €{total_amount}")
                self.stdout.write(f"Total de pedidos: {total_orders}")

                # Listar invoices criados
                self.stdout.write("\n📋 Invoices criados:")
                for invoice in invoices:
                    self.stdout.write(
                        f"  • {invoice.partner.name}: {invoice.invoice_number} - "
                        f"€{invoice.net_amount} ({invoice.total_orders} pedidos)"
                    )

            else:
                # Dry run: apenas contar
                from core.models import Partner

                active_partners = Partner.objects.filter(is_active=True).count()
                self.stdout.write(
                    self.style.WARNING(
                        f"[DRY RUN] Seria calculado para {active_partners} partners ativos"
                    )
                )

        # Mostrar log de debug
        if calculator.debug:
            self.stdout.write("\n📋 Log completo:")
            self.stdout.write(calculator.get_debug_log())

        # Verificar invoices atrasados
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("🔍 Verificando invoices atrasados...")
        overdue = calculator.check_overdue_invoices()

        if overdue:
            self.stdout.write(
                self.style.WARNING(f"⚠️ {len(overdue)} invoices atrasados:")
            )
            for inv in overdue:
                days_overdue = (timezone.now().date() - inv.due_date).days
                self.stdout.write(
                    f"  • {inv.invoice_number} ({inv.partner.name}): "
                    f"€{inv.net_amount} - Vencido há {days_overdue} dias"
                )
        else:
            self.stdout.write(self.style.SUCCESS("✅ Nenhum invoice atrasado"))
