"""Signals do app settlements — audit log para detectar deleções
inesperadas de dados sensíveis (e.g. CainiaoManualForecast).
"""
import logging
import traceback

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import (
    CainiaoManualForecast, CainiaoOperationTask, WaybillResolution,
    WaybillFlag,
)

logger = logging.getLogger("settlements.audit")


# ─── Auto-resolve de Not Arrived em re-import ─────────────────────────
PICKED_STATUSES_AUTO = (
    "Driver Received", "Driver_received",
    "Delivered", "Attempt Failure", "Attempt_Failure",
)


@receiver(post_save, sender=CainiaoOperationTask)
def _auto_resolve_on_picked(sender, instance, created, **kwargs):
    """Se uma operação aparece com status 'picked' e o waybill estava
    marcado manualmente como Not Arrived (com WaybillResolution), nada
    a fazer — a resolução manual prevalece. Mas se NÃO tinha resolução
    e o waybill antes só tinha Assigned/Unassign, agora foi 'picked'
    naturalmente — o `_compute_not_arrived` já o exclui sem precisar
    de intervenção.

    O caso onde precisamos agir: quando o utilizador marcou manualmente
    e depois a planilha real chega trazendo o pacote como Delivered.
    Nesse caso convertemos a resolução para AUTO_REIMPORT e adicionamos
    nota com courier real, para auditoria.
    """
    if instance.task_status not in PICKED_STATUSES_AUTO:
        return
    wb = instance.waybill_number
    if not wb:
        return
    res = WaybillResolution.objects.filter(waybill_number=wb).first()
    if not res:
        return
    # Já estava resolvida manualmente — converter para AUTO_REIMPORT
    # e anexar info do snapshot real.
    if res.resolution_type == WaybillResolution.TYPE_AUTO_REIMPORT:
        return  # já é auto, nada a fazer
    prev = res.resolution_type
    res.resolution_type = WaybillResolution.TYPE_AUTO_REIMPORT
    res.notes = (
        (res.notes or "") + "\n\n[AUTO]\n"
        f"Reimport detectou status real '{instance.task_status}' "
        f"em {instance.task_date} pelo courier "
        f"'{instance.courier_name}'. "
        f"Resolução anterior: {prev}."
    ).strip()
    res.save(update_fields=["resolution_type", "notes", "updated_at"])
    logger.info(
        "[AutoResolve] %s convertido para AUTO_REIMPORT (%s -> %s)",
        wb, prev, instance.task_status,
    )


@receiver(post_save, sender=CainiaoOperationTask)
def _auto_clear_flag_on_picked(sender, instance, created, **kwargs):
    """Quando um waybill volta a aparecer com status picked
    (Driver_received / Delivered / Failure), auto-limpa qualquer
    WaybillFlag activo. Mantém em audit log o motivo da limpeza.
    """
    from django.utils import timezone

    if instance.task_status not in (
        "Driver Received", "Driver_received",
        "Delivered", "Attempt Failure", "Attempt_Failure",
    ):
        return
    wb = instance.waybill_number
    if not wb:
        return
    active = WaybillFlag.objects.filter(
        waybill_number=wb, cleared_at__isnull=True,
    )
    if not active.exists():
        return
    n = active.update(
        cleared_at=timezone.now(),
        cleared_reason=(
            f"Reimport detectou status '{instance.task_status}' "
            f"em {instance.task_date} pelo courier "
            f"'{instance.courier_name}'"
        ),
        auto_cleared=True,
    )
    if n:
        logger.info(
            "[AutoClearFlag] %s flag(s) limpos para waybill %s "
            "(novo status %s pelo courier %s)",
            n, wb, instance.task_status, instance.courier_name,
        )


@receiver(post_save, sender=CainiaoManualForecast)
def _log_manual_forecast_save(sender, instance, created, **kwargs):
    action = "CREATE" if created else "UPDATE"
    logger.info(
        "[ManualForecast %s] id=%s date=%s cp4=%s qty=%s",
        action, instance.id, instance.operation_date,
        instance.cp4, instance.qty,
    )


@receiver(post_delete, sender=CainiaoManualForecast)
def _log_manual_forecast_delete(sender, instance, **kwargs):
    """Regista deleções para auditoria. Stack trace só em DEBUG."""
    # Filtra stack para apenas frames do projecto (ignora django interno)
    project_frames = []
    for frame in traceback.extract_stack(limit=20):
        fname = frame.filename
        if "/site-packages/" in fname or "/python3" in fname:
            continue
        project_frames.append(
            f"  {fname}:{frame.lineno} in {frame.name}"
        )
    caller_summary = (
        project_frames[-2] if len(project_frames) >= 2
        else (project_frames[-1] if project_frames else "<unknown>")
    )
    logger.warning(
        "[ManualForecast DELETE] id=%s date=%s cp4=%s qty=%s | from: %s",
        instance.id, instance.operation_date,
        instance.cp4, instance.qty, caller_summary.strip(),
    )
