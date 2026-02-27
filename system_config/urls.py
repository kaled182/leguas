from django.urls import path

from . import views

app_name = 'system_config'

urlpatterns = [
    path('', views.system_config_view, name='index'),
    path('save/', views.save_config, name='save'),
    path('whatsapp/', views.whatsapp_dashboard, name='whatsapp_dashboard'),
    path('whatsapp/start/', views.whatsapp_start_session, name='whatsapp_start_session'),
    path('whatsapp/status/', views.whatsapp_status, name='whatsapp_status'),
    path('whatsapp/qrcode/', views.whatsapp_qrcode, name='whatsapp_qrcode'),
    path('whatsapp/logout/', views.whatsapp_logout, name='whatsapp_logout'),
    path('whatsapp/send-test/', views.whatsapp_send_test, name='whatsapp_send_test'),
    path('whatsapp/update-config/', views.whatsapp_update_config, name='whatsapp_update_config'),
    path('whatsapp/generate-token/', views.whatsapp_generate_token, name='whatsapp_generate_token'),
    
    # Typebot
    path('typebot/test-connection/', views.typebot_test_connection, name='typebot_test_connection'),
    path('typebot/auto-login/', views.typebot_auto_login, name='typebot_auto_login'),
    path('typebot/generate-secret/', views.typebot_generate_encryption_secret, name='typebot_generate_secret'),
]
