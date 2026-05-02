#!/usr/bin/env python
"""
Atualizar status de sincronização Delnext
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_project.settings')
django.setup()

from core.models import Partner, PartnerIntegration
from django.utils import timezone

print("=" * 70)
print("ATUALIZAR STATUS SINCRONIZAÇÃO DELNEXT")
print("=" * 70)

try:
    # Encontrar integração Delnext
    delnext = Partner.objects.get(name='Delnext')
    integration = delnext.integrations.first()
    
    if not integration:
        print("\n❌ Nenhuma integração Delnext encontrada!")
    else:
        print(f"\n📊 Integração atual:")
        print(f"   • ID: {integration.id}")
        print(f"   • Status: {integration.last_sync_status or 'Nunca'}")
        print(f"   • Última sync: {integration.last_sync_at or 'Nunca'}")
        
        # Atualizar status
        integration.last_sync_at = timezone.now()
        integration.last_sync_status = "SUCCESS"
        integration.last_sync_stats = {
            "total": 144,
            "created": 144,
            "updated": 0,
            "errors": 0,
            "zone": "VianaCastelo", 
            "date": "2026-02-27"
        }
        integration.save()
        
        print(f"\n✅ Status atualizado com sucesso!")
        print(f"   • Última sync: {integration.last_sync_at}")
        print(f"   • Status: {integration.last_sync_status}")
        print(f"   • Stats: {integration.last_sync_stats}")
        
    print("\n" + "=" * 70)
    print("✅ ATUALIZAÇÃO COMPLETA!")
    print("=" * 70)
    print("\n💡 Agora recarregue a página do parceiro para ver as mudanças:")
    print("   http://localhost:8000/core/partners/5/")
    
except Partner.DoesNotExist:
    print("\n❌ Parceiro 'Delnext' não encontrado!")
except Exception as e:
    print(f"\n❌ ERRO: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
