"""
Verificar dados importados.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_project.settings')
django.setup()

from core.models import Partner
from orders_manager.models import Order

# Buscar Partner Delnext
partner = Partner.objects.get(name="Delnext")

# Contar orders
total_orders = Order.objects.filter(partner=partner).count()
print(f"📊 Total de pedidos Delnext: {total_orders}\n")

# Mostrar primeiros 10
print("📦 Primeiros 10 pedidos:\n")
orders = Order.objects.filter(partner=partner).order_by('-created_at')[:10]

for i, order in enumerate(orders, 1):
    print(f"{i}. Ref: {order.external_reference}")
    print(f"   Cliente: {order.recipient_name}")
    print(f"   Endereço: {order.recipient_address[:60]}...")
    print(f"   Código Postal: {order.postal_code}")
    print(f"   Status: {order.current_status}")
    print(f"   Data agendada: {order.scheduled_delivery}")
    print(f"   Notas: {order.notes}")
    print()

# Estatísticas por status
print("\n📊 Distribuição por status:\n")
from django.db.models import Count
stats = Order.objects.filter(partner=partner).values('current_status').annotate(count=Count('id'))

for stat in stats:
    print(f"   • {stat['current_status']}: {stat['count']} pedidos")
