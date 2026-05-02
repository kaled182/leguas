"""
Importação otimizada com bulk_create.
"""
import os
import django
import re
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_project.settings')
django.setup()

from orders_manager.adapters import get_delnext_adapter
from core.models import Partner
from orders_manager.models import Order

# Buscar dados
print("🔍 Buscando dados do Delnext...")
adapter = get_delnext_adapter()
data = adapter.fetch_outbound_data(date="2026-02-27", zone="VianaCastelo")

print(f"✅ {len(data)} pedidos encontrados\n")

# Obter Partner
partner = Partner.objects.get(name="Delnext")
print(f"✅ Partner: {partner.name} (ID: {partner.id})\n")

# Preparar lista de Orders para bulk_create
print("📦 Preparando dados para importação em lote...")
orders_to_create = []

for item in data:
    # Normalizar código postal
    postal_code = item.get("postal_code", "")
    postal_code = re.sub(r'[^\d-]', '', postal_code)
    
    if '-' not in postal_code and len(postal_code) >= 7:
        postal_code = f"{postal_code[:4]}-{postal_code[4:7]}"
    
    if not re.match(r'^\d{4}-\d{3}$', postal_code):
        postal_code = "0000-000"
    
    # Parse data
    scheduled_delivery = None
    date_str = item.get("date", "")
    if date_str:
        try:
            scheduled_delivery = datetime.strptime(date_str, "%Y-%m-%d").date()
        except:
            pass
    
    # Status
    status_map = {
        "Enviada": "IN_TRANSIT",
        "Entregue": "DELIVERED",
        "Pendente": "PENDING",
        "A processar": "PENDING",
        "Devolvida": "RETURNED",
        "Cancelada": "CANCELLED",
    }
    status = status_map.get(item.get("status", "Pendente"), "PENDING")
    
    # Endereço
    address_parts = [item.get("address", ""), item.get("city", "")]
    recipient_address = ", ".join(filter(None, address_parts)) or "Endereço não informado"
    
    # Criar objeto Order
    order = Order(
        partner=partner,
        external_reference=item["product_id"],
        recipient_name=item.get("customer_name", "Cliente")[:200],
        recipient_address=recipient_address[:500],
        postal_code=postal_code,
        scheduled_delivery=scheduled_delivery,
        current_status=status,
        notes=f"Zona: {item.get('destination_zone', '')}",
    )
    orders_to_create.append(order)

print(f"✅ {len(orders_to_create)} pedidos prep arados\n")

# Bulk create com ignore_conflicts
print("📥 Importando em lote (bulk_create)...")
try:
    created_orders = Order.objects.bulk_create(
        orders_to_create,
        ignore_conflicts=True  # Ignorar duplicados
    )
    
    print(f"\n✅ Importação concluída!")    
    print(f"   • Total processado: {len(data)}")
    print(f"   • Criados: {len(created_orders)}")
    print(f"   • Duplicados ignorados: {len(data) - len(created_orders)}")
    
except Exception as e:
    print(f"\n❌ Erro: {e}")
