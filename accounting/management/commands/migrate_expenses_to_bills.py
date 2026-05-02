"""Migra registos do modelo legacy `Expenses` para o novo `Bill`.

Mapeamento:
  - natureza (CHOICE) → ExpenseCategory (cria se não existir)
  - fonte → fornecedor (string descritiva)
  - valor_sem_iva / valor_com_iva → amount_net / amount_total
  - data_entrada → issue_date e due_date (assumimos que era pago à vista)
  - pago + data_pagamento → status PAID/PENDING + paid_date
  - documento → BillAttachment (kind=INVOICE)
  - descricao → description (com fallback)
  - cost_center: fixo "GERAL" (default seguro — admin pode ajustar depois)

Uso:
    python manage.py migrate_expenses_to_bills [--dry-run]
"""
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand

from accounting.models import (
    Bill, BillAttachment, CostCenter, ExpenseCategory, Expenses,
)


# Mapa NATUREZA legacy → (code da nova categoria, name, nature DRE)
NATUREZA_MAP = {
    "OPERACIONAL": ("LEG-OP", "Operacional (legacy)", "VARIAVEL"),
    "MARKETING":   ("LEG-MKT", "Marketing", "FIXO"),
    "TECNOLOGIA":  ("TI", None, None),  # já existe
    "PESSOAL":     ("SAL", None, None),  # já existe
    "ALUGUEL":     ("ALU", None, None),  # já existe
    "VIAGEM":      ("LEG-TRV", "Viagens / Hospedagem", "VARIAVEL"),
    "MATERIAL":    ("LEG-MAT", "Material de Escritório", "FIXO"),
    "JURIDICO":    ("JUR", None, None),  # já existe
    "CONTABIL":    ("CONTAB", None, None),  # já existe
    "FINANCEIRO":  ("JUR-F", None, None),  # já existe (juros)
    "MANUTENCAO":  ("MNT", None, None),  # já existe
    "COMBUSTIVEL": ("CMB", None, None),  # já existe
    "SEGURO":      ("SEG", None, None),  # já existe
    "IMPOSTOS":    ("IMP", None, None),  # já existe
    "OUTROS":      ("LEG-OUT", "Outros (legacy)", "VARIAVEL"),
}


class Command(BaseCommand):
    help = "Migra registos legacy de Expenses para o novo modelo Bill."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Mostra o que seria migrado sem persistir.",
        )

    def handle(self, *args, **opts):
        dry = opts["dry_run"]

        # Garantir centro de custo default
        cc_geral, _ = CostCenter.objects.get_or_create(
            code="GERAL",
            defaults={
                "name": "Geral",
                "type": CostCenter.TYPE_GERAL,
            },
        )

        # Pré-criar/garantir categorias
        cat_cache = {}
        for legacy_code, (new_code, new_name, nature) in NATUREZA_MAP.items():
            cat = ExpenseCategory.objects.filter(code=new_code).first()
            if cat is None and new_name:
                cat, _ = ExpenseCategory.objects.get_or_create(
                    code=new_code,
                    defaults={
                        "name": new_name,
                        "nature": nature or "VARIAVEL",
                    },
                )
            cat_cache[legacy_code] = cat
        # Categoria fallback genérica
        cat_default = (
            ExpenseCategory.objects.filter(code="LEG-OUT").first()
            or ExpenseCategory.objects.first()
        )

        legacy_qs = Expenses.objects.all().order_by("data_entrada")
        n_total = legacy_qs.count()
        n_created = 0
        n_skipped = 0

        for exp in legacy_qs:
            # Idempotente: se já existe um Bill com mesma descrição+data+valor
            # do legacy, salta.
            desc_base = (
                exp.descricao or exp.get_natureza_display() or "Despesa legacy"
            )[:200]
            already = Bill.objects.filter(
                description=desc_base,
                amount_total=exp.valor_com_iva,
                issue_date=exp.data_entrada,
            ).exists()
            if already:
                n_skipped += 1
                continue

            cat = cat_cache.get(exp.natureza) or cat_default
            if cat is None:
                self.stdout.write(self.style.WARNING(
                    f"Sem categoria disponível para Expenses #{exp.pk}, skip."
                ))
                n_skipped += 1
                continue

            iva_rate = Decimal("0")
            if exp.valor_sem_iva and exp.valor_sem_iva > 0:
                iva_rate = (
                    (exp.valor_com_iva - exp.valor_sem_iva)
                    / exp.valor_sem_iva * 100
                ).quantize(Decimal("0.01"))

            status = (
                Bill.STATUS_PAID if exp.pago else Bill.STATUS_PENDING
            )
            paid_date = exp.data_pagamento if exp.pago else None
            due_date = exp.data_pagamento or (
                exp.data_entrada + timedelta(days=30)
            )

            if dry:
                self.stdout.write(
                    f"[DRY] {exp.data_entrada} · {desc_base[:40]} "
                    f"· €{exp.valor_com_iva} → cat={cat.code} "
                    f"status={status}"
                )
                n_created += 1
                continue

            bill = Bill.objects.create(
                description=desc_base,
                supplier=exp.get_fonte_display() or "—",
                category=cat,
                cost_center=cc_geral,
                amount_net=exp.valor_sem_iva,
                iva_rate=iva_rate,
                amount_total=exp.valor_com_iva,
                issue_date=exp.data_entrada,
                due_date=due_date,
                paid_date=paid_date,
                status=status,
                notes=(
                    f"[Migrado de Expenses #{exp.pk}] "
                    f"natureza={exp.natureza}, "
                    f"referência={exp.referencia or '—'}\n"
                    f"{exp.descricao or ''}"
                ).strip(),
                created_by=exp.user,
            )
            # Anexo se existir
            if exp.documento and exp.documento.name:
                BillAttachment.objects.create(
                    bill=bill,
                    kind=BillAttachment.KIND_INVOICE,
                    file=exp.documento.name,  # reutiliza path
                    description=f"Migrado de Expenses #{exp.pk}",
                    uploaded_by=exp.user,
                )
            n_created += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nResumo: {n_created} criadas · {n_skipped} skipped "
            f"· {n_total} total Expenses legacy."
        ))
        if dry:
            self.stdout.write(self.style.WARNING(
                "Dry-run: nada foi persistido."
            ))
