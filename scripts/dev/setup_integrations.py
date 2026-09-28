#!/usr/bin/env python
"""
Criar integrações de exemplo para parceiros (dev)
"""
import django
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "my_project.settings")
django.setup()

from core.models import Partner, PartnerIntegration

print("=" * 60)
print("ATIVANDO INTEGRAÇÕES")
print("=" * 60)

# Criar integrações para outros parceiros (exemplo)
partners_config = [
    {"name": "Amazon", "type": "API", "url": "https://api.amazon-logistics.com/v1", "freq": 30},
    {"name": "DPD", "type": "SFTP", "url": "sftp://dpd.pt/import", "freq": 60},
    {"name": "Glovo", "type": "WEBHOOK", "url": "https://api.glovoapp.com/webhook", "freq": 5},
]

for config in partners_config:
    partner = Partner.objects.filter(name__icontains=config["name"]).first()
    if partner and not partner.integrations.exists():
        integration = PartnerIntegration.objects.create(
            partner=partner,
            integration_type=config["type"],
            endpoint_url=config["url"],
            sync_frequency_minutes=config["freq"],
            is_active=True,
        )
        print(f"✓ Integração {config['type']} criada para {partner.name}")

print("\n" + "=" * 60)
print("RESUMO FINAL")
print("=" * 60)

total_integrations = PartnerIntegration.objects.count()
active_integrations = PartnerIntegration.objects.filter(is_active=True).count()

print(f"\n🔌 Total de integrações: {total_integrations}")
print(f"✓  Integrações ativas: {active_integrations}")

print("\nIntegrações ativas por parceiro:")
for partner in Partner.objects.filter(is_active=True):
    active = partner.integrations.filter(is_active=True).count()
    if active > 0:
        integration = partner.integrations.filter(is_active=True).first()
        print(f"  • {partner.name}: {integration.get_integration_type_display()}")

print("\n💡 Acesse: http://localhost:8000/core/integrations/dashboard/")
print("=" * 60)
