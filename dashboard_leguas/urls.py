from django.urls import path
from . import views
from .views_home import DashboardView

app_name='dashboard_leguas'

urlpatterns = [
    path('', DashboardView.as_view(), name='home'),

    path('dashboard_v2/', views.DashboardV2, name='dashboard_v2'),

]