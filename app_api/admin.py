from django.contrib import admin

from .models import DriverAppToken


@admin.register(DriverAppToken)
class DriverAppTokenAdmin(admin.ModelAdmin):
    list_display = [
        "driver_profile",
        "key_short",
        "created_at",
        "last_used_at",
        "expires_at",
        "revoked",
    ]
    list_filter = ["revoked", "created_at"]
    search_fields = ["driver_profile__nome_completo", "key"]
    readonly_fields = ["created_at", "last_used_at", "key"]

    def key_short(self, obj):
        return f"{obj.key[:10]}…"
    key_short.short_description = "Token"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("driver_profile")
