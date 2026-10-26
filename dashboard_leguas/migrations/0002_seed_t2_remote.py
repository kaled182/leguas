"""Zonas T+2 R (indicação do Paulo, 2026-10-26): 4920, 4930, 4940, 4950."""
from django.db import migrations

CPS = ["4920", "4930", "4940", "4950"]


def forwards(apps, schema_editor):
    Rule = apps.get_model("dashboard_leguas", "SlaZoneRule")
    for cp in CPS:
        Rule.objects.update_or_create(cp4=cp, defaults={"sla_days": 2, "label": "T+2 R"})


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard_leguas", "0001_sla_zone_rule"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
