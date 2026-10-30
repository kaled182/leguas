"""
Relatório de uso por modelo, só de leitura (Fase 0.7 do rebrand).

Mostra só contagens e datas. Não mostra nomes, NIF, moradas nem valores.

Uso:
    python manage.py usage_report
    python manage.py usage_report --json
"""

import json

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import connection, models

PROJECT_APPS = (
    "accounting", "analytics", "app_api", "contracts", "converter", "core",
    "customauth", "dashboard_leguas", "drivers_app", "fleet_management",
    "geozonas", "management", "payroll", "pricing", "settlements", "sorting",
    "system_config",
)

CANDIDATES = {
    "Frota": [
        "fleet_management.Vehicle",
        "fleet_management.VehicleAssignment",
        "fleet_management.VehicleMaintenance",
        "fleet_management.VehicleIncident",
    ],
    "Tarifas e zonas postais": [
        "pricing.PartnerTariff",
        "pricing.PostalZone",
    ],
    "Contratos": [
        "contracts.ContractTemplate",
        "contracts.DriverContract",
        "contracts.GeneratedContract",
    ],
    "Sorting (tabelas sem páginas)": [
        "sorting.SortingSession",
        "sorting.SortingBigbag",
        "sorting.SortingParcel",
    ],
}

TIMESTAMP_NAMES = (
    "updated_at", "atualizado_em", "created_at", "criado_em", "timestamp",
    "date", "data",
)


def enforce_read_only():
    """Pede à base de dados para recusar qualquer escrita nesta sessão."""
    with connection.cursor() as cursor:
        if connection.vendor == "mysql":
            cursor.execute("SET SESSION TRANSACTION READ ONLY")
        elif connection.vendor == "sqlite":
            cursor.execute("PRAGMA query_only = ON")


def timestamp_field(model):
    fields = [
        f for f in model._meta.concrete_fields
        if isinstance(f, (models.DateTimeField, models.DateField))
    ]
    for f in fields:
        if getattr(f, "auto_now", False):
            return f.name
    for f in fields:
        if getattr(f, "auto_now_add", False):
            return f.name
    names = {f.name: f for f in fields}
    for name in TIMESTAMP_NAMES:
        if name in names:
            return name
    return fields[0].name if fields else None


def model_usage(model):
    manager = model._base_manager
    field = timestamp_field(model)
    last = None
    if field:
        last = manager.aggregate(last=models.Max(field))["last"]
    return {
        "model": model._meta.label,
        "table": model._meta.db_table,
        "rows": manager.count(),
        "date_field": field,
        "last_record": last.isoformat() if last else None,
    }


def user_usage():
    users = get_user_model().objects.filter(is_active=True)
    return {
        "active": users.count(),
        "superuser": users.filter(is_superuser=True).count(),
        "staff_not_superuser": users.filter(
            is_staff=True, is_superuser=False,
        ).count(),
        "not_staff": users.filter(is_staff=False, is_superuser=False).count(),
    }


class Command(BaseCommand):
    help = "Conta registos por modelo, sem alterar dados (Fase 0.7 do rebrand)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--json", action="store_true", help="Escreve o resultado em JSON.",
        )

    def handle(self, *args, **options):
        enforce_read_only()
        rows = [
            model_usage(model)
            for model in apps.get_models()
            if model._meta.app_label in PROJECT_APPS
            and model._meta.managed
            and not model._meta.proxy
        ]
        rows.sort(key=lambda row: row["model"])
        by_model = {row["model"]: row for row in rows}
        report = {
            "users": user_usage(),
            "candidates": {
                group: [by_model[label] for label in labels]
                for group, labels in CANDIDATES.items()
            },
            "models": rows,
        }
        if options["json"]:
            self.stdout.write(json.dumps(report, indent=1, ensure_ascii=False))
            return
        self.stdout.write(f"Utilizadores ativos: {report['users']}")
        for group, group_rows in report["candidates"].items():
            self.stdout.write(f"\n== {group}")
            self._write_rows(group_rows)
        self.stdout.write("\n== Todos os modelos")
        self._write_rows(rows)

    def _write_rows(self, rows):
        for row in rows:
            self.stdout.write(
                f"{row['model']:<48} {row['rows']:>9}  "
                f"{row['last_record'] or '-'}"
            )
