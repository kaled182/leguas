"""
Tarefas Celery do core.

Este módulo contém tarefas agendadas para:
- Limpeza de dados antigos das integrações de parceiros
- Relatório semanal das integrações
- Emissão automática de pré-faturas (frotas e motoristas)
"""

from celery import shared_task
from django.utils import timezone
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


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
