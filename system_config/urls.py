from django.urls import path

from . import views
from . import backup_views
from . import user_views
from . import views_updates

app_name = "system_config"

urlpatterns = [
    path("", views.system_config_view, name="index"),
    path("save/", views.save_config, name="save"),

    # ─── Atualização: changelog, sugestões e check do GitHub ───
    path("atualizacao/", views_updates.updates_index, name="updates_index"),
    path(
        "atualizacao/sugestao/criar/",
        views_updates.suggestion_create,
        name="suggestion_create",
    ),
    path(
        "atualizacao/sugestao/<int:suggestion_id>/atualizar/",
        views_updates.suggestion_update_status,
        name="suggestion_update_status",
    ),
    path(
        "atualizacao/github/configurar/",
        views_updates.github_save_config,
        name="github_save_config",
    ),
    path(
        "atualizacao/verificar/",
        views_updates.updates_check,
        name="updates_check",
    ),
    path(
        "atualizacao/aplicar/",
        views_updates.updates_apply,
        name="updates_apply",
    ),
    path(
        "atualizacao/status/",
        views_updates.updates_status,
        name="updates_status",
    ),

    # ─── Gestão de Utilizadores ───
    path("users/", user_views.user_list, name="user_list"),
    path("users/create/", user_views.user_create, name="user_create"),
    path("users/<int:pk>/edit/", user_views.user_edit, name="user_edit"),
    path("users/<int:pk>/delete/", user_views.user_delete, name="user_delete"),
    path("users/<int:pk>/toggle-active/", user_views.user_toggle_active, name="user_toggle_active"),
    path("users/<int:pk>/reset-password/", user_views.user_reset_password, name="user_reset_password"),

    path("whatsapp/", views.whatsapp_dashboard, name="whatsapp_dashboard"),
    path(
        "whatsapp/start/",
        views.whatsapp_start_session,
        name="whatsapp_start_session",
    ),
    path("whatsapp/status/", views.whatsapp_status, name="whatsapp_status"),
    path("whatsapp/qrcode/", views.whatsapp_qrcode, name="whatsapp_qrcode"),
    path("whatsapp/logout/", views.whatsapp_logout, name="whatsapp_logout"),
    path(
        "whatsapp/send-test/",
        views.whatsapp_send_test,
        name="whatsapp_send_test",
    ),
    path(
        "whatsapp/update-config/",
        views.whatsapp_update_config,
        name="whatsapp_update_config",
    ),
    path(
        "whatsapp/generate-token/",
        views.whatsapp_generate_token,
        name="whatsapp_generate_token",
    ),
    # Backups
    path("backups/", backup_views.backups_manager, name="backups_manager"),
    path("backups/delete/", backup_views.delete_backup, name="backup_delete"),
    path("backups/restore/", backup_views.restore_backup, name="backup_restore"),
    path("backups/upload-cloud/", backup_views.upload_backup_to_cloud, name="backup_upload_cloud"),
    path("backups/download/<str:filename>/", backup_views.download_backup, name="backup_download"),
    # Typebot
    path(
        "typebot/test-connection/",
        views.typebot_test_connection,
        name="typebot_test_connection",
    ),
    path(
        "typebot/auto-login/",
        views.typebot_auto_login,
        name="typebot_auto_login",
    ),
    path(
        "typebot/generate-secret/",
        views.typebot_generate_encryption_secret,
        name="typebot_generate_secret",
    ),
]
