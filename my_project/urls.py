"""
URL configuration for my_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

def redirect_mixed(request):

  return redirect('mixed/')

urlpatterns = [
    path('admin/', admin.site.urls),
    #path('', redirect_mixed, name='redirect_mixed'),
    #path('old/', include('management.urls')),  # Para acessar na raiz
    path('auth/' , include('customauth.urls')),  # Para autenticação
    path('management/', include('management.urls')),  # Para /management/
    path('paackos/', include('ordersmanager_paack.urls')),
    #path('delnextos/', include('ordersmanager_delnext.urls')),
    path('', include('paack_dashboard.urls')),  # Dashboard para visualizar dados
    #path('delnext/', include('delnext_dashboard.urls')),
    path('driversapp/', include('drivers_app.urls')),
    path('sendpaackreports/', include('send_paack_reports.urls')),
    #path('mixed/', include('mixed_dashboard.urls')),
    path('converter/', include('converter.urls')),  # Conversor de listas para XLSX
    #path('api/', include('api_paack.urls')),  # APP responsavel por trazer dados da Paack
    #path('paack/', include('dashboard_paack.urls')),  # Dashboard para visualizar dados
    path('manualorders_paack/', include('manualorders_paack.urls')),  # APP para correção manual de encomendas Paack
    path('settlements/', include('settlements.urls')),  # APP para gestão de settlements
    path('accounting/', include('accounting.urls')),
    path('system/', include('system_config.urls')),  # Configurações do Sistema
    path('analytics/', include('analytics.urls')),  # Dashboards de Analytics e Relatórios
]

# Servir arquivos estáticos
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Sempre servir arquivos estáticos (tanto em desenvolvimento quanto em produção)
# Primeiro tenta servir do STATIC_ROOT (onde ficam os arquivos coletados)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Se DEBUG estiver ativo, também serve dos diretórios estáticos das apps
if settings.DEBUG and settings.STATICFILES_DIRS:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
