#!/usr/bin/env python
"""
Importar dados Delnext diretamente (sem confirmação)
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_project.settings')
django.setup()

import importlib
from orders_manager import adapters
importlib.reload(adapters)

from orders_manager.adapters import get_delnext_adapter

print("=" * 70)
print("IMPORTAÇÃO DELNEXT - DATA: 2026-02-27")
print("=" * 70)

try:
    adapter = get_delnext_adapter()
    
    print("\n🔍 Buscando dados...")
    delnext_data = adapter.fetch_outbound_data(date='2026-02-27', zone='VianaCastelo')
    
    print(f"✓ {len(delnext_data)} pedidos encontrados\n")
    
    if delnext_data:
        print("📦 Preview (primeiros 5):")
        for i, item in enumerate(delnext_data[:5], 1):
            print(f"   {i}. {item['product_id']} - {item['customer_name']} - {item['city']} ({item['destination_zone']})")
        
        if len(delnext_data) > 5:
            print(f"   ... e mais {len(delnext_data) - 5} pedidos\n")
        
        print("\n📥 Importando para Orders Manager...")
        stats = adapter.import_to_orders(delnext_data)
        
        print("\n✓ Importação concluída!\n")
        print("📊 Estatísticas:")
        print(f"   • Total processado: {stats['total']}")
        print(f"   • Criados: {stats['created']}")
        print(f"   • Atualizados: {stats['updated']}")
        print(f"   • Erros: {stats['errors']}")
        
    print("\n" + "=" * 70)
    print("✅ SINCRONIZAÇÃO COMPLETA!")
    print("=" * 70)
    
except Exception as e:
    print(f"\n❌ ERRO: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
