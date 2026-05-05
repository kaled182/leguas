"""Tasks Celery do app settlements."""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="settlements.create_daily_not_arrived_snapshot")
def create_daily_not_arrived_snapshot():
    """Snapshot diário automático da lista Not Arrived.

    Corre todos os dias às 18h. Cria um NotArrivedSnapshot com a
    fotografia do dia, comparada com o snapshot anterior, e — se a
    contagem subir >=1.5x ou aumentar 5+ pacotes — envia spike alert
    via WhatsApp ao grupo configurado.
    """
    import requests
    from datetime import timedelta
    from django.conf import settings as dj_settings
    from django.utils import timezone
    from .cainiao_views import _build_snapshot
    from .models import NotArrivedSnapshot

    # Cria/actualiza o snapshot de hoje
    snap = _build_snapshot(automatic=True)
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    prev = NotArrivedSnapshot.objects.filter(
        snapshot_date=yesterday,
    ).first()

    spike_msg = None
    if prev and prev.total_packages > 0:
        ratio = snap.total_packages / prev.total_packages
        delta = snap.total_packages - prev.total_packages
        if ratio >= 1.5 and delta >= 5:
            spike_msg = (
                f"⚠ *SPIKE ALERT* — Not Arrived subiu "
                f"de *{prev.total_packages}* para "
                f"*{snap.total_packages}* "
                f"({delta:+d}, {ratio:.1f}×). "
                f"Verificar urgentemente."
            )
    elif (
        prev is None
        and snap.total_packages >= 5
    ):
        spike_msg = (
            f"⚠ *Snapshot inaugural* — *{snap.total_packages}* "
            "pacotes Not Arrived hoje."
        )

    # Envia daily report ao grupo (se configurado)
    api_url = (
        getattr(dj_settings, "WHATSAPP_API_URL", "")
        or "http://45.160.176.150:9090/message/sendText/leguasreports"
    )
    group = getattr(dj_settings, "WHATSAPP_REPORT_GROUP", "")

    lines = [
        f"📦 *Snapshot Not Arrived — {snap.snapshot_date:%d/%m/%Y}*",
        "",
        f"🔴 Total: *{snap.total_packages}* pacote(s) presos",
        f"⚠️ A escalar (>10d): *{snap.n_to_escalate}*",
        f"💰 Custo estimado: *€{snap.total_cost_eur:.2f}*",
        f"👥 {snap.n_drivers_affected} drivers · "
        f"{snap.n_cp4s_affected} CP4s",
    ]
    if spike_msg:
        lines.insert(2, spike_msg)
        lines.insert(3, "")
    if prev:
        delta = snap.total_packages - prev.total_packages
        sign = "+" if delta > 0 else ""
        lines.append(
            f"_Variação vs ontem: {sign}{delta} "
            f"(ontem: {prev.total_packages})_"
        )
    lines.append("")
    lines.append("(snapshot automático)")
    message = "\n".join(lines)

    sent = False
    if group:
        try:
            r = requests.post(
                api_url,
                json={"number": group, "text": message},
                timeout=15,
            )
            sent = r.status_code in (200, 201)
        except Exception as e:
            logger.exception(
                "[DailySnapshot] erro a enviar WhatsApp: %s", e,
            )

    logger.info(
        "[DailySnapshot] criado snapshot id=%s data=%s "
        "total=%s sent=%s spike=%s",
        snap.id, snap.snapshot_date, snap.total_packages,
        sent, bool(spike_msg),
    )
    return {
        "snapshot_id": snap.id,
        "total": snap.total_packages,
        "sent": sent,
        "spike": bool(spike_msg),
    }


