from decimal import Decimal

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("drivers_app", "0004_empresa_parceira"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EmpresaParceiraLancamento",
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
                    "descricao",
                    models.CharField(max_length=300, verbose_name="Descrição do Serviço"),
                ),
                (
                    "valor_base",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0.00"),
                        max_digits=12,
                        verbose_name="Valor Base (€)",
                    ),
                ),
                (
                    "valor_bonus",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0.00"),
                        max_digits=12,
                        verbose_name="Valor Bónus (€)",
                    ),
                ),
                (
                    "periodo_inicio",
                    models.DateField(db_index=True, verbose_name="Período Início"),
                ),
                ("periodo_fim", models.DateField(verbose_name="Período Fim")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("RASCUNHO", "Rascunho"),
                            ("APROVADO", "Aprovado"),
                            ("PENDENTE", "Pendente Pagamento"),
                            ("PAGO", "Pago"),
                            ("CANCELADO", "Cancelado"),
                        ],
                        db_index=True,
                        default="RASCUNHO",
                        max_length=20,
                    ),
                ),
                ("notas", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="lancamentos_criados",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "empresa",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lancamentos",
                        to="drivers_app.empresaparceira",
                        verbose_name="Empresa Parceira",
                    ),
                ),
            ],
            options={
                "verbose_name": "Lançamento Manual",
                "verbose_name_plural": "Lançamentos Manuais",
                "ordering": ["-periodo_inicio"],
            },
        ),
    ]
