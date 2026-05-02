#!/usr/bin/env python
"""
Script para verificar se o mapa de pedidos está funcional
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

response = client.get('/orders/map/')
content = response.content.decode('utf-8')

print("=" * 60)
print("VERIFICAÇÃO DO MAPA DE PEDIDOS EM TEMPO REAL")
print("=" * 60)

# 1. Status HTTP
print(f"\n✓ Status HTTP: {response.status_code}")

# 2. Leaflet carregado
if 'leaflet.js' in content:
    print("✓ Leaflet.js está sendo carregado")
else:
    print("✗ Leaflet.js NÃO encontrado")

# 3. Elemento map
if 'id="map"' in content:
    print("✓ Elemento <div id='map'> presente")
else:
    print("✗ Elemento map NÃO encontrado")

# 4. Inicialização do mapa
match = re.search(r'L\.map\(\'map\'\)\.setView\(\[([0-9.]+),\s*([0-9.\-]+)\],\s*(\d+)\)', content)
if match:
    lat, lng, zoom = match.group(1), match.group(2), match.group(3)
    print(f"✓ Mapa inicializado em [{lat}, {lng}] com zoom {zoom}")
    
    # Verificar se usa pontos
    if '.' in lat and '.' in lng:
        print("  ✓ Coordenadas usam pontos decimais")
    else:
        print("  ✗ Coordenadas com problema de formatação")
else:
    print("✗ Inicialização do mapa NÃO encontrada")

# 5. Array de pedidos
match = re.search(r'const orders = \[(.*?)\];', content, re.DOTALL)
if match:
    orders_str = match.group(1)
    
    # Contar pedidos contando ocorrências de 'id:'
    order_count = orders_str.count('id:')
    print(f"✓ Array de pedidos criado com {order_count} pedido(s)")
    
    if order_count > 0:
        # Verificar se coordenadas usam pontos
        sample_coords = re.findall(r'lat:\s*([0-9.]+),', orders_str)
        if sample_coords:
            if all('.' in coord for coord in sample_coords[:3]):
                print(f"  ✓ Coordenadas dos pedidos usam pontos decimais")
                print(f"  ✓ Exemplo: lat: {sample_coords[0]}")
            else:
                print(f"  ✗ Coordenadas dos pedidos com problema")
    else:
        print("  ℹ️  Nenhum pedido com coordenadas no momento")
else:
    print("✗ Array de pedidos NÃO encontrado")

# 6. forEach loop
if 'orders.forEach' in content:
    print("✓ Loop forEach(order => ...) presente")
else:
    print("✗ forEach NÃO encontrado")

# 7. Criação de marcadores
if 'L.marker([order.lat, order.lng]' in content:
    print("✓ Código de criação de marcadores presente")
else:
    print("✗ Criação de marcadores NÃO encontrada")

# 8. Estatísticas
stats_match = re.search(r'<p class="text-2xl font-bold text-gray-900[^>]*>(\d+)</p>', content)
if stats_match:
    total = stats_match.group(1)
    print(f"✓ Estatísticas carregadas (Total: {total} pedidos)")
else:
    print("✗ Estatísticas NÃO encontradas")

# 9. Verificar erros JavaScript óbvios
js_errors = []

# Vírgulas decimais em coordenadas JavaScript
if re.search(r'(lat|lng):\s*\d+,\d{6}', content):
    js_errors.append("Vírgulas decimais em coordenadas")

if js_errors:
    print(f"\n⚠ AVISOS:")
    for error in js_errors:
        print(f"  - {error}")
else:
    print("\n✓ Nenhum erro JavaScript óbvio detectado")

print("\n" + "=" * 60)
print("CONCLUSÃO")
print("=" * 60)

# Verificação final
checks = [
    response.status_code == 200,
    'leaflet.js' in content,
    'id="map"' in content,
    'L.map(' in content,
    'const orders = [' in content,
    'orders.forEach' in content,
    'L.marker([order.lat, order.lng]' in content,
    len(js_errors) == 0
]

passed = sum(checks)
total_checks = len(checks)

if passed == total_checks:
    print(f"✅ TUDO OK! ({passed}/{total_checks} verificações passaram)")
    print("\n🗺️  O mapa de pedidos deve estar funcionando!")
    print("   Acesse: http://localhost:8000/orders/map/")
    print("   (certifique-se de estar logado)")
else:
    print(f"⚠️  ATENÇÃO: {passed}/{total_checks} verificações passaram")
    print("   Pode haver problemas com o mapa")

print("=" * 60)
