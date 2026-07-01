from django.urls import path

from . import views

app_name = "sorting"

urlpatterns = [
    # Páginas
    path("", views.sorting_workspace, name="workspace"),
    path("historico/", views.sorting_history, name="history"),

    # API — sessões
    path("api/session/create/", views.session_create, name="session_create"),
    path(
        "api/session/<int:session_id>/",
        views.session_detail, name="session_detail",
    ),
    path(
        "api/session/<int:session_id>/parcels/",
        views.session_parcels, name="session_parcels",
    ),
    path(
        "api/session/<int:session_id>/finish/",
        views.session_finish, name="session_finish",
    ),
    path(
        "api/session/<int:session_id>/reopen/",
        views.session_reopen, name="session_reopen",
    ),
    path(
        "api/session/<int:session_id>/scan/",
        views.scan, name="scan",
    ),
    path(
        "api/session/<int:session_id>/export/xlsx/",
        views.session_export_xlsx, name="session_export_xlsx",
    ),
    path(
        "api/session/<int:session_id>/labels/pdf/",
        views.session_labels_pdf, name="session_labels_pdf",
    ),
    path(
        "session/<int:session_id>/labels/print/",
        views.session_labels_print, name="session_labels_print",
    ),

    # API — bigbags / pacotes
    path(
        "api/bigbag/<int:bigbag_id>/update/",
        views.bigbag_update, name="bigbag_update",
    ),
    path(
        "api/bigbag/<int:bigbag_id>/export/xlsx/",
        views.bigbag_export_xlsx, name="bigbag_export_xlsx",
    ),
    path(
        "api/bigbag/<int:bigbag_id>/label/pdf/",
        views.bigbag_label_pdf, name="bigbag_label_pdf",
    ),
    path(
        "bigbag/<int:bigbag_id>/label/print/",
        views.bigbag_label_print, name="bigbag_label_print",
    ),
    path(
        "api/parcel/<int:parcel_id>/delete/",
        views.parcel_delete, name="parcel_delete",
    ),
    path("api/driver-search/", views.driver_search, name="driver_search"),
]
