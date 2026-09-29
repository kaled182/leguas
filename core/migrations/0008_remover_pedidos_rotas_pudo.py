"""Remove da base de dados as apps retiradas do projeto: Pedidos
(orders_manager), Rotas (route_allocation) e Rede PUDO (pudo_network).

Nunca foram usadas: pedidos e turnos com 0 linhas; a Rede PUDO só com os
dados de um teste de julho de 2026 (1 loja, 4 pacotes).

Faz, por esta ordem:
  1. confirma que só as colunas esperadas (DriverClaim.order_id e
     SortingBigbag.pudo_store_id) apontam para as tabelas a apagar — se
     houver outra, pára antes de mexer em nada;
  2. tira essas duas colunas (e as FKs);
  3. apaga as tabelas das três apps;
  4. limpa django_migrations, content types/permissões/admin log dessas apps
     e dos modelos removidos do analytics;
  5. apaga as tarefas agendadas (django_celery_beat) das apps removidas e
     das sincronizações de parceiros (que só gravavam pedidos).
"""

from django.db import migrations

REMOVED_APPS = ("orders_manager", "route_allocation", "pudo_network")

REMOVED_TABLES = (
    "orders_manager_order",
    "orders_manager_orderstatushistory",
    "orders_manager_orderincident",
    "orders_manager_geocodedaddress",
    "orders_manager_geocodingfailure",
    "route_allocation_drivershift_assigned_postal_zones",
    "route_allocation_drivershift",
    "pudo_network_pudostore",
    "pudo_network_pudoaccess",
    "pudo_network_pudocustodypackage",
    "pudo_network_pudotransaction",
    "pudo_network_pudocustodyevent",
    "pudo_network_pudopickupotp",
    "pudo_network_pudodeliveryproof",
    "pudo_network_pudoupstreamreconciliation",
    "pudo_network_pudostorebillingline",
    "pudo_network_pudostorestatement",
    "pudo_network_pudodevicekey",
    "pudo_network_pudohandshakenonce",
)

# Colunas de tabelas que ficam e que apontavam para as tabelas removidas.
EXPECTED_FK_COLUMNS = {
    ("settlements_driverclaim", "order_id"),
    ("sorting_sortingbigbag", "pudo_store_id"),
}

REMOVED_BEAT_TASKS = (
    "core.sync_all_active_integrations",
    "core.sync_delnext",
    "core.sync_delnext_last_weekday",
    "core.geocode_recent_orders",
    "pudo_network.mark_expired",
    "pudo_network.emit_statements",
    "pudo_network.process_upstream",
)


def _mysql_fks_into_removed(cursor):
    placeholders = ", ".join(["%s"] * len(REMOVED_TABLES))
    cursor.execute(
        f"""
        SELECT TABLE_NAME, COLUMN_NAME, CONSTRAINT_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = DATABASE()
          AND REFERENCED_TABLE_NAME IN ({placeholders})
          AND TABLE_NAME NOT IN ({placeholders})
        """,
        list(REMOVED_TABLES) * 2,
    )
    return cursor.fetchall()


def forwards(apps, schema_editor):
    conn = schema_editor.connection
    qn = schema_editor.quote_name
    with conn.cursor() as cursor:
        existing = set(conn.introspection.table_names(cursor))

        # 1–2. Colunas de tabelas que ficam a apontar para as removidas.
        if conn.vendor == "mysql":
            fks = _mysql_fks_into_removed(cursor)
            unexpected = [(t, c) for t, c, _ in fks if (t, c) not in EXPECTED_FK_COLUMNS]
            if unexpected:
                raise RuntimeError(
                    f"FKs inesperadas para as tabelas a remover: {unexpected}. "
                    "Nada foi alterado."
                )
            for table, _column, constraint in fks:
                cursor.execute(f"ALTER TABLE {qn(table)} DROP FOREIGN KEY {qn(constraint)}")
        for table, column in sorted(EXPECTED_FK_COLUMNS):
            if table not in existing:
                continue
            columns = {c.name for c in conn.introspection.get_table_description(cursor, table)}
            if column in columns:
                cursor.execute(f"ALTER TABLE {qn(table)} DROP COLUMN {qn(column)}")

        # 3. Tabelas das apps removidas.
        to_drop = [t for t in REMOVED_TABLES if t in existing]
        if to_drop:
            if conn.vendor == "mysql":
                cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            try:
                for table in to_drop:
                    cursor.execute(f"DROP TABLE {qn(table)}")
            finally:
                if conn.vendor == "mysql":
                    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")

        # 4. Registos internos do Django.
        if "django_migrations" in existing:
            placeholders = ", ".join(["%s"] * len(REMOVED_APPS))
            cursor.execute(
                f"DELETE FROM django_migrations WHERE app IN ({placeholders})",
                list(REMOVED_APPS),
            )
        if "django_content_type" in existing:
            labels = list(REMOVED_APPS)
            cursor.execute(
                "SELECT id FROM django_content_type WHERE app_label IN (%s, %s, %s) "
                "OR (app_label = %s AND model IN (%s, %s, %s, %s))",
                labels + ["analytics", "dailymetrics", "driverperformance",
                          "performancealert", "volumeforecast"],
            )
            ct_ids = [row[0] for row in cursor.fetchall()]
            if ct_ids:
                ph = ", ".join(["%s"] * len(ct_ids))
                for table in ("auth_permission", "django_admin_log"):
                    if table in existing:
                        cursor.execute(f"DELETE FROM {table} WHERE content_type_id IN ({ph})", ct_ids)
                cursor.execute(f"DELETE FROM django_content_type WHERE id IN ({ph})", ct_ids)

        # 5. Tarefas agendadas órfãs.
        if "django_celery_beat_periodictask" in existing:
            ph = ", ".join(["%s"] * len(REMOVED_BEAT_TASKS))
            cursor.execute(
                f"DELETE FROM django_celery_beat_periodictask WHERE task IN ({ph})",
                list(REMOVED_BEAT_TASKS),
            )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("core", "0007_partner_verdict_claim_amount"),
        ("settlements", "0055_driverclaim_billing_after"),
        ("sorting", "0004_remover_pudo"),
        ("analytics", "0002_remover_metricas_de_pedidos"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("admin", "0003_logentry_add_action_flag_choices"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
