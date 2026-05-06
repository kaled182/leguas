"""Detector de motoristas com entregas mas sem pré-fatura no período.

Cruza `CainiaoOperationTask` (entregas) com `DriverPreInvoice` (PFs)
para encontrar motoristas que entregaram pacotes mas não têm PF que
cubra esse intervalo. Garante que ninguém fica sem ser pago.

Critério "pragmático" (default):
    - Motorista com ≥1 pacote `Delivered` no período
    - Soma de dias COM PF (que sobreponha o período) é < total de dias
      com entregas, com gap ≥ MIN_GAP_DAYS

Cálculo do valor estimado (corrigido):
    - Conta entregas em TODOS os mappings do motorista (DriverCourierMapping
      + apelido + courier_id_cainiao), não só os principais
    - Soma bónus de domingo/feriado pelas faixas €30 (≥30 entregas)
      ou €50 (≥60 entregas) por dia
"""
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

MIN_GAP_DAYS = 7  # Só reporta motoristas com gap >= 7 dias


def _collect_driver_courier_keys():
    """Constrói (drivers_by_id, courier_id_to_driver, courier_name_to_driver).

    courier_id_to_driver: dict de courier_id → driver (TODOS os mappings)
    courier_name_to_driver: dict de courier_name (lowercase) → driver
    """
    from drivers_app.models import DriverProfile
    from settlements.models import DriverCourierMapping, CourierNameAlias

    drivers = DriverProfile.objects.exclude(status="IRREGULAR")
    drivers_by_id = {d.id: d for d in drivers}

    cid_to_driver = {}
    cname_to_driver = {}

    # Direct fields no DriverProfile
    for d in drivers:
        if d.courier_id_cainiao:
            cid_to_driver[d.courier_id_cainiao] = d
        if d.apelido:
            cname_to_driver[d.apelido.strip().lower()] = d

    # DriverCourierMapping (TODOS os couriers extra do mesmo driver)
    for m in DriverCourierMapping.objects.select_related("driver", "partner"):
        if not m.driver_id or m.driver_id not in drivers_by_id:
            continue
        if m.courier_id:
            cid_to_driver[m.courier_id] = drivers_by_id[m.driver_id]
        if m.courier_name:
            cname_to_driver[m.courier_name.strip().lower()] = (
                drivers_by_id[m.driver_id]
            )

    # CourierNameAlias (alternativas de nome para o mesmo courier_id)
    for a in CourierNameAlias.objects.select_related("partner"):
        cid = a.courier_id
        if cid in cid_to_driver and a.courier_name:
            cname_to_driver[a.courier_name.strip().lower()] = (
                cid_to_driver[cid]
            )

    return drivers_by_id, cid_to_driver, cname_to_driver


def _compute_bonus_for_day(qty):
    """Faixas: <30→€0, 30-59→€30, 60+→€50 (em domingo ou feriado)."""
    if qty >= 60:
        return Decimal("50.00")
    if qty >= 30:
        return Decimal("30.00")
    return Decimal("0.00")


