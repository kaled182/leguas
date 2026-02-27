from django.urls import path
from . import views

app_name = 'manualorders_paack'

urlpatterns = [
    path('', views.manual_management, name='manual_management'),
    path('manual-correction/', views.manual_correction, name='manual_correction'),
    path('get-drivers/', views.get_drivers, name='get_drivers'),
    path('check-manual-orders/', views.check_manual_orders, name='check_manual_orders'),
    path('get-manual-corrections/', views.get_manual_corrections_by_date, name='get_manual_corrections'),
    path('delete-manual-corrections/', views.delete_manual_corrections, name='delete_manual_corrections'),
    path('edit-manual-correction/', views.edit_manual_correction, name='edit_manual_correction'),
    path('get-correction-data/<int:correction_id>/', views.get_correction_data, name='get_correction_data'),
]
