import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app_api", "0001_initial"),
        ("drivers_app", "0019_driverautoemitconfig"),
    ]

    operations = [
        migrations.CreateModel(
            name="IncidencePacket",
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
                ("barcode", models.CharField(db_index=True, max_length=80, unique=True)),
                ("tracking_number", models.CharField(blank=True, max_length=100)),
                ("client_name", models.CharField(max_length=255)),
                ("address", models.TextField()),
                ("latitude", models.DecimalField(decimal_places=8, default=0, max_digits=10)),
                ("longitude", models.DecimalField(decimal_places=8, default=0, max_digits=11)),
                (
                    "package_image",
                    models.ImageField(blank=True, null=True, upload_to="incidences/%Y/%m/%d/"),
                ),
                ("scanned_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("ocr_data", models.JSONField(blank=True, null=True)),
                ("zone", models.CharField(blank=True, default="", max_length=80)),
                (
                    "driver_profile",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="incidence_packets",
                        to="drivers_app.driverprofile",
                    ),
                ),
            ],
            options={
                "ordering": ["-scanned_at"],
            },
        ),
        migrations.CreateModel(
            name="OcrScanAttempt",
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
                ("qr_code", models.CharField(db_index=True, max_length=120)),
                (
                    "image",
                    models.ImageField(blank=True, null=True, upload_to="ocr_attempts/%Y/%m/%d/"),
                ),
                ("local_raw_text", models.TextField(blank=True, default="")),
                ("server_raw_text", models.TextField(blank=True, default="")),
                ("detected_data", models.JSONField(blank=True, null=True)),
                ("confirmed_data", models.JSONField(blank=True, null=True)),
                ("confidence", models.JSONField(blank=True, null=True)),
                ("was_edited", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "driver_profile",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ocr_scan_attempts",
                        to="drivers_app.driverprofile",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="OcrCorrectionLearning",
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
                    "field_name",
                    models.CharField(
                        choices=[
                            ("recipient_name", "Nome do Destinatario"),
                            ("address", "Endereco"),
                            ("package_code", "Codigo do Pacote"),
                            ("operation_code", "Codigo de Operacao"),
                            ("city", "Cidade"),
                            ("state", "Estado"),
                            ("country", "Pais"),
                            ("postal_code", "Codigo Postal"),
                        ],
                        max_length=50,
                    ),
                ),
                ("original_value", models.TextField()),
                ("corrected_value", models.TextField()),
                ("normalized_original", models.CharField(db_index=True, max_length=500)),
                ("normalized_corrected", models.CharField(db_index=True, max_length=500)),
                ("occurrence_count", models.IntegerField(default=1)),
                ("success_count", models.IntegerField(default=0)),
                ("correction_count", models.IntegerField(default=0)),
                ("score", models.FloatField(default=0.5)),
                ("last_used_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "incidence",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ocr_corrections",
                        to="app_api.incidencepacket",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="incidencepacket",
            index=models.Index(fields=["driver_profile", "scanned_at"], name="app_api_inc_driver__050f89_idx"),
        ),
        migrations.AddIndex(
            model_name="incidencepacket",
            index=models.Index(fields=["zone", "scanned_at"], name="app_api_inc_zone_30f1c0_idx"),
        ),
        migrations.AddIndex(
            model_name="ocrcorrectionlearning",
            index=models.Index(fields=["field_name", "normalized_original"], name="app_api_ocr_field_n_f8f23f_idx"),
        ),
        migrations.AddIndex(
            model_name="ocrcorrectionlearning",
            index=models.Index(fields=["field_name", "score"], name="app_api_ocr_field_n_3117c0_idx"),
        ),
    ]
