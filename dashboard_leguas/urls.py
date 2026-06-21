from django.urls import path
from . import views

app_name='dashboard_leguas'

urlpatterns = [

    path('dashboard_v2/', views.DashboardV2, name='dashboard_v2'),

]