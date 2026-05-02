"""
Script para executar importação Delnext sem confirmação manual.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_project.settings')
django.setup()

from orders_manager.adapters import get_delnext_adapter

# Buscar dados
print("🔍 Buscando dados do Delnext...")
adapter = get_delnext_adapter()
data = adapter.fetch_outbound_data(date="2026-02-27", zone="VianaCastelo")

print(f"✅ {len(data)} pedidos encontrados\n")

# Preview
print("📦 Preview (primeiros 5):")
for i, item in enumerate(data[:5], 1):
    print(f"   {i}. {item['product_id']} - {item['customer_name']} - {item['city']}")

if len(data) > 5:
    print(f"   ... e mais {len(data) -5} pedidos\n")

# Importar
print("📥 Importando para Orders Manager...")
stats = adapter.import_to_orders(data, partner_name="Delnext")

# Resultados
print("\n✅ Importação concluída!\n")
print("📊 Estatísticas:")
print(f"   • Total processado: {stats['total']}")
print(f"   • Criados: {stats['created']}")
print(f"   • Atualizados: {stats['updated']}")
print(f"   • Erros: {stats['errors']}")
