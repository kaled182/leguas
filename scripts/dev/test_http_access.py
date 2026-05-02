#!/usr/bin/env python
"""
Teste de acesso HTTP real à página de geocoding failures.
"""
import os
import sys
import django

sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_project.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from django.urls import reverse

print("=" * 60)
print("TESTE DE ACESSO HTTP REAL")
print("=" * 60)

User = get_user_model()
client = Client()

# 1. Tenta acessar sem login (deve redirecionar)
url = reverse('orders:geocoding_failures_report')
print(f"\n1. Testando acesso sem login...")
print(f"   URL: {url}")

response = client.get(url)
print(f"   Status: {response.status_code}")

if response.status_code == 302:
    print(f"   ✓ Redirecionou para login (como esperado)")
    print(f"   Redirect: {response.url}")
elif response.status_code == 200:
    print(f"   ✗ Permitiu acesso sem login (problema de segurança)")
else:
    print(f"   ✗ Status inesperado: {response.status_code}")

# 2. Login
print(f"\n2. Fazendo login...")
try:
    user = User.objects.filter(is_active=True).first()
    if not user:
        print(f"   ✗ Nenhum usuário ativo encontrado")
        sys.exit(1)
    
    # Força login
    client.force_login(user)
    print(f"   ✓ Login realizado como: {user.username}")
except Exception as e:
    print(f"   ✗ Erro ao fazer login: {e}")
    sys.exit(1)

# 3. Acessa a página autenticado
print(f"\n3. Acessando página autenticado...")
response = client.get(url)
print(f"   Status: {response.status_code}")

if response.status_code == 200:
    print(f"   ✓ Página acessível!")
    print(f"   Content-Type: {response.get('Content-Type')}")
    print(f"   Tamanho: {len(response.content)} bytes")
    
    # Verifica conteúdo
    content = response.content.decode('utf-8')
    
    checks = [
        ('Título', 'Falhas de Geocodifica'),
        ('Stats', 'Total de Falhas'),
        ('Filters', 'Mostrar Resolvidas'),
        ('Table', 'Endereço Original'),
    ]
    
    print(f"\n   Verificações de conteúdo:")
    for name, text in checks:
        if text in content:
            print(f"   ✓ {name}: encontrado")
        else:
            print(f"   ✗ {name}: NÃO encontrado")
    
    # Verifica se há falhas na página
    from orders_manager.models import GeocodingFailure
    failure_count = GeocodingFailure.objects.count()
    unresolved = GeocodingFailure.objects.filter(resolved=False).count()
    
    print(f"\n   Dados no banco:")
    print(f"   - Total de falhas: {failure_count}")
    print(f"   - Não resolvidas: {unresolved}")
    
else:
    print(f"   ✗ Erro ao acessar: {response.status_code}")
    if hasattr(response, 'content'):
        print(f"   Conteúdo: {response.content[:500]}")

# 4. Testa filtros
print(f"\n4. Testando filtros...")
response = client.get(url + '?show_resolved=false')
print(f"   Com show_resolved=false: {response.status_code}")

response = client.get(url + '?partner=Delnext')
print(f"   Com partner=Delnext: {response.status_code}")

print("\n" + "=" * 60)
print("ACESSE A PÁGINA EM SEU NAVEGADOR:")
print(f"http://localhost:8000{url}")
print("=" * 60)
print("\nSe ainda não funcionar, verifique:")
print("1. Você está logado no sistema?")
print("2. Está acessando a URL correta?")
print("3. Há algum erro no console do navegador (F12)?")
print("=" * 60)
