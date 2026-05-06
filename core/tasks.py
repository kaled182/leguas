"""
Tarefas Celery para sincronização automática de integrações de parceiros.

Este módulo contém tarefas agendadas para:
- Sincronização diária de todos os parceiros ativos
- Sincronização específica do Delnext
- Limpeza de logs antigos
"""

from celery import shared_task
from django.utils import timezone
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task(name='core.sync_all_active_integrations')
def sync_all_active_integrations():
    """
    Sincroniza todas as integrações ativas.
    
    Esta tarefa é executada diariamente e processa todas as integrações
    que estão marcadas como ativas.
    
    Returns:
        dict: Estatísticas de sincronização por parceiro
    """
    from core.models import PartnerIntegration
    from core.services import get_sync_service
    
    logger.info("Iniciando sincronização de todas as integrações ativas")
    
    active_integrations = PartnerIntegration.objects.filter(is_active=True)
    results = {}
    
    for integration in active_integrations:
        partner_name = integration.partner.name
        logger.info(f"Sincronizando parceiro: {partner_name}")
        
        try:
            sync_service = get_sync_service(integration)
            
            # Para Delnext, usar configuração específica
            if partner_name == "Delnext":
                config = integration.auth_config or {}
                zone = config.get('zone', 'VianaCastelo')
                stats = sync_service.sync(zone=zone)
            else:
                stats = sync_service.sync()
            
            results[partner_name] = {
                "success": True,
                "stats": stats
            }
            
            logger.info(
                f"Sincronização {partner_name} concluída: "
                f"{stats.get('total', 0)} pedidos, "
                f"{stats.get('created', 0)} criados, "
                f"{stats.get('updated', 0)} atualizados"
            )
            
        except Exception as e:
            logger.error(f"Erro na sincronização de {partner_name}: {e}", exc_info=True)
            results[partner_name] = {
                "success": False,
                "error": str(e)
            }
    
    logger.info(f"Sincronização global concluída. Resultados: {results}")
    return results


