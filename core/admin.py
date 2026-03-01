from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Partner, PartnerIntegration, SyncLog


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "nif",
        "formatted_status",
        "active_orders_count",
        "has_integrations",
        "contact_email",
        "created_at",
    ]

    list_filter = [
        "is_active",
        "auto_assign_orders",
        "created_at",
    ]

    search_fields = [
        "name",
        "nif",
        "contact_email",
        "contact_phone",
    ]

    readonly_fields = [
        "created_at",
        "updated_at",
        "active_orders_count",
        "has_active_integration",
    ]

    fieldsets = (
        ("Identificação", {"fields": ("name", "nif")}),
        ("Contactos", {"fields": ("contact_email", "contact_phone")}),
        (
            "Configurações de Integração",
            {
                "fields": ("api_credentials",),
                "classes": ("collapse",),
            },
        ),
        (
            "Configurações Operacionais",
            {
                "fields": (
                    "is_active",
                    "auto_assign_orders",
                    "default_delivery_time_days",
                )
            },
        ),
        ("Informações Adicionais", {"fields": ("notes",)}),
        (
            "Metadados",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                    "active_orders_count",
                    "has_active_integration",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def formatted_status(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green;">●</span> Ativo')
        return format_html('<span style="color: red;">●</span> Inativo')

    formatted_status.short_description = "Status"

    def has_integrations(self, obj):
        count = obj.integrations.filter(is_active=True).count()
        if count > 0:
            return format_html(
                '<span style="color: green;">✓</span> {} integraç{}</span>',
                count,
                "ão" if count == 1 else "ões",
            )
        return format_html('<span style="color: orange;">⚠</span> Sem integrações')

    has_integrations.short_description = "Integrações"


@admin.register(PartnerIntegration)
class PartnerIntegrationAdmin(admin.ModelAdmin):
    list_display = [
        "partner",
        "integration_type",
        "formatted_status",
        "sync_status",
        "last_sync_at",
        "is_overdue",
    ]

    list_filter = [
        "integration_type",
        "is_active",
        "last_sync_status",
        "partner",
    ]

    search_fields = [
        "partner__name",
        "endpoint_url",
    ]

    readonly_fields = [
        "last_sync_at",
        "last_sync_status",
        "last_sync_message",
        "is_sync_overdue",
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        ("Parceiro", {"fields": ("partner",)}),
        (
            "Configuração de Integração",
            {
                "fields": (
                    "integration_type",
                    "endpoint_url",
                    "auth_config",
                )
            },
        ),
        (
            "Sincronização",
            {
                "fields": (
                    "is_active",
                    "sync_frequency_minutes",
                    "last_sync_at",
                    "last_sync_status",
                    "last_sync_message",
                    "is_sync_overdue",
                )
            },
        ),
        (
            "Metadados",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def formatted_status(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green;">●</span> Ativo')
        return format_html('<span style="color: red;">●</span> Inativo')

    formatted_status.short_description = "Status"

    def sync_status(self, obj):
        if not obj.last_sync_status:
            return format_html('<span style="color: gray;">Nunca sincronizado</span>')

        colors = {
            "SUCCESS": "green",
            "ERROR": "red",
            "PARTIAL": "orange",
        }

        return format_html(
            '<span style="color: {};">{}</span>',
            colors.get(obj.last_sync_status, "gray"),
            obj.get_last_sync_status_display(),
        )

    sync_status.short_description = "Última Sinc."

    def is_overdue(self, obj):
        if obj.is_sync_overdue:
            return format_html('<span style="color: red;">⚠ Atrasada</span>')
        return format_html('<span style="color: green;">✓ OK</span>')

    is_overdue.short_description = "Status Sinc."

    actions = ["trigger_sync"]

    def trigger_sync(self, request, queryset):
        """Ação para disparar sincronização manual"""
        # TODO: Implementar lógica de sincronização
        self.message_user(
            request,
            f"Sincronização manual disparada para {queryset.count()} integrações.",
        )

    trigger_sync.short_description = "Disparar sincronização manual"


@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "integration_link",
        "operation",
        "formatted_status",
        "started_at",
        "duration_display",
        "records_summary",
        "success_rate_display",
    ]

    list_filter = [
        "status",
        "operation",
        "started_at",
        ("integration__partner", admin.RelatedOnlyFieldListFilter),
    ]

    search_fields = [
        "integration__partner__name",
        "message",
        "error_details",
    ]

    readonly_fields = [
        "integration",
        "operation",
        "status",
        "started_at",
        "completed_at",
        "records_processed",
        "records_created",
        "records_updated",
        "records_failed",
        "message",
        "error_details",
        "request_data",
        "response_data",
        "duration_seconds",
        "success_rate",
    ]

    fieldsets = (
        ("Integração", {"fields": ("integration",)}),
        ("Operação", {"fields": ("operation", "status")}),
        (
            "Timestamps",
            {"fields": ("started_at", "completed_at", "duration_seconds")},
        ),
        (
            "Estatísticas",
            {
                "fields": (
                    "records_processed",
                    "records_created",
                    "records_updated",
                    "records_failed",
                    "success_rate",
                )
            },
        ),
        ("Mensagens", {"fields": ("message", "error_details")}),
        (
            "Dados Detalhados",
            {
                "fields": ("request_data", "response_data"),
                "classes": ("collapse",),
            },
        ),
    )

    date_hierarchy = "started_at"

    def has_add_permission(self, request):
        """Logs são criados automaticamente, não manualmente"""
        return False

    def has_change_permission(self, request, obj=None):
        """Logs são read-only"""
        return False

    def integration_link(self, obj):
        """Link para a integração"""
        url = reverse("admin:core_partnerintegration_change", args=[obj.integration.id])
        return format_html('<a href="{}">{}</a>', url, obj.integration)

    integration_link.short_description = "Integração"

    def formatted_status(self, obj):
        """Status com cores"""
        colors = {
            "STARTED": "blue",
            "SUCCESS": "green",
            "ERROR": "red",
            "PARTIAL": "orange",
            "TIMEOUT": "purple",
        }

        symbols = {
            "STARTED": "⟳",
            "SUCCESS": "✓",
            "ERROR": "✗",
            "PARTIAL": "⚠",
            "TIMEOUT": "⏱",
        }

        return format_html(
            '<span style="color: {};">{} {}</span>',
            colors.get(obj.status, "gray"),
            symbols.get(obj.status, "?"),
            obj.get_status_display(),
        )

    formatted_status.short_description = "Status"

    def duration_display(self, obj):
        """Duração formatada"""
        if not obj.duration_seconds:
            if obj.status == "STARTED":
                return format_html('<span style="color: blue;">Em execução...</span>')
            return "-"

        if obj.duration_seconds < 60:
            return f"{obj.duration_seconds:.1f}s"
        else:
            minutes = int(obj.duration_seconds / 60)
            seconds = obj.duration_seconds % 60
            return f"{minutes}m {seconds:.0f}s"

    duration_display.short_description = "Duração"

    def records_summary(self, obj):
        """Resumo de registros processados"""
        if obj.records_processed == 0:
            return "-"

        return format_html(
            '<span title="Processados: {} | Criados: {} | Atualizados: {} | Falhados: {}">'
            '{} <span style="color: green;">+{}</span> '
            '<span style="color: blue;">~{}</span> '
            '<span style="color: red;">-{}</span>'
            "</span>",
            obj.records_processed,
            obj.records_created,
            obj.records_updated,
            obj.records_failed,
            obj.records_processed,
            obj.records_created,
            obj.records_updated,
            obj.records_failed,
        )

    records_summary.short_description = (
        "Registros (Total/+Criados/~Atualizados/-Falhados)"
    )

    def success_rate_display(self, obj):
        """Taxa de sucesso formatada"""
        if obj.records_processed == 0:
            return "-"

        rate = obj.success_rate

        if rate >= 90:
            color = "green"
        elif rate >= 70:
            color = "orange"
        else:
            color = "red"

        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color,
            rate,
        )

    success_rate_display.short_description = "Taxa de Sucesso"
