from django.urls import path

from . import views

app_name = "routes"

urlpatterns = [
    # Dashboard
    path("dashboard/", views.routes_dashboard, name="dashboard"),
    # Shifts
    path("shifts/", views.shift_list, name="shift_list"),
    path("shifts/calendar/", views.shift_calendar, name="shift_calendar"),
    path("shifts/create/", views.shift_create, name="shift_create"),
    path("shifts/<int:pk>/", views.shift_detail, name="shift_detail"),
    path("shifts/<int:pk>/edit/", views.shift_edit, name="shift_edit"),
    path("shifts/<int:pk>/start/", views.shift_start, name="shift_start"),
    path("shifts/<int:pk>/end/", views.shift_end, name="shift_end"),
]
