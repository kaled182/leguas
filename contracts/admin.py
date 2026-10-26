from django.contrib import admin

from .models import (
    ContractSettings, GeneratedContract, HubContractTerms, HubZoneTariff,
)


@admin.register(ContractSettings)
class ContractSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not ContractSettings.objects.exists()


@admin.register(HubContractTerms)
class HubContractTermsAdmin(admin.ModelAdmin):
    list_display = (
        "hub", "signing_place", "allows_monthly", "allows_weekly",
        "monthly_payment_mode", "monthly_payment_value", "weekly_payday",
    )


@admin.register(HubZoneTariff)
class HubZoneTariffAdmin(admin.ModelAdmin):
    list_display = (
        "hub", "cp4", "zone_name", "tier", "price_monthly", "price_weekly",
        "valid_from", "is_active",
    )
    list_filter = ("hub", "tier", "is_active")
    list_editable = ("price_monthly", "price_weekly", "is_active")
    search_fields = ("cp4", "zone_name")


@admin.register(GeneratedContract)
class GeneratedContractAdmin(admin.ModelAdmin):
    list_display = ("driver", "kind", "status", "regime", "generated_at", "signed_at")
    list_filter = ("kind", "status", "regime")
    raw_id_fields = ("driver",)
    readonly_fields = ("content_hash", "generated_at")
