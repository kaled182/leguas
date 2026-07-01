"""Corre o aging da Rede PUDO manualmente (mesma lógica da task Celery)."""
from django.core.management.base import BaseCommand

from pudo_network.services import mark_expired_packages


class Command(BaseCommand):
    help = "Marca como EXPIRADO os pacotes PUDO cujo prazo de levantamento venceu."

    def handle(self, *args, **options):
        n = mark_expired_packages()
        self.stdout.write(self.style.SUCCESS(f"{n} pacote(s) marcados EXPIRADO."))
