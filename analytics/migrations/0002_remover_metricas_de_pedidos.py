from django.db import migrations


class Migration(migrations.Migration):
    """As métricas eram calculadas a partir dos pedidos (orders_manager),
    que foram removidos. As quatro tabelas estavam vazias."""

    dependencies = [
        ("analytics", "0001_initial"),
    ]

    operations = [
        migrations.DeleteModel(name="DailyMetrics"),
        migrations.DeleteModel(name="DriverPerformance"),
        migrations.DeleteModel(name="PerformanceAlert"),
        migrations.DeleteModel(name="VolumeForecast"),
    ]
