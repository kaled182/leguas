#!/usr/bin/env python
"""
Script para verificar coordenadas dos pedidos no mapa
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_project.settings')
django.setup()

from orders_manager.models import Order
from pricing.models import PostalZone

def check_coordinates():
    """Verifica quantos pedidos têm coordenadas"""
    
    print("=" * 80)
    print("VERIFICAÇÃO DE COORDENADAS DO MAPA")
    print("=" * 80)
    print()
    
    # Buscar pedidos Delnext
    delnext_orders = Order.objects.filter(
        partner__name="Delnext",
        current_status__in=["PENDING", "ASSIGNED", "IN_TRANSIT"]
    ).order_by('-created_at')[:100]
    
    print(f"📦 Total de pedidos Delnext ativos: {delnext_orders.count()}")
    print()
    
    with_coords = 0
    without_coords = 0
    sample_with_coords = []
    sample_without_coords = []
    
    for order in delnext_orders:
        try:
            zone = PostalZone.find_zone_for_postal_code(order.postal_code)
            if zone and zone.center_latitude and zone.center_longitude:
                with_coords += 1
                if len(sample_with_coords) < 5:
                    sample_with_coords.append({
                        'ref': order.external_reference,
                        'postal': order.postal_code,
                        'zone': zone.name,
                        'lat': zone.center_latitude,
                        'lng': zone.center_longitude
                    })
            else:
                without_coords += 1
                if len(sample_without_coords) < 5:
                    sample_without_coords.append({
                        'ref': order.external_reference,
                        'postal': order.postal_code,
                        'zone': zone.name if zone else 'Zona não encontrada'
                    })
        except Exception as e:
            without_coords += 1
            if len(sample_without_coords) < 5:
                sample_without_coords.append({
                    'ref': order.external_reference,
                    'postal': order.postal_code,
                    'error': str(e)
                })
    
    print(f"✅ Pedidos COM coordenadas: {with_coords}")
    print(f"❌ Pedidos SEM coordenadas: {without_coords}")
    print()
    
    if sample_with_coords:
        print("📍 Exemplos de pedidos COM coordenadas:")
        for item in sample_with_coords:
            print(f"   - {item['ref']}: {item['postal']} → {item['zone']}")
            print(f"     Lat: {item['lat']}, Lng: {item['lng']}")
        print()
    
    if sample_without_coords:
        print("⚠️  Exemplos de pedidos SEM coordenadas:")
        for item in sample_without_coords:
            print(f"   - {item['ref']}: {item['postal']}")
            if 'zone' in item:
                print(f"     Zona: {item['zone']}")
            if 'error' in item:
                print(f"     Erro: {item['error']}")
        print()
    
    # Verificar zonas cadastradas
    print("=" * 80)
    print("ZONAS POSTAIS CADASTRADAS")
    print("=" * 80)
    total_zones = PostalZone.objects.count()
    zones_with_coords = PostalZone.objects.filter(
        center_latitude__isnull=False,
        center_longitude__isnull=False
    ).count()
    
    print(f"📊 Total de zonas cadastradas: {total_zones}")
    print(f"📍 Zonas com coordenadas: {zones_with_coords}")
    print(f"❌ Zonas sem coordenadas: {total_zones - zones_with_coords}")
    print()
    
    # Mostrar algumas zonas de exemplo
    sample_zones = PostalZone.objects.filter(
        center_latitude__isnull=False,
        center_longitude__isnull=False
    ).order_by('?')[:10]
    
    if sample_zones:
        print("📍 Exemplos de zonas com coordenadas:")
        for zone in sample_zones:
            print(f"   - {zone.name}: CP {zone.postal_code_start} - {zone.postal_code_end}")
            print(f"     Lat: {zone.center_latitude}, Lng: {zone.center_longitude}")
        print()

if __name__ == "__main__":
    check_coordinates()
