"""Teste de saúde do celery beat (docker healthcheck).

Falha (exit 1) se nenhuma tarefa periódica correu nos últimos
--max-minutes minutos. A tarefa cainiao-sync-claim-verdicts-reliable
corre de hora a hora, 24 h por dia, por isso 120 min tem margem.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Max
from django.utils import timezone


class Command(BaseCommand):
    help = "Verifica se o celery beat está a disparar tarefas."

    def add_arguments(self, parser):
        parser.add_argument("--max-minutes", type=int, default=120)

    def handle(self, *args, **opts):
        from django_celery_beat.models import PeriodicTask

        last = PeriodicTask.objects.filter(enabled=True).aggregate(m=Max("last_run_at"))["m"]
        if last is None:
            raise CommandError("Nenhuma tarefa periódica correu ainda.")
        age = timezone.now() - last
        if age > timedelta(minutes=opts["max_minutes"]):
            raise CommandError(f"Última tarefa há {int(age.total_seconds() // 60)} min.")
        self.stdout.write(f"OK: última tarefa há {int(age.total_seconds() // 60)} min.")
