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
