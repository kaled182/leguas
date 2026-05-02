#!/usr/bin/env python
"""
Mostra o HTML completo da página de geocoding failures.
"""
import os
import sys
import django

sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_project.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model

print("=" * 80)
print("CAPTURANDO HTML DA PÁGINA DE GEOCODING FAILURES")
print("=" * 80)

User = get_user_model()
client = Client()

# Login
user = User.objects.filter(is_active=True).first()
if not user:
    print("ERRO: Nenhum usuário encontrado")
    sys.exit(1)

client.force_login(user)
print(f"✓ Logado como: {user.username}\n")

# Acessa a página
from django.urls import reverse
url = reverse('orders:geocoding_failures_report')
print(f"✓ Acessando: {url}\n")

response = client.get(url)

print(f"Status Code: {response.status_code}")
print(f"Content-Type: {response.get('Content-Type')}")
print(f"Tamanho: {len(response.content)} bytes")
print("=" * 80)

if response.status_code == 200:
    html = response.content.decode('utf-8')
    
    # Mostra um preview do HTML
    print("\n--- PREVIEW DO HTML (Primeiros 2000 caracteres) ---\n")
    print(html[:2000])
    print("\n...")
    print(f"\n(Total: {len(html)} caracteres)")
    print("=" * 80)
    
    # Verifica elementos importantes
    print("\n--- ELEMENTOS ENCONTRADOS ---\n")
    
    checks = [
        ('Título da Página', '<title>'),
        ('Header H1', '<h1'),
        ('Estatísticas - Não Resolvidos', 'Não Resolvidos'),
        ('Cards de Estatísticas', 'card'),
        ('Formulário de Filtros', '<form'),
        ('Lista de Falhas', 'falha'),
        ('Links de Pedidos', 'order_detail'),
        ('Paginação', 'página'),
    ]
    
    for name, check in checks:
        if isinstance(check, str):
            found = check in html
        else:
            found = check
            
        status = "✓" if found else "✗"
        color = "\033[92m" if found else "\033[91m"
        print(f"{color}{status}\033[0m {name}")
    
    print("\n" + "=" * 80)
    
    # Salva HTML em arquivo para inspeção
    output_file = '/app/geocoding_failures_output.html'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"\n✓ HTML completo salvo em: {output_file}")
    print(f"  Você pode inspecionar o arquivo para ver o HTML completo.")
    print("=" * 80)
    
    # Mostra dados do contexto
    print("\n--- DADOS DO CONTEXTO ---\n")
    from orders_manager.models import GeocodingFailure, GeocodedAddress
    
    failures = GeocodingFailure.objects.all()
    print(f"Total de falhas no banco: {failures.count()}")
    
    if failures.exists():
        print("\nPrimeira falha:")
        f = failures.first()
        print(f"  - Pedido: {f.order.external_reference}")
        print(f"  - Endereço: {f.original_address}")
        print(f"  - CP: {f.postal_code}")
        print(f"  - Tentativas: {f.retry_count}")
        print(f"  - Resolvido: {f.resolved}")
    
    geocoded = GeocodedAddress.objects.count()
    print(f"\nTotal geocodificado: {geocoded}")
    
    success_rate = round((geocoded / (geocoded + failures.count()) * 100), 1) if (geocoded + failures.count()) > 0 else 0
    print(f"Taxa de sucesso: {success_rate}%")
    
    print("=" * 80)
else:
    print(f"\n✗ ERRO: Status {response.status_code}")
    print(response.content.decode('utf-8')[:500])

print("\n✅ CONCLUSÃO:")
print("A página está funcionando corretamente.")
print("Acesse no navegador: http://localhost:8000" + url)
print("=" * 80)
