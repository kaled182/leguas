import logging
from pathlib import Path

import environ
import requests
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from management.views import DashboardCalculator
from ordersmanager_paack.sync_service import SyncService

logger = logging.getLogger(__name__)

# Configuração do ambiente
BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")


def sync_before_report():
    """
    Executa sincronização automática antes de gerar o relatório.

    Returns:
        dict: Resultado da sincronização
    """
    try:
        logger.info("🔄 Executando sincronização automática antes do relatório...")
        sync_service = SyncService()
        result = sync_service.sync_data(force_refresh=True)

        if result["success"]:
            logger.info("✅ Sincronização concluída com sucesso!")
        else:
            logger.warning(
                f"⚠️ Sincronização falhou: {result.get('error', 'Erro desconhecido')}"
            )

        return result
    except Exception as e:
        logger.error(f"❌ Erro na sincronização: {str(e)}")
        return {"success": False, "error": str(e)}


def generate_report_text(target_date=None, include_sync_info=False):
    """
    Gera um relatório em texto com as informações atualizadas do dashboard.

    Args:
        target_date (date, optional): Data específica para o relatório. Se None, usa data atual.
        include_sync_info (bool): Se True, inclui informações sobre a sincronização

    Returns:
        str: Relatório formatado em texto
    """
    # Executar sincronização automática
    sync_result = sync_before_report()

    # Inicializar calculadora com dados atualizados
    calculator = DashboardCalculator(target_date)

    # Obter métricas atualizadas
    daily_metrics = calculator.get_daily_metrics()
    weekly_metrics = calculator.get_weekly_metrics()
    top_drivers = calculator.get_top_drivers()
    best_driver = calculator.get_best_driver(top_drivers)

    # Formatar data e hora atual
    now = timezone.localtime(timezone.now())
    formatted_date = now.strftime("%d/%m/%Y")
    formatted_time = now.strftime("%H:%M:%S")

    # Preparar valor de recuperadas (se não houver, mostrar "—")
    recovered_text = (
        str(daily_metrics["recovered"]) if daily_metrics["recovered"] > 0 else "—"
    )

    # Gerar relatório formatado
    report = f"""📋 Relatório Automático
🗓️ {formatted_date} - {formatted_time}

📦 Total de Pedidos: {daily_metrics['total_orders']}
⏳ Por Tentar: {daily_metrics['to_attempt']}
✅ Entregues: {daily_metrics['deliveries']}
❌ Falhadas: {daily_metrics['fails']}
🔄 Recuperadas: {recovered_text}
📈 Taxa de Sucesso: {daily_metrics['success_rate']}
🏅 Melhor Motorista: {best_driver}
⚙️ Eficiência Semanal: {weekly_metrics['efficiency']}"""

    # Adicionar informações de sincronização se solicitado
    if include_sync_info:
        sync_status = (
            "✅ Dados sincronizados" if sync_result["success"] else "⚠️ Sync parcial"
        )
        report += f"\n\n🔄 Status: {sync_status}"

    return report


@login_required
def send_paack_reports(request):
    """
    View para gerar e enviar relatórios automáticos via API.
    """
    try:
        # Verificar se há filtro de data
        date_filter = request.GET.get("date")
        target_date = None

        if date_filter:
            try:
                from datetime import datetime

                target_date = datetime.strptime(date_filter, "%Y-%m-%d").date()
            except ValueError:
                pass

        # Gerar relatório com dados atualizados
        report_text = generate_report_text(target_date)

        # Carregar configurações da API
        api_key = env("AUTHENTICATION_API_KEY")
        url = "http://45.160.176.150:9090/message/sendText/leguasreports"

        # Preparar payload para API
        payload = {
            "number": "120363418429414442@g.us",
            "textMessage": {"text": report_text},
        }
        headers = {"apikey": api_key, "Content-Type": "application/json"}

        # Enviar via API
        response = requests.post(url, json=payload, headers=headers)

        # Aceitar qualquer código de sucesso (2xx)
        if 200 <= response.status_code < 300:
            return JsonResponse(
                {
                    "success": True,
                    "message": "Relatório enviado com sucesso!",
                    "report": report_text,
                    "api_response": response.text,
                    "status_code": response.status_code,
                }
            )
        else:
            return JsonResponse(
                {
                    "success": False,
                    "error": f"Erro na API: {response.status_code}",
                    "report": report_text,
                },
                status=400,
            )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
def generate_report_preview(request):
    """
    View para visualizar o relatório sem enviar.
    """
    try:
        # Verificar se há filtro de data
        date_filter = request.GET.get("date")
        target_date = None

        if date_filter:
            try:
                from datetime import datetime

                target_date = datetime.strptime(date_filter, "%Y-%m-%d").date()
            except ValueError:
                pass

        # Gerar relatório
        report_text = generate_report_text(target_date)

        return JsonResponse(
            {
                "success": True,
                "report": report_text,
                "date_used": (
                    target_date.strftime("%Y-%m-%d")
                    if target_date
                    else timezone.now().date().strftime("%Y-%m-%d")
                ),
            }
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
def send_reports_page(request):
    """
    View para renderizar a página de envio de relatórios.
    """
    return render(request, "send_paack_reports/send_reports.html")
