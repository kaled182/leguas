#!/usr/bin/env python
"""
Teste rápido das funcionalidades Typebot via API Django
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_project.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from system_config.models import SystemConfiguration

def test_typebot_views():
    """Testa as views do Typebot"""
    print("🧪 Testando Views do Typebot\n")
    
    # Get or create superuser
    User = get_user_model()
    user, created = User.objects.get_or_create(
        username='admin',
        defaults={'is_staff': True, 'is_superuser': True}
    )
    if created:
        user.set_password('admin')
        user.save()
    
    # Create test client
    client = Client()
    client.force_login(user)
    
    # Test 1: Test Connection View
    print("1️⃣ Testando endpoint de teste de conexão...")
    response = client.post('/system/typebot/test-connection/')
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        if data.get('success'):
            print(f"   ✅ {data.get('message')}")
            print(f"   Status: {data.get('status')}")
            print(f"   Auth: {data.get('auth_status')}")
        else:
            print(f"   ⚠️ {data.get('error')}")
    else:
        print(f"   Response: {response.content[:200]}")
    
    # Test 2: Generate Secret View
    print("\n2️⃣ Testando geração de encryption secret...")
    response = client.post('/system/typebot/generate-secret/')
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        if data.get('success'):
            secret = data.get('secret', '')
            print(f"   ✅ Secret gerado: {secret[:16]}... ({len(secret)} caracteres)")
        else:
            print(f"   ❌ {data.get('error')}")
    else:
        print(f"   Response: {response.content[:200]}")
    
    # Test 3: Verify configuration
    print("\n3️⃣ Verificando configuração salva...")
    config = SystemConfiguration.get_config()
    print(f"   Typebot Enabled: {config.typebot_enabled}")
    print(f"   Builder URL: {config.typebot_builder_url}")
    print(f"   Has Encryption Secret: {bool(config.typebot_encryption_secret)}")
    print(f"   Admin Email: {config.typebot_admin_email}")
    
    print("\n✅ Todos os testes concluídos!")
    print("\n💡 Próximos passos:")
    print("   1. Acesse http://localhost:8000/system/")
    print("   2. Vá até a seção 'Typebot - Automação de Conversas'")
    print("   3. Clique em 'Testar Conexão'")
    print("   4. Clique em 'Abrir Typebot'")

if __name__ == '__main__':
    test_typebot_views()
