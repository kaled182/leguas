"""
Management command para sincronizar pedidos do Delnext.

Busca dados de Outbound (previsão de entregas) do Delnext via web scraping
e importa para o sistema de Orders Manager.

Uso:
    # Última sexta-feira, zona VianaCastelo (padrão)
    python manage.py sync_delnext

    # Data específica
    python manage.py sync_delnext --date 2026-02-27

    # Zona específica
    python manage.py sync_delnext --zone "2.0 Lisboa"

    # Data + Zona
    python manage.py sync_delnext --date 2026-02-27 --zone VianaCastelo

    # Credenciais customizadas
    python manage.py sync_delnext --username MeuUser --password MinhaPass

    # Dry-run (teste sem salvar)
    python manage.py sync_delnext --dry-run
"""

from django.core.management.base import BaseCommand
from orders_manager.adapters import get_delnext_adapter


class Command(BaseCommand):
    help = "Sincroniza pedidos do Delnext (Outbound - Previsão de Entregas)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=str,
            default=None,
            help="Data para buscar (YYYY-MM-DD). Default: última sexta-feira",
        )
        parser.add_argument(
            "--zone",
            type=str,
            default="VianaCastelo",
            help='Zona para filtrar. Default: "VianaCastelo"',
        )
        parser.add_argument(
            "--username",
            type=str,
            default=None,
            help="Usuário Delnext. Default: VianaCastelo",
        )
        parser.add_argument(
            "--password",
            type=str,
            default=None,
            help="Senha Delnext. Default: HelloViana23432",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Apenas busca dados sem importar (teste)",
        )

    def handle(self, *args, **options):
        date = options["date"]
        zone = options["zone"]
        username = options["username"]
        password = options["password"]
        dry_run = options["dry_run"]

        self.stdout.write(self.style.SUCCESS("=" * 70))
        self.stdout.write(self.style.SUCCESS(" SINCRONIZAÇÃO DELNEXT"))
        self.stdout.write(self.style.SUCCESS("=" * 70 + "\n"))

        if dry_run:
            self.stdout.write(
                self.style.WARNING("⚠ MODO DRY-RUN (dados não serão salvos)\n")
            )

        # Parâmetros
        self.stdout.write("📋 Parâmetros:")
        self.stdout.write(
            f"   • Data: {date or 'Última sexta-feira (automático)'}"
        )
        self.stdout.write(f"   • Zona: {zone}")
        self.stdout.write(f"   • Usuário: {username or 'VianaCastelo (padrão)'}\n")

        # Criar adapter
        adapter = get_delnext_adapter(username, password)

        # Buscar dados
        self.stdout.write(self.style.WARNING("🔍 Buscando dados do Delnext..."))
        
        try:
            delnext_data = adapter.fetch_outbound_data(date=date, zone=zone)
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"\n❌ Erro ao buscar dados: {str(e)}")
            )
            return

        if not delnext_data:
            self.stdout.write(
                self.style.WARNING(
                    "\n⚠ Nenhum dado encontrado para os parâmetros fornecidos."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"✓ {len(delnext_data)} pedidos encontrados no Delnext\n"
            )
        )

        # Preview dos primeiros 5
        self.stdout.write("📦 Preview (primeiros 5):")
        for i, item in enumerate(delnext_data[:5], 1):
            self.stdout.write(
                f"   {i}. {item['product_id']} - "
                f"{item['customer_name']} - "
                f"{item['city']} ({item['destination_zone']})"
            )

        if len(delnext_data) > 5:
            self.stdout.write(f"   ... e mais {len(delnext_data) - 5} pedidos\n")

        # Dry-run: apenas mostrar dados
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "\n✓ Dry-run concluído. Nenhum dado foi importado."
                )
            )
            return

        # Confirmar importação
        self.stdout.write("")
        confirm = input("Deseja importar estes pedidos? (sim/não): ")
        if confirm.lower() not in ["sim", "s", "yes", "y"]:
            self.stdout.write(self.style.WARNING("\nImportação cancelada."))
            return

        # Importar
        self.stdout.write(
            self.style.WARNING("\n📥 Importando para Orders Manager...")
        )
        
        try:
            stats = adapter.import_to_orders(delnext_data)
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"\n❌ Erro ao importar: {str(e)}")
            )
            return

        # Resultados
        self.stdout.write(self.style.SUCCESS("\n✓ Importação concluída!\n"))
        self.stdout.write("📊 Estatísticas:")
        self.stdout.write(f"   • Total processado: {stats['total']}")
        self.stdout.write(
            self.style.SUCCESS(f"   • Criados: {stats['created']}")
        )
        self.stdout.write(
            self.style.WARNING(f"   • Atualizados: {stats['updated']}")
        )
        if stats["errors"] > 0:
            self.stdout.write(
                self.style.ERROR(f"   • Erros: {stats['errors']}")
            )
        else:
            self.stdout.write(f"   • Erros: 0")

        self.stdout.write(
            self.style.SUCCESS("\n✓ Sincronização Delnext finalizada!")
        )
