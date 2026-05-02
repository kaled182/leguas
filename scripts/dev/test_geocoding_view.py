"""
Testa a view geocoding_failures_report diretamente.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_project.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
from orders_manager.views import geocoding_failures_report
from django.contrib.auth import get_user_model

User = get_user_model()

# Criar request factory
factory = RequestFactory()

# Criar request
request = factory.get('/orders/geocoding-failures/')

# Tentar criar um usuário de teste ou usar um existente
try:
    user = User.objects.first()
    if not user:
        print("❌ Nenhum usuário encontrado. Crie um super usuário primeiro.")
        exit(1)
    request.user = user
    print(f"✓ Usando usuário: {user.username}")
except Exception as e:
    print(f"❌ Erro ao obter usuário: {e}")
    exit(1)

# Testar view
try:
    print("\nTestando view geocoding_failures_report...")
    response = geocoding_failures_report(request)
    print(f"✓ Status Code: {response.status_code}")
    print(f"✓ Content-Type: {response.get('Content-Type', 'N/A')}")
    
    if response.status_code == 200:
        print("✓ View executou com sucesso!")
    else:
        print(f"⚠ Status inesperado: {response.status_code}")
        
except Exception as e:
    print(f"❌ Erro ao executar view: {e}")
    import traceback
    traceback.print_exc()