@shared_task(name="settlements.send_not_arrived_weekly_report")
def send_not_arrived_weekly_report():
    """Envia o relatório semanal de Pacotes Not Arrived via WhatsApp
    para o grupo configurado em WHATSAPP_REPORT_GROUP / WHATSAPP_API_URL.

    Inclui: total, top 5 drivers, top 5 CP4s, custo estimado, n a
    escalar, spike alert se houver.
    """
    import requests
    from django.conf import settings as dj_settings
    from .cainiao_views import _compute_not_arrived

    rows = _compute_not_arrived(min_days=2)
    if not rows:
        logger.info(
            "[NotArrivedWeekly] Sem pacotes — relatório saltado.",
        )
        return {"sent": False, "reason": "no_rows"}

    # Sumário
    total = len(rows)
    n_escalate = sum(1 for r in rows if r.get("should_escalate"))
    total_cost = sum(r.get("estimated_cost_eur", 0) for r in rows)

    # Top drivers
    by_driver = {}
    for r in rows:
        key = r["courier_name"] or "(sem driver)"
        by_driver.setdefault(key, 0)
        by_driver[key] += 1
    top_drivers = sorted(
        by_driver.items(), key=lambda x: -x[1],
    )[:5]

    # Top CP4s
    by_cp4 = {}
    for r in rows:
        key = r["cp4"] or "(?)"
        by_cp4.setdefault(key, 0)
        by_cp4[key] += 1
    top_cp4s = sorted(by_cp4.items(), key=lambda x: -x[1])[:5]

    lines = [
        "📦 *RELATÓRIO SEMANAL — PACOTES NOT ARRIVED*",
        "",
        f"🔴 Total: *{total}* pacotes presos",
        f"⚠️ A escalar (>10d): *{n_escalate}*",
        f"💰 Custo estimado: *€{total_cost:.2f}*",
        "",
        "*Top drivers:*",
    ]
    for drv, n in top_drivers:
        lines.append(f"  • {drv} — *{n}*")
    lines.append("")
    lines.append("*Top CP4s:*")
    for cp4, n in top_cp4s:
        lines.append(f"  • CP4 {cp4} — *{n}*")
    lines.append("")
    lines.append("(gerado automaticamente pelo sistema)")
    message = "\n".join(lines)

    api_url = (
        getattr(dj_settings, "WHATSAPP_API_URL", "")
        or "http://45.160.176.150:9090/message/sendText/leguasreports"
    )
    group = getattr(dj_settings, "WHATSAPP_REPORT_GROUP", "")

    if not group:
        logger.warning(
            "[NotArrivedWeekly] WHATSAPP_REPORT_GROUP não config; "
            "saltando envio.",
        )
        return {"sent": False, "reason": "no_group", "preview": message}

    try:
        r = requests.post(
            api_url,
            json={"number": group, "text": message},
            timeout=15,
        )
        ok = r.status_code in (200, 201)
        logger.info(
            "[NotArrivedWeekly] enviado: %s (status=%s)",
            ok, r.status_code,
        )
        return {
            "sent": ok, "total": total,
            "n_escalate": n_escalate, "cost": total_cost,
        }
    except Exception as e:
        logger.exception("[NotArrivedWeekly] erro: %s", e)
        return {"sent": False, "reason": str(e)}


