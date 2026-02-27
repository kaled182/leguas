#!/usr/bin/env python
"""
Script para testar funcionalidades do Typebot
"""
import os
import sys
import django
import requests

# Setup Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_project.settings')
django.setup()

from system_config.models import SystemConfiguration

def test_typebot_connection():
    """Testa conexão com Typebot"""
    config = SystemConfiguration.get_config()
    
    print("🔍 Testando Typebot...")
    print(f"  • Enabled: {config.typebot_enabled}")
    print(f"  • Builder URL: {config.typebot_builder_url}")
    print(f"  • Viewer URL: {config.typebot_viewer_url}")
    print()
    
    if not config.typebot_enabled:
        print("❌ Typebot não está habilitado")
        return
    
    if not config.typebot_builder_url:
        print("❌ Builder URL não configurada")
        return
    
    builder_url = config.typebot_builder_url.rstrip('/')
    
    # Convert localhost to internal Docker network address
    internal_builder_url = builder_url.replace('http://localhost:8081', 'http://typebot_builder:3000')
    
    # Teste 1: Health Check
    print("1️⃣ Testando Health Endpoint...")
    print(f"   URL externa: {builder_url}")
    print(f"   URL interna: {internal_builder_url}")
    try:
        response = requests.get(f"{internal_builder_url}/api/health", timeout=10)
        if response.status_code == 200:
            print(f"   ✅ Health OK (Status: {response.status_code})")
        else:
            print(f"   ⚠️  Health endpoint retornou: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
    except requests.exceptions.ConnectionError as e:
        print(f"   ❌ Erro de conexão: {e}")
        print(f"   💡 Verifique se o container está rodando: docker compose ps typebot_builder")
        return
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return
    
    # Teste 2: Authentication
    print("\n2️⃣ Testando Autenticação...")
    if config.typebot_admin_email and config.typebot_admin_password:
        try:
            auth_response = requests.post(
                f"{internal_builder_url}/api/auth/signin",
                json={
                    "email": config.typebot_admin_email,
                    "password": config.typebot_admin_password
                },
                timeout=10,
                allow_redirects=False  # Don't follow redirects to localhost
            )
            
            if auth_response.status_code == 200:
                data = auth_response.json()
                if data.get('user'):
                    print(f"   ✅ Autenticação bem-sucedida!")
                    print(f"   User: {data['user'].get('email', 'N/A')}")
                else:
                    print(f"   ⚠️  Resposta sem usuário: {data}")
            elif auth_response.status_code == 302:
                print(f"   ℹ️  Redirect recebido (pode ser normal para NextAuth)")
                print(f"   Location: {auth_response.headers.get('Location', 'N/A')}")
            else:
                print(f"   ❌ Falha na autenticação (Status: {auth_response.status_code})")
                print(f"   Response: {auth_response.text[:200]}")
        except Exception as e:
            print(f"   ❌ Erro ao autenticar: {e}")
    else:
        print("   ⚠️  Credenciais não configuradas")
    
    # Teste 3: Viewer
    print("\n3️⃣ Testando Viewer...")
    if config.typebot_viewer_url:
        viewer_url = config.typebot_viewer_url.rstrip('/')
        internal_viewer_url = viewer_url.replace('http://localhost:8082', 'http://typebot_viewer:3000')
        print(f"   URL externa: {viewer_url}")
        print(f"   URL interna: {internal_viewer_url}")
        try:
            viewer_response = requests.get(internal_viewer_url, timeout=10)
            if viewer_response.status_code == 200:
                print(f"   ✅ Viewer OK (Status: {viewer_response.status_code})")
            else:
                print(f"   ⚠️  Viewer retornou: {viewer_response.status_code}")
        except Exception as e:
            print(f"   ❌ Erro: {e}")
    
    print("\n✅ Teste concluído!")

if __name__ == '__main__':
    test_typebot_connection()
