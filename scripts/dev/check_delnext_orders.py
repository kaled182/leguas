#!/usr/bin/env python
"""
Verificar pedidos Delnext no banco de dados
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_project.settings')
django.setup()

from orders_manager.models import Order
from core.models import Partner

print("=" * 70)
print("VERIFICAÇÃO DE PEDIDOS DELNEXT NO BANCO")
print("=" * 70)

try:
    delnext = Partner.objects.get(name='Delnext')
    orders = Order.objects.filter(partner=delnext)
    
    print(f"\n📊 Total de pedidos Delnext: {orders.count()}")
    
    if orders.exists():
        print(f"\n📦 Últimos 10 pedidos:")
        for i, o in enumerate(orders.order_by('-id')[:10], 1):
            print(f"   {i}. #{o.external_reference}: {o.recipient_name} - {o.postal_code} ({o.current_status})")
        
        print(f"\n📈 Status dos pedidos:")
        from django.db.models import Count
        status_counts = orders.values('current_status').annotate(count=Count('id')).order_by('-count')
        for item in status_counts:
            print(f"   • {item['current_status']}: {item['count']}")
        
        print(f"\n🗓️ Pedidos por data de criação:")
        from datetime import date as dt_date
        today_orders = orders.filter(created_at__date=dt_date.today()).count()
        print(f"   • Hoje: {today_orders} pedidos")
        print(f"   • Total geral: {orders.count()} pedidos")
    
    print("\n" + "=" * 70)
    print("✅ VERIFICAÇÃO COMPLETA!")
    print("=" * 70)
    
except Partner.DoesNotExist:
    print("\n❌ Parceiro 'Delnext' não encontrado no banco de dados!")
except Exception as e:
    print(f"\n❌ ERRO: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
