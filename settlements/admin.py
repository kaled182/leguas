from django.contrib import admin
from .models import SettlementRun, CompensationPlan, PerPackageRate, ThresholdBonus

@admin.register(SettlementRun)
class SettlementRunAdmin(admin.ModelAdmin):
    list_display  = ("run_date","client","driver","area_code","qtd_entregue","vl_pct","total_pct","vl_final")
    list_filter   = ("client","area_code","run_date","driver")
    search_fields = ("driver__name","client","area_code")
    date_hierarchy = "run_date"
    autocomplete_fields = ("driver",)

class PerPackageRateInline(admin.TabularInline):
    model = PerPackageRate
    extra = 0

class ThresholdBonusInline(admin.TabularInline):
    model = ThresholdBonus
    extra = 0

@admin.register(CompensationPlan)
class CompensationPlanAdmin(admin.ModelAdmin):
    list_display = ("driver","client","area_code","starts_on","ends_on","base_fixed","is_active")
    list_filter  = ("client","area_code","is_active")
    search_fields = ("driver__name","client","area_code")
    date_hierarchy = "starts_on"
    autocomplete_fields = ("driver",)
    inlines = [PerPackageRateInline, ThresholdBonusInline]
