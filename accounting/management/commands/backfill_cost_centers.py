"""Backfill cost_center em registos antigos de Imposto e DriverPreInvoice.

Impostos sem cost_center → CostCenter ADMIN.

DriverPreInvoice sem cost_center → heurística em camadas:
  1. Centro mais frequente em Bills com este motorista (Bill.driver=X)
  2. Hub do task Cainiao mais recente do motorista no período da PF
     (resolvido via zip_code → CainiaoHub.cp4_codes → CostCenter)
  3. Deixa NULL se nada se encontrou

Idempotente: --dry-run para simular sem gravar. --reset reaplica mesmo a
registos que já têm cost_center (útil se a heurística mudou).
"""
from collections import Counter

from django.core.management.base import BaseCommand
from django.db.models import Count

from accounting.models import CostCenter, Imposto


class Command(BaseCommand):
    help = "Preenche cost_center em Impostos e PFs legadas."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Não grava — só mostra o que faria.",
        )
        parser.add_argument(
            "--reset", action="store_true",
            help="Reaplica mesmo a registos que já têm cost_center.",
        )
        parser.add_argument(
            "--only", choices=["impostos", "pfs"], default=None,
            help="Restringe a uma das duas tabelas.",
        )

    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        reset = opts["reset"]
        only = opts["only"]

        self._ensure_admin_cc()

        if only != "pfs":
            self.backfill_impostos(dry, reset)
        if only != "impostos":
            self.backfill_pfs(dry, reset)

    # ── Helpers ────────────────────────────────────────────────────

    def _ensure_admin_cc(self):
        cc = CostCenter.objects.filter(type=CostCenter.TYPE_ADMIN).first()
        if not cc:
            cc, _ = CostCenter.objects.get_or_create(
                code="ADMIN",
                defaults={
                    "name": "Administrativo",
                    "type": CostCenter.TYPE_ADMIN,
                },
            )
            self.stdout.write(self.style.WARNING(
                f"Criado CostCenter ADMIN (id={cc.id})."
            ))
        self.admin_cc = cc

    # ── Impostos ───────────────────────────────────────────────────

    def backfill_impostos(self, dry, reset):
        qs = Imposto.objects.all()
        if not reset:
            qs = qs.filter(cost_center__isnull=True)

        total = qs.count()
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\nImpostos: {total} registo(s) a atualizar"
            + (" [dry-run]" if dry else "")
        ))
        if total == 0:
            return

        # Propaga do pai PARCELADO se disponível, senão ADMIN
        with_parent_cc = 0
        admin_default = 0
        for imp in qs.select_related("parent").iterator():
            target = None
            if imp.parent_id and imp.parent.cost_center_id:
                target = imp.parent.cost_center
                with_parent_cc += 1
            else:
                target = self.admin_cc
                admin_default += 1
            if not dry:
                imp.cost_center = target
                imp.save(update_fields=["cost_center", "updated_at"])

        self.stdout.write(
            f"  · herdados do pai: {with_parent_cc}"
        )
        self.stdout.write(
            f"  · ADMIN default: {admin_default}"
        )

    # ── PFs ────────────────────────────────────────────────────────

    def backfill_pfs(self, dry, reset):
        from settlements.models import DriverPreInvoice
        qs = DriverPreInvoice.objects.all()
        if not reset:
            qs = qs.filter(cost_center__isnull=True)

        total = qs.count()
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\nDriverPreInvoice: {total} registo(s) a inferir"
            + (" [dry-run]" if dry else "")
        ))
        if total == 0:
            return

        # Cache mapeamento CP4→CostCenter para evitar N+1
        cp4_to_cc = self._build_cp4_to_cc_map()

        stats = Counter()
        for pf in qs.select_related("driver").iterator():
            cc = self._infer_cc_for_pf(pf, cp4_to_cc)
            if cc is None:
                stats["nao_inferido"] += 1
                continue
            stats["inferido"] += 1
            if not dry:
                pf.cost_center = cc
                pf.save(update_fields=["cost_center"])

        self.stdout.write(f"  · inferido: {stats['inferido']}")
        self.stdout.write(self.style.WARNING(
            f"  · sem inferência (mantido NULL): {stats['nao_inferido']}"
        ))

    def _build_cp4_to_cc_map(self):
        try:
            from settlements.models import CainiaoHub
        except ImportError:
            return {}
        mapping = {}
        for hub in CainiaoHub.objects.prefetch_related("cp4_codes"):
            cc = CostCenter.objects.filter(cainiao_hub=hub).first()
            if not cc:
                continue
            for cp4 in hub.cp4_codes.values_list("cp4", flat=True):
                mapping[cp4] = cc
        return mapping

    def _infer_cc_for_pf(self, pf, cp4_to_cc):
        """Heurística em camadas para encontrar o centro de custo de uma PF."""
        if not pf.driver_id:
            return None

        # 1. Centro mais frequente nas Bills do motorista
        try:
            from accounting.models import Bill
            bill_cc_id = (
                Bill.all_objects
                .filter(driver_id=pf.driver_id, cost_center__isnull=False)
                .values("cost_center")
                .annotate(n=Count("id")).order_by("-n")
                .values_list("cost_center", flat=True).first()
            )
            if bill_cc_id:
                return CostCenter.objects.filter(pk=bill_cc_id).first()
        except Exception:
            pass

        # 2. Hub do task Cainiao mais recente do motorista no período.
        #    CainiaoOperationTask não tem FK directa ao DriverProfile —
        #    liga via DriverCourierMapping.courier_id.
        try:
            from settlements.models import (
                CainiaoOperationTask, DriverCourierMapping,
            )
            courier_ids = list(
                DriverCourierMapping.objects
                .filter(driver_id=pf.driver_id)
                .values_list("courier_id", flat=True)
            )
            if courier_ids:
                tasks = (
                    CainiaoOperationTask.objects
                    .filter(
                        courier_id_cainiao__in=courier_ids,
                        task_status="Delivered",
                        task_date__gte=pf.periodo_inicio,
                        task_date__lte=pf.periodo_fim,
                    )
                    .exclude(zip_code="")
                    .values_list("zip_code", flat=True)[:500]
                )
                cp4_counter = Counter()
                for zc in tasks:
                    if not zc:
                        continue
                    cp4 = zc[:4]
                    cc = cp4_to_cc.get(cp4)
                    if cc:
                        cp4_counter[cc.id] += 1
                if cp4_counter:
                    top_cc_id = cp4_counter.most_common(1)[0][0]
                    return CostCenter.objects.filter(pk=top_cc_id).first()
        except Exception:
            pass

        return None
