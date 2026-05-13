"""Seed mínimo das tabelas de retenção IRS 2026 (continente).

Valores aproximados baseados nas tabelas oficiais AT 2025 — devem ser
revistos/actualizados em /admin/ pelo gestor. Cobre apenas Tabela I
(Não Casado, sem dependentes) — o admin adiciona as restantes (II-IX)
conforme necessidade.

Cada escalão: (limite_superior, taxa%, parcela_abater).
"""
from decimal import Decimal

from django.db import migrations


# Tabela I — Trabalho Dependente, Não Casado, sem dependentes (2025/26 aprox.)
TABELA_I_2026 = [
    # (limite_superior, taxa %, parcela_abater)
    (Decimal("870.00"),   Decimal("0.00"),  Decimal("0.00")),
    (Decimal("991.00"),   Decimal("13.25"), Decimal("115.28")),
    (Decimal("1070.00"),  Decimal("18.00"), Decimal("162.36")),
    (Decimal("1429.00"),  Decimal("21.00"), Decimal("194.46")),
    (Decimal("1820.00"),  Decimal("26.00"), Decimal("266.91")),
    (Decimal("2350.00"),  Decimal("31.00"), Decimal("367.50")),
    (Decimal("3060.00"),  Decimal("33.00"), Decimal("417.50")),
    (Decimal("4259.00"),  Decimal("36.50"), Decimal("532.55")),
    (Decimal("5687.00"),  Decimal("40.50"), Decimal("702.91")),
    (Decimal("8200.00"),  Decimal("42.00"), Decimal("793.96")),
    (Decimal("99999.99"), Decimal("47.50"), Decimal("1245.83")),
]


def seed_irs(apps, schema_editor):
    IRSTable = apps.get_model("payroll", "IRSTable")
    IRSEscalao = apps.get_model("payroll", "IRSEscalao")

    tabela, _ = IRSTable.objects.get_or_create(
        ano=2026, tabela_id=1,
        defaults={
            "nome": "Trabalho Dependente — Não Casado, sem dependentes",
            "is_active": True,
        },
    )
    if tabela.escaloes.exists():
        return
    for limite, taxa, abater in TABELA_I_2026:
        IRSEscalao.objects.create(
            tabela=tabela,
            limite_superior=limite,
            taxa=taxa,
            parcela_abater=abater,
        )


def unseed_irs(apps, schema_editor):
    IRSTable = apps.get_model("payroll", "IRSTable")
    IRSTable.objects.filter(ano=2026, tabela_id=1).delete()


class Migration(migrations.Migration):
    dependencies = [("payroll", "0001_initial")]
    operations = [migrations.RunPython(seed_irs, unseed_irs)]
