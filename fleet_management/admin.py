from django.contrib import admin
from django.utils.html import format_html
from .models import Vehicle, VehicleAssignment, VehicleMaintenance, VehicleIncident


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = [
        'license_plate',
        'brand',
        'model',
        'year',
        'vehicle_type',
        'formatted_status',
        'inspection_status',
        'insurance_status',
    ]
    
    list_filter = [
        'status',
        'vehicle_type',
        'is_company_owned',
        'fuel_type',
    ]
    
    search_fields = [
        'license_plate',
        'brand',
        'model',
        'owner',
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
        'is_inspection_valid',
        'is_insurance_valid',
        'inspection_expires_soon',
        'insurance_expires_soon',
        'is_available',
    ]
    
    fieldsets = (
        ('Identificação', {
            'fields': (
                'license_plate',
                'brand',
                'model',
                'year',
                'vehicle_type',
            )
        }),
        ('Propriedade', {
            'fields': (
                'owner',
                'is_company_owned',
            )
        }),
        ('Especificações', {
            'fields': (
                'max_load_kg',
                'fuel_type',
                'current_odometer_km',
            )
        }),
        ('Documentação', {
            'fields': (
                'inspection_expiry',
                'insurance_expiry',
                'insurance_policy_number',
            )
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Observações', {
            'fields': ('notes',)
        }),
        ('Metadados', {
            'fields': (
                'created_at',
                'updated_at',
                'is_inspection_valid',
                'is_insurance_valid',
                'is_available',
            ),
            'classes': ('collapse',),
        }),
    )
    
    def formatted_status(self, obj):
        colors = {
            'ACTIVE': 'green',
            'MAINTENANCE': 'orange',
            'INACTIVE': 'gray',
            'SOLD': 'red',
        }
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            colors.get(obj.status, 'gray'),
            obj.get_status_display()
        )
    formatted_status.short_description = 'Status'
    
    def inspection_status(self, obj):
        if obj.is_inspection_valid:
            if obj.inspection_expires_soon:
                return format_html(
                    '<span style="color: orange;">⚠ Expira em breve</span>'
                )
            return format_html('<span style="color: green;">✓ Válida</span>')
        return format_html('<span style="color: red;">✗ Expirada</span>')
    inspection_status.short_description = 'Inspeção'
    
    def insurance_status(self, obj):
        if obj.is_insurance_valid:
            if obj.insurance_expires_soon:
                return format_html(
                    '<span style="color: orange;">⚠ Expira em breve</span>'
                )
            return format_html('<span style="color: green;">✓ Válido</span>')
        return format_html('<span style="color: red;">✗ Expirado</span>')
    insurance_status.short_description = 'Seguro'


@admin.register(VehicleAssignment)
class VehicleAssignmentAdmin(admin.ModelAdmin):
    list_display = [
        'vehicle',
        'driver',
        'date',
        'start_time',
        'end_time',
        'kilometers_driven',
    ]
    
    list_filter = [
        ('date', admin.DateFieldListFilter),
        'vehicle',
        'driver',
    ]
    
    search_fields = [
        'vehicle__license_plate',
        'driver__user__first_name',
        'driver__user__last_name',
    ]
    
    readonly_fields = ['created_at', 'updated_at', 'kilometers_driven', 'duration_hours']
    
    fieldsets = (
        ('Atribuição', {
            'fields': ('vehicle', 'driver', 'date')
        }),
        ('Horário', {
            'fields': ('start_time', 'end_time', 'duration_hours')
        }),
        ('Odómetro', {
            'fields': ('odometer_start', 'odometer_end', 'kilometers_driven')
        }),
        ('Observações', {
            'fields': ('notes',)
        }),
        ('Metadados', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(VehicleMaintenance)
class VehicleMaintenanceAdmin(admin.ModelAdmin):
    list_display = [
        'vehicle',
        'maintenance_type',
        'scheduled_date',
        'completed_date',
        'formatted_completed',
        'cost',
        'workshop',
    ]
    
    list_filter = [
        'maintenance_type',
        'is_completed',
        ('scheduled_date', admin.DateFieldListFilter),
    ]
    
    search_fields = [
        'vehicle__license_plate',
        'description',
        'workshop',
    ]
    
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Veículo', {
            'fields': ('vehicle',)
        }),
        ('Detalhes', {
            'fields': (
                'maintenance_type',
                'description',
                'workshop',
            )
        }),
        ('Datas', {
            'fields': (
                'scheduled_date',
                'completed_date',
                'is_completed',
            )
        }),
        ('Financeiro', {
            'fields': (
                'cost',
                'invoice_number',
                'odometer_at_service',
            )
        }),
        ('Observações', {
            'fields': ('notes',)
        }),
        ('Metadados', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    def formatted_completed(self, obj):
        if obj.is_completed:
            return format_html('<span style="color: green;">✓ Concluído</span>')
        return format_html('<span style="color: orange;">⚠ Pendente</span>')
    formatted_completed.short_description = 'Status'


@admin.register(VehicleIncident)
class VehicleIncidentAdmin(admin.ModelAdmin):
    list_display = [
        'vehicle',
        'incident_type',
        'incident_date',
        'driver',
        'fine_amount',
        'driver_responsible',
        'formatted_resolved',
    ]
    
    list_filter = [
        'incident_type',
        'resolved',
        'driver_responsible',
        ('incident_date', admin.DateFieldListFilter),
    ]
    
    search_fields = [
        'vehicle__license_plate',
        'driver__user__first_name',
        'driver__user__last_name',
        'description',
    ]
    
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Veículo e Motorista', {
            'fields': ('vehicle', 'driver')
        }),
        ('Detalhes do Incidente', {
            'fields': (
                'incident_type',
                'description',
                'incident_date',
                'location',
                'photos',
                'police_report_number',
            )
        }),
        ('Financeiro', {
            'fields': (
                'fine_amount',
                'driver_responsible',
                'claim_amount',
            )
        }),
        ('Resolução', {
            'fields': (
                'resolved',
                'resolution_notes',
            )
        }),
        ('Metadados', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    def formatted_resolved(self, obj):
        if obj.resolved:
            return format_html('<span style="color: green;">✓ Resolvido</span>')
        return format_html('<span style="color: red;">⚠ Pendente</span>')
    formatted_resolved.short_description = 'Status'
