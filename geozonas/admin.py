from django.contrib import admin

from .models import (
    CodigoPostal,
    Concelho,
    Freguesia,
    IngestJob,
    Localidade,
    ZonaGeo,
)


@admin.register(Concelho)
class ConcelhoAdmin(admin.ModelAdmin):
    list_display = ("nome", "distrito", "codigo_ine")
    search_fields = ("nome", "distrito", "codigo_ine")


@admin.register(Freguesia)
class FreguesiaAdmin(admin.ModelAdmin):
    list_display = ("nome", "concelho", "codigo_ine")
    list_filter = ("concelho__distrito",)
    search_fields = ("nome", "concelho__nome", "codigo_ine")
    autocomplete_fields = ("concelho",)


@admin.register(Localidade)
class LocalidadeAdmin(admin.ModelAdmin):
    list_display = ("nome", "freguesia")
    search_fields = ("nome",)
    autocomplete_fields = ("freguesia",)


@admin.register(CodigoPostal)
class CodigoPostalAdmin(admin.ModelAdmin):
    list_display = ("codigo_postal", "designacao_postal", "concelho", "freguesia", "fonte", "atualizado_em")
    list_filter = ("fonte", "concelho")
    search_fields = ("cp4", "cp3", "designacao_postal")
    autocomplete_fields = ("localidade", "freguesia", "concelho")


@admin.register(ZonaGeo)
class ZonaGeoAdmin(admin.ModelAdmin):
    list_display = (
        "nome", "codigo", "cor", "postal_zone", "motorista_default", "is_active"
    )
    list_filter = ("is_active",)
    search_fields = ("nome", "codigo")
    prepopulated_fields = {"codigo": ("nome",)}


@admin.register(IngestJob)
class IngestJobAdmin(admin.ModelAdmin):
    list_display = (
        "cp4", "concelho", "status", "percent", "processados", "total",
        "coords_feitas", "coords_falhadas", "created_at",
    )
    list_filter = ("status", "com_coordenadas")
    search_fields = ("cp4", "concelho")
    readonly_fields = ("created_at", "updated_at")
