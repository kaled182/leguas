from django.urls import path
from . import views

app_name = 'send_paack_reports'

urlpatterns = [
    # Página principal
    path('', views.send_reports_page, name='send_reports_page'),
    
    # Endpoint para enviar relatório automaticamente
    path('send/', views.send_paack_reports, name='send_report'),
    
    # Endpoint para prévia do relatório (sem enviar)
    path('preview/', views.generate_report_preview, name='preview_report'),
]
