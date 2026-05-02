"""
Comando Django para sincronização de dados de parceiros.
Adaptado de ordersmanager_paack/management/commands/sync_paack.py.
"""

import logging

from django.core.management.base import BaseCommand, CommandError

from core.models import Partner, PartnerIntegration
from core.services import PartnerSyncService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Comando Django para sincronização via terminal ou cron.
    
    Uso:
        python manage.py sync_partner --partner=paack
        python manage.py sync_partner --partner=paack --force
        python manage.py sync_partner --all
    """

    help = "Sincroniza dados de parceiros logísticos"

    def add_arguments(self, parser):
        parser.add_argument(
            "--partner",
            type=str,
            help="Nome do parceiro para sincronizar (ex: paack, amazon)",
        )
        
        parser.add_argument(
            "--all",
            action="store_true",
            help="Sincronizar todos os parceiros com integrações ativas",
        )

        parser.add_argument(
            "--force",
            action="store_true",
            help="Força a sincronização ignorando o cache",
        )

        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Exibir logs detalhados",
        )

    def handle(self, *args, **options):
        if options["verbose"]:
            logging.getLogger().setLevel(logging.DEBUG)

        # Validar argumentos
        if not options["partner"] and not options["all"]:
            raise CommandError(
                "Especifique --partner=NOME ou --all para sincronizar todos"
            )

        # Sincronizar todos os parceiros
        if options["all"]:
            self._sync_all_partners(options["force"])
        else:
            self._sync_single_partner(options["partner"], options["force"])

    def _sync_all_partners(self, force_refresh):
        """Sincroniza todos os parceiros com integrações ativas"""
        self.stdout.write("🚀 Sincronizando todos os parceiros...")

        integrations = PartnerIntegration.objects.filter(
            is_active=True,
            integration_type="API"
        ).select_related("partner")

        if not integrations.exists():
            self.stdout.write(
                self.style.WARNING("⚠️ Nenhuma integração ativa encontrada")
            )
            return

        total = integrations.count()
        self.stdout.write(f"   📋 Total de integrações ativas: {total}\n")

        success_count = 0
        error_count = 0

        for integration in integrations:
            self.stdout.write(
                f"🔄 Sincronizando {integration.partner.name}..."
            )

            try:
                sync_service = PartnerSyncService(integration)
                result = sync_service.sync_data(force_refresh=force_refresh)

                if result["success"]:
                    stats = result["stats"]
                    success_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✅ {integration.partner.name} - Sucesso!\n"
                            f"   📊 Processados: {stats.get('total_processed', 0)}\n"
                            f"   ➕ Criados: {stats.get('orders_created', 0)}\n"
                            f"   🔄 Atualizados: {stats.get('orders_updated', 0)}\n"
                        )
                    )
                else:
                    error_count += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f"❌ {integration.partner.name} - Erro: {result.get('error')}\n"
                        )
                    )

            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"💥 {integration.partner.name} - Exceção: {str(e)}\n"
                    )
                )

        # Resumo final
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(
            self.style.SUCCESS(f"✅ Sucesso: {success_count}/{total}")
        )
        if error_count > 0:
            self.stdout.write(
                self.style.ERROR(f"❌ Erros: {error_count}/{total}")
            )
        self.stdout.write("=" * 50)

    def _sync_single_partner(self, partner_name, force_refresh):
        """Sincroniza um parceiro específico"""
        self.stdout.write(f"🚀 Iniciando sincronização: {partner_name}...\n")

        try:
            # Buscar parceiro
            partner = Partner.objects.get(name__iexact=partner_name)

            # Buscar integração ativa
            integration = PartnerIntegration.objects.filter(
                partner=partner,
                is_active=True,
                integration_type="API"
            ).first()

            if not integration:
                raise CommandError(
                    f"❌ Nenhuma integração API ativa encontrada para {partner_name}\n"
                    f"   Verifique: python manage.py shell\n"
                    f"   >>> from core.models import PartnerIntegration\n"
                    f"   >>> PartnerIntegration.objects.filter(partner__name__iexact='{partner_name}')"
                )

            # Sincronizar
            sync_service = PartnerSyncService(integration)
            result = sync_service.sync_data(force_refresh=force_refresh)

            # Exibir resultado
            if result["success"]:
                stats = result["stats"]
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ Sincronização concluída!\n\n"
                        f"📊 ESTATÍSTICAS:\n"
                        f"   • Total processado: {stats.get('total_processed', 0)}\n"
                        f"   • Pedidos criados: {stats.get('orders_created', 0)}\n"
                        f"   • Pedidos atualizados: {stats.get('orders_updated', 0)}\n"
                    )
                )
                
                if result.get("from_cache"):
                    self.stdout.write(
                        self.style.WARNING("   ℹ️ Dados processados do cache")
                    )
                    
                if stats.get("errors"):
                    self.stdout.write(
                        self.style.WARNING(
                            f"   ⚠️ Erros encontrados: {len(stats['errors'])}"
                        )
                    )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f"❌ Sincronização falhou!\n"
                        f"   Erro: {result.get('error')}"
                    )
                )

        except Partner.DoesNotExist:
            raise CommandError(
                f"❌ Parceiro '{partner_name}' não encontrado\n"
                f"   Parceiros disponíveis: {', '.join(Partner.objects.values_list('name', flat=True))}"
            )
