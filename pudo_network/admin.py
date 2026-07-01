"""Admin da Rede PUDO — CRUD de lojas e gestão de credenciais do lojista."""
import secrets
import string

from django.contrib import admin, messages

from .models import (
    PudoAccess,
    PudoCustodyEvent,
    PudoCustodyPackage,
    PudoDeliveryProof,
    PudoStore,
    PudoStoreBillingLine,
    PudoStoreStatement,
    PudoTransaction,
    PudoUpstreamReconciliation,
)


def _gen_password(length=12):
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class PudoAccessInline(admin.StackedInline):
    model = PudoAccess
    extra = 0
    fields = ("username", "email", "papel", "is_active", "last_login")
    readonly_fields = ("last_login",)
    can_delete = True


@admin.register(PudoStore)
class PudoStoreAdmin(admin.ModelAdmin):
    list_display = (
        "numero", "nome", "status", "cidade", "ciclo_pagamento",
        "capacidade_max", "partner",
    )
    list_filter = ("status", "ciclo_pagamento", "partner")
    search_fields = ("numero", "nome", "nif", "cidade", "codigo_postal")
    readonly_fields = ("numero", "created_at", "updated_at")
    inlines = [PudoAccessInline]
    fieldsets = (
        ("Identidade", {"fields": ("numero", "nome", "status")}),
        ("Fiscal / Contacto", {
            "fields": (
                "nif", "morada", "codigo_postal", "cidade", "email",
                "telefone", "contacto_nome", "iban", "taxa_iva",
            ),
        }),
        ("Geo", {"fields": ("latitude", "longitude")}),
        ("Operação", {"fields": ("capacidade_max", "horario")}),
        ("Preço à loja", {
            "fields": ("preco_1a_entrega", "preco_adicional", "ciclo_pagamento"),
        }),
        ("Carrier", {"fields": ("partner",)}),
        ("Meta", {"fields": ("notas", "created_at", "updated_at")}),
    )


@admin.register(PudoAccess)
class PudoAccessAdmin(admin.ModelAdmin):
    list_display = ("username", "store", "papel", "is_active", "last_login")
    list_filter = ("papel", "is_active")
    search_fields = ("username", "email", "store__numero", "store__nome")
    readonly_fields = ("last_login", "created_at", "updated_at", "created_by")
    actions = ["definir_password_aleatoria"]
    exclude = ("password",)

    @admin.action(description="Definir nova password aleatória (mostrada uma vez)")
    def definir_password_aleatoria(self, request, queryset):
        for access in queryset:
            pw = _gen_password()
            access.set_password(pw)
            access.save(update_fields=["password", "updated_at"])
            self.message_user(
                request,
                f"{access.username} → nova password: {pw}",
                level=messages.WARNING,
            )

    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by:
            obj.created_by = request.user
        # Ao criar sem hash, gera uma password inicial visível ao admin.
        if not obj.password:
            pw = _gen_password()
            obj.set_password(pw)
            messages.warning(request, f"Password inicial de {obj.username}: {pw}")
        super().save_model(request, obj, form, change)


class PudoCustodyEventInline(admin.TabularInline):
    model = PudoCustodyEvent
    extra = 0
    fields = ("created_at", "from_status", "to_status", "actor_type", "actor", "motivo")
    readonly_fields = fields
    can_delete = False
    ordering = ("-created_at",)

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(PudoCustodyPackage)
class PudoCustodyPackageAdmin(admin.ModelAdmin):
    list_display = (
        "tracking_ref", "store", "status", "driver", "received_at",
        "aging_deadline", "delivered_at",
    )
    list_filter = ("status", "store", "source_kind")
    search_fields = ("tracking_ref", "source_ref", "store__numero", "store__nome")
    readonly_fields = ("created_at", "updated_at", "received_at", "delivered_at")
    autocomplete_fields = ("store",)
    inlines = [PudoCustodyEventInline]
    date_hierarchy = "created_at"


@admin.register(PudoTransaction)
class PudoTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "uuid", "tipo", "origin", "store", "tracking_ref", "status", "synced_at",
    )
    list_filter = ("tipo", "origin", "status", "store")
    search_fields = ("uuid", "tracking_ref", "store__numero")
    readonly_fields = (
        "uuid", "synced_at", "custody_package", "payload", "created_at_device",
    )
    date_hierarchy = "synced_at"


@admin.register(PudoCustodyEvent)
class PudoCustodyEventAdmin(admin.ModelAdmin):
    list_display = (
        "created_at", "package", "from_status", "to_status", "actor_type", "actor",
    )
    list_filter = ("actor_type", "to_status")
    search_fields = ("package__tracking_ref", "actor", "motivo")
    readonly_fields = (
        "package", "from_status", "to_status", "actor", "actor_type",
        "motivo", "meta", "created_at",
    )
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(PudoDeliveryProof)
class PudoDeliveryProofAdmin(admin.ModelAdmin):
    list_display = (
        "package", "metodo", "levantador_nome", "doc_mascarado", "otp_ok",
        "created_at",
    )
    list_filter = ("metodo", "otp_ok")
    search_fields = ("package__tracking_ref", "levantador_nome")
    readonly_fields = (
        "package", "metodo", "levantador_nome", "doc_mascarado", "otp_ok",
        "assinatura", "actor", "created_at",
    )
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False


@admin.register(PudoStoreBillingLine)
class PudoStoreBillingLineAdmin(admin.ModelAdmin):
    list_display = (
        "emitted_at", "store", "tracking_ref", "valor", "iva_pct",
        "ciclo_pagamento",
    )
    list_filter = ("store", "ciclo_pagamento")
    search_fields = ("tracking_ref", "store__numero", "store__nome")
    readonly_fields = (
        "store", "package", "tracking_ref", "valor", "iva_pct",
        "ciclo_pagamento", "emitted_at",
    )
    date_hierarchy = "emitted_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False  # ledger imutável

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PudoUpstreamReconciliation)
class PudoUpstreamReconciliationAdmin(admin.ModelAdmin):
    list_display = (
        "created_at", "package", "tipo", "status", "motivo", "sent_at",
    )
    list_filter = ("status", "tipo")
    search_fields = ("package__tracking_ref", "motivo")
    readonly_fields = ("package", "tipo", "created_at", "payload")


@admin.register(PudoStoreStatement)
class PudoStoreStatementAdmin(admin.ModelAdmin):
    list_display = (
        "emitted_at", "store", "periodo_inicio", "periodo_fim",
        "n_linhas", "total_valor", "total_com_iva",
    )
    list_filter = ("ciclo_pagamento", "store")
    search_fields = ("store__numero", "store__nome")
    readonly_fields = (
        "store", "ciclo_pagamento", "periodo_inicio", "periodo_fim",
        "total_valor", "total_com_iva", "n_linhas", "emitted_at",
    )
    date_hierarchy = "periodo_fim"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
