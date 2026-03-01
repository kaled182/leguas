import logging

from django.core.management.base import BaseCommand

from ordersmanager_paack.models import Dispatch, Driver, Order
from ordersmanager_paack.sync_service import SyncService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Comando Django para sincronização via terminal ou cron.
    Implementação real baseada no ordersmanager funcional.
    """

    help = "Sincroniza dados da API Paack"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Força a sincronização ignorando o cache",
        )

        parser.add_argument(
            "--verbose", action="store_true", help="Exibir logs detalhados"
        )

    def handle(self, *args, **options):
        if options["verbose"]:
            logging.getLogger().setLevel(logging.DEBUG)

        self.stdout.write("🚀 Iniciando sincronização Paack...")

        try:
            sync_service = SyncService()
            result = sync_service.sync_data(force_refresh=options["force"])

            if result["success"]:
                stats = result["stats"]
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ Sincronização concluída!\n"
                        f"   📊 Total processado: {stats.get('total_processed', 0)}\n"
                        f"   ➕ Ordens criadas: {stats.get('orders_created', 0)}\n"
                        f"   🔄 Ordens atualizadas: {stats.get('orders_updated', 0)}\n"
                        f"   🚛 Motoristas criados: {stats.get('drivers_created', 0)}\n"
                        f"   📋 Dispatches criados: {stats.get('dispatches_created', 0)}"
                    )
                )

                if stats.get("errors"):
                    self.stdout.write(
                        self.style.WARNING(
                            f"⚠️ {len(stats['errors'])} erros encontrados"
                        )
                    )
                    for error in stats["errors"][:5]:  # Mostrar primeiros 5 erros
                        self.stdout.write(f"   - {error}")

            else:
                self.stdout.write(
                    self.style.ERROR(
                        f"❌ Falha: {result.get('error', 'Erro desconhecido')}"
                    )
                )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Erro inesperado: {e}"))

        # Exibir contagem de registros
        self.stdout.write(f"Orders: {Order.objects.count()}")
        self.stdout.write(f"Drivers: {Driver.objects.count()}")
        self.stdout.write(f"Dispatches: {Dispatch.objects.count()}")
