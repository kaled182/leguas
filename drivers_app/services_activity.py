"""Atividade operacional dos motoristas — última entrega e inactividade.

Fonte: `CainiaoOperationTask` com estado Delivered / Attempt Failure.
Driver_received não conta: o roll-forward diário move esses pacotes
para "hoje" e daria uma atividade falsa.

A atribuição task → motorista segue a regra de
`portal_views._driver_base_queryset`, mas em lote (uma query para todos):
  - courier_name de um motorista → task desse motorista;
  - senão, courier_id do motorista → task desse motorista (só se o
    courier_name não pertencer a outro motorista);
  - transferências (WaybillAttributionOverride) contam para o destino.
"""
from collections import defaultdict
from datetime import timedelta

from django.db.models import Count, Max, Q
from django.utils import timezone

INACTIVITY_DAYS = 7
ACTIVITY_STATUSES = ("Delivered", "Attempt Failure")
# Janela máxima para procurar a última atividade.
LOOKBACK_DAYS = 400


def _courier_index():
    """Devolve (name_owners, id_owners): courier_name/courier_id → {driver_id}."""
    from settlements.models import CourierNameAlias, DriverCourierMapping
    from .models import DriverProfile

    name_owners = defaultdict(set)
    id_owners = defaultdict(set)
    for did, cid, apelido in DriverProfile.objects.values_list(
        "id", "courier_id_cainiao", "apelido",
    ):
        if cid:
            id_owners[cid].add(did)
        if apelido:
            name_owners[apelido].add(did)
    for did, cid, cname in DriverCourierMapping.objects.filter(
        partner__name__iexact="CAINIAO",
    ).values_list("driver_id", "courier_id", "courier_name"):
        if cid:
            id_owners[cid].add(did)
        if cname:
            name_owners[cname].add(did)
    # Aliases de nome: o nome passa a pertencer aos donos do courier_id.
    for cname, cid in CourierNameAlias.objects.filter(
        partner__name__iexact="CAINIAO", courier_id__in=list(id_owners),
    ).values_list("courier_name", "courier_id"):
        if cname:
            name_owners[cname] |= id_owners[cid]
    return name_owners, id_owners


def _owners(cid, cname, name_owners, id_owners):
    if cname and cname in name_owners:
        return name_owners[cname]
    if cid:
        return id_owners.get(cid, ())
    return ()


def last_activity_map(today=None):
    """{driver_id: date} — último dia com entrega/tentativa."""
    from settlements.models import CainiaoOperationTask, WaybillAttributionOverride

    today = today or timezone.localdate()
    since = today - timedelta(days=LOOKBACK_DAYS)
    name_owners, id_owners = _courier_index()

    result = {}

    def _bump(did, d):
        if d and (did not in result or d > result[did]):
            result[did] = d

    rows = (
        CainiaoOperationTask.objects
        .filter(task_date__gte=since, task_date__lte=today,
                task_status__in=ACTIVITY_STATUSES)
        .values("courier_id_cainiao", "courier_name")
        .annotate(last=Max("task_date"))
    )
    for r in rows:
        for did in _owners(r["courier_id_cainiao"], r["courier_name"],
                           name_owners, id_owners):
            _bump(did, r["last"])

    for did, last in (
        WaybillAttributionOverride.objects
        .filter(task_date__gte=since, task_date__lte=today)
        .values_list("attributed_to_driver_id")
        .annotate(last=Max("task_date"))
    ):
        _bump(did, last)
    return result


def daily_activity(date_from, date_to):
    """{driver_id: {date: delivered_count}} — só dias com atividade.

    Um dia só com tentativas falhadas aparece com 0 entregas.
    """
    from settlements.models import CainiaoOperationTask

    name_owners, id_owners = _courier_index()
    out = defaultdict(lambda: defaultdict(int))
    rows = (
        CainiaoOperationTask.objects
        .filter(task_date__range=(date_from, date_to),
                task_status__in=ACTIVITY_STATUSES)
        .values("task_date", "courier_id_cainiao", "courier_name")
        .annotate(delivered=Count("id", filter=Q(task_status="Delivered")))
    )
    for r in rows:
        for did in _owners(r["courier_id_cainiao"], r["courier_name"],
                           name_owners, id_owners):
            out[did][r["task_date"]] += r["delivered"]
    return out


def is_inactive(last_activity, created_at, today):
    """Regra: mais de INACTIVITY_DAYS dias sem atividade.

    Sem atividade registada, conta a data de criação (dá tempo ao
    motorista novo para começar).
    """
    ref = last_activity or (created_at.date() if created_at else None)
    if ref is None:
        return True
    return (today - ref).days > INACTIVITY_DAYS


def refresh_driver_activity(today=None):
    """Actualiza last_activity_date / inactive_since de todos os motoristas.

    Reactiva automaticamente (inactive_since = None) quem voltou a ter
    atividade. Devolve contagens para log.
    """
    from .models import DriverProfile

    today = today or timezone.localdate()
    now = timezone.now()
    last_map = last_activity_map(today)

    checked = inactivated = reactivated = 0
    to_update = []
    for d in DriverProfile.objects.only(
        "id", "created_at", "last_activity_date", "inactive_since",
    ):
        checked += 1
        last = last_map.get(d.id)
        inactive = is_inactive(last, d.created_at, today)
        new_since = d.inactive_since
        if inactive and d.inactive_since is None:
            new_since = today
            inactivated += 1
        elif not inactive and d.inactive_since is not None:
            new_since = None
            reactivated += 1
        d.last_activity_date = last
        d.inactive_since = new_since
        d.activity_checked_at = now
        to_update.append(d)

    DriverProfile.objects.bulk_update(
        to_update,
        ["last_activity_date", "inactive_since", "activity_checked_at"],
        batch_size=500,
    )
    return {
        "checked": checked,
        "inactivated": inactivated,
        "reactivated": reactivated,
        "ran_at": now.isoformat(),
    }
