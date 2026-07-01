"""Fecha os extratos periódicos PUDO cujo período termina hoje."""
from django.core.management.base import BaseCommand

from pudo_network.services import emit_due_statements


class Command(BaseCommand):
    help = "Emite os extratos periódicos PUDO devidos hoje (mensal/semanal)."

    def handle(self, *args, **options):
        stmts = emit_due_statements()
        self.stdout.write(
            self.style.SUCCESS(f"{len(stmts)} extrato(s) emitido(s).")
        )
