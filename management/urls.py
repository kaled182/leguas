from django.urls import path

from . import tools_views

app_name = "management"

urlpatterns = [
    # Ferramentas
    path(
        "tools/qr-generator/",
        tools_views.qr_generator_view,
        name="qr-generator",
    ),
]
