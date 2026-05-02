#!/usr/bin/env python
"""
Script para contar marcadores corretamente
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

# Contar marcadores de várias formas
marker_count_1 = content.count('L.marker([')
marker_count_2 = content.count('const marker =')
marker_count_3 = len(re.findall(r'L\.marker\(\[', content))

print(f"L.marker([ count: {marker_count_1}")
print(f"const marker = count: {marker_count_2}")
print(f"Regex count: {marker_count_3}")

# Verificar se há zones.forEach
if 'zones.forEach' in content:
    print("\n✓ zones.forEach está no código")
    
    # Extrair o array de zonas e contar objetos
    match = re.search(r'const zones = \[(.*?)\];', content, re.DOTALL)
    if match:
        zones_str = match.group(1)
        # Contar objetos { ... }
        zone_objects = zones_str.split('{')
        num_zones = len(zone_objects) - 1  # Primeiro item é vazio
        print(f"✓ Array de zonas tem {num_zones} objetos")
        
        # Verificar se há vírgulas decimais
        if ',,' in zones_str or re.search(r'\d,\d', zones_str):
            print("❌ ATENÇÃO: Ainda há vírgulas decimais no array de zonas!")
            # Mostrar primeira ocorrência
            match_comma = re.search(r'(lat|lng):\s*([0-9]+),(\d+)', zones_str)
            if match_comma:
                print(f"   Exemplo: {match_comma.group(1)}: {match_comma.group(2)},{match_comma.group(3)}")
        else:
            print("✓ Sem vírgulas decimais detectadas")
else:
    print("\n❌ zones.forEach NÃO está no código!")

# Vamos procurar por erros de sintaxe JavaScript
print("\nVerificando sintaxe JavaScript:")
if re.search(r'\d,\d{6},', content):
    print("❌ ERRO: Coordenadas com vírgulas causando sintaxe inválida")
    matches = re.findall(r'(lat|lng):\s*([0-9.,\-]+)', content)
    print(f"   Primeiras 3 coordenadas encontradas:")
    for i, (key, value) in enumerate(matches[:3]):
        print(f"   {key}: {value}")
else:
    print("✓ Sintaxe parece OK")
