import csv
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from ordersmanager_paack.models import Driver
from settlements.models import SettlementRun
from datetime import datetime

class Command(BaseCommand):
    help = "Importa fechos (planilha)."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str)
        parser.add_argument("--client", type=str, default="Paack")
        parser.add_argument("--delimiter", type=str, default=";")
        parser.add_argument("--date-format", type=str, default="%Y-%m-%d")

    def handle(self, *args, **opts):
        path = opts["csv_path"]; client = opts["client"]
        delim = opts["delimiter"]; date_fmt = opts["date_format"]

        def to_int(x):
            x = (x or "").strip()
            digits = "".join(ch for ch in x if ch.isdigit())
            return int(digits or "0")

        def to_money(x):
            x = (x or "").strip().replace(".", "").replace(",", ".")
            try: return float(x)
            except: return 0.0

        with open(path, newline="", encoding="utf-8") as f, transaction.atomic():
            r = csv.DictReader(f, delimiter=delim)
            total = 0
            for row in r:
                motorista = (row.get("motorista") or row.get("driver") or "").strip()
                if not motorista:
                    raise CommandError("Coluna 'motorista' obrigatória")

                driver, _ = Driver.objects.get_or_create(name=motorista, defaults={
                    "driver_id": motorista, "vehicle": "", "vehicle_norm": ""
                })

                area   = (row.get("area") or "").strip() or None
                data_s = (row.get("data") or row.get("date") or "").strip()
                run_date = datetime.strptime(data_s, date_fmt).date()

                SettlementRun.objects.update_or_create(
                    driver=driver, run_date=run_date, client=client, area_code=area,
                    defaults=dict(
                        qtd_saida=to_int(row.get("qtd_saida")),
                        qtd_pact=to_int(row.get("qtd_pact")),
                        qtd_entregue=to_int(row.get("entregue")),
                        vl_pct=to_money(row.get("vl_pct")),
                        gasoleo=to_money(row.get("gasoleo")),
                        desconto_tickets=to_money(row.get("desc_tickets") or row.get("desconto_tickets")),
                        rec_liq_tickets=to_money(row.get("recl_dec_tickets") or row.get("rec_liq_tickets")),
                        outros=to_money(row.get("outros") or row.get("sum_of_outros")),
                        notes=row.get("notes") or None,
                    )
                )
                total += 1
        self.stdout.write(self.style.SUCCESS(f"Importados {total} registros ({client})."))
