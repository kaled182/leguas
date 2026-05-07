"""Cria CostCenter para CainiaoHubs existentes que não tenham.

Idempotente: só cria se não existe CostCenter ligado ao HUB.
Roda uma vez no deploy. Para HUBs novos, o signal post_save em
accounting/signals.py trata da criação automaticamente.
"""
import re
import unicodedata

from django.db import migrations


def _slugify_code(name: str) -> str:
    n = unicodedata.normalize("NFKD", name or "")
    n = n.encode("ascii", "ignore").decode("ascii")
    n = re.sub(r"[^a-zA-Z0-9]+", "-", n).strip("-").upper()
    return f"HUB-{n}"[:20]


def backfill(apps, schema_editor):
    CainiaoHub = apps.get_model("settlements", "CainiaoHub")
    CostCenter = apps.get_model("accounting", "CostCenter")

    for hub in CainiaoHub.objects.all():
        if CostCenter.objects.filter(cainiao_hub=hub).exists():
            continue
        code = _slugify_code(hub.name)
        base = code
        i = 2
        while CostCenter.objects.filter(code=code).exists():
            code = f"{base}-{i}"[:20]
            i += 1
        CostCenter.objects.create(
            code=code,
            name=hub.name,
            type="HUB",
            cainiao_hub=hub,
            is_active=True,
            notes=(
                f"Criado pela migração 0008_backfill_hub_cost_centers "
                f"para o HUB #{hub.id}."
            ),
        )


def noop(apps, schema_editor):
    """Reverter não apaga (preservar histórico)."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "0007_imposto"),
        ("settlements", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(backfill, noop),
    ]
