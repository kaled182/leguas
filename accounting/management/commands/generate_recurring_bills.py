"""Gera próximas instâncias de Bills recorrentes.

Para cada Bill que é template (recurrence != NONE e parent is None),
verifica se a próxima instância na cadeia já foi criada. Se não, cria.

Uso manual:
    python manage.py generate_recurring_bills
    python manage.py generate_recurring_bills --lookahead-days 7

Schedule (Celery beat): correr 1× ao dia.
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand

from accounting.models import Bill


class Command(BaseCommand):
    help = "Gera próximas instâncias de contas a pagar recorrentes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--lookahead-days", type=int, default=7,
            help=(
                "Janela em dias para gerar instâncias futuras "
                "(default 7). Só gera se a próxima due_date "
                "estiver dentro deste horizonte."
            ),
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Mostra o que seria gerado, mas não persiste.",
        )

    def handle(self, *args, **opts):
        lookahead = opts["lookahead_days"]
        dry = opts["dry_run"]
        cutoff = date.today() + timedelta(days=lookahead)

        templates = Bill.objects.filter(
            parent__isnull=True,
        ).exclude(recurrence=Bill.RECURRENCE_NONE)

        n_created = 0
        n_skipped = 0
        for tpl in templates:
            next_due = tpl.next_due_date()
            if not next_due:
                continue
            if next_due > cutoff:
                # Ainda longe — não geramos
                n_skipped += 1
                continue
            already = Bill.objects.filter(
                parent=tpl, due_date=next_due,
            ).exists()
            if already:
                n_skipped += 1
                continue
            if dry:
                self.stdout.write(
                    f"[DRY] Iria gerar: {tpl.description} "
                    f"due={next_due} (template #{tpl.pk})"
                )
                n_created += 1
                continue
            new_bill = tpl.generate_next_instance()
            if new_bill:
                self.stdout.write(self.style.SUCCESS(
                    f"+ {new_bill.description} "
                    f"due={new_bill.due_date} (#{new_bill.pk})"
                ))
                n_created += 1
            else:
                n_skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nResumo: {n_created} geradas, {n_skipped} skipped, "
            f"{templates.count()} templates totais."
        ))
