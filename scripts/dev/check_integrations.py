#!/usr/bin/env python
"""
Script para verificar e criar integração PAACK
"""
import django
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "my_project.settings")
django.setup()

from core.models import Partner, PartnerIntegration

print("=" * 60)
print("VERIFICAÇÃO DE PARCEIROS E INTEGRAÇÕES")
print("=" * 60)

# Listar todos os parceiros
partners = Partner.objects.all()
print(f"\n📦 Total de parceiros: {partners.count()}")

if partners.exists():
    print("\nParceiros cadastrados:")
    for partner in partners:
        print(f"  • {partner.name} ({partner.nif}) - {'✓ Ativo' if partner.is_active else '✗ Inativo'}")
        
        # Listar integrações
        integrations = partner.integrations.all()
        if integrations.exists():
            print(f"    Integrações:")
            for integration in integrations:
                status = f"{'✓' if integration.is_active else '✗'} {integration.get_integration_type_display()}"
                last_sync = integration.last_sync_at.strftime("%d/%m/%Y %H:%M") if integration.last_sync_at else "Nunca"
                print(f"      - {status} | Última sync: {last_sync}")
        else:
            print(f"    ⚠️  Sem integrações")
else:
    print("\n⚠️  Nenhum parceiro cadastrado")

# Verificar se existe PAACK
paack_partner = Partner.objects.filter(name__icontains="paack").first()

if paack_partner:
    print(f"\n✓ Parceiro PAACK encontrado: {paack_partner.name}")
    print(f"  NIF: {paack_partner.nif}")
    print(f"  Email: {paack_partner.contact_email}")
    print(f"  Ativo: {'Sim' if paack_partner.is_active else 'Não'}")
    print(f"  Integrações: {paack_partner.integrations.count()}")
else:
    print("\n❌ Parceiro PAACK NÃO encontrado")
    print("\nCriando parceiro PAACK...")
    
    try:
        paack_partner = Partner.objects.create(
            name="Paack Portugal",
            nif="PT123456789",
            contact_email="portugal@paack.co",
            contact_phone="+351 912 000 000",
            default_delivery_time_days=1,
            auto_assign_orders=True,
            is_active=True,
            notes="Parceiro logístico principal - API de entregas"
        )
        print(f"✓ Parceiro PAACK criado: {paack_partner.name}")
        
        # Criar integração API para PAACK
        integration = PartnerIntegration.objects.create(
            partner=paack_partner,
            integration_type="API",
            endpoint_url="https://api.paack.co/v1",
            sync_frequency_minutes=15,
            is_active=True,
            auth_config={
                "type": "bearer",  
                "api_key": "***",
            }
        )
        print(f"✓ Integração API criada")
        
    except Exception as e:
        print(f"❌ Erro: {e}")

print("\n" + "=" * 60)
print("RESUMO")
print("=" * 60)

total_partners = Partner.objects.count()
active_partners = Partner.objects.filter(is_active=True).count()
total_integrations = PartnerIntegration.objects.count()
active_integrations = PartnerIntegration.objects.filter(is_active=True).count()

print(f"\n📊 Parceiros: {total_partners} total | {active_partners} ativos")
print(f"🔌 Integrações: {total_integrations} total | {active_integrations} ativas")

print("\n💡 Acesse: http://localhost:8000/core/integrations/dashboard/")
print("=" * 60)
