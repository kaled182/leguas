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
    path("api/hubs/", views.api_hubs, name="api-hubs"),
    path("api/zonas/from-cp4s/", views.api_zona_from_cp4s, name="api-zona-from-cp4s"),
    path("api/zonas/from-hub/", views.api_zona_from_hub, name="api-zona-from-hub"),
    path("api/ingest/", views.api_ingest, name="api-ingest"),
    path("api/ingest/coords-faltam/", views.api_coords_faltam, name="api-coords-faltam"),
    path("api/ingest/status/", views.api_job_status, name="api-job-status"),
    path("api/ingest/active/", views.api_jobs_active, name="api-jobs-active"),
    path("api/quota/", views.api_quota, name="api-quota"),
    path("api/geoapi-key/", views.api_geoapi_key, name="api-geoapi-key"),
]
