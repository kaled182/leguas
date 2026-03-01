import logging
import time
from datetime import timedelta

from django.contrib import messages
from django.core.cache import cache
from django.db.models import Count, Q
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import Dispatch, Driver, Order
from .sync_service import SyncService

logger = logging.getLogger(__name__)

# ========== ENDPOINTS DE SINCRONIZAÇÃO ========== #


@csrf_exempt
@require_POST
def sync_data_manual(request):
    """
    Endpoint para sincronização manual dos dados.
    IMPLEMENTAÇÃO REAL - não mais simulação.
    """
    try:
        logger.info("=" * 60)
        logger.info("🚀 INICIANDO SINCRONIZAÇÃO MANUAL")
        logger.info("=" * 60)

        # Usar o serviço real de sincronização
        sync_service = SyncService()
        logger.info("📡 Conectando com a API para buscar dados...")

        result = sync_service.sync_data(force_refresh=True)

        # Adicionar timestamp
        result["timestamp"] = timezone.now().strftime("%Y-%m-%d %H:%M:%S")

        # Salvar timestamp da última sincronização
        cache.set("last_sync_time", result["timestamp"], 86400)  # 24 horas

        if result.get("success", False):
            stats = result.get("stats", {})
            logger.info("✅ SINCRONIZAÇÃO CONCLUÍDA COM SUCESSO!")
            logger.info(f"📊 Estatísticas finais:")
            logger.info(f"   • Total processado: {stats.get('total_processed', 0)}")
            logger.info(f"   • Ordens criadas: {stats.get('orders_created', 0)}")
            logger.info(f"   • Ordens atualizadas: {stats.get('orders_updated', 0)}")
            logger.info(f"   • Motoristas criados: {stats.get('drivers_created', 0)}")
            logger.info(
                f"   • Dispatches criados: {stats.get('dispatches_created', 0)}"
            )
            logger.info(f"   • Erros encontrados: {len(stats.get('errors', []))}")

            if stats.get("errors"):
                logger.warning("⚠️ Erros durante o processamento:")
                for error in stats.get("errors", [])[
                    :5
                ]:  # Mostra apenas os primeiros 5 erros
                    logger.warning(f"   • {error}")

            messages.success(
                request,
                f'Sincronização concluída! {stats.get("total_processed", 0)} registros processados.',
            )
        else:
            error_msg = result.get("error", "Erro desconhecido")
            logger.error(f"❌ FALHA NA SINCRONIZAÇÃO: {error_msg}")
            messages.error(request, f"Falha na sincronização: {error_msg}")

        logger.info("=" * 60)

        return redirect("paack_dashboard:dashboard_paack")

    except Exception as e:
        logger.error("💥 ERRO CRÍTICO NA SINCRONIZAÇÃO!")
        logger.error(f"❌ Erro: {str(e)}")
        logger.error("=" * 60)
        return JsonResponse(
            {
                "success": False,
                "error": f"Erro interno do servidor: {str(e)}",
                "timestamp": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            status=500,
        )


@require_GET
def test_sync_page(request):
    """
    Página simples para testar o sync manualmente
    """
    from django.http import HttpResponse

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Teste de Sincronização</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .button { padding: 15px 30px; font-size: 16px; margin: 10px;
                     background: #007cba; color: white; border: none;
                     border-radius: 5px; cursor: pointer; }
            .button:hover { background: #005a87; }
            .info { background: #e7f3ff; padding: 15px; border-radius: 5px; margin: 20px 0; }
        </style>
    </head>
    <body>
        <h1>🔄 Teste de Sincronização</h1>

        <div class="info">
            <strong>📋 Instruções:</strong><br>
            1. Clique no botão "Executar Sync" abaixo<br>
            2. Acompanhe os logs detalhados no terminal do servidor<br>
            3. Verifique se os dados foram gravados na base MySQL<br>
        </div>

        <form method="post" action="/paackos/sync/" style="display: inline;">
            <button type="submit" class="button">🚀 Executar Sync</button>
        </form>

        <button onclick="window.location.reload()" class="button" style="background: #28a745;">
            🔄 Atualizar Página
        </button>

        <button onclick="window.location.href='/paack_dashboard/'" class="button" style="background: #6c757d;">
            📊 Ir para Dashboard
        </button>

        <div class="info">
            <strong>🔍 Verificar Resultados:</strong><br>
            • Abra o terminal onde o servidor está rodando<br>
            • Procure por logs detalhados com emojis (🚀, ✅, ❌, etc.)<br>
            • Verifique contadores de registros criados/atualizados<br>
        </div>

    </body>
    </html>
    """
    return HttpResponse(html)


@require_GET
def real_time_sync_status(request):
    """
    View que retorna status de sincronização em tempo real via streaming.
    """

    def event_stream():
        try:
            # Início da sincronização
            yield f"[{now().strftime('%H:%M:%S')}] 🚀 Iniciando sincronização...\n"
            time.sleep(0.5)

            yield f"[{now().strftime('%H:%M:%S')}] � Preparando serviço de sincronização...\n"
            time.sleep(0.5)

            yield f"[{now().strftime('%H:%M:%S')}] �📡 Conectando com a API Paack...\n"
            time.sleep(1)

            # Executar o serviço real de sincronização
            sync_service = SyncService()
            yield f"[{now().strftime('%H:%M:%S')}] 🔄 Processando dados da API...\n"

            result = sync_service.sync_data(force_refresh=True)

            # Verificar resultado e mostrar estatísticas detalhadas
            if result.get("success"):
                stats = result.get("stats", {})
                yield f"[{now().strftime('%H:%M:%S')}] ✅ Sincronização concluída com sucesso!\n"
                yield f"\n📊 Estatísticas da sincronização:\n"
                yield f"   • Total processado: {stats.get('total_processed', 0)}\n"
                yield f"   • Ordens criadas: {stats.get('orders_created', 0)}\n"
                yield f"   • Ordens atualizadas: {stats.get('orders_updated', 0)}\n"
                yield f"   • Motoristas criados: {stats.get('drivers_created', 0)}\n"
                yield f"   • Dispatches criados: {stats.get('dispatches_created', 0)}\n"

                # Mostrar erros se houver
                errors = stats.get("errors", [])
                if errors:
                    yield f"   • Erros encontrados: {len(errors)}\n"
                    yield f"\n⚠️ Detalhes dos erros:\n"
                    for i, error in enumerate(
                        errors[:3], 1
                    ):  # Mostra apenas os primeiros 3 erros
                        yield f"   {i}. {error}\n"
                    if len(errors) > 3:
                        yield f"   ... e mais {len(errors) - 3} erro(s)\n"
                else:
                    yield f"   • Erros encontrados: 0\n"

                yield f"\n🎯 Sincronização finalizada em {now().strftime('%H:%M:%S')}\n"

                # Salvar timestamp da última sincronização
                cache.set(
                    "last_sync_time",
                    now().strftime("%Y-%m-%d %H:%M:%S"),
                    86400,
                )
                yield f"✅ Cache atualizado com timestamp da sincronização\n"

            else:
                error_msg = result.get("error", "Erro desconhecido")
                yield f"[{now().strftime('%H:%M:%S')}] ❌ Falha na sincronização!\n"
                yield f"🔴 Erro: {error_msg}\n"
                yield f"💡 Verifique os logs do servidor para mais detalhes\n"

        except Exception as e:
            logger.error(f"Erro crítico em real_time_sync_status: {e}")
            yield f"[{now().strftime('%H:%M:%S')}] 💥 Erro crítico durante a sincronização!\n"
            yield f"🔴 Erro: {str(e)}\n"
            yield f"💡 Verifique a configuração da API e conexão com o banco de dados\n"

    return StreamingHttpResponse(event_stream(), content_type="text/plain")


@require_GET
def database_stats(request):
    """
    Mostra estatísticas da base de dados para verificar se os dados foram gravados
    """
    from django.http import HttpResponse
    from django.utils import timezone

    from .models import Dispatch, Driver, Order

    try:
        # Estatísticas gerais
        total_orders = Order.objects.count()
        total_drivers = Driver.objects.count()
        total_dispatches = Dispatch.objects.count()

        # Estatísticas de hoje
        today = timezone.now().date()
        orders_today = Order.objects.filter(created_at__date=today).count()
        orders_updated_today = Order.objects.filter(updated_at__date=today).count()

        # Últimas 10 ordens
        latest_orders = Order.objects.order_by("-updated_at")[:10]

        # Últimos 5 motoristas
        latest_drivers = Driver.objects.order_by("-created_at")[:5]

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Estatísticas da Base de Dados</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .stats {{ background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0; }}
                .success {{ background: #d4edda; border: 1px solid #c3e6cb; }}
                .info {{ background: #d1ecf1; border: 1px solid #bee5eb; }}
                table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .button {{ padding: 10px 20px; background: #007cba; color: white;
                          text-decoration: none; border-radius: 5px; margin: 5px; }}
            </style>
        </head>
        <body>
            <h1>📊 Estatísticas da Base de Dados MySQL</h1>

            <div class="stats success">
                <h3>📈 Totais Gerais</h3>
                <p><strong>📦 Total de Ordens:</strong> {total_orders}</p>
                <p><strong>🚛 Total de Motoristas:</strong> {total_drivers}</p>
                <p><strong>🚚 Total de Dispatches:</strong> {total_dispatches}</p>
            </div>

            <div class="stats info">
                <h3>📅 Atividade de Hoje ({today})</h3>
                <p><strong>🆕 Ordens criadas hoje:</strong> {orders_today}</p>
                <p><strong>🔄 Ordens atualizadas hoje:</strong> {orders_updated_today}</p>
            </div>

            <h3>📋 Últimas 10 Ordens</h3>
            <table>
                <tr>
                    <th>Order ID</th>
                    <th>Status</th>
                    <th>Retailer</th>
                    <th>Data Atualização</th>
                </tr>
        """

        for order in latest_orders:
            html += f"""
                <tr>
                    <td>{order.order_id}</td>
                    <td>{order.status}</td>
                    <td>{order.retailer}</td>
                    <td>{order.updated_at.strftime('%Y-%m-%d %H:%M:%S')}</td>
                </tr>
            """

        html += """
            </table>

            <h3>🚛 Últimos 5 Motoristas</h3>
            <table>
                <tr>
                    <th>Driver ID</th>
                    <th>Nome</th>
                    <th>Veículo</th>
                    <th>Criado em</th>
                </tr>
        """

        for driver in latest_drivers:
            html += f"""
                <tr>
                    <td>{driver.driver_id}</td>
                    <td>{driver.name}</td>
                    <td>{driver.vehicle}</td>
                    <td>{driver.created_at.strftime('%Y-%m-%d %H:%M:%S')}</td>
                </tr>
            """

        html += f"""
            </table>

            <div style="margin-top: 30px;">
                <a href="/paackos/sync/test/" class="button">🔄 Fazer Novo Sync</a>
                <a href="/paack_dashboard/" class="button" style="background: #28a745;">📊 Ver Dashboard</a>
                <a href="javascript:window.location.reload()" class="button" style="background: #6c757d;">🔄 Atualizar</a>
            </div>

            <div class="stats" style="margin-top: 20px; background: #fff3cd; border: 1px solid #ffeaa7;">
                <h4>💡 Dica:</h4>
                <p>Se você ver dados aqui, significa que a sincronização está funcionando corretamente!
                O fato de mostrar "0 ordens criadas" e "535 ordens atualizadas" indica que os registros
                já existiam na base e foram atualizados com sucesso.</p>
            </div>

        </body>
        </html>
        """

        return HttpResponse(html)

    except Exception as e:
        logger.error(f"Erro ao gerar estatísticas: {e}")
        return HttpResponse(f"<h1>Erro</h1><p>{str(e)}</p>")


@require_GET
def sync_status(request):
    """
    Endpoint para verificar status da última sincronização.
    """
    try:
        last_sync = cache.get("last_sync_time")
        cache_exists = cache.get("paack_api_data") is not None

        return JsonResponse(
            {
                "success": True,
                "last_sync": last_sync,
                "cache_active": cache_exists,
                "current_time": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
                "app_status": "running",
            }
        )

    except Exception as e:
        logger.error(f"Erro ao verificar status: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# ========== ENDPOINTS DE DASHBOARD ========== #


def get_dashboard_stats(driver_id=None, target_date=None):
    """
    Função auxiliar para obter estatísticas do dashboard baseadas nas models.
    """
    today = target_date or timezone.now().date()

    # Queries base
    to_attempt_query = Dispatch.objects.filter(
        driver__isnull=False,
        order__actual_delivery_date__isnull=True,
        order__status__in=["pending", "dispatched", "in_transit"],
    )

    failed_query = Order.objects.filter(
        Q(status__in=["failed", "returned", "cancelled"])
        | Q(simplified_order_status__in=["failed", "undelivered"])
    )

    delivered_query = Order.objects.filter(is_delivered=True, status="delivered")

    recovered_query = Dispatch.objects.filter(recovered=True)

    # Aplicar filtro de motorista se fornecido
    if driver_id:
        to_attempt_query = to_attempt_query.filter(driver__driver_id=driver_id)
        failed_query = failed_query.filter(dispatch__driver__driver_id=driver_id)
        delivered_query = delivered_query.filter(dispatch__driver__driver_id=driver_id)
        recovered_query = recovered_query.filter(driver__driver_id=driver_id)

    # Calcular métricas
    to_attempt = to_attempt_query.count()
    failed = failed_query.count()
    delivered = delivered_query.count()
    total_recovered = recovered_query.count()
    total_orders = to_attempt + failed + delivered

    # Taxa de sucesso geral
    total_attempts = delivered + failed
    if total_attempts > 0:
        success_rate = f"{(delivered / total_attempts * 100):.1f}%"
    else:
        success_rate = "0.0%"

    # Estatísticas de hoje
    today_deliveries_query = Order.objects.filter(
        actual_delivery_date=today, is_delivered=True, status="delivered"
    )

    today_fails_query = Order.objects.filter(actual_delivery_date=today).filter(
        Q(status__in=["failed", "returned", "cancelled"])
        | Q(simplified_order_status__in=["failed", "undelivered"])
    )

    today_recovered_query = Dispatch.objects.filter(
        recovered=True, dispatch_time__date=today
    )

    # Aplicar filtro de motorista nas estatísticas de hoje
    if driver_id:
        today_deliveries_query = today_deliveries_query.filter(
            dispatch__driver__driver_id=driver_id
        )
        today_fails_query = today_fails_query.filter(
            dispatch__driver__driver_id=driver_id
        )
        today_recovered_query = today_recovered_query.filter(
            driver__driver_id=driver_id
        )

    today_deliveries = today_deliveries_query.count()
    today_fails = today_fails_query.count()
    today_recovered = today_recovered_query.count()

    # Taxa de sucesso de hoje
    total_today_attempts = today_deliveries + today_fails
    if total_today_attempts > 0:
        today_success_rate = f"{(today_deliveries / total_today_attempts * 100):.1f}%"
    else:
        today_success_rate = "0.0%"

    stats = {
        "total_orders": total_orders,
        "to_attempt": to_attempt,
        "failed": failed,
        "delivered": delivered,
        "total_recovered": total_recovered,
        "success_rate": success_rate,
        "today_deliveries": today_deliveries,
        "today_fails": today_fails,
        "today_recovered": today_recovered,
        "today_success_rate": today_success_rate,
        "total_dispatches": Dispatch.objects.count(),
        "total_drivers": Driver.objects.filter(is_active=True).count(),
        "timestamp": timezone.now().isoformat(),
    }

    return stats


@require_GET
def dashboard_api(request):
    """
    API endpoint para obter dados do dashboard em tempo real.
    """
    try:
        driver_id = request.GET.get("driver_id")
        stats = get_dashboard_stats(driver_id)
        return JsonResponse({"success": True, "data": stats})
    except Exception as e:
        logger.error(f"Erro na API do dashboard: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@require_GET
def driver_recovery_stats(request):
    """
    Endpoint específico para estatísticas de recovered por motorista.
    """
    try:
        today = timezone.now().date()
        week_start = today - timedelta(days=7)

        # Estatísticas detalhadas de recovered por motorista
        drivers_recovery_stats = (
            Driver.objects.filter(is_active=True, dispatch__recovered=True)
            .annotate(
                total_recovered=Count("dispatch", filter=Q(dispatch__recovered=True)),
                today_recovered=Count(
                    "dispatch",
                    filter=Q(
                        dispatch__recovered=True,
                        dispatch__dispatch_time__date=today,
                    ),
                ),
                week_recovered=Count(
                    "dispatch",
                    filter=Q(
                        dispatch__recovered=True,
                        dispatch__dispatch_time__date__gte=week_start,
                    ),
                ),
            )
            .order_by("-total_recovered")[:10]
        )

        # Converter para lista de dicionários
        stats_list = []
        for driver in drivers_recovery_stats:
            stats_list.append(
                {
                    "driver_id": driver.driver_id,
                    "driver_name": driver.name,
                    "vehicle": driver.vehicle,
                    "total_recovered": driver.total_recovered,
                    "today_recovered": driver.today_recovered,
                    "week_recovered": driver.week_recovered,
                }
            )

        return JsonResponse(
            {
                "success": True,
                "drivers_recovery_stats": stats_list,
                "total_recovered_all_drivers": Dispatch.objects.filter(
                    recovered=True
                ).count(),
                "timestamp": timezone.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Erro nas estatísticas de recovery: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@require_GET
def driver_stats_api(request):
    """
    API para estatísticas detalhadas de motoristas.
    """
    try:
        today = timezone.now().date()
        driver_id = request.GET.get("driver_id")

        # Base query
        drivers_query = Driver.objects.filter(is_active=True)

        if driver_id:
            drivers_query = drivers_query.filter(driver_id=driver_id)

        # Estatísticas por motorista
        drivers_stats = drivers_query.annotate(
            total_orders=Count("dispatch__order"),
            delivered_orders=Count(
                "dispatch__order", filter=Q(dispatch__order__is_delivered=True)
            ),
            failed_orders=Count(
                "dispatch__order", filter=Q(dispatch__order__is_failed=True)
            ),
            pending_orders=Count(
                "dispatch__order",
                filter=Q(
                    dispatch__order__actual_delivery_date__isnull=True,
                    dispatch__order__status__in=[
                        "pending",
                        "dispatched",
                        "in_transit",
                    ],
                ),
            ),
            recovered_dispatches=Count("dispatch", filter=Q(dispatch__recovered=True)),
            today_deliveries=Count(
                "dispatch__order",
                filter=Q(
                    dispatch__order__actual_delivery_date=today,
                    dispatch__order__is_delivered=True,
                ),
            ),
        ).order_by("-delivered_orders")[:20]

        # Converter para lista
        stats_list = []
        for driver in drivers_stats:
            success_rate = 0
            if driver.delivered_orders + driver.failed_orders > 0:
                success_rate = (
                    driver.delivered_orders
                    / (driver.delivered_orders + driver.failed_orders)
                ) * 100

            stats_list.append(
                {
                    "driver_id": driver.driver_id,
                    "driver_name": driver.name,
                    "vehicle": driver.vehicle,
                    "total_orders": driver.total_orders,
                    "delivered_orders": driver.delivered_orders,
                    "failed_orders": driver.failed_orders,
                    "pending_orders": driver.pending_orders,
                    "recovered_dispatches": driver.recovered_dispatches,
                    "today_deliveries": driver.today_deliveries,
                    "success_rate": f"{success_rate:.1f}%",
                }
            )

        return JsonResponse(
            {
                "success": True,
                "drivers_stats": stats_list,
                "total_drivers": Driver.objects.filter(is_active=True).count(),
                "timestamp": timezone.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Erro nas estatísticas de motoristas: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@require_GET
def debug_dashboard_counts(request):
    """
    Endpoint para debug - verificar contagens detalhadas baseadas nas models.
    """
    try:
        today = timezone.now().date()
        driver_id = request.GET.get("driver_id")

        # Contagens detalhadas para debug
        debug_info = {
            "database_counts": {
                "total_orders": Order.objects.count(),
                "total_dispatches": Dispatch.objects.count(),
                "total_drivers": Driver.objects.count(),
                "active_drivers": Driver.objects.filter(is_active=True).count(),
            },
            "dispatch_analysis": {
                "dispatches_with_driver": Dispatch.objects.filter(
                    driver__isnull=False
                ).count(),
                "dispatches_without_driver": Dispatch.objects.filter(
                    driver__isnull=True
                ).count(),
                "dispatches_recovered": Dispatch.objects.filter(recovered=True).count(),
                "dispatches_recovered_today": Dispatch.objects.filter(
                    recovered=True, dispatch_time__date=today
                ).count(),
            },
            "order_analysis": {
                "orders_delivered": Order.objects.filter(is_delivered=True).count(),
                "orders_failed": Order.objects.filter(is_failed=True).count(),
                "orders_not_delivered": Order.objects.filter(
                    actual_delivery_date__isnull=True
                ).count(),
                "orders_delivered_today": Order.objects.filter(
                    actual_delivery_date=today, is_delivered=True
                ).count(),
            },
            "status_breakdown": {
                "by_status": dict(
                    Order.objects.values_list("status").annotate(Count("status"))
                ),
                "by_simplified_status": dict(
                    Order.objects.values_list("simplified_order_status").annotate(
                        Count("simplified_order_status")
                    )
                ),
            },
            "calculated_metrics": {
                "to_attempt": Dispatch.objects.filter(
                    driver__isnull=False,
                    order__actual_delivery_date__isnull=True,
                    order__status__in=["pending", "dispatched", "in_transit"],
                ).count(),
                "delivered": Order.objects.filter(
                    is_delivered=True, status="delivered"
                ).count(),
                "failed": Order.objects.filter(
                    Q(status__in=["failed", "returned", "cancelled"])
                    | Q(simplified_order_status__in=["failed", "undelivered"])
                ).count(),
            },
        }

        # Se driver_id específico for fornecido
        if driver_id:
            try:
                driver = Driver.objects.get(driver_id=driver_id)
                debug_info["specific_driver_stats"] = {
                    "driver_name": driver.name,
                    "driver_id": driver.driver_id,
                    "is_active": driver.is_active,
                    "total_dispatches": Dispatch.objects.filter(driver=driver).count(),
                    "recovered_dispatches": Dispatch.objects.filter(
                        driver=driver, recovered=True
                    ).count(),
                    "to_attempt": Dispatch.objects.filter(
                        driver=driver,
                        order__actual_delivery_date__isnull=True,
                        order__status__in=[
                            "pending",
                            "dispatched",
                            "in_transit",
                        ],
                    ).count(),
                    "delivered_orders": Order.objects.filter(
                        dispatch__driver=driver, is_delivered=True
                    ).count(),
                    "failed_orders": Order.objects.filter(
                        dispatch__driver=driver, is_failed=True
                    ).count(),
                }
            except Driver.DoesNotExist:
                debug_info["specific_driver_stats"] = {
                    "error": f"Driver with ID {driver_id} not found"
                }

        return JsonResponse(
            {
                "success": True,
                "debug_info": debug_info,
                "timestamp": timezone.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Erro no debug: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)
