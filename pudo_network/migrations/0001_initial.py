from decimal import Decimal

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("core", "0006_partner_pudo_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PudoStore",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("numero", models.CharField(db_index=True, editable=False, help_text="Identidade do PUDO (ex.: PUDO-0001). Gerado automaticamente.", max_length=20, unique=True, verbose_name="Número PUDO")),
                ("nome", models.CharField(help_text="Apenas descritivo/enriquecimento. A identidade é o número.", max_length=200, verbose_name="Nome (descritivo)")),
                ("nif", models.CharField(blank=True, max_length=20, verbose_name="NIF")),
                ("morada", models.TextField(blank=True, verbose_name="Morada")),
                ("codigo_postal", models.CharField(blank=True, max_length=8, verbose_name="Código Postal")),
                ("cidade", models.CharField(blank=True, max_length=100, verbose_name="Cidade")),
                ("email", models.EmailField(blank=True, max_length=254, verbose_name="Email")),
                ("telefone", models.CharField(blank=True, max_length=20, verbose_name="Telefone")),
                ("contacto_nome", models.CharField(blank=True, max_length=150, verbose_name="Nome do Contacto")),
                ("iban", models.CharField(blank=True, max_length=34, verbose_name="IBAN")),
                ("taxa_iva", models.DecimalField(decimal_places=2, default=Decimal("23.00"), max_digits=5, verbose_name="Taxa IVA (%)")),
                ("latitude", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, verbose_name="Latitude")),
                ("longitude", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, verbose_name="Longitude")),
                ("status", models.CharField(choices=[("ATIVO", "Ativo"), ("PAUSADO", "Pausado"), ("INATIVO", "Inativo")], db_index=True, default="ATIVO", max_length=10, verbose_name="Estado")),
                ("capacidade_max", models.PositiveIntegerField(default=0, help_text="0 = sem limite. Proxy grosseiro de espaço para o MVP; a regra de overflow entra na Fase 1.", verbose_name="Capacidade máxima (pacotes)")),
                ("horario", models.JSONField(blank=True, default=dict, help_text="Horário de funcionamento (estrutura livre por dia da semana).", verbose_name="Horário")),
                ("preco_1a_entrega", models.DecimalField(decimal_places=4, default=Decimal("0.0000"), max_digits=8, verbose_name="Preço 1ª entrega (€)")),
                ("preco_adicional", models.DecimalField(decimal_places=4, default=Decimal("0.0000"), max_digits=8, verbose_name="Preço entrega adicional (€)")),
                ("ciclo_pagamento", models.CharField(choices=[("SEMANAL", "Semanal"), ("MENSAL", "Mensal")], default="MENSAL", max_length=10, verbose_name="Ciclo de pagamento")),
                ("notas", models.TextField(blank=True, verbose_name="Notas")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("partner", models.ForeignKey(blank=True, help_text="Vazio = multi-carrier. Preencher restringe a um cliente.", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="pudo_stores", to="core.partner", verbose_name="Cliente/Carrier (opcional)")),
            ],
            options={
                "verbose_name": "PUDO (Loja da Rede)",
                "verbose_name_plural": "PUDOs (Rede)",
                "ordering": ["numero"],
            },
        ),
        migrations.CreateModel(
            name="PudoAccess",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("username", models.CharField(help_text="Username único de login.", max_length=100, unique=True, verbose_name="Username")),
                ("email", models.EmailField(blank=True, max_length=254, verbose_name="Email")),
                ("password", models.CharField(max_length=255, verbose_name="Password (hash)")),
                ("papel", models.CharField(choices=[("DONO", "Dono (vê financeiro)"), ("ATENDENTE", "Atendente (só operação)")], default="DONO", max_length=10, verbose_name="Papel")),
                ("is_active", models.BooleanField(default=True, help_text="Desativar bloqueia o login sem apagar a conta.", verbose_name="Ativo")),
                ("last_login", models.DateTimeField(blank=True, null=True, verbose_name="Último login")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_pudo_accesses", to=settings.AUTH_USER_MODEL)),
                ("store", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="access", to="pudo_network.pudostore")),
            ],
            options={
                "verbose_name": "Acesso de PUDO",
                "verbose_name_plural": "Acessos de PUDO",
                "ordering": ["store__numero"],
            },
        ),
    ]
