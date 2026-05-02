#!/usr/bin/env python
"""
Script para testar se o mapa está funcionando
"""
import django
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "my_project.settings")
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model

User = get_user_model()

# Criar um client de teste
client = Client()

# Tentar obter um superuser
try:
    user = User.objects.filter(is_superuser=True).first()
    if user:
        print(f"✓ Usuário encontrado: {user.username}")
        
        # Fazer login
        client.force_login(user)
        print(f"✓ Login realizado com sucesso")
        
        # Acessar a página do mapa
        response = client.get('/pricing/zones/map/')
        print(f"✓ Status: {response.status_code}")
        
        if response.status_code == 200:
            # Verificar se o mapa está no HTML
            content = response.content.decode('utf-8')
            
            if 'id="map"' in content:
                print("✓ Elemento #map encontrado no HTML")
            else:
                print("✗ Elemento #map NÃO encontrado")
            
            if 'L.map(' in content:
                print("✓ Inicialização do Leaflet encontrada")
            else:
                print("✗ Inicialização do Leaflet NÃO encontrada")
            
            if 'leaflet.js' in content:
                print("✓ Leaflet.js sendo carregado")
            else:
                print("✗ Leaflet.js NÃO encontrado")
            
            # Verificar se há zonas
            if 'const zones = [' in content:
                print("✓ Array de zonas encontrado")
                # Contar quantas zonas
                import re
                zones_count = content.count('L.marker([')
                print(f"  → {zones_count} marcadores serão criados")
            else:
                print("✗ Array de zonas NÃO encontrado")
        else:
            print(f"✗ Erro ao acessar página: {response.status_code}")
    else:
        print("✗ Nenhum superuser encontrado")
        print("  Criando um usuário de teste...")
        user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='admin123'
        )
        print(f"✓ Usuário criado: {user.username} / admin123")
except Exception as e:
    print(f"✗ Erro: {e}")
    import traceback
    traceback.print_exc()
