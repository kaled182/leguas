#!/usr/bin/env python
"""
Teste de conteúdo da página de geocoding failures
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

User = get_user_model()
client = Client()

# Login
user = User.objects.filter(is_active=True).first()
client.force_login(user)

# Acessa a página
url = reverse('orders:geocoding_failures_report')
response = client.get(url)

print(f"Status: {response.status_code}")
html = response.content.decode('utf-8')

# Busca por elementos específicos
checks = {
    'Título H1': '<h1' in html or '<h2' in html,
    'Estatísticas Não Resolvidos': 'Não Resolvidos' in html,
    'Card de Stats': 'stat-card' in html or 'card' in html,
    'Valor 7': '>7<' in html,
    'Valor 456': '>456<' in html,
    'Taxa 98': '98' in html,
    'Formulário': '<form' in html,
    'Lista de Falhas': 'Pedido' in html and ('7472285' in html or 'external_reference' in html),
    'Bootstrap': 'bootstrap' in html.lower() or 'btn' in html,
}

print("\n--- ELEMENTOS ENCONTRADOS ---")
for name, found in checks.items():
    status = "✓" if found else "✗"
    print(f"{status} {name}")

# Procura por "7" como valor de estatísticas
import re
numbers = re.findall(r'>\s*(\d+)\s*<', html)
print(f"\nNúmeros encontrados no HTML: {numbers[:20]}")

# Mostra parte do conteúdo principal
main_start = html.find('<main')
if main_start > 0:
    main_end = html.find('</main>', main_start)
    if main_end > 0:
        main_content = html[main_start:main_end+7]
        print(f"\n--- CONTEÚDO DO <main> ({len(main_content)} chars) ---")
        print(main_content[:1000])
else:
    # Procura por container
    container_start = html.find('class="container')
    if container_start > 0:
        print(f"\n--- ENCONTROU CONTAINER em posição {container_start} ---")
        print(html[container_start:container_start+500])
    else:
        print("\n--- NÃO ENCONTROU <main> nem container ---")
        # Mostra depois do </nav> (sidebar)
        nav_end = html.find('</nav>')
        if nav_end > 0:
            print(f"Conteúdo após </nav>:")
            print(html[nav_end:nav_end+1000])
