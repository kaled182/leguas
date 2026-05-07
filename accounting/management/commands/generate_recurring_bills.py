"""Gera próximas instâncias de Bills recorrentes.

Dois mecanismos complementares:

  1. **Templates de Bill** (legacy) — Bill com recurrence != NONE e
     parent=None gera Bill filha (parent=template) na próxima due_date.
     Usado quando se quer um modelo concreto que se repete (mesmo valor,
     mesma descrição).

  2. **Fornecedor recorrente** (novo) — Fornecedor activo com
     recorrencia_default ≠ PONTUAL e dia_vencimento preenchido gera Bill
     standalone (parent=None) em AWAITING com amount_net=0/amount_total=0.
     O operador preenche o valor real ao receber a fatura. Usado para
     contas regulares de valor variável (combustível, internet variável).

Uso manual:
    python manage.py generate_recurring_bills
    python manage.py generate_recurring_bills --lookahead-days 7
    python manage.py generate_recurring_bills --skip-fornecedor

Schedule (Celery beat): correr 1× ao dia.
"""
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from accounting.models import Bill, CostCenter, ExpenseCategory, Fornecedor


def _add_months(d: date, months: int) -> date:
    """Soma meses preservando o dia (ajusta se for fim de mês)."""
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    last_day = monthrange(y, m)[1]
    return date(y, m, min(d.day, last_day))


def _next_occurrence_of_day(dia: int, today: date) -> date:
    """Próxima data com 'dia' a partir de hoje (este mês ou seguinte)."""
    last_this = monthrange(today.year, today.month)[1]
    candidate = date(today.year, today.month, min(dia, last_this))
    if candidate >= today:
        return candidate
    nm = today.month + 1
    ny = today.year + (1 if nm > 12 else 0)
    nm = ((nm - 1) % 12) + 1
    last_next = monthrange(ny, nm)[1]
    return date(ny, nm, min(dia, last_next))


_PERIOD_MONTHS = {
    Fornecedor.RECORRENCIA_MENSAL: 1,
    Fornecedor.RECORRENCIA_TRIMESTRAL: 3,
    Fornecedor.RECORRENCIA_SEMESTRAL: 6,
    Fornecedor.RECORRENCIA_ANUAL: 12,
}
_BILL_RECURRENCE_MAP = {
    Fornecedor.RECORRENCIA_MENSAL: Bill.RECURRENCE_MONTHLY,
    Fornecedor.RECORRENCIA_TRIMESTRAL: Bill.RECURRENCE_QUARTERLY,
    Fornecedor.RECORRENCIA_SEMESTRAL: Bill.RECURRENCE_QUARTERLY,
    Fornecedor.RECORRENCIA_ANUAL: Bill.RECURRENCE_YEARLY,
}