@shared_task(name="settlements.roll_forward_active_packages")
def roll_forward_active_packages(threshold_days=None, dry_run=False):
    """Move pacotes Driver_received "vivos" (com Task Date < hoje, mas
    dentro do threshold) para a data de HOJE.

    Reflecte realidade operacional: pacote que está com driver há 1-7 dias
    sem entrega ainda está em rota. Cainiao não regista uma "ainda comigo"
    diariamente, então fazemos o roll-forward para o pacote aparecer no
    relatório do dia actual como activo.

    Pacotes Driver_received há mais de threshold_days vão para
    `mark_stale_armazem` (gestão separada).

    Args:
        threshold_days: pacotes com data >= hoje - threshold_days são
                        considerados activos. Default: settings.CAINIAO_ROLLFORWARD_DAYS (7).
        dry_run: se True, apenas conta sem alterar.

    Returns:
        dict com {rolled, deleted_duplicate, today, threshold_days}
    """
    from datetime import timedelta
    from django.conf import settings as dj_settings
    from django.db import transaction
    from django.utils import timezone
    from .models import (
        CainiaoOperationTask, CainiaoOperationTaskHistory,
    )

    if threshold_days is None:
        threshold_days = getattr(dj_settings, "CAINIAO_ROLLFORWARD_DAYS", 7)
    threshold_days = int(threshold_days)

    today = timezone.now().date()
    cutoff_old = today - timedelta(days=threshold_days)

    # Pacotes Driver_received com task_date < hoje E data >= hoje - threshold.
    # Excluímos hoje (já estão lá) e datas muito antigas (vão para stale).
    qs = CainiaoOperationTask.objects.filter(
        task_status="Driver_received",
        task_date__lt=today,
        task_date__gte=cutoff_old,
    )

    total = qs.count()
    if total == 0:
        logger.info(
            "[RollForward] sem pacotes activos a mover (today=%s, cutoff=%s).",
            today, cutoff_old,
        )
        return {
            "rolled": 0, "today": str(today),
            "threshold_days": threshold_days, "dry_run": dry_run,
        }

    if dry_run:
        from collections import Counter
        breakdown = Counter(qs.values_list("task_date", "courier_name"))
        return {
            "rolled": 0, "would_roll": total,
            "today": str(today),
            "threshold_days": threshold_days,
            "dry_run": True,
            "by_date_courier": [
                {"task_date": str(d), "courier": c, "count": n}
                for (d, c), n in breakdown.most_common(50)
            ],
        }

    # Recolher info para criar history entries antes do UPDATE/DELETE
    rows = list(qs.values(
        "id", "waybill_number", "task_date", "task_status", "courier_name",
        "courier_id_cainiao",
    ))

    # Conflitos: se waybill já existe em HOJE, não duplicar — apaga a row de ontem
    today_waybills_existing = set(
        CainiaoOperationTask.objects.filter(
            task_date=today,
            waybill_number__in=[r["waybill_number"] for r in rows],
        ).values_list("waybill_number", flat=True)
    )
    rows_to_move = [r for r in rows if r["waybill_number"] not in today_waybills_existing]
    rows_to_delete = [r for r in rows if r["waybill_number"] in today_waybills_existing]

    # History entries (preserva timeline)
    history_objs = [
        CainiaoOperationTaskHistory(
            waybill_number=r["waybill_number"],
            task_date=today,
            task_status=r["task_status"],
            courier_name=r["courier_name"],
            courier_id_cainiao=r["courier_id_cainiao"],
            previous_task_date=r["task_date"],
            previous_task_status=r["task_status"],
            previous_courier_name=r["courier_name"],
            change_type="rolled_forward",
            event_timestamp=None,
            batch=None,
        )
        for r in rows_to_move
    ]

    with transaction.atomic():
        if history_objs:
            CainiaoOperationTaskHistory.objects.bulk_create(
                history_objs, batch_size=1000,
            )
        if rows_to_move:
            CainiaoOperationTask.objects.filter(
                id__in=[r["id"] for r in rows_to_move]
            ).update(task_date=today)
        if rows_to_delete:
            CainiaoOperationTask.objects.filter(
                id__in=[r["id"] for r in rows_to_delete]
            ).delete()

    logger.info(
        "[RollForward] %d pacotes movidos para hoje (%s); "
        "%d duplicados apagados (já existiam em hoje); threshold=%d dias.",
        len(rows_to_move), today, len(rows_to_delete), threshold_days,
    )

    return {
        "rolled": len(rows_to_move),
        "deleted_duplicate": len(rows_to_delete),
        "today": str(today),
        "threshold_days": threshold_days,
        "history_created": len(history_objs),
        "dry_run": False,
    }


