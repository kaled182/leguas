"""Decisão C2 (opção A, 2026-10-26): copia o preço individual do motorista
(price_per_package) para "valor negociado" nos CP onde entregou.

Só copia quando o preço individual é MAIOR do que a tarifa padrão do CP
(coluna mensal): ninguém perde com a regra nova e quem ganha com a
tarifa (ex.: Porto 1,10 €) fica com a tarifa. Não altera valores
negociados que já existam. Seleciona o CP e o hub na ficha se ainda não
estiverem; o hub com mais entregas fica principal se não houver nenhum.

Uso: python manage.py copy_individual_price_to_cp [--dry-run] [--days 60]
"""
from collections import Counter, defaultdict
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count
from django.db.models.functions import Substr
from django.utils import timezone


class Command(BaseCommand):
    help = "Copia o preço individual para valor negociado nos CP onde o motorista entregou."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--days", type=int, default=60)

    def handle(self, *args, **opts):
        from contracts.models import ContractSettings, HubZoneTariff

        from drivers_app.models import DriverHubAssignment, DriverProfile, DriverProfileEditLog
        from drivers_app.portal_views import _driver_base_queryset

        today = timezone.localdate()
        since = today - timedelta(days=opts["days"])
        settings = ContractSettings.get()
        # Tarifa mensal em vigor por CP (a mais recente) e o seu hub.
        tariffs = {}
        for t in HubZoneTariff.objects.filter(is_active=True, valid_from__lte=today).order_by("valid_from"):
            tariffs[t.cp4] = t

        total_set = 0
        for d in DriverProfile.objects.filter(price_per_package__gt=0).order_by("nome_completo"):
            price = Decimal(d.price_per_package).quantize(Decimal("0.01"))
            cps = Counter()
            for r in (
                _driver_base_queryset(d, since, today).filter(task_status="Delivered")
                .annotate(cp=Substr("zip_code", 1, 4)).values("cp").annotate(n=Count("id"))
            ):
                if r["cp"]:
                    cps[r["cp"]] += r["n"]
            by_hub = defaultdict(dict)   # hub_id → {cp: preço}
            hub_volume = Counter()
            kept, skipped = [], []
            for cp, n in cps.items():
                t = tariffs.get(cp)
                if not t:
                    continue
                hub_volume[t.hub_id] += n
                std = t.price_for("MENSAL", settings).quantize(Decimal("0.01"))
                if price > std:
                    by_hub[t.hub_id][cp] = str(price)
                    kept.append(f"{cp} ({n}) {std}→{price}")
                else:
                    skipped.append(f"{cp} ({n}) fica {std}")
            if not kept and not skipped:
                continue
            self.stdout.write(
                f"{d.id:>4} {d.nome_completo[:30]:<30} preço {price} € · copia: "
                f"{', '.join(kept) or '—'} · tarifa: {', '.join(skipped) or '—'}"
            )
            if opts["dry_run"] or not by_hub:
                total_set += sum(len(v) for v in by_hub.values())
                continue
            with transaction.atomic():
                changes = []
                has_primary = d.hub_assignments.filter(is_primary=True).exists()
                main_hub = hub_volume.most_common(1)[0][0] if hub_volume else None
                for hub_id, prices in by_hub.items():
                    a, _ = DriverHubAssignment.objects.get_or_create(driver=d, hub_id=hub_id)
                    cp4s = set(a.cp4s or [])
                    cp_prices = dict(a.cp_prices or {})
                    for cp, val in prices.items():
                        cp4s.add(cp)
                        if cp not in cp_prices:
                            cp_prices[cp] = val
                            changes.append(f"{cp}={val}€")
                            total_set += 1
                    a.cp4s = sorted(cp4s)
                    a.cp_prices = cp_prices
                    if not has_primary and hub_id == main_hub:
                        a.is_primary = True
                    a.save()
                if changes:
                    DriverProfileEditLog.objects.create(
                        driver=d, user=None, section="hubs",
                        changes={"valor negociado (C2)": [
                            f"preço individual {price} €", ", ".join(changes),
                        ]},
                    )
        verb = "a criar" if opts["dry_run"] else "criados"
        self.stdout.write(f"Valores negociados {verb}: {total_set}.")
