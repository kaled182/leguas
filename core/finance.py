"""Helpers financeiros centralizados — resolução de preços, margens, etc."""
from decimal import Decimal


def resolve_driver_price(driver, partner):
    """Resolve o preço por pacote pago ao motorista usando a cascata:

    1. driver.price_per_package (override individual) — se > 0
    2. driver.empresa_parceira.driver_default_price_per_package (frota)
       — se > 0
    3. partner.driver_default_price_per_package (default global do parceiro)
       — se > 0
    4. Decimal("0") + source="none" (sem preço configurado)

    Returns:
        tuple (price: Decimal, source: str)
        source ∈ {"driver_override", "fleet_default",
                  "partner_default", "none"}
    """
    if driver and driver.price_per_package and driver.price_per_package > 0:
        return (driver.price_per_package, "driver_override")

    fleet = getattr(driver, "empresa_parceira", None) if driver else None
    if (fleet
            and fleet.driver_default_price_per_package
            and fleet.driver_default_price_per_package > 0):
        return (fleet.driver_default_price_per_package, "fleet_default")

    if (partner
            and partner.driver_default_price_per_package
            and partner.driver_default_price_per_package > 0):
        return (partner.driver_default_price_per_package, "partner_default")

    return (Decimal("0"), "none")


def resolve_partner_price(partner):
    """Preço que o parceiro paga à Léguas por pacote (não ao driver)."""
    if partner and partner.price_per_package:
        return partner.price_per_package
    return Decimal("0")


def margin_per_package(driver, partner):
    """Margem por pacote = preço cobrado ao parceiro - preço pago ao driver.

    Returns:
        tuple (margin: Decimal, partner_price: Decimal, driver_price: Decimal,
               driver_price_source: str)
    """
    partner_price = resolve_partner_price(partner)
    driver_price, source = resolve_driver_price(driver, partner)
    margin = partner_price - driver_price
    return (margin, partner_price, driver_price, source)
