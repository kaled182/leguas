#!/usr/bin/env python
"""
Script para ver o HTML gerado do mapa
"""
import django
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "my_project.settings")
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model

User = get_user_model()

client = Client()
user = User.objects.filter(is_superuser=True).first()
client.force_login(user)

response = client.get('/pricing/zones/map/')
content = response.content.decode('utf-8')

# Extrair só a parte do JavaScript com as zonas
import re

# Encontrar a definição do array zones
match = re.search(r'const zones = \[(.*?)\];', content, re.DOTALL)
if match:
    zones_js = match.group(1)
    print("=== ARRAY DE ZONAS NO JAVASCRIPT ===")
    print(f"const zones = [{zones_js}];")
    print("\n=== TOTAL DE OBJETOS ===")
    # Contar quantos objetos { ... } existem
    obj_count = zones_js.count('{')
    print(f"Total de objetos no array: {obj_count}")
else:
    print("Array de zonas não encontrado!")

# Verificar se há forEach
if 'zones.forEach' in content:
    print("\n✓ forEach encontrado")
else:
    print("\n✗ forEach NÃO encontrado")

# Buscar a linha do setView
match = re.search(r'L\.map\(\'map\'\)\.setView\((.*?)\)', content)
if match:
    print(f"\n=== MAPA CENTER ===")
    print(f"setView({match.group(1)})")
