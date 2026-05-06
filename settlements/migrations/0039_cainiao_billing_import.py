from decimal import Decimal

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("drivers_app", "0001_initial"),
        ("settlements", "0038_preinvoicenote"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CainiaoBillingImport",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID",
                    ),
                ),
                ("file_name", models.CharField(max_length=255, verbose_name="Nome do Ficheiro")),
                (
                    "file_hash",
                    models.CharField(
                        db_index=True, max_length=64, unique=True,
                        help_text="Bloqueia reimport do mesmo ficheiro (idempotência).",
                        verbose_name="SHA256 do Ficheiro",
                    ),
                ),
                ("period_from", models.DateField(db_index=True, verbose_name="Período Início")),
                ("period_to", models.DateField(db_index=True, verbose_name="Período Fim")),
                ("total_lines", models.PositiveIntegerField(default=0, verbose_name="Total de Linhas")),
                (
                    "total_envio",
                    models.DecimalField(
                        decimal_places=2, default=Decimal("0.00"),
                        max_digits=12, verbose_name="Total Envios (€)",
                    ),
                ),
                (
                    "total_compensacion",
                    models.DecimalField(
                        decimal_places=2, default=Decimal("0.00"),
                        max_digits=12, verbose_name="Total Compensações (€)",
                    ),
                ),
                ("n_billing_ids", models.PositiveIntegerField(default=0, verbose_name="Lotes (billing_id)")),
                ("n_staff_ids", models.PositiveIntegerField(default=0, verbose_name="Motoristas distintos")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PROCESSING", "Em processamento"),
                            ("COMPLETED", "Concluído"),
                            ("FAILED", "Falhou"),
                        ],
                        default="PROCESSING", max_length=20, verbose_name="Estado",
                    ),
                ),
                ("error_message", models.TextField(blank=True, verbose_name="Erro")),
                ("imported_at", models.DateTimeField(auto_now_add=True)),
                (
                    "imported_by",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="cainiao_billing_imports",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "partner_invoice",
                    models.OneToOneField(
                        blank=True, null=True,
                        on_delete=models.deletion.CASCADE,
                        related_name="cainiao_import",
                        to="settlements.partnerinvoice",
                        help_text="PartnerInvoice criada automaticamente com os totais agregados.",
                    ),
                ),
            ],
            options={
                "verbose_name": "Importação Cainiao",
                "verbose_name_plural": "Importações Cainiao",
                "ordering": ["-imported_at"],
                "indexes": [
                    models.Index(
                        fields=["period_from", "period_to"],
                        name="settlement_period__cb_idx",
                    ),
                    models.Index(
                        fields=["status", "-imported_at"],
                        name="settlement_status_imp_idx",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="CainiaoBillingLine",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID",
                    ),
                ),
                (
                    "fee_type",
                    models.CharField(
                        choices=[
                            ("envio fee", "Envio fee"),
                            ("compensacion", "Compensación"),
                        ],
                        db_index=True, max_length=30, verbose_name="Fee Type",
                    ),
                ),
                ("biz_time", models.DateTimeField(db_index=True, verbose_name="Biz Time")),
                ("amount", models.DecimalField(decimal_places=4, max_digits=10, verbose_name="Valor (€)")),
                ("moneda", models.CharField(default="EUR", max_length=10, verbose_name="Moneda")),
                (
                    "waybill_number",
                    models.CharField(
                        db_index=True, max_length=100, verbose_name="Waybill (REFs)",
                    ),
                ),
                ("cp_name", models.CharField(blank=True, max_length=120, verbose_name="CP Name")),
                ("ciudad", models.CharField(blank=True, max_length=120, verbose_name="Cidade")),
                (
                    "staff_id",
                    models.CharField(
                        blank=True, db_index=True, max_length=50,
                        help_text="courier_id_cainiao do motorista que entregou.",
                        verbose_name="Staff ID (Cainiao)",
                    ),
                ),
                (
                    "cainiao_billing_id",
                    models.CharField(
                        blank=True, db_index=True, max_length=50,
                        help_text="ID do lote/corte de facturação Cainiao.",
                        verbose_name="Billing ID Cainiao",
                    ),
                ),
                ("fb1", models.TextField(blank=True, verbose_name="FB1")),
                (
                    "fb2",
                    models.TextField(
                        blank=True,
                        help_text="Razão da compensação (apenas em compensaciones).",
                        verbose_name="FB2 (motivo)",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "import_session",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="lines",
                        to="settlements.cainiaobillingimport",
                    ),
                ),
                (
                    "task",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="billing_lines",
                        to="settlements.cainiaooperationtask",
                        help_text="Task local resolvida pelo waybill_number.",
                    ),
                ),
                (
                    "driver",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="cainiao_billing_lines",
                        to="drivers_app.driverprofile",
                        help_text=(
                            "Driver resolvido por staff_id "
                            "(DriverProfile.courier_id_cainiao ou "
                            "DriverCourierMapping). Para compensaciones com "
                            "staff_id vazio, é resolvido via "
                            "task.courier_id_cainiao."
                        ),
                    ),
                ),
                (
                    "claim",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="cainiao_billing_lines",
                        to="settlements.driverclaim",
                        help_text="DriverClaim criado a partir desta linha (se compensación).",
                    ),
                ),
                (
                    "price_override",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="cainiao_billing_lines",
                        to="settlements.packagepriceoverride",
                        help_text="PackagePriceOverride criado para preço especial (≠ €1.60).",
                    ),
                ),
            ],
            options={
                "verbose_name": "Linha Pré-Fatura Cainiao",
                "verbose_name_plural": "Linhas Pré-Fatura Cainiao",
                "ordering": ["-biz_time"],
                "unique_together": {
                    ("waybill_number", "fee_type", "cainiao_billing_id"),
                },
                "indexes": [
                    models.Index(
                        fields=["fee_type", "-biz_time"],
                        name="settlement_fee_biz_idx",
                    ),
                    models.Index(
                        fields=["staff_id", "-biz_time"],
                        name="settlement_staff_biz_idx",
                    ),
                    models.Index(
                        fields=["cainiao_billing_id"],
                        name="settlement_cn_bil_idx",
                    ),
                    models.Index(
                        fields=["import_session", "fee_type"],
                        name="settlement_imp_fee_idx",
                    ),
                ],
            },
        ),
    ]
