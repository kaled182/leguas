"""
Script para verificar e popular falhas de geocodificação de exemplo.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_project.settings')
django.setup()

from orders_manager.models import Order, GeocodingFailure, GeocodedAddress
from orders_manager.geocoding import AddressNormalizer

# Verificar pedidos sem geocodificação
print("Verificando pedidos sem geocodificação...\n")

orders_without_geo = []
for order in Order.objects.filter(partner__name__icontains='Delnext').order_by('-created_at')[:50]:
    if not order.recipient_address or not order.postal_code:
        continue
    
    locality = order.recipient_address.split()[-1] if order.recipient_address else "Portugal"
    if len(locality) < 3:
        locality = "Portugal"
    
    normalized = AddressNormalizer.normalize(
        order.recipient_address,
        order.postal_code,
        locality
    )
    
    # Verificar se tem geocodificação
    has_geo = GeocodedAddress.objects.filter(normalized_address=normalized).exists()
    
    if not has_geo:
        orders_without_geo.append((order, normalized, locality))

print(f"Encontrados {len(orders_without_geo)} pedidos sem geocodificação")

# Registrar falhas
failures_created = 0
for order, normalized, locality in orders_without_geo[:10]:  # Registrar apenas 10 como exemplo
    failure, created = GeocodingFailure.objects.get_or_create(
        order=order,
        defaults={
            'original_address': order.recipient_address,
            'normalized_address': normalized,
            'postal_code': order.postal_code,
            'locality': locality,
            'failure_reason': 'Endereço não encontrado automaticamente'
        }
    )
    
    if created:
        failures_created += 1
        print(f"✓ Falha registrada: {order.external_reference}")

print(f"\n{failures_created} novas falhas registradas")

# Estatísticas
total_failures = GeocodingFailure.objects.count()
unresolved = GeocodingFailure.objects.filter(resolved=False).count()
resolved = GeocodingFailure.objects.filter(resolved=True).count()

print(f"\nESTATÍSTICAS:")
print(f"Total de falhas: {total_failures}")
print(f"Não resolvidas: {unresolved}")
print(f"Resolvidas: {resolved}")
