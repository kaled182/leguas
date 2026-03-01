"""
Management command para monitorar consistência entre sistemas durante dual write.

Uso:
    python manage.py monitor_dual_write
    python manage.py monitor_dual_write --days 7  # Últimos 7 dias
"""

import sys
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.db.models import Count


class Command(BaseCommand):
    help = "Monitora consistência entre sistema antigo e novo durante dual write"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=1,
            help="Número de dias para verificar (default: 1)",
        )
        parser.add_argument(
            "--detailed",
            action="store_true",
            help="Mostra exemplos de inconsistências",
        )

    def handle(self, *args, **options):
        days = options["days"]
        detailed = options["detailed"]

        self.stdout.write(self.style.SUCCESS("=" * 70))
        self.stdout.write(self.style.SUCCESS(" MONITORAMENTO DE DUAL WRITE"))
        self.stdout.write(self.style.SUCCESS("=" * 70 + "\n"))

        # Verificar imports
        try:
            from django.conf import settings

            from core.models import Partner
            from orders_manager.models import Order as GenericOrder
            from ordersmanager_paack.models import Order as PaackOrder
        except ImportError as e:
            self.stdout.write(self.style.ERROR(f"❌ Erro ao importar: {str(e)}"))
            sys.exit(1)

        # Verificar se dual write está ativo
        dual_write = getattr(settings, "DUAL_WRITE_ORDERS", False)

        self.stdout.write(self.style.HTTP_INFO("⚙️ Configuração:\n"))
        self.stdout.write(
            f'  • Dual Write: {"🟢 ATIVADO" if dual_write else "❌ DESATIVADO"}'
        )
        self.stdout.write(f"  • Período: Últimos {days} dia(s)\n")

        if not dual_write:
            self.stdout.write(
                self.style.WARNING(
                    "⚠️ DUAL_WRITE_ORDERS não está ativado!\n"
                    "   Este relatório pode não refletir a realidade.\n"
                )
            )

        # Período de análise
        cutoff_date = datetime.now() - timedelta(days=days)

        # Estatísticas gerais
        self.stdout.write(self.style.HTTP_INFO("📊 Estatísticas Gerais:\n"))

        paack_count = PaackOrder.objects.filter(created_at__gte=cutoff_date).count()

        try:
            paack_partner = Partner.objects.get(name="Paack")
            generic_count = GenericOrder.objects.filter(
                partner=paack_partner, created_at__gte=cutoff_date
            ).count()
        except Partner.DoesNotExist:
            generic_count = 0
            self.stdout.write(self.style.WARNING('  ⚠️ Partner "Paack" não encontrado'))
            paack_partner = None

        self.stdout.write(f"  • Pedidos Paack (antigo): {paack_count:,}")
        self.stdout.write(f"  • Pedidos Generic (novo): {generic_count:,}")

        # Análise de diferenças
        if paack_count > 0 or generic_count > 0:
            diff = abs(paack_count - generic_count)

            if diff == 0:
                self.stdout.write(
                    self.style.SUCCESS(f"  ✅ Contagens match perfeitamente!")
                )
            else:
                percentage = (diff / max(paack_count, generic_count)) * 100
                self.stdout.write(
                    self.style.WARNING(
                        f"  ⚠️ Diferença: {diff:,} pedidos ({percentage:.1f}%)"
                    )
                )

        # Análise de referências órfãs
        if paack_partner and generic_count > 0:
            self.stdout.write(
                "\n" + self.style.HTTP_INFO("🔗 Análise de Referências:\n")
            )

            # Pedidos Generic sem correspondente no Paack
            generic_refs = set(
                GenericOrder.objects.filter(
                    partner=paack_partner, created_at__gte=cutoff_date
                ).values_list("external_reference", flat=True)
            )

            paack_uuids = set(
                str(uuid)
                for uuid in PaackOrder.objects.filter(
                    created_at__gte=cutoff_date
                ).values_list("uuid", flat=True)
            )

            orphan_generic = generic_refs - paack_uuids
            orphan_paack = paack_uuids - generic_refs

            if len(orphan_generic) > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f"  ⚠️ {len(orphan_generic)} pedidos Generic sem correspondente no Paack"
                    )
                )
                if detailed and orphan_generic:
                    self.stdout.write("     Exemplos:")
                    for ref in list(orphan_generic)[:5]:
                        self.stdout.write(f"       - {ref}")
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        "  ✅ Todos pedidos Generic têm correspondente no Paack"
                    )
                )

            if len(orphan_paack) > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f"  ⚠️ {len(orphan_paack)} pedidos Paack sem correspondente no Generic"
                    )
                )
                if detailed and orphan_paack:
                    self.stdout.write("     Exemplos:")
                    for ref in list(orphan_paack)[:5]:
                        self.stdout.write(f"       - {ref}")
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        "  ✅ Todos pedidos Paack têm correspondente no Generic"
                    )
                )

        # Análise de status
        if paack_partner and generic_count > 0:
            self.stdout.write(
                "\n" + self.style.HTTP_INFO("📈 Distribuição de Status:\n")
            )

            paack_statuses = (
                PaackOrder.objects.filter(created_at__gte=cutoff_date)
                .values("status")
                .annotate(count=Count("id"))
                .order_by("-count")
            )

            generic_statuses = (
                GenericOrder.objects.filter(
                    partner=paack_partner, created_at__gte=cutoff_date
                )
                .values("current_status")
                .annotate(count=Count("id"))
                .order_by("-count")
            )

            self.stdout.write("  Paack (sistema antigo):")
            for stat in paack_statuses[:5]:
                self.stdout.write(f'    - {stat["status"]}: {stat["count"]:,}')

            self.stdout.write("\n  Generic (sistema novo):")
            for stat in generic_statuses[:5]:
                self.stdout.write(f'    - {stat["current_status"]}: {stat["count"]:,}')

        # Análise temporal
        if paack_partner and generic_count > 0:
            self.stdout.write("\n" + self.style.HTTP_INFO("⏱️ Análise Temporal:\n"))

            # Últimas 24 horas
            last_24h = datetime.now() - timedelta(hours=24)

            paack_24h = PaackOrder.objects.filter(created_at__gte=last_24h).count()

            generic_24h = GenericOrder.objects.filter(
                partner=paack_partner, created_at__gte=last_24h
            ).count()

            self.stdout.write(f"  Últimas 24 horas:")
            self.stdout.write(f"    - Paack: {paack_24h:,}")
            self.stdout.write(f"    - Generic: {generic_24h:,}")

            if paack_24h == generic_24h:
                self.stdout.write(self.style.SUCCESS(f"    ✅ Match perfeito!"))
            else:
                diff_24h = abs(paack_24h - generic_24h)
                self.stdout.write(self.style.WARNING(f"    ⚠️ Diferença: {diff_24h}"))

        # Recomendações
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS(" RECOMENDAÇÕES"))
        self.stdout.write("=" * 70)

        if (
            paack_count == generic_count
            and len(orphan_generic) == 0
            and len(orphan_paack) == 0
        ):
            self.stdout.write(
                self.style.SUCCESS(
                    "\n✅ EXCELENTE! Sistemas perfeitamente sincronizados.\n"
                    "   Continue monitorando por mais 1-2 semanas antes de\n"
                    "   ativar USE_GENERIC_ORDERS_READ = True.\n"
                )
            )
        elif diff < 10:
            self.stdout.write(
                self.style.WARNING(
                    "\n⚠️ BOA! Pequenas diferenças detectadas.\n"
                    "   Investigue as inconsistências antes de prosseguir.\n"
                    "   Execute: python manage.py validate_migration --detailed\n"
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR(
                    "\n❌ ATENÇÃO! Diferenças significativas detectadas.\n"
                    "   Revise a implementação do dual write.\n"
                    '   Verifique logs: docker compose logs web | grep "DUAL WRITE"\n'
                )
            )

        self.stdout.write("=" * 70)
