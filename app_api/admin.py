from django.contrib import admin

from .models import DriverAppToken, IncidencePacket, OcrCorrectionLearning, OcrScanAttempt


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


@admin.register(IncidencePacket)
class IncidencePacketAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "barcode",
        "driver_profile",
        "client_name",
        "zone",
        "scanned_at",
    ]
    list_filter = ["zone", "scanned_at"]
    search_fields = ["barcode", "tracking_number", "client_name", "driver_profile__nome_completo"]
    readonly_fields = ["scanned_at", "updated_at"]


@admin.register(OcrCorrectionLearning)
class OcrCorrectionLearningAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "field_name",
        "score",
        "occurrence_count",
        "created_at",
    ]
    list_filter = ["field_name", "created_at"]
    search_fields = ["original_value", "corrected_value", "normalized_original"]


@admin.register(OcrScanAttempt)
class OcrScanAttemptAdmin(admin.ModelAdmin):
    list_display = ["id", "qr_code", "driver_profile", "was_edited", "created_at"]
    list_filter = ["was_edited", "created_at"]
    search_fields = ["qr_code", "driver_profile__nome_completo"]
