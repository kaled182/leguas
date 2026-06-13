from django.urls import path

from . import views

app_name = "geozonas"

urlpatterns = [
    path("mapa/", views.mapa, name="mapa"),
    path("catalogo/", views.catalogo, name="catalogo"),
    # APIs JSON
    path("api/cps/", views.api_cps, name="api-cps"),
    path("api/selecionar/", views.api_selecionar, name="api-selecionar"),
    path("api/zonas/criar/", views.api_criar_zona, name="api-criar-zona"),
    path("api/ingest/", views.api_ingest, name="api-ingest"),
    path("api/ingest/status/", views.api_job_status, name="api-job-status"),
    path("api/ingest/active/", views.api_jobs_active, name="api-jobs-active"),
]
