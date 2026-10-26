"""Porto: valor único de 1,10 €/volume em todos os CP do hub
(indicação do Paulo, 2026-10-26). Regime só mensal, como Aveiro
(hub de valor único); pagamento por omissão: 30 dias após o fecho."""
from datetime import date
from decimal import Decimal

from django.db import migrations

PRICE = Decimal("1.10")
VALID_FROM = date(2026, 1, 1)


def forwards(apps, schema_editor):
    CainiaoHub = apps.get_model("settlements", "CainiaoHub")
    Terms = apps.get_model("contracts", "HubContractTerms")
    Tariff = apps.get_model("contracts", "HubZoneTariff")
    hub = CainiaoHub.objects.filter(name="Porto").first()
    if not hub:
        return
    Terms.objects.get_or_create(hub=hub, defaults=dict(
        allows_monthly=True, allows_weekly=False,
        monthly_payment_mode="DAYS_AFTER_CLOSE", monthly_payment_value=30,
    ))
    CP4 = apps.get_model("settlements", "CainiaoHubCP4")
    for cp4 in CP4.objects.filter(hub=hub).values_list("cp4", flat=True):
        Tariff.objects.update_or_create(
            hub=hub, cp4=cp4, valid_from=VALID_FROM,
            defaults=dict(zone_name="Porto", tier="", price_monthly=PRICE, price_weekly=None),
        )


class Migration(migrations.Migration):

    dependencies = [
        ("contracts", "0004_cp_negotiated_prices"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
