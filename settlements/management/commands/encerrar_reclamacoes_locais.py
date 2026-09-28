"""Encerra as reclamações locais abertas: passam a ser geridas no ReliableMaps.

O desconto, quando houver, nasce do julgamento da Cainiao (sync_claim_verdicts).
Por omissão só conta; --gravar aplica. Não cria nem mexe em DriverClaim.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

OPEN_STATUSES = ("ABERTO", "NOTIFICADO", "RESPONDIDO")
NOTE = "Encerrada sem desconto: reclamações geridas no ReliableMaps; o desconto vem do julgamento da Cainiao."


class Command(BaseCommand):
    help = "Encerra (CANCELADO) as reclamações locais abertas, sem criar descontos."

    def add_arguments(self, parser):
        parser.add_argument("--gravar", action="store_true", help="Aplica (sem isto só conta).")

    def handle(self, *args, **opts):
        from collections import Counter

        from drivers_app.models import CustomerComplaint

        qs = CustomerComplaint.objects.filter(status__in=OPEN_STATUSES)
        by_status = Counter(qs.values_list("status", flat=True))
        self.stdout.write(f"Abertas: {sum(by_status.values())} {dict(by_status)}")
        if not opts["gravar"]:
            self.stdout.write("Só contagem. Corre com --gravar para encerrar.")
            return
        now = timezone.now()
        n = 0
        for c in qs:
            c.status = "CANCELADO"
            c.data_fecho = now
            c.notas = f"{c.notas}\n{NOTE}".strip()
            c.save(update_fields=["status", "data_fecho", "notas", "updated_at"])
            n += 1
        self.stdout.write(self.style.SUCCESS(f"Encerradas: {n}"))
