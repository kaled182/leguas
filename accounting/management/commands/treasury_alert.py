"""Envia alertas WhatsApp sobre o estado da tesouraria.

Três níveis de detecção (combinados na mesma mensagem):
  - DANGER: saldo projectado em +30d fica negativo
  - WARNING: Σ saídas vencidas > TREASURY_ALERT_OVERDUE_THRESHOLD (default €500)
  - INFO: saídas a vencer amanhã > TREASURY_ALERT_HEADSUP_THRESHOLD (default €100)

Uso:
    python manage.py treasury_alert [--dry-run]

Schedule sugerido: 1× ao dia (manhã).
"""
import logging
from datetime import timedelta
from decimal import Decimal

import requests
from django.conf import settings as dj_settings
from django.core.management.base import BaseCommand
from django.db.models import Sum, Q
from django.utils import timezone

from accounting.models import Bill, Imposto
from accounting.services_treasury import treasury_snapshot

logger = logging.getLogger(__name__)


def _zero():
    return Decimal("0.00")


class Command(BaseCommand):
    help = "Envia alerta WhatsApp do estado de tesouraria."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Imprime a mensagem mas não envia.",
        )

    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        today = timezone.localdate()
        tomorrow = today + timedelta(days=1)
        snap = treasury_snapshot(today)

        # ── 1. Saídas vencidas (já passaram do due_date) ──────────────
        overdue_bills = (
            Bill.objects.filter(
                status__in=[Bill.STATUS_PENDING, Bill.STATUS_OVERDUE],
                due_date__lt=today,
            ).aggregate(t=Sum("amount_total"))["t"] or _zero()
        )
        overdue_taxes = (
            Imposto.objects.filter(
                Q(status=Imposto.STATUS_PENDENTE)
                | Q(status=Imposto.STATUS_EM_ATRASO),
                data_vencimento__lt=today,
            )
            .filter(
                Q(parent__isnull=False)
                | ~Q(modalidade=Imposto.MODALIDADE_PARCELADO),
            )
            .aggregate(t=Sum("valor"))["t"] or _zero()
        )
        overdue_total = overdue_bills + overdue_taxes

        # ── 2. D-1: saídas que vencem amanhã ──────────────────────────
        d1_bills = list(
            Bill.objects.filter(
                status__in=[Bill.STATUS_PENDING, Bill.STATUS_AWAITING],
                due_date=tomorrow,
            ).select_related("fornecedor")[:10]
        )
        d1_taxes = list(
            Imposto.objects.filter(
                Q(status=Imposto.STATUS_PENDENTE),
                data_vencimento=tomorrow,
            ).filter(
                Q(parent__isnull=False)
                | ~Q(modalidade=Imposto.MODALIDADE_PARCELADO),
            )[:10]
        )
        d1_total = sum(
            (b.amount_total for b in d1_bills), _zero(),
        ) + sum((i.valor for i in d1_taxes), _zero())

        # ── Limiares ──────────────────────────────────────────────────
        overdue_threshold = Decimal(str(getattr(
            dj_settings, "TREASURY_ALERT_OVERDUE_THRESHOLD", 500,
        )))
        headsup_threshold = Decimal(str(getattr(
            dj_settings, "TREASURY_ALERT_HEADSUP_THRESHOLD", 100,
        )))

        # ── Decisão de alertas ───────────────────────────────────────
        flags = []
        if snap["saldo_projectado_30d"] < 0:
            flags.append("danger")
        if overdue_total > overdue_threshold:
            flags.append("warning")
        if d1_total > headsup_threshold:
            flags.append("info")

        if not flags:
            self.stdout.write(
                "Tesouraria saudável — sem alertas a enviar."
            )
            return

        # ── Construir mensagem ───────────────────────────────────────
        if "danger" in flags:
            emoji, title = "🚨", "ALERTA Tesouraria"
        elif "warning" in flags:
            emoji, title = "⚠", "Aviso Tesouraria"
        else:
            emoji, title = "📅", "Tesouraria — heads-up"

        lines = [
            f"{emoji} *{title}*",
            f"_{today:%d/%m/%Y}_",
            "",
            f"🏦 Saldo bancário: *€{snap['saldo_bancario']:.2f}*",
            f"📈 Projectado +30d: *€{snap['saldo_projectado_30d']:.2f}*",
            f"💸 A pagar 30d: €{snap['a_pagar_total']:.2f}  "
            f"💰 A receber 30d: €{snap['a_receber_total']:.2f}",
        ]

        if "danger" in flags:
            lines.append(
                f"\n🚨 *Saldo projectado fica NEGATIVO* nos próximos 30 dias."
            )
        if "warning" in flags:
            lines.append(
                f"\n⚠ Vencidos acumulados: *€{overdue_total:.2f}*"
            )
            if overdue_bills > 0:
                lines.append(f"   · Bills: €{overdue_bills:.2f}")
            if overdue_taxes > 0:
                lines.append(f"   · Impostos: €{overdue_taxes:.2f}")
        if "info" in flags:
            lines.append(
                f"\n📅 *Amanhã ({tomorrow:%d/%m})*: €{d1_total:.2f} a sair"
            )
            shown = 0
            for b in d1_bills[:5]:
                name = (
                    b.fornecedor.name if b.fornecedor_id
                    else (b.supplier or "Fornecedor")
                )
                lines.append(f"   · {name}: €{b.amount_total:.2f}")
                shown += 1
            for i in d1_taxes[:5]:
                lines.append(
                    f"   · {i.get_tipo_display()}: €{i.valor:.2f}"
                )
                shown += 1
            if (len(d1_bills) + len(d1_taxes)) > shown:
                lines.append(
                    f"   · +{(len(d1_bills) + len(d1_taxes)) - shown} mais…"
                )

        lines.append("")
        lines.append(
            "🔗 Hub: /accounting/hub/  ·  Reconcilia: /accounting/reconciliacao-bancaria/"
        )

        message = "\n".join(lines)

        if dry:
            self.stdout.write("--- Mensagem ---")
            self.stdout.write(message)
            return

        api_url = (
            getattr(dj_settings, "WHATSAPP_API_URL", "")
            or "http://45.160.176.150:9090/message/sendText/leguasreports"
        )
        group = getattr(dj_settings, "WHATSAPP_REPORT_GROUP", "")
        if not group:
            self.stderr.write("WHATSAPP_REPORT_GROUP não configurado.")
            return
        try:
            r = requests.post(
                api_url,
                json={"number": group, "text": message},
                timeout=15,
            )
            ok = r.status_code in (200, 201)
            self.stdout.write(self.style.SUCCESS(
                f"Enviado · status={r.status_code} · flags={','.join(flags)}"
            ) if ok else self.style.WARNING(
                f"Falha · status={r.status_code}"
            ))
        except Exception as e:
            logger.exception("Erro a enviar treasury_alert: %s", e)
