import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "my_project.settings")
django.setup()

from core.models import Partner, PartnerIntegration

# Pegar configurações do .env
api_url = os.getenv("API_URL", "").strip('"')
cookie_key = os.getenv("COOKIE_KEY", "").strip('"')
sync_token = os.getenv("SYNC_TOKEN", "").strip('"')

print("🔍 Configurações encontradas no .env:")
print(f"   API_URL: {api_url[:50]}...")
print(f"   COOKIE_KEY: {cookie_key[:50]}...")
print(f"   SYNC_TOKEN: {sync_token[:50]}...")

# Pegar parceiro Paack
try:
    paack = Partner.objects.get(name__iexact="paack")
    print(f"\n✅ Parceiro Paack encontrado: {paack}")
    
    # Pegar ou criar integração
    integration, created = PartnerIntegration.objects.get_or_create(
        partner=paack,
        integration_type="API",
        defaults={
            "endpoint_url": api_url,
            "is_active": True,
            "sync_frequency_minutes": 15,
        }
    )
    
    # Atualizar auth_config com todas as configurações
    integration.auth_config = {
        "type": "custom_paack",
        "api_url": api_url,
        "cookie_key": cookie_key,
        "sync_token": sync_token,
        "description": "AppSheet API - Paack Integration (migrated from .env)"
    }
    integration.endpoint_url = api_url
    integration.is_active = True
    integration.save()
    
    print(f"\n{'🆕' if created else '🔄'} Integração Paack {'criada' if created else 'atualizada'}!")
    print(f"   ID: {integration.id}")
    print(f"   Endpoint: {integration.endpoint_url[:60]}...")
    print(f"   Auth Config: {len(str(integration.auth_config))} caracteres")
    print(f"   Ativa: {integration.is_active}")
    print(f"   Sync: {integration.sync_frequency_minutes} minutos")
    
    print("\n✅ Migração concluída com sucesso!")
    
except Partner.DoesNotExist:
    print("\n❌ Parceiro Paack não encontrado!")
    print("Execute: python setup_integrations.py primeiro")

