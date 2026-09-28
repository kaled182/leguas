"""
Configuração do Django Admin para customauth.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import DriverAccess, DriverLoginOTP


@admin.register(DriverAccess)
class DriverAccessAdmin(admin.ModelAdmin):
    """
    Configuração do admin para DriverAccess.
    """

    list_display = [
        "full_name",
        "email",
        "nif",
        "phone",
        "driver_display",
        "user",
        "created_at",
    ]

    list_filter = ["created_at", "updated_at", "user"]

    search_fields = [
        "profile_picture" "first_name",
        "last_name",
        "email",
        "nif",
        "phone",
    ]

    readonly_fields = ["created_at", "updated_at", "password"]

    fieldsets = (
        (
            "Informações Pessoais",
            {
                "fields": (
                    "profile_picture",
                    "first_name",
                    "last_name",
                    "email",
                    "phone",
                    "nif",
                )
            },
        ),
        ("Relacionamentos", {"fields": ("user", "driver_profile")}),
        ("Autenticação", {"fields": ("password",), "classes": ("collapse",)}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def driver_display(self, obj):
        """Exibe o motorista associado."""
        if obj.driver_profile_id:
            return format_html('<span style="color: green;">✓ {}</span>', obj.driver_profile)
        return format_html('<span style="color: orange;">⚠ Não vinculado</span>')

    driver_display.short_description = "Motorista"

    def get_queryset(self, request):
        """Otimiza consultas do admin."""
        return super().get_queryset(request).select_related("user", "driver_profile")


@admin.register(DriverLoginOTP)
class DriverLoginOTPAdmin(admin.ModelAdmin):
    """Códigos OTP de login por WhatsApp (auditoria/diagnóstico)."""

    list_display = [
        "phone",
        "driver_profile",
        "code",
        "created_at",
        "expires_at",
        "used_at",
        "attempts",
    ]
    list_filter = ["created_at", "used_at"]
    search_fields = ["phone", "driver_profile__nome_completo"]
    readonly_fields = ["created_at"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("driver_profile")
