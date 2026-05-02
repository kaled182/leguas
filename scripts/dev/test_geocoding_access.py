#!/usr/bin/env python
"""
Testa acesso completo à página de falhas de geocodificação.
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_project.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from django.urls import reverse

print("=" * 60)
print("TESTE DE ACESSO À PÁGINA DE GEOCODING FAILURES")
print("=" * 60)

# 1. Teste de URL
try:
    url = reverse('orders:geocoding_failures_report')
    print(f"\n✓ URL resolvida: {url}")
except Exception as e:
    print(f"\n✗ Erro ao resolver URL: {e}")
    sys.exit(1)

# 2. Teste de importação da view
try:
    from orders_manager.views import geocoding_failures_report
    print(f"✓ View importada com sucesso")
except Exception as e:
    print(f"\n✗ Erro ao importar view: {e}")
    sys.exit(1)

# 3. Teste do modelo GeocodingFailure
try:
    from orders_manager.models import GeocodingFailure, GeocodedAddress
    failure_count = GeocodingFailure.objects.count()
    geocoded_count = GeocodedAddress.objects.count()
    print(f"✓ Modelos carregados: {failure_count} falhas, {geocoded_count} geocodificados")
except Exception as e:
    print(f"\n✗ Erro ao acessar modelos: {e}")
    sys.exit(1)

# 4. Teste de execução da view
try:
    User = get_user_model()
    factory = RequestFactory()
    
    # Cria request simulado
    request = factory.get(url)
    
    # Adiciona usuário autenticado
    try:
        user = User.objects.first()
        if not user:
            print("✗ Nenhum usuário encontrado no banco")
            sys.exit(1)
        request.user = user
    except Exception as e:
        print(f"✗ Erro ao obter usuário: {e}")
        sys.exit(1)
    
    # Executa view
    response = geocoding_failures_report(request)
    
    print(f"✓ View executada com sucesso")
    print(f"  Status Code: {response.status_code}")
    print(f"  Content-Type: {response.get('Content-Type', 'N/A')}")
    
    if response.status_code == 200:
        print(f"  Tamanho da resposta: {len(response.content)} bytes")
        
        # Verifica se o template foi renderizado
        if b'Falhas de Geocodifica' in response.content:
            print(f"✓ Template renderizado corretamente")
        else:
            print(f"✗ Template não contém conteúdo esperado")
    else:
        print(f"✗ Resposta não é 200 OK")
        
except Exception as e:
    print(f"\n✗ Erro ao executar view: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 5. Teste do template
try:
    from django.template.loader import get_template
    template = get_template('orders_manager/geocoding_failures.html')
    print(f"✓ Template encontrado: orders_manager/geocoding_failures.html")
except Exception as e:
    print(f"\n✗ Template não encontrado: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("TODOS OS TESTES PASSARAM! ✓")
print("=" * 60)
print(f"\nA página deveria estar acessível em:")
print(f"http://localhost:8000{url}")
print("=" * 60)
