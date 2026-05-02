#!/usr/bin/env python
"""
Script para ver os primeiros 2 objetos do array
"""
import django
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "my_project.settings")
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
import re

User = get_user_model()

client = Client()
user = User.objects.filter(is_superuser=True).first()
client.force_login(user)

response = client.get('/pricing/zones/map/')
content = response.content.decode('utf-8')

# Extrair o array de zonas
match = re.search(r'const zones = \[(.*?)\];', content, re.DOTALL)
if match:
    zones_str = match.group(1)
    
    # Pegar os primeiros 500 caracteres
    print("=== PRIMEIROS 500 CARACTERES DO ARRAY ===")
    print(zones_str[:500])
    print("\n=== PRÓXIMOS 500 CARACTERES ===")
    print(zones_str[500:1000])