@shared_task(name="settlements.mark_stale_armazem")
def mark_stale_armazem(threshold_days=None, dry_run=False):
    """Marca pacotes 'esquecidos' no armazém (placeholder courier) com
    status `Driver_received` há mais de N dias como `Stale_Armazem`.

    Reflecte a realidade: a Cainiao geralmente já reciclou esses pacotes
    (entrega bem-sucedida posterior, devolução, ou cancelamento), mas as
    planilhas que recebemos não voltam a trazer essas waybills, deixando
    o nosso BD com snapshots stale.

    Args:
        threshold_days: dias após os quais um waybill é considerado stale.
                        Default = settings.CAINIAO_STALE_DAYS (fallback 5).
        dry_run: se True, apenas conta sem alterar.

    Cria entry no CainiaoOperationTaskHistory para cada waybill afectado
    (change_type='stale_cleanup') — preserva timeline.

    Returns:
        dict com {marked, threshold_days, dry_run, by_date_courier}
    """
    from datetime import timedelta
    from django.conf import settings as dj_settings
    from django.utils import timezone
    from .models import (
        CainiaoOperationTask, CainiaoOperationTaskHistory,
    )

    if threshold_days is None:
        threshold_days = getattr(dj_settings, "CAINIAO_STALE_DAYS", 7)
    threshold_days = int(threshold_days)

    cutoff = timezone.now().date() - timedelta(days=threshold_days)

    # Pacotes "esquecidos" — qualquer courier com Driver_received há mais
    # de threshold_days. A regra do operador: pacotes activos recentes
    # (1-7 dias) são movidos para hoje pelo roll_forward; os mais antigos
    # provavelmente foram entregues/perdidos sem o Cainiao actualizar.
    qs = CainiaoOperationTask.objects.filter(
        task_status="Driver_received",
        task_date__lte=cutoff,
    )

    total = qs.count()
    if total == 0:
        logger.info(
            "[StaleArmazem] sem pacotes stale a marcar (cutoff=%s).",
            cutoff,
        )
        return {
            "marked": 0, "threshold_days": threshold_days,
            "dry_run": dry_run, "cutoff": str(cutoff),
        }

    if dry_run:
        # Distribuição p/ inspecção
        from collections import Counter
        breakdown = Counter(
            qs.values_list("task_date", "courier_name")
        )
        logger.info(
            "[StaleArmazem] DRY-RUN: marcaria %d pacotes (cutoff=%s).",
            total, cutoff,
        )
        return {
            "marked": 0, "would_mark": total,
            "threshold_days": threshold_days,
            "dry_run": True, "cutoff": str(cutoff),
            "by_date_courier": [
                {"task_date": str(d), "courier": c, "count": n}
                for (d, c), n in breakdown.most_common(50)
            ],
        }

    # Recolher info para criar history entries antes do UPDATE
    rows = list(qs.values(
        "id", "waybill_number", "task_date", "task_status", "courier_name",
        "courier_id_cainiao",
    ))
    history_objs = [
        CainiaoOperationTaskHistory(
            waybill_number=r["waybill_number"],
            task_date=r["task_date"],
            task_status="Stale_Armazem",
            courier_name=r["courier_name"],
            courier_id_cainiao=r["courier_id_cainiao"],
            previous_task_date=r["task_date"],
            previous_task_status=r["task_status"],
            previous_courier_name=r["courier_name"],
            change_type="stale_cleanup",
            event_timestamp=None,
            batch=None,
        )
        for r in rows
    ]
    CainiaoOperationTaskHistory.objects.bulk_create(history_objs, batch_size=1000)

    # UPDATE em massa — só toca em task_status (preserva courier/data)
    updated = qs.update(task_status="Stale_Armazem")

    logger.info(
        "[StaleArmazem] marcados %d pacotes como Stale_Armazem "
        "(cutoff=%s, threshold=%d dias).",
        updated, cutoff, threshold_days,
    )

    return {
        "marked": updated,
        "threshold_days": threshold_days,
        "dry_run": False,
        "cutoff": str(cutoff),
        "history_created": len(history_objs),
    }
