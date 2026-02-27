import csv
from django.core.management.base import BaseCommand
from datetime import datetime
from settlements.services import compute_payouts

class Command(BaseCommand):
    help = "Exporta CSV de payouts por motorista no período."

    def add_arguments(self, parser):
        parser.add_argument("--from", dest="from_date", required=True, help="YYYY-MM-DD")
        parser.add_argument("--to", dest="to_date", required=True, help="YYYY-MM-DD")
        parser.add_argument("--client", dest="client", default=None)
        parser.add_argument("--area", dest="area", default=None)
        parser.add_argument("--out", dest="outfile", default="payouts.csv")

    def handle(self, *args, **opts):
        pf = datetime.strptime(opts["from_date"], "%Y-%m-%d").date()
        pt = datetime.strptime(opts["to_date"], "%Y-%m-%d").date()
        data = compute_payouts(pf, pt, opts["client"], opts["area"])

        with open(opts["outfile"], "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["driver","period_from","period_to","entregues","bruto_pkg","bonus","fixo","bruto_total","descontos","liquido","media_liq_por_pacote"])
            for r in data:
                w.writerow([r["driver"], r["period_from"], r["period_to"], r["entregues"], r["bruto_pkg"], r["bonus"], r["fixo"], r["bruto_total"], r["descontos"], r["liquido"], r["media_liq_por_pacote"]])

        self.stdout.write(self.style.SUCCESS(f"Exportado {len(data)} registros para {opts['outfile']}"))
