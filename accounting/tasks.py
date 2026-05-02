"""Tasks Celery do app accounting."""
import logging

from celery import shared_task
from django.core.management import call_command

logger = logging.getLogger(__name__)


@shared_task(name="accounting.generate_recurring_bills")
def generate_recurring_bills_task(lookahead_days=7):
    """Gera próximas instâncias de Bills recorrentes.

    Schedule: 1× ao dia (Celery beat).
    """
    try:
        call_command(
            "generate_recurring_bills",
            "--lookahead-days", str(lookahead_days),
        )
        return {"success": True}
    except Exception as e:
        logger.exception("[accounting] generate_recurring_bills falhou")
        return {"success": False, "error": str(e)}


@shared_task(name="accounting.send_bill_reminders")
def send_bill_reminders_task(days=3):
    """Envia alerta WhatsApp das contas a vencer/vencidas.

    Schedule: 1× ao dia (Celery beat).
    """
    try:
        call_command("send_bill_reminders", "--days", str(days))
        return {"success": True}
    except Exception as e:
        logger.exception("[accounting] send_bill_reminders falhou")
        return {"success": False, "error": str(e)}


@shared_task(name="accounting.break_even_alert")
def break_even_alert_task():
    """Envia alerta WhatsApp se BE atingido / em risco / ritmo lento.

    Schedule: 1× ao dia (Celery beat).
    """
    try:
        call_command("break_even_alert")
        return {"success": True}
    except Exception as e:
        logger.exception("[accounting] break_even_alert falhou")
        return {"success": False, "error": str(e)}
