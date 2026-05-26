from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "0015_banktransaction_matched_partner_pf"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AccountingPeriodLock",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                )),
                ("year", models.PositiveSmallIntegerField(
                    db_index=True, verbose_name="Ano",
                )),
                ("month", models.PositiveSmallIntegerField(
                    db_index=True, verbose_name="Mês",
                )),
                ("is_locked", models.BooleanField(
                    db_index=True, default=True, verbose_name="Fechado",
                )),
                ("locked_at", models.DateTimeField(
                    blank=True, null=True, verbose_name="Fechado em",
                )),
                ("unlocked_at", models.DateTimeField(
                    blank=True, null=True, verbose_name="Reaberto em",
                )),
                ("notes", models.TextField(blank=True, verbose_name="Notas")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("locked_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="periods_locked",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("unlocked_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="periods_unlocked",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "verbose_name": "Fecho de Período",
                "verbose_name_plural": "Fechos de Período",
                "ordering": ["-year", "-month"],
            },
        ),
        migrations.AddIndex(
            model_name="accountingperiodlock",
            index=models.Index(
                fields=["is_locked", "year", "month"],
                name="accounting__is_lock_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="accountingperiodlock",
            constraint=models.UniqueConstraint(
                fields=("year", "month"),
                name="accounting_period_year_month_uniq",
            ),
        ),
    ]