@shared_task(name='core.sync_delnext')
def sync_delnext(date=None, zone=None):
    """
    Sincronização específica para Delnext.
    
    Args:
        date (str, optional): Data no formato YYYY-MM-DD. Se None, usa último dia útil.
        zone (str, optional): Zona de entrega. Se None, usa configuração do parceiro.
    
    Returns:
        dict: Estatísticas da sincronização
    """
    from core.models import PartnerIntegration
    from core.services import DelnextSyncService
    
    logger.info(f"Iniciando sincronização Delnext (date={date}, zone={zone})")
    
    try:
        # Buscar integração Delnext ativa
        integration = PartnerIntegration.objects.get(
            partner__name="Delnext",
            is_active=True
        )
        
        # Usar configuração se não fornecida
        if zone is None:
            config = integration.auth_config or {}
            zone = config.get('zone', 'VianaCastelo')
        
        # Executar sincronização
        sync_service = DelnextSyncService(integration)
        stats = sync_service.sync(date=date, zone=zone)
        
        logger.info(
            f"Sincronização Delnext concluída: "
            f"{stats.get('total', 0)} pedidos, "
            f"{stats.get('created', 0)} criados, "
            f"{stats.get('updated', 0)} atualizados, "
            f"zona={stats.get('zone')}, data={stats.get('date')}"
        )
        
        return {
            "success": True,
            "stats": stats
        }
        
    except PartnerIntegration.DoesNotExist:
        error_msg = "Integração Delnext não encontrada ou inativa"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }
        
    except Exception as e:
        logger.error(f"Erro na sincronização Delnext: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


@shared_task(name='core.sync_delnext_last_weekday')
def sync_delnext_last_weekday(zone=None):
    """
    Sincroniza Delnext usando o último dia útil (Segunda-Sexta).
    
    Útil para execuções aos fins de semana ou feriados, onde
    queremos importar dados do último dia de operação.
    
    Args:
        zone (str, optional): Zona de entrega. Se None, usa configuração.
    
    Returns:
        dict: Estatísticas da sincronização
    """
    from datetime import datetime, timedelta
    
    # Calcular último dia útil
    today = datetime.now()
    days_to_subtract = 1
    
    # Se hoje é Segunda (0), pegar Sexta (-3 dias)
    if today.weekday() == 0:  # Monday
        days_to_subtract = 3
    # Se hoje é Domingo (6), pegar Sexta (-2 dias)
    elif today.weekday() == 6:  # Sunday
        days_to_subtract = 2
    # Se hoje é Sábado (5), pegar Sexta (-1 dia)
    elif today.weekday() == 5:  # Saturday
        days_to_subtract = 1
    
    last_weekday = today - timedelta(days=days_to_subtract)
    date_str = last_weekday.strftime('%Y-%m-%d')
    
    logger.info(f"Sincronizando Delnext do último dia útil: {date_str}")
    
    return sync_delnext(date=date_str, zone=zone)


@shared_task(name='core.cleanup_old_partner_data')
def cleanup_old_partner_data(days=90):
    """
    Remove dados antigos de sincronizações de parceiros.
    
    Args:
        days (int): Número de dias para manter. Dados mais antigos serão removidos.
    
    Returns:
        dict: Contagem de registros removidos
    """
    from core.models import PartnerIntegration
    
    logger.info(f"Iniciando limpeza de dados com mais de {days} dias")
    
    cutoff_date = timezone.now() - timedelta(days=days)
    results = {
        "cleaned_integrations": 0
    }
    
    # Limpar estatísticas antigas de integrações
    # (mantém apenas last_sync_stats, mas pode-se expandir para logs)
    integrations = PartnerIntegration.objects.filter(
        last_sync_at__lt=cutoff_date,
        is_active=False
    )
    
    for integration in integrations:
        # Você pode adicionar lógica para limpar logs aqui
        # Por exemplo, se tiver uma modelo de SyncLog
        pass
    
    logger.info(f"Limpeza concluída: {results}")
    return results


@shared_task(name='core.send_sync_report')
def send_sync_report(email_to=None):
    """
    Envia relatório de sincronização por email.
    
    Args:
        email_to (str, optional): Email do destinatário. Se None, usa admin padrão.
    
    Returns:
        dict: Status do envio
    """
    from django.core.mail import send_mail
    from django.conf import settings
    from core.models import PartnerIntegration
    
    logger.info("Gerando relatório de sincronização")
    
    # Buscar todas as integrações
    integrations = PartnerIntegration.objects.filter(is_active=True)
    
    # Construir relatório
    report_lines = [
        "Relatório de Sincronização de Parceiros",
        "=" * 50,
        ""
    ]
    
    for integration in integrations:
        report_lines.append(f"Parceiro: {integration.partner.name}")
        report_lines.append(f"  Status: {'✓ Ativo' if integration.is_active else '✗ Inativo'}")
        
        if integration.last_sync_at:
            report_lines.append(f"  Última Sincronização: {integration.last_sync_at.strftime('%Y-%m-%d %H:%M:%S')}")
            report_lines.append(f"  Status: {integration.last_sync_status}")
            
            if integration.last_sync_stats:
                stats = integration.last_sync_stats
                report_lines.append(f"  Total: {stats.get('total', 0)} pedidos")
                report_lines.append(f"  Criados: {stats.get('created', 0)}")
                report_lines.append(f"  Atualizados: {stats.get('updated', 0)}")
                report_lines.append(f"  Erros: {stats.get('errors', 0)}")
        else:
            report_lines.append("  Nunca sincronizado")
        
        report_lines.append("")
    
    report_text = "\n".join(report_lines)
    
    # Enviar email
    try:
        recipient = email_to or settings.ADMINS[0][1] if settings.ADMINS else None
        
        if not recipient:
            logger.warning("Nenhum email de destino configurado")
            return {
                "success": False,
                "error": "Nenhum email configurado"
            }
        
        send_mail(
            subject=f"Relatório de Sincronização - {timezone.now().strftime('%Y-%m-%d')}",
            message=report_text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
        
        logger.info(f"Relatório enviado para {recipient}")
        return {
            "success": True,
            "sent_to": recipient
        }
        
    except Exception as e:
        logger.error(f"Erro ao enviar relatório: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


@shared_task(name='core.test_task')
def test_task():
    """
    Tarefa de teste para verificar se Celery está funcionando.
    
    Returns:
        dict: Mensagem de sucesso com timestamp
    """
    logger.info("Executando tarefa de teste do Celery")
    
    return {
        "success": True,
        "message": "Celery está funcionando!",
        "timestamp": timezone.now().isoformat()
    }


@shared_task(name='core.geocode_recent_orders')
def geocode_recent_orders(partner_name='Delnext', hours=24):
    """
    Geocodifica pedidos recentes que ainda não têm coordenadas.
    
    Esta tarefa é executada após a sincronização para geocodificar
    os novos pedidos importados.
    
    Args:
        partner_name: Nome do parceiro (padrão: Delnext)
        hours: Buscar pedidos das últimas N horas (padrão: 24)
    
    Returns:
        dict: Estatísticas de geocodificação
    """
    from orders_manager.models import Order, GeocodedAddress, GeocodingFailure
    from orders_manager.geocoding import GeocodingService, AddressNormalizer
    from django.utils import timezone
    import time
    
    logger.info(f"Iniciando geocodificação de pedidos recentes do {partner_name}")
    
    # Buscar pedidos recentes
    since = timezone.now() - timedelta(hours=hours)
    orders = Order.objects.filter(
        partner__name__icontains=partner_name,
        created_at__gte=since
    ).select_related('partner')
    
    total = orders.count()
    geocoded = 0
    cached = 0
    failed = 0
    skipped = 0
    
    logger.info(f"Encontrados {total} pedidos para geocodificar")
    
    for order in orders:
        try:
            # Verificar se tem endereço
            if not order.recipient_address or not order.postal_code:
                skipped += 1
                continue
            
            # Extrair localidade
            locality = order.recipient_address.split()[-1] if order.recipient_address else "Portugal"
            if len(locality) < 3:
                locality = "Portugal"
            
            # Normalizar endereço
            normalized = AddressNormalizer.normalize(
                order.recipient_address,
                order.postal_code,
                locality
            )
            
            # Verificar cache
            existing = GeocodedAddress.objects.filter(
                normalized_address=normalized
            ).first()
            
            if existing:
                cached += 1
                continue
            
            # Geocodificar
            coords = GeocodingService.geocode(
                order.recipient_address,
                order.postal_code,
                locality
            )
            
            if coords:
                # Salvar no cache
                GeocodedAddress.objects.update_or_create(
                    normalized_address=normalized,
                    defaults={
                        'address': order.recipient_address,
                        'postal_code': order.postal_code,
                        'locality': locality,
                        'latitude': coords[0],
                        'longitude': coords[1],
                        'geocode_quality': 'EXACT',
                        'geocode_source': 'Nominatim'
                    }
                )
                geocoded += 1
                logger.info(f"✓ Geocodificado: {order.external_reference}")
            else:
                # Registrar falha
                failure, created = GeocodingFailure.objects.get_or_create(
                    order=order,
                    defaults={
                        'original_address': order.recipient_address,
                        'normalized_address': normalized,
                        'postal_code': order.postal_code,
                        'locality': locality,
                        'failure_reason': 'Nominatim não retornou coordenadas'
                    }
                )
                
                if not created:
                    # Incrementar contador de tentativas
                    failure.retry_count += 1
                    failure.save()
                
                failed += 1
                logger.warning(f"✗ Falha ao geocodificar: {order.external_reference}")
            
            # Rate limiting
            time.sleep(1.1)
            
        except Exception as e:
            logger.error(f"Erro ao processar pedido {order.external_reference}: {e}")
            failed += 1
    
    result = {
        "success": True,
        "total": total,
        "geocoded": geocoded,
        "cached": cached,
        "failed": failed,
        "skipped": skipped,
        "success_rate": round((geocoded + cached) / total * 100, 1) if total > 0 else 0
    }
    
    logger.info(f"Geocodificação concluída: {result}")

    return result


@shared_task(name='core.auto_emit_fleet_invoices')
def auto_emit_fleet_invoices():
    """Verifica configs FleetAutoEmitConfig e dispara emissão automática.

    Corre 1x/dia. Para cada frota com auto-emit activo:
      - period_type=monthly: dispara no dia X do mês, cobre mês anterior
      - period_type=weekly: dispara no dia da semana X, cobre semana anterior

    Idempotente: usa last_emitted_period_to para não emitir duas vezes
    o mesmo período.
    """
    from datetime import timedelta
    from drivers_app.models import FleetAutoEmitConfig
    from django.test import RequestFactory
    from django.contrib.auth import get_user_model
    from settlements.views import (
        empresa_lote_emit, empresa_whatsapp_lote,
    )
    import json

    today = timezone.now().date()
    User = get_user_model()
    bot_user = User.objects.filter(is_superuser=True).first()
    if not bot_user:
        logger.warning("[AUTO_EMIT] Sem superuser para attribuir created_by")
        return {"error": "no superuser"}

    rf = RequestFactory()
    results = []

    for cfg in FleetAutoEmitConfig.objects.filter(enabled=True).select_related("empresa"):
        # Determinar período-alvo
        if cfg.period_type == "monthly":
            if today.day != cfg.day_of_month:
                continue
            first_this = today.replace(day=1)
            period_to = first_this - timedelta(days=1)
            period_from = period_to.replace(day=1)
        elif cfg.period_type == "weekly":
            if today.weekday() != cfg.weekday:
                continue
            this_monday = today - timedelta(days=today.weekday())
            period_from = this_monday - timedelta(days=7)
            period_to = this_monday - timedelta(days=1)
        else:
            continue

        # Idempotência
        if (cfg.last_emitted_period_to
                and cfg.last_emitted_period_to >= period_to):
            logger.info(
                f"[AUTO_EMIT] {cfg.empresa.nome}: já emitido para "
                f"{period_from}→{period_to}, skip"
            )
            continue

        # Disparar lote-emit
        body = json.dumps({
            "from": period_from.strftime("%Y-%m-%d"),
            "to": period_to.strftime("%Y-%m-%d"),
            "skip_overlap": True,
        }).encode("utf-8")
        req = rf.post(
            f"/settlements/empresas/{cfg.empresa.id}/lote-emit/",
            data=body, content_type="application/json",
        )
        req.user = bot_user
        try:
            resp = empresa_lote_emit(req, cfg.empresa.id)
            data = json.loads(resp.content)
        except Exception as e:
            logger.exception(f"[AUTO_EMIT] {cfg.empresa.nome}: ERRO")
            results.append({"empresa": cfg.empresa.nome, "error": str(e)})
            continue

        summary = data.get("summary", {})
        cfg.last_emitted_at = timezone.now()
        cfg.last_emitted_period_from = period_from
        cfg.last_emitted_period_to = period_to
        cfg.last_summary = summary
        cfg.save(update_fields=[
            "last_emitted_at", "last_emitted_period_from",
            "last_emitted_period_to", "last_summary",
        ])

        logger.info(
            f"[AUTO_EMIT] {cfg.empresa.nome}: "
            f"{summary.get('n_created', 0)} PFs criadas, "
            f"€{summary.get('total_amount', 0)}"
        )

        # WhatsApp opcional
        if cfg.auto_send_whatsapp and summary.get("n_created", 0) > 0:
            try:
                wa_body = json.dumps({
                    "from": period_from.strftime("%Y-%m-%d"),
                    "to": period_to.strftime("%Y-%m-%d"),
                }).encode("utf-8")
                wa_req = rf.post(
                    f"/settlements/empresas/{cfg.empresa.id}"
                    f"/whatsapp-lote/",
                    data=wa_body, content_type="application/json",
                )
                wa_req.user = bot_user
                empresa_whatsapp_lote(wa_req, cfg.empresa.id)
            except Exception as e:
                logger.warning(
                    f"[AUTO_EMIT] {cfg.empresa.nome}: WA falhou: {e}"
                )

        results.append({
            "empresa": cfg.empresa.nome,
            "period": f"{period_from} → {period_to}",
            "summary": summary,
        })

    logger.info(f"[AUTO_EMIT] Concluído: {len(results)} frotas processadas")
    return {"processed": len(results), "results": results}



@shared_task(name='core.auto_emit_driver_pre_invoices')
def auto_emit_driver_pre_invoices():
    """Análogo a auto_emit_fleet_invoices mas para motoristas individuais.

    Itera DriverAutoEmitConfig com enabled=True. Para cada motorista no
    dia/condição configurada, cria DriverPreInvoice cobrindo o período.
    Idempotente via last_emitted_period_to.

    Períodos:
      - monthly: mês anterior completo, dispara no dia X
      - biweekly: 15 dias anteriores, dispara no dia X
      - weekly: semana anterior, dispara no weekday X
    """
    from datetime import timedelta
    from drivers_app.models import DriverAutoEmitConfig
    from django.test import RequestFactory
    from django.contrib.auth import get_user_model
    from settlements.views import driver_pre_invoice_create
    import json

    today = timezone.now().date()
    User = get_user_model()
    bot_user = User.objects.filter(is_superuser=True).first()
    if not bot_user:
        logger.warning("[AUTO_EMIT_DRV] Sem superuser para attribuir created_by")
        return {"error": "no superuser"}

    rf = RequestFactory()
    results = []

    for cfg in DriverAutoEmitConfig.objects.filter(enabled=True).select_related("driver"):
        if cfg.period_type == "monthly":
            if today.day != cfg.day_of_month:
                continue
            first_this = today.replace(day=1)
            period_to = first_this - timedelta(days=1)
            period_from = period_to.replace(day=1)
        elif cfg.period_type == "biweekly":
            if today.day != cfg.day_of_month:
                continue
            period_to = today - timedelta(days=1)
            period_from = period_to - timedelta(days=14)
        elif cfg.period_type == "weekly":
            if today.weekday() != cfg.weekday:
                continue
            this_monday = today - timedelta(days=today.weekday())
            period_from = this_monday - timedelta(days=7)
            period_to = this_monday - timedelta(days=1)
        else:
            continue

        if (cfg.last_emitted_period_to
                and cfg.last_emitted_period_to >= period_to):
            continue

        body = json.dumps({
            "periodo_inicio": period_from.strftime("%Y-%m-%d"),
            "periodo_fim": period_to.strftime("%Y-%m-%d"),
        }).encode("utf-8")
        req = rf.post(
            f"/settlements/pre-invoices/driver/{cfg.driver.id}/create/",
            data=body, content_type="application/json",
        )
        req.user = bot_user
        try:
            resp = driver_pre_invoice_create(req, cfg.driver.id)
            data = json.loads(resp.content)
        except Exception as e:
            logger.exception(f"[AUTO_EMIT_DRV] {cfg.driver.nome_completo}: ERRO")
            results.append({"driver": cfg.driver.nome_completo, "error": str(e)})
            continue

        if data.get("success"):
            pf_id = data.get("id") or data.get("pre_invoice_id")
            cfg.last_emitted_at = timezone.now()
            cfg.last_emitted_period_from = period_from
            cfg.last_emitted_period_to = period_to
            cfg.last_pf_id = pf_id
            cfg.save(update_fields=[
                "last_emitted_at", "last_emitted_period_from",
                "last_emitted_period_to", "last_pf_id",
            ])

            # Auto-aprovar se configurado
            if cfg.auto_approve and pf_id:
                from settlements.models import DriverPreInvoice
                pf = DriverPreInvoice.objects.filter(pk=pf_id).first()
                if pf and pf.status == "CALCULADO":
                    pf.status = "APROVADO"
                    pf.save(update_fields=["status"])

            results.append({
                "driver": cfg.driver.nome_completo,
                "pf_id": pf_id,
                "period": f"{period_from} → {period_to}",
            })
        else:
            results.append({
                "driver": cfg.driver.nome_completo,
                "error": data.get("error", "unknown"),
            })

    logger.info(f"[AUTO_EMIT_DRV] Concluído: {len(results)} drivers processados")
    return {"processed": len(results), "results": results}
