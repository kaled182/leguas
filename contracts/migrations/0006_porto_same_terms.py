"""Porto: mesmas condições dos outros hubs (Fão / Ponte da Barca) —
só os valores mudam (indicação do Paulo, 2026-10-26). Semanal = mensal
menos o desconto semanal dos parâmetros (1,10 − 0,05 = 1,05 €)."""
from django.db import migrations


def forwards(apps, schema_editor):
    CainiaoHub = apps.get_model("settlements", "CainiaoHub")
    Terms = apps.get_model("contracts", "HubContractTerms")
    porto = CainiaoHub.objects.filter(name="Porto").first()
    ref = Terms.objects.filter(hub__name="Fão").first()
    if not porto or not ref:
        return
    fields = [
        "signing_place", "allows_monthly", "allows_weekly",
        "monthly_payment_mode", "monthly_payment_value",
        "weekly_payday", "weekly_lag_weeks",
    ]
    Terms.objects.update_or_create(
        hub=porto, defaults={f: getattr(ref, f) for f in fields},
    )


class Migration(migrations.Migration):

    dependencies = [
        ("contracts", "0005_porto_tariff"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
