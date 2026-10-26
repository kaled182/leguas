"""Preenche data_prevista_pagamento nas PF que ainda não a têm.

Uso: python manage.py fill_expected_payment_dates [--all]
  --all  recalcula também as que já têm data (ex.: depois de mudar
         as condições de um hub).
"""
from django.core.management.base import BaseCommand

from drivers_app.services_payments import expected_for_pf


class Command(BaseCommand):
    help = "Preenche a data prevista de pagamento das pré-faturas."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true")

    def handle(self, *args, **opts):
        from settlements.models import DriverPreInvoice

        qs = DriverPreInvoice.objects.select_related("driver")
        if not opts["all"]:
            qs = qs.filter(data_prevista_pagamento__isnull=True)
        n = 0
        for pf in qs.iterator():
            d = expected_for_pf(pf)
            if d and d != pf.data_prevista_pagamento:
                DriverPreInvoice.objects.filter(pk=pf.pk).update(data_prevista_pagamento=d)
                n += 1
        self.stdout.write(f"{n} pré-faturas actualizadas.")
