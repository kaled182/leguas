"""
Testa se a URL de geocoding failures está configurada corretamente.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_project.settings')
django.setup()

from django.urls import reverse

try:
    url = reverse('orders:geocoding_failures_report')
    print(f"✓ URL encontrada: {url}")
except Exception as e:
    print(f"✗ Erro: {e}")

# Testar se a view existe
try:
    from orders_manager.views import geocoding_failures_report
    print(f"✓ View encontrada: geocoding_failures_report")
except Exception as e:
    print(f"✗ Erro ao importar view: {e}")

# Verificar URLconf
from django.conf import settings
print(f"\nROOT_URLCONF: {settings.ROOT_URLCONF}")

# Listar URLs do app orders
from django.urls import get_resolver
resolver = get_resolver()

print("\nURLs do app 'orders':")
for pattern in resolver.url_patterns:
    if hasattr(pattern, 'app_name') and pattern.app_name == 'orders':
        for url_pattern in pattern.url_patterns:
            print(f"  - {url_pattern.pattern}")
