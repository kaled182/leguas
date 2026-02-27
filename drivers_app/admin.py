from django.contrib import admin
from .models import DriverProfile, DriverDocument, Vehicle, VehicleDocument


class DriverDocumentInline(admin.TabularInline):
    model = DriverDocument
    extra = 0
    fields = ('tipo_documento', 'arquivo', 'data_validade', 'categoria_cnh', 'observacoes')


class VehicleInline(admin.StackedInline):
    model = Vehicle
    extra = 0
    fields = ('matricula', 'marca', 'modelo', 'tipo_veiculo', 'ano', 'is_active')


@admin.register(DriverProfile)
class DriverProfileAdmin(admin.ModelAdmin):
    list_display = ('nif', 'nome_completo', 'telefone', 'email', 'status', 'tipo_vinculo', 'is_active', 'created_at')
    list_filter = ('status', 'tipo_vinculo', 'is_active', 'created_at')
    search_fields = ('nif', 'nome_completo', 'email', 'telefone')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Dados Pessoais', {
            'fields': ('nif', 'nome_completo', 'niss', 'data_nascimento', 'nacionalidade')
        }),
        ('Contato', {
            'fields': ('telefone', 'email', 'endereco_residencia', 'codigo_postal', 'cidade')
        }),
        ('Vinculo Profissional', {
            'fields': ('tipo_vinculo', 'nome_frota')
        }),
        ('Status e Controle', {
            'fields': ('status', 'is_active', 'approved_at', 'approved_by', 'observacoes')
        }),
        ('Metadados', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [DriverDocumentInline, VehicleInline]
    
    def save_model(self, request, obj, form, change):
        if obj.status == 'ATIVO' and not obj.approved_at:
            from django.utils import timezone
            obj.approved_at = timezone.now()
            obj.approved_by = request.user.username
        super().save_model(request, obj, form, change)


@admin.register(DriverDocument)
class DriverDocumentAdmin(admin.ModelAdmin):
    list_display = ('motorista', 'tipo_documento', 'data_validade', 'is_expired', 'uploaded_at')
    list_filter = ('tipo_documento', 'uploaded_at')
    search_fields = ('motorista__nome_completo', 'motorista__nif')
    readonly_fields = ('uploaded_at',)
    
    def is_expired(self, obj):
        if obj.data_validade:
            return obj.is_expired
        return None
    is_expired.boolean = True
    is_expired.short_description = 'Expirado'


class VehicleDocumentInline(admin.TabularInline):
    model = VehicleDocument
    extra = 0


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('matricula', 'motorista', 'marca', 'modelo', 'tipo_veiculo', 'is_active')
    list_filter = ('tipo_veiculo', 'is_active')
    search_fields = ('matricula', 'motorista__nome_completo', 'marca', 'modelo')
    readonly_fields = ('created_at', 'updated_at')
    
    inlines = [VehicleDocumentInline]


@admin.register(VehicleDocument)
class VehicleDocumentAdmin(admin.ModelAdmin):
    list_display = ('veiculo', 'tipo_documento', 'data_validade', 'is_expired', 'uploaded_at')
    list_filter = ('tipo_documento', 'uploaded_at')
    search_fields = ('veiculo__matricula', 'veiculo__motorista__nome_completo')
    readonly_fields = ('uploaded_at',)
