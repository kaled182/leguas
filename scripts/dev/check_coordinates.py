#!/usr/bin/env python
"""
Script para ver as coordenadas exatas geradas
"""
import django
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "my_project.settings")
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
import re

User = get_user_model()

client = Client()
user = User.objects.filter(is_superuser=True).first()
client.force_login(user)

response = client.get('/pricing/zones/map/')
content = response.content.decode('utf-8')

# Encontrar primeira zona no array
match = re.search(r'\{\s*name:\s*"([^"]+)"[^}]*lat:\s*([0-9.,\-]+)[^}]*lng:\s*([0-9.,\-]+)', content, re.DOTALL)
if match:
    print(f"Primeira zona encontrada:")
    print(f"  Nome: {match.group(1)}")
    print(f"  Lat: '{match.group(2)}'")
    print(f"  Lng: '{match.group(3)}'")
    
    # Verificar se tem vírgula ou ponto
    lat_str = match.group(2)
    if ',' in lat_str and '.' not in lat_str:
        print(f"\n❌ PROBLEMA: Lat usa vírgula como decimal!")
    elif '.' in lat_str:
        print(f"\n✓ OK: Lat usa ponto como decimal")
else:
    print("Zona não encontrada!")

# Verificar também o setView
match = re.search(r'setView\(\[([0-9.,\-]+),\s*([0-9.,\-]+)\]', content)
if match:
    print(f"\nsetView encontrado:")
    print(f"  Lat: '{match.group(1)}'")
    print(f"  Lng: '{match.group(2)}'")
    
    lat_str = match.group(1)
    if ',' in lat_str:
        print(f"  ❌ PROBLEMA: setView usa vírgula!")
    else:
        print(f"  ✓ OK: setView usa ponto")
