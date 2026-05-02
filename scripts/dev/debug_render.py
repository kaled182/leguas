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

html = r.content.decode('utf-8')

# Procura pelo bloco content
import re
content_match = re.search(r'{% block content %}.*?{% endblock %}', html)
if content_match:
    print("ERRO: Template tags não foram renderizados!")
else:
    print("✓ Template tags foram renderizados")

# Procura por elementos específicos
if 'container mx-auto' in html:
    print("✓ Container mx-auto encontrado")
    # Encontra onde começa o container
    idx = html.find('container mx-auto')
    print(f"\nConteúdo perto do container (500 chars):")
    print(html[idx:idx+500])
else:
    print("✗ Container mx-auto NÃO encontrado")

# Procura por "Relatório de Falhas"
if 'Relatório de Falhas' in html or 'Relatorio de Falhas' in html:
    print("✓ Título encontrado")
else:
    print("✗ Título NÃO encontrado")

# Verifica se o stats existe
if 'stats.unresolved' in html:
    print("✗ Variável não renderizada: stats.unresolved")
elif '>7<' in html or '>456<' in html:
    print("✓ Estatísticas renderizadas")
else:
    print("? Estatísticas podem estar presentes")

# Mostra a estrutura do body
body_start = html.find('<body')
if body_start > 0:
    body_end = html.find('>', body_start) + 1
    next_500 = html[body_end:body_end+1000]
    print(f"\n--- Primeiros 1000 chars após <body> ---")
    print(next_500)
