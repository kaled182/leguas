"""Carrega condições e tabelas de CP a partir dos geradores em uso
(gerador_contrato_Viana_1.html e gerador_contrato_Aveiro.html)."""
from datetime import date
from decimal import Decimal as D

from django.db import migrations

VALID_FROM = date(2026, 1, 1)

# hub → (termos, [(cp4, zona, escalão, mensal, semanal)])
VIANA_TERMS = dict(
    signing_place="Esposende", allows_monthly=True, allows_weekly=True,
    monthly_payment_mode="DAYS_AFTER_CLOSE", monthly_payment_value=30,
    weekly_payday=1, weekly_lag_weeks=4,
)
SEED = {
    "Fão": (VIANA_TERMS, [
        ("4740", "Esposende", "A", D("0.95"), D("0.90")),
        ("4900", "Viana do Castelo", "B", D("1.00"), D("0.95")),
        ("4905", "Barroselas", "B", D("1.00"), D("0.95")),
        ("4925", "Lanheses", "B", D("1.00"), D("0.95")),
        ("4935", "Afife", "B", D("1.00"), D("0.95")),
        ("4910", "Caminha", "B", D("1.10"), D("1.05")),
        ("4920", "V. N. de Cerveira", "C", D("1.15"), D("1.10")),
        ("4990", "Ponte de Lima", "C", D("1.20"), D("1.15")),
    ]),
    "Ponte da Barca": (VIANA_TERMS, [
        ("4930", "Valença", "C", D("1.20"), D("1.15")),
        ("4940", "Paredes de Coura", "C", D("1.20"), D("1.15")),
        ("4950", "Monção", "C", D("1.20"), D("1.15")),
        ("4970", "Arcos de Valdevez", "C", D("1.20"), D("1.15")),
        ("4980", "Ponte da Barca", "C", D("1.20"), D("1.15")),
    ]),
    "Aveiro": (dict(
        signing_place="Válega", allows_monthly=True, allows_weekly=False,
        monthly_payment_mode="DAY_OF_NEXT_MONTH", monthly_payment_value=15,
        weekly_payday=1, weekly_lag_weeks=4,
    ), [
        ("3700", "S. João da Madeira / Oliveira de Azeméis", "", D("1.00"), None),
        ("3880", "Ovar", "", D("1.00"), None),
        ("3885", "Esmoriz / Cortegaça", "", D("1.00"), None),
        ("4500", "Espinho", "", D("1.00"), None),
        ("4505", "Argoncilhe / Fiães", "", D("1.00"), None),
        ("4520", "Santa Maria da Feira", "", D("1.00"), None),
        ("4525", "Canedo", "", D("1.00"), None),
        ("4535", "Mozelos / Lourosa", "", D("1.00"), None),
    ]),
}


def forwards(apps, schema_editor):
    CainiaoHub = apps.get_model("settlements", "CainiaoHub")
    Terms = apps.get_model("contracts", "HubContractTerms")
    Tariff = apps.get_model("contracts", "HubZoneTariff")
    Settings = apps.get_model("contracts", "ContractSettings")
    Settings.objects.get_or_create(pk=1)
    for name, (terms, zones) in SEED.items():
        hub = CainiaoHub.objects.filter(name=name).first()
        if not hub:
            continue
        Terms.objects.update_or_create(hub=hub, defaults=terms)
        for cp4, zone, tier, pm, pw in zones:
            Tariff.objects.update_or_create(
                hub=hub, cp4=cp4, valid_from=VALID_FROM,
                defaults=dict(zone_name=zone, tier=tier,
                              price_monthly=pm, price_weekly=pw),
            )


class Migration(migrations.Migration):

    dependencies = [
        ("contracts", "0002_contract_payment_fields"),
        ("settlements", "0055_driverclaim_billing_after"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