class Command(BaseCommand):
    help = "Gera próximas instâncias de contas a pagar recorrentes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--lookahead-days", type=int, default=7,
            help=(
                "Janela em dias para gerar instâncias futuras "
                "(default 7). Só gera se a próxima due_date "
                "estiver dentro deste horizonte."
            ),
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Mostra o que seria gerado, mas não persiste.",
        )
        parser.add_argument(
            "--skip-templates", action="store_true",
            help="Pula geração via templates Bill (legacy).",
        )
        parser.add_argument(
            "--skip-fornecedor", action="store_true",
            help="Pula geração via Fornecedor recorrente.",
        )

    def handle(self, *args, **opts):
        lookahead = opts["lookahead_days"]
        dry = opts["dry_run"]
        cutoff = date.today() + timedelta(days=lookahead)

        if not opts["skip_templates"]:
            self._run_templates(cutoff, dry)
        if not opts["skip_fornecedor"]:
            self._run_fornecedor(cutoff, dry)

    def _run_templates(self, cutoff: date, dry: bool):
        """Mecanismo legacy: Bills templates com parent=None."""
        templates = Bill.objects.filter(
            parent__isnull=True,
        ).exclude(recurrence=Bill.RECURRENCE_NONE)

        n_created = 0
        n_skipped = 0
        for tpl in templates:
            next_due = tpl.next_due_date()
            if not next_due:
                continue
            if next_due > cutoff:
                # Ainda longe — não geramos
                n_skipped += 1
                continue
            already = Bill.objects.filter(
                parent=tpl, due_date=next_due,
            ).exists()
            if already:
                n_skipped += 1
                continue
            if dry:
                self.stdout.write(
                    f"[DRY] Iria gerar: {tpl.description} "
                    f"due={next_due} (template #{tpl.pk})"
                )
                n_created += 1
                continue
            new_bill = tpl.generate_next_instance()
            if new_bill:
                self.stdout.write(self.style.SUCCESS(
                    f"+ {new_bill.description} "
                    f"due={new_bill.due_date} (#{new_bill.pk})"
                ))
                n_created += 1
            else:
                n_skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f"[templates] {n_created} geradas, {n_skipped} skipped, "
            f"{templates.count()} templates totais."
        ))

    def _run_fornecedor(self, cutoff: date, dry: bool):
        """Mecanismo novo: gera Bills standalone a partir do cadastro do
        Fornecedor (recorrencia_default + dia_vencimento). Bill criada
        com amount=0 — operador preenche valor real ao receber a fatura.
        """
        today = date.today()
        qs = Fornecedor.objects.filter(
            is_active=True, dia_vencimento__isnull=False,
        ).exclude(recorrencia_default=Fornecedor.RECORRENCIA_PONTUAL)

        n_created = 0
        n_skipped = 0
        n_total = qs.count()
        for f in qs:
            months = _PERIOD_MONTHS.get(f.recorrencia_default)
            if not months:
                n_skipped += 1
                continue

            last = (
                Bill.objects.filter(fornecedor=f)
                .order_by("-due_date").first()
            )
            if last:
                next_due = _add_months(last.due_date, months)
            else:
                next_due = _next_occurrence_of_day(f.dia_vencimento, today)

            if next_due > cutoff:
                n_skipped += 1
                continue

            if Bill.objects.filter(fornecedor=f, due_date=next_due).exists():
                n_skipped += 1
                continue

            if dry:
                self.stdout.write(
                    f"[DRY/forn] criaria Bill: {f.name} venc {next_due}"
                )
                n_created += 1
                continue

            cat = f.default_categoria
            cc = f.default_centro_custo
            if not cat:
                cat, _ = ExpenseCategory.objects.get_or_create(
                    code="REC",
                    defaults={
                        "name": "Recorrente (auto)",
                        "nature": ExpenseCategory.NATURE_FIXO,
                        "icon": "repeat",
                        "sort_order": 90,
                    },
                )
            if not cc:
                cc = (
                    CostCenter.objects.filter(
                        type=CostCenter.TYPE_GERAL,
                    ).first()
                )
                if not cc:
                    cc, _ = CostCenter.objects.get_or_create(
                        code="GERAL",
                        defaults={
                            "name": "Geral",
                            "type": CostCenter.TYPE_GERAL,
                        },
                    )

            with transaction.atomic():
                Bill.objects.create(
                    description=(
                        f"[Auto] {f.name} — "
                        f"{f.get_recorrencia_default_display()} "
                        f"{next_due.strftime('%m/%Y')}"
                    ),
                    fornecedor=f,
                    supplier=f.name,
                    supplier_nif=f.nif,
                    category=cat,
                    cost_center=cc,
                    amount_net=Decimal("0.00"),
                    iva_rate=f.default_iva_rate,
                    amount_total=Decimal("0.00"),
                    issue_date=next_due,
                    due_date=next_due,
                    status=Bill.STATUS_AWAITING,
                    recurrence=_BILL_RECURRENCE_MAP.get(
                        f.recorrencia_default, Bill.RECURRENCE_NONE,
                    ),
                    notes=(
                        "Conta gerada automaticamente pelo gerador de "
                        "recorrência. Preenche o valor real ao receber a "
                        f"fatura. Origem: Fornecedor #{f.pk} "
                        f"({f.get_recorrencia_default_display()}, "
                        f"dia {f.dia_vencimento})."
                    ),
                )
            self.stdout.write(
                f"+ [forn] {f.name} venc {next_due}"
            )
            n_created += 1

        self.stdout.write(self.style.SUCCESS(
            f"[fornecedor] {n_created} geradas, {n_skipped} skipped, "
            f"{n_total} fornecedores recorrentes activos."
        ))
