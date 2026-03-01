"""
Script de teste para verificar paginação e funcionalidades do sistema
"""

import os

import django
from django.contrib.auth import get_user_model

from settlements.models import DriverClaim, DriverSettlement, PartnerInvoice

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "my_project.settings")
django.setup()


User = get_user_model()

print("=" * 60)
print("TESTE DE FUNCIONALIDADES - SETTLEMENTS")
print("=" * 60)

# Contagem de dados
invoice_count = PartnerInvoice.objects.count()
settlement_count = DriverSettlement.objects.count()
claim_count = DriverClaim.objects.count()

print(f"\n📊 DADOS DISPONÍVEIS:")
print(f"  • Invoices: {invoice_count}")
print(f"  • Settlements: {settlement_count}")
print(f"  • Claims: {claim_count}")

# Status da paginação
print(f"\n📄 STATUS DA PAGINAÇÃO (25 por página):")
print(f"  • Invoices: {'🔴 Oculta (<25)' if invoice_count < 25 else '🟢 Visível'}")
print(
    f"  • Settlements: {'🔴 Oculta (<25)' if settlement_count < 25 else '🟢 Visível'}"
)
print(f"  • Claims: {'🔴 Oculta (<25)' if claim_count < 25 else '🟢 Visível'}")

# Verificar amostras de dados
print(f"\n📋 AMOSTRAS RECENTES:")

if invoice_count > 0:
    recent_invoice = (
        PartnerInvoice.objects.select_related("partner").order_by("-created_at").first()
    )
    print(f"\n  Invoice #{recent_invoice.invoice_number}")
    print(f"    Partner: {recent_invoice.partner.name}")
    print(f"    Valor: €{recent_invoice.net_amount:,.2f}")
    print(f"    Status: {recent_invoice.status}")
    print(f"    ID: {recent_invoice.id}")

if settlement_count > 0:
    recent_settlement = (
        DriverSettlement.objects.select_related("driver")
        .order_by("-created_at")
        .first()
    )
    print(f"\n  Settlement")
    print(f"    Motorista: {recent_settlement.driver.nome_completo}")
    print(f"    Período: {recent_settlement.period_type}")
    print(f"    Valor: €{recent_settlement.net_amount:,.2f}")
    print(f"    Status: {recent_settlement.status}")
    print(f"    ID: {recent_settlement.id}")

if claim_count > 0:
    recent_claim = (
        DriverClaim.objects.select_related("driver").order_by("-created_at").first()
    )
    print(f"\n  Claim")
    print(f"    Motorista: {recent_claim.driver.nome_completo}")
    print(f"    Tipo: {recent_claim.get_claim_type_display()}")
    print(f"    Valor: €{recent_claim.amount:,.2f}")
    print(f"    Status: {recent_claim.status}")
    print(f"    ID: {recent_claim.id}")

print("\n" + "=" * 60)
print("🔗 URLs PARA TESTAR NO NAVEGADOR:")
print("=" * 60)
print("\n📑 LISTAS (com paginação):")
print("  http://localhost:8000/settlements/invoices/")
print("  http://localhost:8000/settlements/settlements/")
print("  http://localhost:8000/settlements/claims/")

if invoice_count > 0:
    inv_id = PartnerInvoice.objects.first().id
    print(f"\n📄 DETALHES (páginas modernizadas):")
    print(f"  http://localhost:8000/settlements/invoices/{inv_id}/")

if settlement_count > 0:
    set_id = DriverSettlement.objects.first().id
    print(f"  http://localhost:8000/settlements/settlements/{set_id}/")

if claim_count > 0:
    clm_id = DriverClaim.objects.first().id
    print(f"  http://localhost:8000/settlements/claims/{clm_id}/")

if invoice_count > 0:
    inv_id = PartnerInvoice.objects.first().id
    print(f"\n📥 PDFs:")
    print(f"  http://localhost:8000/settlements/invoices/{inv_id}/pdf/")

if settlement_count > 0:
    set_id = DriverSettlement.objects.first().id
    print(f"  http://localhost:8000/settlements/settlements/{set_id}/pdf/")

print("\n🔍 FILTROS PARA TESTAR:")
print("  • Status: ?status=PENDING")
print("  • Data: ?date_from=2026-01-01&date_to=2026-02-28")
print("  • Busca: ?search=Paulo")
print("  • Paginação: ?page=2")
print("  • Combinado: ?status=PAID&date_from=2026-01-01&page=1")

print("\n✅ SISTEMA PRONTO PARA TESTE!")
print("=" * 60)
