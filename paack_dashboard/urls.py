from django.urls import path
from .views import DashboardView, DriversManagementView, DebugWeeklyEfficiencyView, driver_profile_image

app_name = 'paack_dashboard'

urlpatterns = [
    path('', DashboardView.as_view(), name='dashboard_paack'),
    path('driversmanagement/', DriversManagementView.as_view(), name='drivers_management'),
    path('debug-week-efficiency/', DebugWeeklyEfficiencyView.as_view(), name='debug_week_efficiency'),
    path('driver-image/<int:driver_id>/', driver_profile_image, name='driver_profile_image'),
]
