"""
Management command para processar c claims pendentes.
Execução: python manage.py process_pending_claims
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from settlements.calculators import ClaimProcessor


class Command(BaseCommand):
    help = "Lista os claims pendentes e estatísticas por motorista"

    def add_arguments(self, parser):
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

        # Processar claims pendentes
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("📋 Claims pendentes:\n")

        pending_claims = DriverClaim.objects.filter(status="PENDING")

        if options["driver_id"]:
            pending_claims = pending_claims.filter(driver_id=options["driver_id"])

        pending_claims = pending_claims.select_related("driver").order_by(
            "-occurred_at"
        )

        if pending_claims.exists():
            self.stdout.write(f"Total: {pending_claims.count()} claims")

            for claim in pending_claims[:20]:  # Mostrar apenas 20
                self.stdout.write(
                    f"  • #{claim.id} - {claim.driver.nome_completo}: "
                    f"{claim.get_claim_type_display()} - €{claim.amount}"
                )
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
