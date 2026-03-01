"""
Management command para migrar pedidos da Paack do sistema antigo (ordersmanager_paack)
para o novo sistema genérico (orders_manager).

Uso:
    python manage.py migrate_paack_orders --dry-run  # Teste sem salvar
    python manage.py migrate_paack_orders  # Migração real
"""

import sys

from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Migra pedidos do ordersmanager_paack para orders_manager (genérico)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Executa sem salvar no banco (teste)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Número de pedidos por lote (default: 500)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Limitar migração a N pedidos (para testes)",
        )

    def handle(self, *args, **options):
        self.dry_run = options["dry_run"]
        self.batch_size = options["batch_size"]
        self.limit = options["limit"]

        self.stdout.write(self.style.SUCCESS("=" * 70))
        self.stdout.write(self.style.SUCCESS(" MIGRAÇÃO DE PEDIDOS PAACK"))
        self.stdout.write(self.style.SUCCESS("=" * 70 + "\n"))

        if self.dry_run:
            self.stdout.write(
                self.style.WARNING("⚠ MODO DRY-RUN (nenhum dado será salvo)\n")
            )

        # Verificar se imports estão disponíveis
        try:
            from core.models import Partner
            from orders_manager.models import Order
            from ordersmanager_paack.models import Order as PaackOrder
        except ImportError as e:
            self.stdout.write(self.style.ERROR(f"❌ Erro ao importar models: {str(e)}"))
            sys.exit(1)

        # Verificar se Partner Paack existe
        try:
            paack = Partner.objects.get(name="Paack")
            self.stdout.write(
                self.style.SUCCESS(f'✓ Partner "Paack" encontrado (ID: {paack.id})\n')
            )
        except Partner.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(
                    '❌ Partner "Paack" não encontrado!\n'
                    "   Execute primeiro: python manage.py create_initial_partners"
                )
            )
            sys.exit(1)

        # Contar pedidos
        total_paack_orders = PaackOrder.objects.count()
        already_migrated = Order.objects.filter(partner=paack).count()

        self.stdout.write(f"📊 Estatísticas:")
        self.stdout.write(f"   • Pedidos Paack (antigo): {total_paack_orders}")
        self.stdout.write(f"   • Pedidos já migrados: {already_migrated}")

        if self.limit:
            self.stdout.write(
                self.style.WARNING(
                    f"   • LIMITE: Apenas {self.limit} pedidos serão processados\n"
                )
            )
        else:
            self.stdout.write("")

        # Confirmar
        if not self.dry_run:
            confirm = input("Deseja continuar com a migração? (sim/não): ")
            if confirm.lower() not in ["sim", "s", "yes", "y"]:
                self.stdout.write(
                    self.style.WARNING("\nMigração cancelada pelo usuário.")
                )
                return

        # Executar migração
        self.stdout.write("\n🚀 Iniciando migração...\n")

        migrated = 0
        skipped = 0
        errors = []

        # Buscar pedidos (ordenar por data para manter histórico)
        queryset = PaackOrder.objects.all().order_by("created_at")

        if self.limit:
            queryset = queryset[: self.limit]

        total_to_process = queryset.count()

        # Processar em lotes
        for offset in range(0, total_to_process, self.batch_size):
            batch = list(queryset[offset : offset + self.batch_size])

            self.stdout.write(
                f"📦 Processando lote {offset // self.batch_size + 1} "
                f"({offset + 1}-{min(offset + self.batch_size, total_to_process)}/{total_to_process})..."
            )

            try:
                with transaction.atomic():
                    for paack_order in batch:
                        try:
                            # Verificar se já foi migrado
                            if Order.objects.filter(
                                partner=paack,
                                external_reference=paack_order.tracking_code,
                            ).exists():
                                skipped += 1
                                continue

                            # Mapear dados
                            order_data = self._map_paack_order(paack_order, paack)

                            if not self.dry_run:
                                # Criar pedido
                                Order.objects.create(**order_data)

                                # TODO: Migrar histórico de status se existir
                                # status_history = PaackOrderStatus.objects.filter(order=paack_order)
                                # for old_status in status_history:
                                #     OrderStatusHistory.objects.create(...)

                            migrated += 1

                        except Exception as e:
                            error_msg = (
                                f"Erro no pedido {paack_order.tracking_code}: {str(e)}"
                            )
                            errors.append(error_msg)

                    # Se dry-run, fazer rollback
                    if self.dry_run:
                        transaction.set_rollback(True)

                self.stdout.write(self.style.SUCCESS(f"   ✓ Lote concluído"))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"   ❌ Erro no lote: {str(e)}"))
                errors.append(
                    f"Erro no lote {offset}-{offset + self.batch_size}: {str(e)}"
                )

        # Resumo
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS(" RESUMO DA MIGRAÇÃO"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"✅ Pedidos migrados: {migrated}")
        self.stdout.write(f"⏭️  Pedidos pulados (já existiam): {skipped}")
        self.stdout.write(f"❌ Erros: {len(errors)}")

        if errors:
            self.stdout.write("\n⚠️ ERROS ENCONTRADOS:")
            for error in errors[:10]:  # Mostrar apenas os 10 primeiros
                self.stdout.write(f"   • {error}")
            if len(errors) > 10:
                self.stdout.write(f"   ... e mais {len(errors) - 10} erros")

        self.stdout.write("=" * 70)

        if self.dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "\n⚠ DRY-RUN: Nenhum dado foi salvo! Execute sem --dry-run para migrar de verdade.\n"
                )
            )

    def _map_paack_order(self, paack_order, partner):
        """Mapeia PaackOrder para Order (genérico)"""

        # Extrair código postal do endereço se disponível
        postal_code = "0000-000"
        if hasattr(paack_order, "client_address") and paack_order.client_address:
            # Tentar extrair código postal do endereço
            import re

            match = re.search(r"\d{4}-\d{3}", str(paack_order.client_address))
            if match:
                postal_code = match.group()

        return {
            "partner": partner,
            "external_reference": str(paack_order.uuid),
            "recipient_name": paack_order.retailer or "",
            "recipient_address": paack_order.client_address_text
            or paack_order.client_address
            or "",
            "postal_code": postal_code,
            "recipient_phone": paack_order.client_phone or "",
            "recipient_email": paack_order.client_email or "",
            "declared_value": Decimal("0.00"),
            "weight_kg": None,
            "scheduled_delivery": paack_order.intended_delivery_date,
            "assigned_driver_id": None,
            "current_status": self._map_status(paack_order.status or "pending"),
            "notes": f"Order ID: {paack_order.order_id}, Type: {paack_order.order_type}",
            "created_at": paack_order.created_at,
            "updated_at": paack_order.updated_at,
        }

    def _map_status(self, paack_status):
        """Mapeia status da Paack para status genérico"""

        if not paack_status:
            return "PENDING"

        mapping = {
            "pending": "PENDING",
            "assigned": "ASSIGNED",
            "in_transit": "IN_TRANSIT",
            "out_for_delivery": "IN_TRANSIT",
            "delivered": "DELIVERED",
            "returned": "RETURNED",
            "incident": "INCIDENT",
            "failed": "INCIDENT",
            "undelivered": "INCIDENT",
            "cancelled": "CANCELLED",
        }

        return mapping.get(paack_status.lower(), "PENDING")
