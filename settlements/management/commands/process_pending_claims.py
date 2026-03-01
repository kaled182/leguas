"""
Management command para processar c claims pendentes.
Execução: python manage.py process_pending_claims
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from settlements.calculators import ClaimProcessor


class Command(BaseCommand):
    help = "Processa claims pendentes e auto-cria claims de pedidos falhados"

    def add_arguments(self, parser):
        parser.add_argument(
            "--auto-create",
            action="store_true",
            help="Criar claims automaticamente para pedidos falhados",
        )
        parser.add_argument(
            "--start-date",
            type=str,
            help="Data inicial (YYYY-MM-DD) para auto-criação",
        )
        parser.add_argument(
            "--end-date",
            type=str,
            help="Data final (YYYY-MM-DD) para auto-criação",
        )
        parser.add_argument(
            "--driver-id",
            type=int,
            help="Processar apenas claims de um motorista específico",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Executa sem salvar no banco (teste)",
        )

    def handle(self, *args, **options):
        from datetime import datetime, timedelta

        from settlements.models import DriverClaim

        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(
                self.style.WARNING("🔍 Modo DRY RUN - Nenhuma alteração será salva\n")
            )

        processor = ClaimProcessor()

        # Auto-criar claims de pedidos falhados
        if options["auto_create"]:
            self.stdout.write(
                self.style.SUCCESS("🤖 Auto-criando claims de pedidos falhados...\n")
            )

            # Determinar datas
            if options["start_date"]:
                start_date = datetime.strptime(options["start_date"], "%Y-%m-%d").date()
            else:
                start_date = (
                    timezone.now() - timedelta(days=7)
                ).date()  # Última semana

            if options["end_date"]:
                end_date = datetime.strptime(options["end_date"], "%Y-%m-%d").date()
            else:
                end_date = timezone.now().date()

            self.stdout.write(f"Período: {start_date} → {end_date}")

            if not dry_run:
                claims_created = processor.auto_create_claims_from_failed_orders(
                    start_date, end_date
                )

                self.stdout.write(
                    self.style.SUCCESS(f"✅ {len(claims_created)} claims auto-criados")
                )

                for claim in claims_created:
                    self.stdout.write(
                        f"  • {claim.driver.nome_completo}: {claim.get_claim_type_display()} - "
                        f"€{claim.amount} (Order: {claim.order.tracking_code})"
                    )
            else:
                self.stdout.write(
                    self.style.WARNING("[DRY RUN] Claims seriam auto-criados")
                )

        # Processar claims pendentes
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("📋 Claims pendentes:\n")

        pending_claims = DriverClaim.objects.filter(status="PENDING")

        if options["driver_id"]:
            pending_claims = pending_claims.filter(driver_id=options["driver_id"])

        pending_claims = pending_claims.select_related("driver", "order").order_by(
            "-occurred_at"
        )

        if pending_claims.exists():
            self.stdout.write(f"Total: {pending_claims.count()} claims")

            for claim in pending_claims[:20]:  # Mostrar apenas 20
                self.stdout.write(
                    f"  • #{claim.id} - {claim.driver.nome_completo}: "
                    f"{claim.get_claim_type_display()} - €{claim.amount}"
                )
                if claim.order:
                    self.stdout.write(f"    Order: {claim.order.tracking_code}")
                self.stdout.write(f"    Descrição: {claim.description[:80]}...")
                self.stdout.write("")

        else:
            self.stdout.write(self.style.SUCCESS("✅ Nenhum claim pendente"))

        # Estatísticas por motorista
        if options["driver_id"]:
            from drivers_app.models import DriverProfile

            try:
                driver = DriverProfile.objects.get(id=options["driver_id"])

                self.stdout.write("\n" + "=" * 60)
                self.stdout.write(f"📊 Resumo de claims: {driver.nome_completo}\n")

                summary = processor.get_driver_claims_summary(driver)

                self.stdout.write(f'Total de claims: {summary["total_count"]}')
                self.stdout.write(f'  • Pendentes: {summary["pending_count"]}')
                self.stdout.write(f'  • Aprovados: {summary["approved_count"]}')
                self.stdout.write(f'  • Rejeitados: {summary["rejected_count"]}')
                self.stdout.write(f'Valor total aprovado: €{summary["total_amount"]}')

                self.stdout.write("\nPor tipo:")
                for claim_type, data in summary["by_type"].items():
                    if data["count"] > 0:
                        self.stdout.write(
                            f'  • {data["label"]}: {data["count"]} (€{data["total"]})'
                        )

            except DriverProfile.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(
                        f'❌ Motorista com ID {options["driver_id"]} não encontrado'
                    )
                )

        # Mostrar notificações
        if processor.notifications:
            self.stdout.write("\n" + "=" * 60)
            self.stdout.write("📬 Notificações:")
            for notification in processor.notifications:
                self.stdout.write(f"  • {notification}")
