"""
Serviço de Automações para o sistema.
Inclui atribuição automática, alertas e otimizações.
"""

from datetime import date, timedelta

from django.utils import timezone


class AutomationService:
    """Serviço central para automações do sistema"""

    @staticmethod
    def auto_assign_orders_for_date(target_date=None):
        """
        Atribui automaticamente pedidos pendentes aos motoristas disponíveis.

        Args:
            target_date: Data para atribuição (padrão: hoje)

        Returns:
            dict: Estatísticas da atribuição
        """
        from route_allocation.models import RouteOptimizer

        if target_date is None:
            target_date = date.today()

        result = RouteOptimizer.auto_assign_shifts_for_date(target_date)

        # Adicionar timestamp
        result["execution_time"] = timezone.now()
        result["target_date"] = target_date

        return result

    @staticmethod
    def auto_assign_pending_orders(max_orders=50):
        """
        Atribui pedidos pendentes sem data agendada aos motoristas.
        Prioriza pedidos mais antigos.

        Args:
            max_orders: Número máximo de pedidos a atribuir

        Returns:
            dict: Estatísticas da atribuição
        """
        from orders_manager.models import Order
        from pricing.models import PostalZone
        from route_allocation.models import DriverShift

        # Buscar pedidos pendentes (mais antigos primeiro)
        pending_orders = Order.objects.filter(
            current_status="PENDING", assigned_driver__isnull=True
        ).order_by("created_at")[:max_orders]

        # Buscar turnos ativos hoje
        today = date.today()
        active_shifts = DriverShift.objects.filter(
            date=today, status__in=["SCHEDULED", "IN_PROGRESS"]
        ).prefetch_related("assigned_postal_zones", "driver")

        assigned_count = 0
        failed_count = 0

        for order in pending_orders:
            # Tentar encontrar turno adequado baseado no CP
            zone = PostalZone.find_zone_for_postal_code(order.postal_code)

            if not zone:
                failed_count += 1
                continue

            # Encontrar turno que cobre essa zona
            suitable_shift = None
            for shift in active_shifts:
                if zone in shift.assigned_postal_zones.all():
                    suitable_shift = shift
                    break

            if suitable_shift:
                order.assign_to_driver(suitable_shift.driver)
                # Atualizar data agendada se não houver
                if not order.scheduled_delivery:
                    order.scheduled_delivery = today
                    order.save()
                assigned_count += 1
            else:
                failed_count += 1

        return {
            "success": True,
            "assigned": assigned_count,
            "failed": failed_count,
            "total_processed": len(pending_orders),
            "execution_time": timezone.now(),
        }

    @staticmethod
    def get_overdue_orders():
        """
        Retorna pedidos atrasados (data agendada expirou).

        Returns:
            QuerySet: Pedidos atrasados
        """
        from orders_manager.models import Order

        today = date.today()

        return (
            Order.objects.filter(
                scheduled_delivery__lt=today,
                current_status__in=["PENDING", "ASSIGNED", "IN_TRANSIT"],
            )
            .select_related("partner", "assigned_driver")
            .order_by("scheduled_delivery")
        )

    @staticmethod
    def get_pending_maintenances():
        """
        Retorna manutenções vencidas ou próximas do vencimento.

        Returns:
            QuerySet: Manutenções pendentes
        """
        from fleet_management.models import VehicleMaintenance

        today = date.today()
        warning_date = today + timedelta(days=7)  # Alertar 7 dias antes

        return (
            VehicleMaintenance.objects.filter(
                is_completed=False,  # Não concluídas
                scheduled_date__lte=warning_date,  # Agendadas para os próximos 7 dias
            )
            .select_related("vehicle")
            .order_by("scheduled_date")
        )

    @staticmethod
    def get_unassigned_shifts():
        """
        Retorna turnos sem pedidos atribuídos.

        Returns:
            QuerySet: Turnos sem atribuições
        """
        from route_allocation.models import DriverShift

        today = date.today()
        future_date = today + timedelta(days=7)

        return (
            DriverShift.objects.filter(
                date__gte=today,
                date__lte=future_date,
                status="SCHEDULED",
                total_deliveries=0,
            )
            .select_related("driver")
            .order_by("date")
        )

    @staticmethod
    def get_alerts_summary():
        """
        Retorna resumo de todos os alertas ativos.

        Returns:
            dict: Contadores de alertas
        """
        overdue_orders = AutomationService.get_overdue_orders()
        pending_maintenances = AutomationService.get_pending_maintenances()
        unassigned_shifts = AutomationService.get_unassigned_shifts()

        # Pedidos sem motorista há mais de 24h
        from orders_manager.models import Order

        old_pending = Order.objects.filter(
            current_status="PENDING",
            assigned_driver__isnull=True,
            created_at__lt=timezone.now() - timedelta(hours=24),
        ).count()

        return {
            "overdue_orders": overdue_orders.count(),
            "pending_maintenances": pending_maintenances.count(),
            "unassigned_shifts": unassigned_shifts.count(),
            "old_pending_orders": old_pending,
            "total_alerts": (
                overdue_orders.count()
                + pending_maintenances.count()
                + unassigned_shifts.count()
                + old_pending
            ),
            "timestamp": timezone.now(),
        }

    @staticmethod
    def optimize_route_for_driver(driver, target_date=None):
        """
        Otimiza sequência de entregas para um motorista.
        Agrupa pedidos por proximidade de zona postal.

        Args:
            driver: DriverProfile
            target_date: Data das entregas (padrão: hoje)

        Returns:
            list: Pedidos ordenados otimizadamente
        """
        from orders_manager.models import Order
        from pricing.models import PostalZone

        if target_date is None:
            target_date = date.today()

        # Buscar pedidos do motorista para o dia
        orders = Order.objects.filter(
            assigned_driver=driver,
            scheduled_delivery=target_date,
            current_status__in=["ASSIGNED", "IN_TRANSIT"],
        ).select_related("partner")

        # Agrupar por zona postal
        orders_by_zone = {}
        orders_without_zone = []

        for order in orders:
            zone = PostalZone.find_zone_for_postal_code(order.postal_code)
            if zone:
                zone_code = zone.code
                if zone_code not in orders_by_zone:
                    orders_by_zone[zone_code] = {"zone": zone, "orders": []}
                orders_by_zone[zone_code]["orders"].append(order)
            else:
                orders_without_zone.append(order)

        # Ordenar zonas por região e tipo (urbanas primeiro)
        sorted_zones = sorted(
            orders_by_zone.values(),
            key=lambda x: (
                x["zone"].region,
                not x["zone"].is_urban,
                x["zone"].code,
            ),
        )

        # Montar lista final
        optimized_orders = []
        for zone_group in sorted_zones:
            # Dentro de cada zona, ordenar por prioridade (mais antigos primeiro)
            zone_orders = sorted(zone_group["orders"], key=lambda o: o.created_at)
            optimized_orders.extend(zone_orders)

        # Adicionar pedidos sem zona no final
        optimized_orders.extend(orders_without_zone)

        return {
            "optimized_orders": optimized_orders,
            "total_orders": len(optimized_orders),
            "total_zones": len(orders_by_zone),
            "orders_without_zone": len(orders_without_zone),
            "zones_summary": [
                {
                    "zone_code": zone_data["zone"].code,
                    "zone_name": zone_data["zone"].name,
                    "orders_count": len(zone_data["orders"]),
                }
                for zone_data in sorted_zones
            ],
        }

    @staticmethod
    def suggest_shift_assignments_for_week(start_date=None):
        """
        Sugere atribuições de turnos para a próxima semana baseado em histórico.

        Args:
            start_date: Data de início (padrão: próxima segunda)

        Returns:
            dict: Sugestões de turnos
        """
        from drivers_app.models import DriverProfile
        from route_allocation.models import DriverShift

        if start_date is None:
            today = date.today()
            days_until_monday = (7 - today.weekday()) % 7
            start_date = today + timedelta(
                days=days_until_monday if days_until_monday > 0 else 7
            )

        end_date = start_date + timedelta(days=6)

        # Buscar motoristas ativos
        active_drivers = DriverProfile.objects.filter(status="ATIVO")

        suggestions = []

        # Para cada dia da semana
        for day_offset in range(7):
            target_date = start_date + timedelta(days=day_offset)

            # Buscar turnos similares (mesmo dia da semana, últimas 4 semanas)
            similar_shifts = (
                DriverShift.objects.filter(
                    date__week_day=target_date.isoweekday(),
                    date__gte=target_date - timedelta(days=28),
                    date__lt=target_date,
                    status="COMPLETED",
                )
                .select_related("driver")
                .prefetch_related("assigned_postal_zones")
            )

            # Agrupar por motorista
            driver_stats = {}
            for shift in similar_shifts:
                driver_id = shift.driver.id
                if driver_id not in driver_stats:
                    driver_stats[driver_id] = {
                        "driver": shift.driver,
                        "times_worked": 0,
                        "avg_deliveries": 0,
                        "zones": set(),
                    }
                driver_stats[driver_id]["times_worked"] += 1
                driver_stats[driver_id]["avg_deliveries"] += shift.total_deliveries
                for zone in shift.assigned_postal_zones.all():
                    driver_stats[driver_id]["zones"].add(zone.code)

            # Calcular médias
            for stats in driver_stats.values():
                if stats["times_worked"] > 0:
                    stats["avg_deliveries"] = (
                        stats["avg_deliveries"] / stats["times_worked"]
                    )

            # Recomendar motoristas que trabalharam mais vezes neste dia
            recommended = sorted(
                driver_stats.values(),
                key=lambda x: (x["times_worked"], x["avg_deliveries"]),
                reverse=True,
            )[
                :5
            ]  # Top 5

            suggestions.append(
                {
                    "date": target_date,
                    "day_name": target_date.strftime("%A"),
                    "recommended_drivers": [
                        {
                            "driver_id": d["driver"].id,
                            "driver_name": d["driver"].nome_completo,
                            "times_worked": d["times_worked"],
                            "avg_deliveries": round(d["avg_deliveries"], 1),
                            "common_zones": list(d["zones"]),
                        }
                        for d in recommended
                    ],
                }
            )

        return {
            "success": True,
            "start_date": start_date,
            "end_date": end_date,
            "suggestions": suggestions,
        }
