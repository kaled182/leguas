"""
Migration 0006:
- Cria PreInvoiceLine (parceiro, pacotes, taxa, dsr por linha)
- Migra dados existentes de DriverPreInvoice para linhas
- Remove campos de entrega de DriverPreInvoice
"""
from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


def _migrate_existing_data(apps, schema_editor):
    """Converte pre-faturas existentes em linhas PreInvoiceLine."""
    DriverPreInvoice = apps.get_model("settlements", "DriverPreInvoice")
    PreInvoiceLine = apps.get_model("settlements", "PreInvoiceLine")

    for pf in DriverPreInvoice.objects.all():
        total_pacotes = getattr(pf, "total_pacotes", 0) or 0
        taxa = getattr(pf, "taxa_por_entrega", Decimal("0.00"))
        taxa = taxa or Decimal("0.00")
        dsr = getattr(pf, "dsr_percentual", Decimal("0.00"))
        dsr = dsr or Decimal("0.00")

        if total_pacotes > 0 or taxa > 0:
            base = Decimal(total_pacotes) * taxa
            dsr_valor = base * (dsr / Decimal("100"))
            PreInvoiceLine.objects.create(
                pre_invoice=pf,
                parceiro=getattr(pf, "parceiro", None),
                courier_id=getattr(pf, "courier_id", "") or "",
                total_pacotes=total_pacotes,
                taxa_por_entrega=taxa,
                dsr_percentual=dsr,
                base_entregas=base + dsr_valor,
            )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
        ("settlements", "0005_add_parceiro_to_preinvoice"),
    ]

    operations = [
        # 1. Criar tabela PreInvoiceLine
        migrations.CreateModel(
            name="PreInvoiceLine",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "pre_invoice",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="linhas",
                        to="settlements.driverpreinvoice",
                        verbose_name="Pre-Fatura",
                    ),
                ),
                (
                    "parceiro",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="core.partner",
                        verbose_name="Parceiro / Operacao",
                    ),
                ),
                (
                    "courier_id",
                    models.CharField(
                        blank=True, max_length=100, verbose_name="Courier ID"
                    ),
                ),
                (
                    "total_pacotes",
                    models.PositiveIntegerField(
                        default=0, verbose_name="Total Pacotes"
                    ),
                ),
                (
                    "taxa_por_entrega",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0.00"),
                        max_digits=8,
                        validators=[
                            django.core.validators.MinValueValidator(0)
                        ],
                        verbose_name="Taxa por Entrega (EUR)",
                    ),
                ),
                (
                    "dsr_percentual",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0.00"),
                        max_digits=5,
                        validators=[
                            django.core.validators.MinValueValidator(0)
                        ],
                        verbose_name="DSR (%)",
                    ),
                ),
                (
                    "base_entregas",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0.00"),
                        editable=False,
                        max_digits=12,
                        verbose_name="Base Entregas (EUR)",
                    ),
                ),
                (
                    "observacoes",
                    models.CharField(
                        blank=True, max_length=300, verbose_name="Observacoes"
                    ),
                ),
                ("api_source", models.CharField(blank=True, max_length=50)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Linha de Trabalho",
                "verbose_name_plural": "Linhas de Trabalho",
                "ordering": ["created_at"],
            },
        ),
        # 2. Migrar dados existentes para linhas
        migrations.RunPython(
            code=_migrate_existing_data,
            reverse_code=migrations.RunPython.noop,
        ),
        # 3. Remover campos de entrega do DriverPreInvoice
        migrations.RemoveField(
            model_name="driverpreinvoice", name="parceiro"
        ),
        migrations.RemoveField(
            model_name="driverpreinvoice", name="courier_id"
        ),
        migrations.RemoveField(
            model_name="driverpreinvoice", name="taxa_por_entrega"
        ),
        migrations.RemoveField(
            model_name="driverpreinvoice", name="total_pacotes"
        ),
        migrations.RemoveField(
            model_name="driverpreinvoice", name="dsr_percentual"
        ),
    ]
