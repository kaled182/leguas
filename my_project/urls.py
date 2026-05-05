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

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import include, path


def redirect_mixed(request):

    return redirect("mixed/")


def healthcheck(request):
    """Endpoint /health/ — usado pelo Docker healthcheck e Caddy.

    Verifica:
      - DB conecta e responde a `SELECT 1`
      - Cache (Redis) está acessível

    Devolve 200 + JSON `{"status": "ok", ...}` se tudo OK,
    senão 503 + detalhes do erro.
    """
    checks = {"db": "unknown", "cache": "unknown"}
    status_code = 200
    try:
        with connection.cursor() as c:
            c.execute("SELECT 1")
            c.fetchone()
        checks["db"] = "ok"
    except Exception as e:
        checks["db"] = f"error: {e}"[:80]
        status_code = 503
    try:
        from django.core.cache import cache
        cache.set("_health", "1", 5)
        cache.get("_health")
        checks["cache"] = "ok"
    except Exception as e:
        checks["cache"] = f"error: {e}"[:80]
        status_code = 503
    return JsonResponse(
        {
            "status": "ok" if status_code == 200 else "degraded",
            "checks": checks,
        },
        status=status_code,
    )


urlpatterns = [
    path("health/", healthcheck, name="healthcheck"),
    path("admin/", admin.site.urls),
    # path('', redirect_mixed, name='redirect_mixed'),
    # path('old/', include('management.urls')),  # Para acessar na raiz
    path("auth/", include("customauth.urls")),  # Para autenticação
    path("management/", include("management.urls")),  # Para /management/
    path("paackos/", include("ordersmanager_paack.urls")),
    # path('delnextos/', include('ordersmanager_delnext.urls')),
    path("", include("paack_dashboard.urls")),  # Dashboard para visualizar dados
    # path('delnext/', include('delnext_dashboard.urls')),
    path("driversapp/", include("drivers_app.urls")),
    path("sendpaackreports/", include("send_paack_reports.urls")),
    # path('mixed/', include('mixed_dashboard.urls')),
    path("converter/", include("converter.urls")),  # Conversor de listas para XLSX
    # path('api/', include('api_paack.urls')),  # APP responsavel por trazer dados da Paack
    # path('paack/', include('dashboard_paack.urls')),  # Dashboard para visualizar dados
    path(
        "manualorders_paack/", include("manualorders_paack.urls")
    ),  # APP para correção manual de encomendas Paack
    path("settlements/", include("settlements.urls")),  # APP para gestão de settlements
    path("accounting/", include("accounting.urls")),
    path("core/", include("core.urls")),  # APP para gestão de parceiros e integrações
    path(
        "pricing/", include("pricing.urls")
    ),  # APP para gestão de zonas postais e tarifas
    path("fleet/", include("fleet_management.urls")),  # APP para gestão de frota
    path(
        "routes/", include("route_allocation.urls")
    ),  # APP para alocação de rotas e turnos
    path("orders/", include("orders_manager.urls")),  # APP para gestão de pedidos
    path("system/", include("system_config.urls")),  # Configurações do Sistema
    path(
        "analytics/", include("analytics.urls")
    ),  # Dashboards de Analytics e Relatórios
    path("contracts/", include("contracts.urls")),  # Sistema de Contratos
]

# Servir arquivos estáticos
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Sempre servir arquivos estáticos (tanto em desenvolvimento quanto em produção)
# Primeiro tenta servir do STATIC_ROOT (onde ficam os arquivos coletados)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Se DEBUG estiver ativo, também serve dos diretórios estáticos das apps
if settings.DEBUG and settings.STATICFILES_DIRS:
    urlpatterns += static(
        settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0]
    )
