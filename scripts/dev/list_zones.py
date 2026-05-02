#!/usr/bin/env python
"""
Script para listar zonas postais
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_project.settings')
django.setup()

from pricing.models import PostalZone

print("=" * 80)
print("ZONAS POSTAIS CADASTRADAS")
print("=" * 80)

zones = PostalZone.objects.all().order_by('name')
print(f"\nTotal: {zones.count()} zonas\n")

for zone in zones:
    print(f"📍 {zone.name}")
    print(f"   Padrão CP: {zone.postal_code_pattern}")
    print(f"   Coordenadas: Lat {zone.center_latitude}, Lng {zone.center_longitude}")
    print()
