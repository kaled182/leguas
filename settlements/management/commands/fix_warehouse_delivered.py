"""Corrige tasks com warehouse courier registado como Delivered/Failure.

Warehouse (XPT, HUB, ARMAZEM, etc.) só recebe e transfere — nunca entrega.
Se a Cainiao reportou XPT-Delivered erradamente, a task fica com:
  task_status=Delivered, courier_name=ARMAZEM XPT...

Este comando:
  1. Identifica todas as tasks (warehouse + Delivered/Attempt Failure).
  2. Tenta resolver o courier real via CainiaoOperationTaskHistory:
     procura signature posterior por driver não-warehouse no mesmo
     waybill/dia. Se houver, atribui esse courier à task.
  3. Caso não haja driver real no histórico, rebaixa o status para
     Driver_received (warehouse pode receber, não entregar).

Uso:
  python manage.py fix_warehouse_delivered           # dry-run
  python manage.py fix_warehouse_delivered --apply   # aplica
"""
from django.core.management.base import BaseCommand
from django.db.models import Q

WAREHOUSE_KEYWORDS = (
    "ARMAZEM", "ARMAZÉM", "HUB", "WAREHOUSE",
    "DEPOSITO", "DEPÓSITO", "CENTRO_OPERACIONAL",
)


def is_warehouse(name):
    if not name:
        return True
    upper = name.upper()
    return any(kw in upper for kw in WAREHOUSE_KEYWORDS)


class Command(BaseCommand):
    help = "Corrige tasks com warehouse marcado como Delivered/Failure."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply", action="store_true",
            help="Aplica as mudanças. Sem este flag corre em dry-run.",
        )

    def handle(self, *args, **opts):
        from settlements.models import (
            CainiaoOperationTask, CainiaoOperationTaskHistory,
        )

        apply = opts["apply"]

        # Construir filtro warehouse
        warehouse_q = Q()
        for kw in WAREHOUSE_KEYWORDS:
            warehouse_q |= Q(courier_name__icontains=kw)

        # 1. Tasks alvo: warehouse + Delivered/Failure
        target_qs = CainiaoOperationTask.objects.filter(
            warehouse_q,
            task_status__in=["Delivered", "Attempt Failure"],
        )
        total = target_qs.count()
        self.stdout.write(self.style.WARNING(
            f"Tasks warehouse com Delivered/Failure: {total}"
        ))

        n_replaced = 0
        n_downgraded = 0

        for t in target_qs.iterator(chunk_size=500):
            # 2. Procurar signature posterior por driver real
            real_signature = (
                CainiaoOperationTaskHistory.objects
                .filter(
                    waybill_number=t.waybill_number,
                    task_date=t.task_date,
                    change_type="signature",
                )
                .exclude(courier_name="")
                .order_by("-recorded_at")
            )

            chosen = None
            for sig in real_signature:
                if not is_warehouse(sig.courier_name):
                    chosen = sig
                    break

            if chosen:
                if apply:
                    t.courier_name = chosen.courier_name
                    if chosen.courier_id_cainiao:
                        t.courier_id_cainiao = chosen.courier_id_cainiao
                    t.save(update_fields=[
                        "courier_name", "courier_id_cainiao", "updated_at",
                    ])
                n_replaced += 1
                self.stdout.write(
                    f"  REPLACE wb={t.waybill_number} "
                    f"{t.courier_name!r} → {chosen.courier_name!r} "
                    f"(status={t.task_status})"
                )
            else:
                # 3. Sem driver real no histórico → downgrade status
                if apply:
                    t.task_status = "Driver_received"
                    t.save(update_fields=["task_status", "updated_at"])
                n_downgraded += 1
                if n_downgraded <= 10:
                    self.stdout.write(
                        f"  DOWNGRADE wb={t.waybill_number} "
                        f"courier={t.courier_name!r} "
                        f"{t.task_status} → Driver_received"
                    )

        self.stdout.write(self.style.SUCCESS(
            f"\nResumo:"
        ))
        self.stdout.write(f"  Substituídos por driver real: {n_replaced}")
        self.stdout.write(f"  Status rebaixado a Driver_received: {n_downgraded}")
        if not apply:
            self.stdout.write(self.style.WARNING(
                "\nDRY-RUN — corre com --apply para aplicar."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                "\n✓ Aplicado."
            ))
