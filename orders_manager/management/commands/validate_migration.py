"""
Management command para validar a integridade da migração de dados.

Uso:
    python manage.py validate_migration
    python manage.py validate_migration --detailed  # Relatório detalhado
"""

import sys

from django.core.management.base import BaseCommand
from django.db.models import Count


class Command(BaseCommand):
    help = "Valida integridade da migração de dados Paack → Generic"

    def add_arguments(self, parser):
        parser.add_argument(
            "--detailed",
            action="store_true",
            help="Mostra relatório detalhado com exemplos",
        )

    def handle(self, *args, **options):
        self.detailed = options["detailed"]

        self.stdout.write(self.style.SUCCESS("=" * 70))
        self.stdout.write(self.style.SUCCESS(" VALIDAÇÃO DE MIGRAÇÃO DE DADOS"))
        self.stdout.write(self.style.SUCCESS("=" * 70 + "\n"))

        # Verificar imports
        try:
            from core.models import Partner
            from orders_manager.models import Order
            from ordersmanager_paack.models import Order as PaackOrder
        except ImportError as e:
            self.stdout.write(self.style.ERROR(f"❌ Erro ao importar models: {str(e)}"))
            sys.exit(1)

        # Validar estrutura
        issues = []

        # 1. Verificar se Partner Paack existe
        self.stdout.write(self.style.HTTP_INFO("📋 Verificando estrutura base...\n"))

        try:
            paack = Partner.objects.get(name="Paack")
            self.stdout.write(
                self.style.SUCCESS(f'  ✓ Partner "Paack" encontrado (ID: {paack.id})')
            )
        except Partner.DoesNotExist:
            self.stdout.write(self.style.ERROR('  ❌ Partner "Paack" não encontrado!'))
            issues.append("Partner Paack não existe")
            paack = None

        # 2. Contar registros
        self.stdout.write("\n" + self.style.HTTP_INFO("📊 Contando registros...\n"))

        paack_count = PaackOrder.objects.count()
        generic_count = Order.objects.filter(partner=paack).count() if paack else 0

        self.stdout.write(f"  • Pedidos Paack (antigo): {paack_count:,}")
        self.stdout.write(f"  • Pedidos Generic (novo): {generic_count:,}")

        if paack_count > 0:
            percentage = (generic_count / paack_count) * 100
            self.stdout.write(f"  • Progresso: {percentage:.1f}%")

            if generic_count < paack_count:
                diff = paack_count - generic_count
                self.stdout.write(
                    self.style.WARNING(
                        f"  ⚠️ Faltam {diff:,} pedidos para migrar ({100-percentage:.1f}%)"
                    )
                )
                issues.append(f"{diff} pedidos não migrados")

        # 3. Verificar duplicatas
        if paack and generic_count > 0:
            self.stdout.write(
                "\n" + self.style.HTTP_INFO("🔍 Verificando duplicatas...\n")
            )

            duplicates = (
                Order.objects.filter(partner=paack)
                .values("external_reference")
                .annotate(count=Count("id"))
                .filter(count__gt=1)
            )

            dup_count = duplicates.count()

            if dup_count > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f"  ⚠️ Encontradas {dup_count} referências duplicadas!"
                    )
                )
                issues.append(f"{dup_count} external_reference duplicados")

                if self.detailed:
                    self.stdout.write("\n  Exemplos de duplicatas:")
                    for dup in duplicates[:5]:
                        self.stdout.write(
                            f'    - {dup["external_reference"]}: {dup["count"]} ocorrências'
                        )
            else:
                self.stdout.write(
                    self.style.SUCCESS("  ✓ Nenhuma duplicata encontrada")
                )

        # 4. Validar mapeamento de status
        if paack and generic_count > 0:
            self.stdout.write(
                "\n" + self.style.HTTP_INFO("📈 Validando distribuição de status...\n")
            )

            paack_statuses = (
                PaackOrder.objects.values("status")
                .annotate(count=Count("id"))
                .order_by("-count")
            )

            generic_statuses = (
                Order.objects.filter(partner=paack)
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

        # 5. Validar códigos postais
        if paack and generic_count > 0:
            self.stdout.write(
                "\n" + self.style.HTTP_INFO("📮 Validando códigos postais...\n")
            )

            invalid_postal = Order.objects.filter(
                partner=paack, postal_code__in=["0000-000", "", None]
            ).count()

            if invalid_postal > 0:
                percentage = (invalid_postal / generic_count) * 100
                self.stdout.write(
                    self.style.WARNING(
                        f"  ⚠️ {invalid_postal:,} pedidos sem código postal válido ({percentage:.1f}%)"
                    )
                )
                issues.append(f"{invalid_postal} pedidos sem código postal")
            else:
                self.stdout.write(
                    self.style.SUCCESS("  ✓ Todos os pedidos têm código postal")
                )

        # 6. Validar datas
        if paack and generic_count > 0:
            self.stdout.write("\n" + self.style.HTTP_INFO("📅 Validando datas...\n"))

            null_dates = Order.objects.filter(
                partner=paack, scheduled_delivery__isnull=True
            ).count()

            if null_dates > 0:
                percentage = (null_dates / generic_count) * 100
                self.stdout.write(
                    self.style.WARNING(
                        f"  ⚠️ {null_dates:,} pedidos sem data de entrega ({percentage:.1f}%)"
                    )
                )
                issues.append(f"{null_dates} pedidos sem data de entrega")
            else:
                self.stdout.write(
                    self.style.SUCCESS("  ✓ Todos os pedidos têm data de entrega")
                )

        # 7. Validar integridade referencial
        if paack and generic_count > 0 and self.detailed:
            self.stdout.write(
                "\n" + self.style.HTTP_INFO("🔗 Amostragem de dados migrados...\n")
            )

            # Pegar 5 pedidos aleatórios e comparar
            sample_generic = Order.objects.filter(partner=paack).order_by("?")[:5]

            for order in sample_generic:
                try:
                    paack_order = PaackOrder.objects.get(uuid=order.external_reference)

                    self.stdout.write(f"\n  Pedido: {order.external_reference}")
                    self.stdout.write(f"    - Status antigo: {paack_order.status}")
                    self.stdout.write(f"    - Status novo: {order.current_status}")
                    self.stdout.write(f"    - Data entrega: {order.scheduled_delivery}")
                    self.stdout.write(f"    - Código postal: {order.postal_code}")

                except PaackOrder.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  ⚠️ Pedido {order.external_reference} não encontrado no sistema antigo!"
                        )
                    )

        # RESUMO FINAL
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS(" RESUMO DA VALIDAÇÃO"))
        self.stdout.write("=" * 70)

        if len(issues) == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    "\n✅ VALIDAÇÃO PASSOU! Nenhum problema encontrado.\n"
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"\n⚠️ VALIDAÇÃO ENCONTROU {len(issues)} PROBLEMA(S):\n"
                )
            )
            for i, issue in enumerate(issues, 1):
                self.stdout.write(f"  {i}. {issue}")

            self.stdout.write(
                "\n💡 Execute a migração novamente ou corrija os problemas acima.\n"
            )

        self.stdout.write("=" * 70)
