"""Refactor PreInvoiceAdvance para conta-corrente do motorista.

- Adiciona FK `driver` (sempre obrigatório no estado final).
- Adiciona campo `status` (PENDENTE/INCLUIDO_PF/CANCELADO).
- Torna `pre_invoice` nullable e on_delete=SET_NULL (lançamento sobrevive
  à cancelação da PF, voltando ao estado PENDENTE).

Backfill: lançamentos existentes copiam `driver` da PF actual e ficam
marcados como `INCLUIDO_PF` (já estão numa PF, por construção).
"""
import django.db.models.deletion
from django.db import migrations, models


def backfill_driver_and_status(apps, schema_editor):
    PreInvoiceAdvance = apps.get_model("settlements", "PreInvoiceAdvance")
    for adv in PreInvoiceAdvance.objects.all().iterator():
        # pre_invoice ainda é NOT NULL nesta etapa
        adv.driver_id = adv.pre_invoice.driver_id
        adv.status = "INCLUIDO_PF"
        adv.save(update_fields=["driver", "status"])


def reverse_backfill(apps, schema_editor):
    # noop — a FK driver é apagada pela AlterField reverse
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("drivers_app", "0001_initial"),
        ("settlements", "0034_shareholder_preinvoiceadvance_paid_by_source_and_more"),
    ]

    operations = [
        # 1. Adicionar driver (nullable temporário)
        migrations.AddField(
            model_name="preinvoiceadvance",
            name="driver",
            field=models.ForeignKey(
                null=True, blank=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="cash_entries",
                to="drivers_app.driverprofile",
                verbose_name="Motorista",
            ),
        ),
        # 2. Adicionar status (default PENDENTE)
        migrations.AddField(
            model_name="preinvoiceadvance",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDENTE", "Pendente"),
                    ("INCLUIDO_PF", "Incluído em PF"),
                    ("CANCELADO", "Cancelado"),
                ],
                db_index=True,
                default="PENDENTE",
                max_length=20,
                verbose_name="Status",
            ),
        ),
        # 3. Backfill: driver = pre_invoice.driver, status='INCLUIDO_PF'
        migrations.RunPython(
            backfill_driver_and_status,
            reverse_code=reverse_backfill,
        ),
        # 4. Tornar driver NOT NULL
        migrations.AlterField(
            model_name="preinvoiceadvance",
            name="driver",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="cash_entries",
                to="drivers_app.driverprofile",
                verbose_name="Motorista",
            ),
        ),
        # 5. Tornar pre_invoice nullable + SET_NULL on delete
        migrations.AlterField(
            model_name="preinvoiceadvance",
            name="pre_invoice",
            field=models.ForeignKey(
                null=True, blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="adiantamentos",
                to="settlements.driverpreinvoice",
                verbose_name="Pré-Fatura (quando incluído)",
            ),
        ),
    ]