def find_drivers_without_pf(date_from, date_to, min_gap_days=MIN_GAP_DAYS,
                            include_all=False):
    """Devolve lista de motoristas com gap entre entregas e PFs no período.

    Devolve lista de dicts com `estimated_amount` agora a incluir bónus
    de domingo/feriado pelas faixas standard.
    """
    from settlements.models import (
        CainiaoOperationTask, DriverPreInvoice, Holiday,
    )
    from core.models import Partner
    from core.finance import resolve_driver_price

    drivers_by_id, cid_to_driver, cname_to_driver = _collect_driver_courier_keys()

    # Pacotes entregues no período: agrupados por (driver_id, task_date)
    qs = CainiaoOperationTask.objects.filter(
        task_date__range=(date_from, date_to),
        task_status="Delivered",
    ).values("courier_id_cainiao", "courier_name", "task_date")

    # driver_id → { task_date → count }
    driver_day_counts = defaultdict(lambda: defaultdict(int))

    for row in qs:
        cid = (row["courier_id_cainiao"] or "").strip()
        cname = (row["courier_name"] or "").strip().lower()
        d = row["task_date"]

        # Resolve para driver: tenta primeiro courier_id, depois courier_name
        driver = None
        if cid and cid in cid_to_driver:
            driver = cid_to_driver[cid]
        elif cname and cname in cname_to_driver:
            driver = cname_to_driver[cname]
        if driver is None:
            continue
        driver_day_counts[driver.id][d] += 1

    # PFs que sobrepõem o período por driver
    pfs_qs = DriverPreInvoice.objects.filter(
        periodo_inicio__lte=date_to,
        periodo_fim__gte=date_from,
    ).order_by("driver_id", "-periodo_fim")
    pfs_by_driver = defaultdict(list)
    for pf in pfs_qs:
        pfs_by_driver[pf.driver_id].append(pf)

    # Holidays cache no período
    holidays = set(
        Holiday.objects.filter(date__range=(date_from, date_to))
        .values_list("date", flat=True)
    )

    cainiao = Partner.objects.filter(name__iexact="CAINIAO").first()

    results = []
    for driver_id, day_counts in driver_day_counts.items():
        if not day_counts:
            continue
        driver = drivers_by_id.get(driver_id)
        if not driver:
            continue

        active_dates = set(day_counts.keys())
        delivered_total = sum(day_counts.values())

        # Dias cobertos por PFs no período
        covered_dates = set()
        for pf in pfs_by_driver.get(driver_id, []):
            cur = max(pf.periodo_inicio, date_from)
            end = min(pf.periodo_fim, date_to)
            while cur <= end:
                covered_dates.add(cur)
                cur += timedelta(days=1)

        active_days = len(active_dates)
        covered_days = len(active_dates & covered_dates)
        gap_days = active_days - covered_days

        if not include_all and gap_days < min_gap_days:
            continue

        uncovered = sorted(active_dates - covered_dates)
        first_uncovered = uncovered[0] if uncovered else None
        last_uncovered = uncovered[-1] if uncovered else None

        # Pricing base
        price_per_pkg, _src = resolve_driver_price(driver, cainiao)
        base_amount = (price_per_pkg or Decimal("0")) * delivered_total

        # Bónus por domingo/feriado (cumulativo por dia eligível)
        bonus_amount = Decimal("0")
        bonus_days_count = 0
        for d, qty in day_counts.items():
            is_sunday = d.weekday() == 6
            is_holiday = d in holidays
            if not (is_sunday or is_holiday):
                continue
            day_bonus = _compute_bonus_for_day(qty)
            if day_bonus > 0:
                bonus_amount += day_bonus
                bonus_days_count += 1

        estimated = base_amount + bonus_amount

        # Última PF (qualquer)
        last_pf_info = None
        if pfs_by_driver.get(driver_id):
            lpf = pfs_by_driver[driver_id][0]
            last_pf_info = {
                "numero": lpf.numero,
                "periodo_fim": lpf.periodo_fim.isoformat(),
                "status": lpf.status,
                "status_display": lpf.get_status_display(),
            }
        else:
            any_pf = (
                DriverPreInvoice.objects.filter(driver=driver)
                .order_by("-periodo_fim").first()
            )
            if any_pf:
                last_pf_info = {
                    "numero": any_pf.numero,
                    "periodo_fim": any_pf.periodo_fim.isoformat(),
                    "status": any_pf.status,
                    "status_display": any_pf.get_status_display(),
                }

        results.append({
            "driver_id": driver_id,
            "driver_nome": driver.nome_completo,
            "driver_apelido": driver.apelido or "",
            "courier_id_cainiao": driver.courier_id_cainiao or "",
            "delivered_count": delivered_total,
            "active_days": active_days,
            "covered_days": covered_days,
            "gap_days": gap_days,
            "first_uncovered_date": first_uncovered,
            "last_uncovered_date": last_uncovered,
            "estimated_amount": estimated,
            "estimated_base": base_amount,
            "estimated_bonus": bonus_amount,
            "bonus_days_count": bonus_days_count,
            "last_pf": last_pf_info,
        })

    results.sort(key=lambda r: (-r["gap_days"], -r["delivered_count"]))
    return results
