"""Tasks Celery do app accounting."""
import logging

from celery import shared_task
from django.core.management import call_command

logger = logging.getLogger(__name__)


@shared_task(name="accounting.generate_recurring_bills")
def generate_recurring_bills_task(lookahead_days=7, force=False):
    """Gera próximas instâncias de Bills recorrentes.

    DESACTIVADA por defeito (settings.ACCOUNTING_AUTO_RECURRING_BILLS_ENABLED
    = False) — havia bug de duplicação quando o mesmo fornecedor tinha
    recorrência configurada em ambos os mecanismos. Para correr
    manualmente: `python manage.py generate_recurring_bills` (CLI) ou
    chamar esta task com `force=True`.
    """
    from django.conf import settings
    enabled = getattr(
        settings, "ACCOUNTING_AUTO_RECURRING_BILLS_ENABLED", False,
    )
    if not enabled and not force:
        logger.info(
            "[accounting] generate_recurring_bills SKIPPED "
            "(ACCOUNTING_AUTO_RECURRING_BILLS_ENABLED=False)"
        )
        return {"success": True, "skipped": True}
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
