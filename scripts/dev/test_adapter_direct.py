#!/usr/bin/env python
"""
Teste direto do DelnextAdapter - forçando reload do módulo
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_project.settings')
django.setup()

# Forçar reload dos módulos
import importlib
from orders_manager import adapters

# Recarregar adapter para garantir código atualizado
importlib.reload(adapters)

from orders_manager.adapters import get_delnext_adapter

print("=" * 70)
print("TESTE DIRETO DELNEXT ADAPTER (COM RELOAD)")
print("=" * 70)

try:
    print("\n1. Criando adapter...")
    adapter = get_delnext_adapter()
    print(f"   ✅ Adapter criado: {adapter}")
    
    print("\n2. Buscando dados (último dia útil, VianaCastelo)...")
    data = adapter.fetch_outbound_data()
    
    print(f"\n✅ SUCESSO! {len(data)} pedidos encontrados")
    
    if data:
        print("\n📦 Primeiros 3 pedidos:")
        for i, pedido in enumerate(data[:3], 1):
            print(f"\n   {i}. Product ID: {pedido.get('product_id')}")
            print(f"      Cliente: {pedido.get('customer_name')}")
            print(f"      Cidade: {pedido.get('city')}")
            print(f"      Zona: {pedido.get('destination_zone')}")
    
    print("\n" + "=" * 70)
    print("✅ TESTE COMPLETO - ADAPTER FUNCIONANDO!")
    print("=" * 70)
    
except Exception as e:
    print(f"\n❌ ERRO: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    print("=" * 70)
