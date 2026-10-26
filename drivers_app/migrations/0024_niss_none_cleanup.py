from django.db import migrations


def forwards(apps, schema_editor):
    # A página Editar mostrava NISS vazio como "None" e gravava esse texto.
    DriverProfile = apps.get_model("drivers_app", "DriverProfile")
    DriverProfile.objects.filter(niss__in=["None", ""]).update(niss=None)


class Migration(migrations.Migration):

    dependencies = [
        ("drivers_app", "0023_contract_payment_fields"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
