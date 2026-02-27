from django.contrib import admin
from .models import ManualCorrection

@admin.register(ManualCorrection)
class ManualCorrectionAdmin(admin.ModelAdmin):
    list_display = ('correction_type', 'driver', 'reason', 'created_by', 'created_at')
    list_filter = ('correction_type', 'driver', 'created_by', 'created_at')
    search_fields = ('reason', 'driver__name', 'created_by__username')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)
    raw_id_fields = ('driver', 'order', 'dispatch')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'driver', 'order', 'dispatch', 'created_by'
        )
