from django.db import migrations


class Migration(migrations.Migration):
    """A Rede PUDO foi removida. A coluna pudo_store_id sai na migration
    core.0008_remover_pedidos_rotas_pudo (tem uma FK para a tabela PUDO)."""

    dependencies = [
        ("sorting", "0003_bigbag_pudo"),
    ]

    operations = [
        migrations.RemoveField(model_name="sortingbigbag", name="consumida"),
    ]
