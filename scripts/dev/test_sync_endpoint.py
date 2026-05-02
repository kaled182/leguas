#!/usr/bin/env python
"""
Script de teste para verificar o endpoint de sincronização manual
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_project.settings')
django.setup()

from django.test import RequestFactory
from core.views import partner_sync_manual
from core.models import PartnerIntegration
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.auth.models import AnonymousUser
import json

User = get_user_model()

def add_middleware_to_request(request, user=None):
    """Adiciona middleware necessário ao request de teste"""
    # Adicionar session
    middleware = SessionMiddleware(lambda x: None)
    middleware.process_request(request)
    request.session.save()
    
    # Adicionar user
    request.user = user if user else AnonymousUser()
    return request

def test_sync_endpoint():
    """Testa o endpoint de sincronização"""
    
    # Buscar a integração Delnext
    try:
        integration = PartnerIntegration.objects.get(
            partner__name="Delnext",
            is_active=True
        )
        print(f"✅ Integração encontrada: ID {integration.pk}")
        print(f"   Partner: {integration.partner.name}")
        print(f"   URL: {integration.endpoint_url}")
        print(f"   Status: {'Ativa' if integration.is_active else 'Inativa'}")
        print()
        
    except PartnerIntegration.DoesNotExist:
        print("❌ Integração Delnext não encontrada!")
        return
    
    # Criar uma request factory
    factory = RequestFactory()
    
    # Criar ou obter um usuário de teste
    user, created = User.objects.get_or_create(
        username='test_user',
        defaults={'email': 'test@example.com'}
    )
    if created:
        user.set_password('test123')
        user.is_staff = True
        user.save()
        print(f"✅ Usuário de teste criado: {user.username}")
    else:
        print(f"✅ Usuário de teste encontrado: {user.username}")
    print()
    
    # Dados de teste
    sync_data = {
        'date': '2026-02-27',
        'zone': 'VianaCastelo'
    }
    
    # Criar request POST com JSON
    request = factory.post(
        f'/core/integrations/{integration.pk}/sync/',
        data=json.dumps(sync_data),
        content_type='application/json'
    )
    
    # Adicionar middleware e usuário ao request
    request = add_middleware_to_request(request, user)
    
    print("🔄 Testando endpoint de sincronização...")
    print(f"   URL: /core/integrations/{integration.pk}/sync/")
    print(f"   Dados: {sync_data}")
    print()
    
    # Chamar a view
    try:
        response = partner_sync_manual(request, integration.pk)
        
        # Verificar resposta
        response_data = json.loads(response.content.decode('utf-8'))
        
        print("📊 Resposta do endpoint:")
        print(f"   Status Code: {response.status_code}")
        print(f"   Success: {response_data.get('success', False)}")
        
        if response_data.get('success'):
            stats = response_data.get('stats', {})
            print(f"   ✅ Sincronização bem-sucedida!")
            print(f"   Total: {stats.get('total', 0)}")
            print(f"   Criados: {stats.get('created', 0)}")
            print(f"   Atualizados: {stats.get('updated', 0)}")
            print(f"   Erros: {stats.get('errors', 0)}")
            if stats.get('zone'):
                print(f"   Zona: {stats.get('zone')}")
            if stats.get('date'):
                print(f"   Data: {stats.get('date')}")
        else:
            print(f"   ❌ Erro: {response_data.get('error', 'Erro desconhecido')}")
            
    except Exception as e:
        print(f"❌ Erro ao testar endpoint: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_sync_endpoint()
