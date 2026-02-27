from django.urls import path
from . import views, driversmanagement

app_name = 'management'

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('dashboard/', views.dashboard_view, name='dashboard_detail'),
    # Debug views
    path('debug-week-efficiency/', views.debug_week_efficiency, name='debug_week_efficiency'),
    # API endpoints
    path('api/dashboard/', views.dashboard_api_view, name='dashboard_api'),
    path('api/drivers/recovery/', views.recovery_api, name='recovery_api'),
    path('driversmanagement/', driversmanagement.drivers_management_view, name='drivers_management'),
    path('driversmanagement/edit/<int:access_id>/', driversmanagement.edit_driver_access, name='edit_driver_access'),
    path('driversmanagement/change_password/<int:access_id>/', driversmanagement.change_driver_password, name='change_driver_password'),
]