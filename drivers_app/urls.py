from django.urls import path
from . import views

app_name = 'drivers_app'

urlpatterns = [
    # Pagina publica de cadastro
    path('cadastro/', views.public_driver_register, name='public_register'),
    path('cadastro-completo/', views.public_driver_register_full, name='public_register_full'),
    
    # Dashboard de motoristas
    path('dashboard/', views.driver_dashboard_view, name='driver_dashboard'),
    path('export/xlsx/', views.driver_export_xlsx, name='driver_export_xlsx'),
    path('logout/', views.driver_logout_view, name='driver_logout'),
    
    # Admin - Gestao de Motoristas
    path('admin/criar/', views.admin_create_driver, name='admin_create_driver'),
    path('admin/aprovar/', views.admin_approve_drivers, name='admin_approve_drivers'),
    path('admin/aprovar/<int:driver_id>/', views.admin_approve_driver_action, name='admin_approve_driver_action'),
    path('admin/ativos/', views.admin_active_drivers, name='admin_active_drivers'),
    
    # Admin - Gestão Completa (Edição, Documentos, Veículos)
    path('admin/editar/<int:driver_id>/pessoal/', views.admin_edit_driver_personal, name='admin_edit_driver_personal'),
    path('admin/editar/<int:driver_id>/profissional/', views.admin_edit_driver_professional, name='admin_edit_driver_professional'),
    path('admin/anexar-documento/<int:driver_id>/', views.admin_attach_document, name='admin_attach_document'),
    path('admin/deletar-documento/<int:document_id>/', views.admin_delete_document, name='admin_delete_document'),
    path('admin/adicionar-veiculo/<int:driver_id>/', views.admin_add_vehicle, name='admin_add_vehicle'),
    path('admin/deletar-veiculo/<int:vehicle_id>/', views.admin_delete_vehicle, name='admin_delete_vehicle'),
    path('admin/deletar-documento-veiculo/<int:document_id>/', views.admin_delete_vehicle_document, name='admin_delete_vehicle_document'),
    path('admin/desativar/<int:driver_id>/', views.admin_deactivate_driver, name='admin_deactivate_driver'),
    path('admin/ativar/<int:driver_id>/', views.admin_activate_driver, name='admin_activate_driver'),
    path('admin/excluir/<int:driver_id>/', views.admin_delete_driver, name='admin_delete_driver'),
    path('admin/get-driver-data/<int:driver_id>/', views.admin_get_driver_data, name='admin_get_driver_data'),
    
    # API endpoints
    path('api/register-typebot/', views.register_driver_typebot, name='register_driver_typebot'),
]
