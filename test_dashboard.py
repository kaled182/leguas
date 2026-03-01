#!/usr/bin/env python
"""Quick test script for financial dashboard"""

import os

import django
from django.test import Client

from settlements.models import DriverClaim, DriverSettlement, PartnerInvoice

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "my_project.settings")
django.setup()


# Test models
print("=" * 50)
print("DATABASE CHECK")
print("=" * 50)
print(f"Invoices: {PartnerInvoice.objects.count()}")
print(f"Settlements: {DriverSettlement.objects.count()}")
print(f"Claims: {DriverClaim.objects.count()}")
print()

# Test view without login
print("=" * 50)
print("VIEW TEST (no auth)")
print("=" * 50)
c = Client()
response = c.get("/settlements/financial/")
print(f"Status Code: {response.status_code}")

if response.status_code == 302:
    print(f"Redirect to: {response.url}")
    print("✅ Login required - working as expected")
elif response.status_code == 200:
    print("✅ Page loaded successfully")
elif response.status_code == 500:
    print("❌ Server error")
    if hasattr(response, "content"):
        print(response.content[:500])
else:
    print(f"⚠️  Unexpected status: {response.status_code}")

print()
print("=" * 50)
print("SAMPLE DATA CHECK")
print("=" * 50)

# Check recent invoices
recent_invoices = PartnerInvoice.objects.select_related("partner").order_by(
    "-created_at"
)[:3]
for inv in recent_invoices:
    print(
        f"Invoice: {inv.invoice_number} - {inv.partner.name} - €{inv.net_amount} - {inv.status}"
    )

print()

# Check recent settlements
recent_settlements = DriverSettlement.objects.select_related(
    "driver", "partner"
).order_by("-created_at")[:3]
for sett in recent_settlements:
    driver_name = sett.driver.nome_completo if sett.driver else "N/A"
    print(f"Settlement: {driver_name} - €{sett.net_amount} - {sett.status}")

print()

# Check recent claims
recent_claims = DriverClaim.objects.select_related("driver").order_by("-created_at")[:3]
for claim in recent_claims:
    driver_name = claim.driver.nome_completo if claim.driver else "N/A"
    print(
        f"Claim: {driver_name} - {claim.get_claim_type_display()} - €{claim.amount} - {claim.status}"
    )

print()
print("=" * 50)
print("✅ ALL CHECKS COMPLETED")
print("=" * 50)
