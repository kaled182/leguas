"""Envia alertas de Bills com vencimento próximo + Bills já vencidas.

Por defeito, alerta:
  - Bills PENDING que vencem dentro de N dias (default 3)
  - Bills OVERDUE (já vencidas)

Envia 1 mensagem WhatsApp consolidada para WHATSAPP_REPORT_GROUP
(o mesmo grupo do daily report). URL e grupo lidos de settings.

Uso manual:
    python manage.py send_bill_reminders
    python manage.py send_bill_reminders --days 5
    python manage.py send_bill_reminders --dry-run
"""
import logging
from datetime import date, timedelta

import requests
from django.conf import settings as dj_settings
from django.core.management.base import BaseCommand

from accounting.models import Bill

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Envia alerta WhatsApp de contas a pagar próximas/vencidas."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days", type=int, default=3,
            help="Dias de antecedência para alertar (default 3).",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Mostra a mensagem sem enviar.",
        )

    def handle(self, *args, **opts):
        days = opts["days"]
        dry = opts["dry_run"]
        today = date.today()
        cutoff = today + timedelta(days=days)

        upcoming = list(
            Bill.objects.filter(
                status=Bill.STATUS_PENDING,
                due_date__gte=today,
                due_date__lte=cutoff,
            ).select_related("category", "cost_center")
            .order_by("due_date")
        )
        overdue = list(
            Bill.objects.filter(
                status=Bill.STATUS_OVERDUE,
            ).select_related("category", "cost_center")
            .order_by("due_date")
        )

        if not upcoming and not overdue:
            self.stdout.write(
                "Nenhuma conta a vencer nos próximos "
                f"{days} dia(s) e nenhuma vencida. Nada a enviar.",
            )
            return

        lines = [
            f"💰 *Contas a Pagar — {today:%d/%m/%Y}*",
            "",
        ]
        if overdue:
            total_o = sum(b.amount_total for b in overdue)
            lines.append(
                f"🔴 *Vencidas ({len(overdue)}) · "
                f"€{total_o:.2f}*",
            )
            for b in overdue[:15]:
                d_late = (today - b.due_date).days
                lines.append(
                    f"  • {b.description} · {b.supplier} · "
                    f"€{b.amount_total:.2f} · venceu há {d_late}d "
                    f"({b.due_date:%d/%m})",
                )
            if len(overdue) > 15:
                lines.append(f"  …e mais {len(overdue) - 15}")
            lines.append("")

        if upcoming:
            total_u = sum(b.amount_total for b in upcoming)
            lines.append(
                f"⏰ *A vencer em {days}d ({len(upcoming)}) · "
                f"€{total_u:.2f}*",
            )
            for b in upcoming[:15]:
                d_left = (b.due_date - today).days
                if d_left == 0:
                    when = "hoje"
                elif d_left == 1:
                    when = "amanhã"
                else:
                    when = f"em {d_left}d"
                lines.append(
                    f"  • {b.description} · {b.supplier} · "
                    f"€{b.amount_total:.2f} · {when} "
                    f"({b.due_date:%d/%m})",
                )
            if len(upcoming) > 15:
                lines.append(f"  …e mais {len(upcoming) - 15}")
            lines.append("")

        lines.append("(alerta automático)")
        message = "\n".join(lines)

        if dry:
            self.stdout.write("--- Mensagem ---")
            self.stdout.write(message)
            self.stdout.write("--- Fim (dry-run, nada enviado) ---")
            return

        api_url = (
            getattr(dj_settings, "WHATSAPP_API_URL", "")
            or "http://45.160.176.150:9090/message/sendText/leguasreports"
        )
        group = getattr(dj_settings, "WHATSAPP_REPORT_GROUP", "")
        if not group:
            self.stderr.write(
                "WHATSAPP_REPORT_GROUP não configurado. "
                "Define-o no .env para ativar o envio.",
            )
            return

        try:
            r = requests.post(
                api_url,
                json={"number": group, "text": message},
                timeout=15,
            )
            ok = r.status_code in (200, 201)
            self.stdout.write(self.style.SUCCESS(
                f"Enviado · status={r.status_code} · "
                f"overdue={len(overdue)} upcoming={len(upcoming)}"
            ) if ok else self.style.WARNING(
                f"Falha · status={r.status_code} · resp={r.text[:200]}"
            ))
        except Exception as e:
            logger.exception("Erro a enviar WhatsApp: %s", e)
            self.stderr.write(f"Erro: {e}")
