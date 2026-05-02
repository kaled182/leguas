#!/usr/bin/env python
"""
Script para analisar códigos postais dos pedidos
"""
import os
import sys
import django
from collections import Counter

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_project.settings')
django.setup()

from orders_manager.models import Order

print("=" * 80)
print("ANÁLISE DE CÓDIGOS POSTAIS")
print("=" * 80)
print()

# Buscar pedidos Delnext
orders = Order.objects.filter(partner__name="Delnext")
print(f"📦 Total de pedidos Delnext: {orders.count()}")
print()

# Extrair primeiros 4 dígitos dos códigos postais
postal_codes_4 = []
for order in orders:
    cp = order.postal_code
    if cp and len(cp) >= 4:
        # Pegar primeiros 4 dígitos
        cp_4 = cp[:4]
        postal_codes_4.append(cp_4)

# Contar frequências
counter = Counter(postal_codes_4)

print(f"📊 Total de códigos únicos (4 dígitos): {len(counter)}")
print()

print("🔝 Top 30 códigos postais mais frequentes:")
print()

for cp, count in counter.most_common(30):
    print(f"   {cp}XX: {count} pedidos")

print()
print("=" * 80)
