from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "0014_imposto_cost_center"),
        ("settlements", "0048_driverpreinvoice_cost_center"),
    ]

    operations = [
        migrations.AddField(
            model_name="banktransaction",
            name="matched_partner_invoice",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="bank_transactions",
                to="settlements.partnerinvoice",
                verbose_name="Fatura de parceiro conciliada",
            ),
        ),
        migrations.AddField(
            model_name="banktransaction",
            name="matched_pf",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="bank_transactions",
                to="settlements.driverpreinvoice",
                verbose_name="Pré-fatura conciliada",
            ),
        ),
    ]
