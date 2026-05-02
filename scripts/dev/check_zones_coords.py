#!/usr/bin/env python
"""
Script para verificar coordenadas das zonas postais
"""
import django
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "my_project.settings")
django.setup()

from pricing.models import PostalZone

zones = PostalZone.objects.all()
print(f"Total de zonas: {zones.count()}")

zones_with_coords = PostalZone.objects.filter(
    center_latitude__isnull=False, center_longitude__isnull=False
)
print(f"Zonas com coordenadas: {zones_with_coords.count()}")

print("\nPrimeiras 5 zonas:")
for z in zones[:5]:
    print(f"  {z.name} - lat: {z.center_latitude}, lng: {z.center_longitude}")

if zones_with_coords.count() > 0:
    print("\nZonas COM coordenadas:")
    for z in zones_with_coords:
        print(f"  {z.name} - lat: {z.center_latitude}, lng: {z.center_longitude}")
