"""
Step 1: Criar Partner Delnext
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_project.settings')
django.setup()

from core.models import Partner

# Criar Partner Delnext
partner, created = Partner.objects.get_or_create(
    name="Delnext",
    defaults={
        "nif": "999999999",  # TODO: NIF real
        "contact_email": "operacoes@delnext.com",
        "contact_phone": "",
        "is_active": True,
    }
)

if created:
    print("✅ Partner 'Delnext' criado com sucesso!")
else:
    print("ℹ️  Partner 'Delnext' já existe")

print(f"   ID: {partner.id}")
print(f"   Nome: {partner.name}")
print(f"   NIF: {partner.nif}")
print(f"   Email: {partner.contact_email}")
