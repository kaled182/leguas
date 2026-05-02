"""
Script simples para verificar estatísticas de geocodificação.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_project.settings')
django.setup()

from orders_manager.models import GeocodedAddress

# Estatísticas
total = GeocodedAddress.objects.count()
print(f"Total de endereços geocodificados: {total}\n")

if total > 0:
    # Por qualidade
    print("DISTRIBUIÇÃO POR QUALIDADE:")
    print("-" * 40)
    for quality, count in GeocodedAddress.objects.values_list('geocode_quality').annotate(
        count=django.db.models.Count('id')
    ).order_by('-count'):
        quality_name = quality or 'UNKNOWN'
        print(f"  {quality_name:15s}: {count:4d}")
    
    print("\nEXEMPLOS DE ENDEREÇOS GEOCODIFICADOS:")
    print("-" * 80)
    for addr in GeocodedAddress.objects.all()[:10]:
        print(f"\nOriginal:    {addr.address[:60]}...")
        print(f"Normalizado: {addr.normalized_address}")
        print(f"Coordenadas: ({addr.latitude}, {addr.longitude})")
        print(f"Qualidade:   {addr.geocode_quality}")
