from django.contrib import admin
from django.utils.html import format_html

from .models import PartnerTariff, PostalZone


@admin.register(PostalZone)
class PostalZoneAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "code",
        "region",
        "formatted_urban",
        "average_delivery_time_hours",
        "formatted_active",
    ]

    list_filter = [
        "region",
        "is_urban",
        "is_active",
    ]

    search_fields = [
        "name",
        "code",
        "postal_code_pattern",
    ]

    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        ("Identificação", {"fields": ("name", "code")}),
        (
            "Padrão de Códigos Postais",
            {"fields": ("postal_code_pattern", "region")},
        ),
        (
            "Coordenadas Geográficas",
            {
                "fields": ("center_latitude", "center_longitude"),
                "classes": ("collapse",),
            },
        ),
        (
            "Características Operacionais",
            {
                "fields": (
                    "is_urban",
                    "average_delivery_time_hours",
                )
            },
        ),
        ("Status", {"fields": ("is_active",)}),
        ("Observações", {"fields": ("notes",)}),
        (
            "Metadados",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def formatted_urban(self, obj):
        if obj.is_urban:
            return format_html('<span style="color: blue;">🏙️ Urbana</span>')
        return format_html('<span style="color: green;">🌳 Rural</span>')

    formatted_urban.short_description = "Tipo"

    def formatted_active(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green;">✓ Ativa</span>')
        return format_html('<span style="color: red;">✗ Inativa</span>')

    formatted_active.short_description = "Status"


@admin.register(PartnerTariff)
class PartnerTariffAdmin(admin.ModelAdmin):
    list_display = [
        "partner",
        "postal_zone",
        "formatted_base_price",
        "success_bonus",
        "valid_from",
        "valid_until",
        "formatted_active",
    ]

    list_filter = [
        "partner",
        "postal_zone__region",
        "is_active",
        ("valid_from", admin.DateFieldListFilter),
    ]

    search_fields = [
        "partner__name",
        "postal_zone__name",
        "postal_zone__code",
    ]

    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        ("Parceiro e Zona", {"fields": ("partner", "postal_zone")}),
        (
            "Preços",
            {
                "fields": (
                    "base_price",
                    "success_bonus",
                )
            },
        ),
        (
            "Penalizações",
            {
                "fields": (
                    "failure_penalty",
                    "late_delivery_penalty",
                )
            },
        ),
        (
            "Modificadores",
            {
                "fields": (
                    "weekend_multiplier",
                    "express_multiplier",
                )
            },
        ),
        (
            "Validade",
            {
                "fields": (
                    "valid_from",
                    "valid_until",
                    "is_active",
                )
            },
        ),
        ("Observações", {"fields": ("notes",)}),
        (
            "Metadados",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def formatted_base_price(self, obj):
        total = obj.base_price + obj.success_bonus
        return format_html(
            "<strong>€{:.2f}</strong> <small>(base: €{:.2f} + bónus: €{:.2f})</small>",
            total,
            obj.base_price,
            obj.success_bonus,
        )

    formatted_base_price.short_description = "Preço Total"

    def formatted_active(self, obj):
        if obj.is_active:
            if obj.is_valid_on_date():
                return format_html('<span style="color: green;">✓ Ativa</span>')
            return format_html('<span style="color: orange;">⚠ Fora do período</span>')
        return format_html('<span style="color: red;">✗ Inativa</span>')

    formatted_active.short_description = "Status"

    actions = ["duplicate_tariff"]

    def duplicate_tariff(self, request, queryset):
        """Duplica tarifas selecionadas para novo período"""
        for tariff in queryset:
            tariff.pk = None
            tariff.valid_from = tariff.valid_until or date.today()
            tariff.valid_until = None
            tariff.save()

        self.message_user(
            request, f"{queryset.count()} tarifa(s) duplicada(s) com sucesso."
        )

    duplicate_tariff.short_description = "Duplicar tarifas para novo período"
