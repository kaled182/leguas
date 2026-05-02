"""Envia alertas WhatsApp sobre o break-even mensal.

Lógica:
  - Se atingiste BE pela primeira vez no mês → mensagem de celebração 🎉
  - Se já passaste do meio do mês e <50% do BE → alerta vermelho ⚠
  - Se ritmo actual não cobre o necessário → aviso amarelo

Uso:
    python manage.py break_even_alert [--dry-run]

Schedule sugerido: 1× ao dia.
"""
import logging
from calendar import monthrange
from datetime import date

import requests
from django.conf import settings as dj_settings
from django.core.management.base import BaseCommand

from accounting.views import _compute_break_even

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Envia alerta WhatsApp do break-even mensal."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
        )

    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        today = date.today()
        first = today.replace(day=1)
        last = date(
            today.year, today.month,
            monthrange(today.year, today.month)[1],
        )
        d = _compute_break_even(first, last, include_awaiting=True)

        days_total = (last - first).days + 1
        days_elapsed = (today - first).days + 1
        elapsed_pct = days_elapsed / days_total * 100

        # Decidir nível de alerta
        level = None
        if d["be_atingido"]:
            level = "ok"
        elif elapsed_pct >= 50 and d["pct_atingido"] < 50:
            level = "danger"
        elif d["rate_actual"] < d["rate_needed"] and d["pct_atingido"] < 100:
            level = "warning"

        if level is None:
            self.stdout.write(
                "Sem alerta a enviar (no caminho ou início do mês)."
            )
            return

        if level == "ok":
            emoji = "🎉"
            title = "Break-even atingido!"
        elif level == "danger":
            emoji = "🚨"
            title = "ATENÇÃO — Break-even em risco"
        else:
            emoji = "⚠"
            title = "Aviso — Ritmo abaixo do necessário"

        lines = [
            f"{emoji} *{title}*",
            f"_Mensal · {first:%d/%m} → {last:%d/%m/%Y}_",
            "",
            f"📊 Atingido: *{d['pct_atingido']:.1f}%* do equilíbrio",
            f"📦 Entregues: *{d['n_delivered']}* / "
            f"{d['pkgs_be'] or '—'} para BE",
            f"💰 Margem contribuição: *€{d['margem_contrib']:.2f}*",
            f"💸 Custos fixos: *€{d['cost_fixed']:.2f}*",
            f"📅 Dias decorridos: {days_elapsed}/{days_total} "
            f"({elapsed_pct:.0f}%)",
            f"🎯 Ritmo: {d['rate_actual']:.0f}/dia · "
            f"precisa {d['rate_needed']:.0f}/dia",
        ]
        if level == "ok":
            extra = d["pct_atingido"] - 100
            if extra > 0:
                lines.append(
                    f"\n✅ {extra:.1f}% acima do equilíbrio. Lucro saudável!"
                )
        elif level == "danger":
            lines.append(
                "\n⚠ Estás a *meio do mês* mas só atingiste menos de "
                "metade do BE. Acção urgente recomendada."
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
                f"Enviado · status={r.status_code} · level={level}"
            ) if ok else self.style.WARNING(
                f"Falha · status={r.status_code}"
            ))
        except Exception as e:
            logger.exception("Erro a enviar BE alert: %s", e)
