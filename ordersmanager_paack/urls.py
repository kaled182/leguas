from django.urls import path
from . import views

app_name = 'ordersmanager_paack'

urlpatterns = [
    # Endpoints de sincronização
    path('sync/', views.sync_data_manual, name='sync_data_paack'),
    path('sync/test/', views.test_sync_page, name='test_sync_page'),
    path('sync/status/', views.sync_status, name='sync_status'),
    path('sync/stats/', views.database_stats, name='database_stats'),
    path('real-time-sync-status/', views.real_time_sync_status, name='real_time_sync_status'),
    
    # APIs do dashboard
    path('api/dashboard/', views.dashboard_api, name='dashboard_api'),
    path('api/drivers/stats/', views.driver_stats_api, name='driver_stats'),
    path('api/drivers/recovery/', views.driver_recovery_stats, name='driver_recovery'),
    
    # Debug
    path('api/debug/', views.debug_dashboard_counts, name='debug_counts'),
]