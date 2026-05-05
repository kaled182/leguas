"""Unificação de cadastros de motoristas.

Quando o mesmo motorista existe duas vezes na DB (ex: importação
duplicada com courier_ids diferentes), o admin pode usar
`merge_drivers(source, target, user)` para:

  1. Mover todos os FKs apontados ao `source` para `target`
     (DriverPreInvoice, DriverAccess, DriverCourierMapping, etc.)
  2. Apagar o `source` driver
  3. Gravar registo de auditoria em `DriverMergeAudit`

Tudo dentro de uma única transacção atómica — se algum passo falhar,
nada é alterado.
"""
from django.db import transaction

from .models import DriverMergeAudit, DriverProfile


# Modelos com FK directa para DriverProfile.
# Lista mantida sincronizada com o código real — see grep:
#   grep -rE "ForeignKey.*DriverProfile" --include='*.py'
#
# Cada entrada: (app_label, model_name, fk_field_name)
FK_TARGETS = [
    ("contracts", "DriverContract", "driver"),
    ("customauth", "DriverAccess", "driver_profile"),
    ("fleet_management", "VehicleAssignment", "driver"),
    ("fleet_management", "VehicleIncident", "driver"),
    ("route_allocation", "DriverShift", "driver"),
    ("settlements", "DriverSettlement", "driver"),
    ("settlements", "DriverClaim", "driver"),
    ("settlements", "DriverPreInvoice", "driver"),
    ("settlements", "PreInvoiceAdvance", "driver"),
    ("settlements", "DriverCourierMapping", "driver"),
    ("settlements", "CainiaoDelivery", "driver"),
    ("settlements", "DriverHelper", "driver"),
    ("settlements", "OperationalCost", "driver"),
    ("settlements", "FinancialAlert", "driver"),
    ("settlements", "FleetInvoiceDriverLine", "driver"),
    ("settlements", "ForecastPlanAssignment", "driver"),
    ("settlements", "WaybillAttributionOverride", "attributed_to_driver"),
    ("analytics", "DriverPerformance", "driver"),
    ("drivers_app", "DriverProfileChangeRequest", "driver"),
    ("drivers_app", "EmpresaParceiraLancamento", "driver"),
]

# Modelos opcionais — só processados se existirem no projecto
OPTIONAL_FK_TARGETS = [
    ("settlements", "PreInvoiceLine", "driver"),
    ("settlements", "PreInvoiceBonus", "driver"),
    ("settlements", "PreInvoiceLostPackage", "driver"),
    ("settlements", "ThirdPartyReimbursement", "driver"),
    ("settlements", "Shareholder", "user"),  # diferente: aponta a User
]


def _get_model(app_label, model_name):
    """Devolve a classe do modelo ou None se não existir."""
    from django.apps import apps
    try:
        return apps.get_model(app_label, model_name)
    except LookupError:
        return None


def preview_merge(source: DriverProfile, target: DriverProfile) -> dict:
    """Conta quantas linhas serão transferidas, sem alterar nada.

    Devolve dict { "<app.Model>": int, "_total": int }.
    """
    counts = {}
    total = 0
    for app, model, field in FK_TARGETS + OPTIONAL_FK_TARGETS:
        Model = _get_model(app, model)
        if Model is None:
            continue
        try:
            n = Model.objects.filter(**{field: source}).count()
        except Exception:
            continue
        if n > 0:
            counts[f"{app}.{model}"] = n
            total += n
    counts["_total"] = total
    return counts


@transaction.atomic
def merge_drivers(source: DriverProfile, target: DriverProfile,
                  user=None, notes: str = "") -> DriverMergeAudit:
    """Move tudo do `source` para o `target` e apaga `source`.

    Levanta ValueError se source == target ou se source já não existe.
    Retorna o `DriverMergeAudit` criado.
    """
    if source.pk == target.pk:
        raise ValueError("Source e target são o mesmo motorista.")
    if not DriverProfile.objects.filter(pk=source.pk).exists():
        raise ValueError(f"Source driver #{source.pk} não existe.")
    if not DriverProfile.objects.filter(pk=target.pk).exists():
        raise ValueError(f"Target driver #{target.pk} não existe.")

    transferred = {}

    for app, model, field in FK_TARGETS + OPTIONAL_FK_TARGETS:
        Model = _get_model(app, model)
        if Model is None:
            continue
        try:
            n = Model.objects.filter(**{field: source}).update(
                **{field: target}
            )
        except Exception as e:
            raise RuntimeError(
                f"Falha a reassignar {app}.{model}.{field}: {e}"
            )
        if n > 0:
            transferred[f"{app}.{model}"] = n

    # Snapshot textual do source antes de apagar
    source_repr = (
        f"#{source.pk} · {source.nome_completo} · {source.apelido or '-'}"
    )
    if source.courier_id_cainiao:
        source_repr += f" · cainiao={source.courier_id_cainiao}"

    # Audit log
    audit = DriverMergeAudit.objects.create(
        source_driver_repr=source_repr,
        source_driver_id=source.pk,
        target_driver=target,
        transferred_counts=transferred,
        notes=notes,
        merged_by=user if (user and user.is_authenticated) else None,
    )

    # Apagar source
    source.delete()

    return audit
