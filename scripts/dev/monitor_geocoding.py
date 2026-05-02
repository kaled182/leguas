"""
Monitor de progresso de geocodificação em tempo real.
"""
import os
import django
import time

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_project.settings')
django.setup()

from orders_manager.models import GeocodedAddress, Order

print("Monitorando progresso de geocodificação...\n")
print("Pressione Ctrl+C para sair\n")

prev_count = 0
try:
    while True:
        total_geocoded = GeocodedAddress.objects.count()
        total_orders = Order.objects.filter(partner__name__icontains='Delnext').count()
        
        # Estatísticas por qualidade
        exact = GeocodedAddress.objects.filter(geocode_quality='EXACT').count()
        
        coverage = (total_geocoded / total_orders * 100) if total_orders > 0 else 0
        
        new_items = total_geocoded - prev_count
        status = f"[+{new_items}]" if new_items > 0 else ""
        
        print(f"\r{status} Geocodificados: {total_geocoded}/{total_orders} ({coverage:.1f}%) | EXACT: {exact}", end='', flush=True)
        
        prev_count = total_geocoded
        time.sleep(2)
        
except KeyboardInterrupt:
    print("\n\nMonitoramento finalizado.")
    print(f"\nTotal final: {total_geocoded} endereços geocodificados")
