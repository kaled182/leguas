"""Prepara/drena a fila de reconciliação a montante das devoluções PUDO."""
from django.core.management.base import BaseCommand

from pudo_network.services import process_upstream_reconciliations


class Command(BaseCommand):
    help = "Prepara (e envia, quando houver spec) as devoluções PUDO a montante."

    def handle(self, *args, **options):
        preparados, enviados = process_upstream_reconciliations()
        self.stdout.write(
            self.style.SUCCESS(
                f"{preparados} preparado(s), {enviados} enviado(s)."
            )
        )
