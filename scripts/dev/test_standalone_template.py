#!/usr/bin/env python
import os
import sys
import django

sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_project.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model

c = Client()
u = get_user_model().objects.first()
c.force_login(u)
r = c.get('/orders/geocoding-failures/')

print('=' * 60)
print('TESTE DO NOVO TEMPLATE STANDALONE')
print('=' * 60)
print(f'STATUS: {r.status_code}')
print(f'TAMANHO: {len(r.content)} bytes')

html = r.content.decode('utf-8')

# Checks específicos do novo template
checks = {
    'Emoji no título': '🗺️' in html,
    'Estatísticas Card': 'stat-card' in html,
    'Valor 7': '>7<' in html,
    'Valor 456': '>456<' in html,
    'Filtros': '<form method="get">' in html,
    'Endereço Original': 'Endereço Original' in html,
    'Pedido link': 'order_detail' in html,
    'CSS inline': '<style>' in html,
    'Sem dependências externas': 'tailwind' not in html.lower() and 'bootstrap' not in html.lower(),
}

print('\nVERIFICAÇÕES:')
for name, result in checks.items():
    status = '✓' if result else '✗'
    print(f'{status} {name}')

# Mostra preview
print('\n--- PREVIEW (primeiros 500 chars) ---')
print(html[:500])

print('=' * 60)
if all(checks.values()):
    print('✅ TUDO OK! Template standalone funcionando!')
else:
    print('⚠️  Alguns elementos faltando')
print('=' * 60)
