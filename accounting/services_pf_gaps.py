"""Detector de motoristas com entregas mas sem pré-fatura no período.

Cruza `CainiaoOperationTask` (entregas) com `DriverPreInvoice` (PFs)
para encontrar motoristas que entregaram pacotes mas não têm PF que
cubra esse intervalo. Garante que ninguém fica sem ser pago.

Critério "pragmático" (default):
    - Motorista com ≥1 pacote `Delivered` no período
    - Soma de dias COM PF (que sobreponha o período) é < total de dias
      com entregas, com gap ≥ MIN_GAP_DAYS
"""
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Q

MIN_GAP_DAYS = 7  # Só reporta motoristas com gap >= 7 dias


def find_drivers_without_pf(date_from, date_to, min_gap_days=MIN_GAP_DAYS,
                            include_all=False):
    """Devolve lista de motoristas com gap entre entregas e PFs no período.

    Args:
        date_from, date_to: limites do período (inclusive)
        min_gap_days: número mínimo de dias sem cobertura para reportar
        include_all: se True, mostra todos os motoristas com entregas
                     (mesmo que tenham PF), útil para auditoria total

    Devolve lista de dicts:
        {
            "driver_id", "driver_nome", "driver_apelido",
            "courier_id_cainiao",
            "delivered_count": int (pacotes no período),
            "active_days": int (dias com pelo menos 1 entrega),
            "covered_days": int (dias cobertos por alguma PF),
            "gap_days": int (active_days - covered_days),
            "first_uncovered_date", "last_uncovered_date",
            "estimated_amount": Decimal,
            "last_pf": {numero, periodo_fim, status} | None,
        }
    """
    from settlements.models import (
        CainiaoOperationTask, DriverPreInvoice,
    )
    from drivers_app.models import DriverProfile
    from core.models import Partner
    from core.finance import resolve_driver_price, resolve_partner_price

    # 1. Pacotes entregues por driver no período (via courier_name → DriverProfile)
    # Para correctude máxima, replica a lógica de _kpi_for_period:
    #   driver_q = (courier_id_cainiao IN ids) | (courier_name IN names)
    # Mas para escala, simplificamos: courier_name === driver.apelido OU
    # courier_id_cainiao === driver.courier_id_cainiao
    qs = CainiaoOperationTask.objects.filter(
        task_date__range=(date_from, date_to),
        task_status="Delivered",
    )
    # Agrega por (courier_id, courier_name) e depois resolve para drivers
    by_courier_id = defaultdict(set)  # courier_id → set(task_dates)
    by_courier_name = defaultdict(set)
    counts_id = defaultdict(int)
    counts_name = defaultdict(int)
    for row in qs.values("courier_id_cainiao", "courier_name", "task_date"):
        cid = row["courier_id_cainiao"] or ""
        cname = row["courier_name"] or ""
        d = row["task_date"]
        if cid:
            by_courier_id[cid].add(d)
            counts_id[cid] += 1
        if cname:
            by_courier_name[cname].add(d)
            counts_name[cname] += 1

    # 2. Resolve drivers (one driver pode ter múltiplos courier_ids/names)
    drivers_by_id = {
        d.id: d for d in DriverProfile.objects.exclude(status="IRREGULAR")
    }
    driver_active_days = defaultdict(set)  # driver_id → set(dates)
    driver_delivered = defaultdict(int)

    for d in drivers_by_id.values():
        if d.courier_id_cainiao and d.courier_id_cainiao in by_courier_id:
            driver_active_days[d.id] |= by_courier_id[d.courier_id_cainiao]
            driver_delivered[d.id] += counts_id[d.courier_id_cainiao]
        if d.apelido and d.apelido in by_courier_name:
            driver_active_days[d.id] |= by_courier_name[d.apelido]
            # Não somamos counts_name para evitar dupla contagem se cid == nome
            # (o set de datas já é deduplicado)

    # Recalcular delivered baseado no set único de dates × counts
    # (simplificação: usar count via task_date in set)
    # Por agora, usamos a contagem cumulativa simples:
    for did in list(driver_delivered.keys()):
        driver_delivered[did] = sum(
            counts_id.get(d.courier_id_cainiao, 0)
            for d in [drivers_by_id[did]] if d.courier_id_cainiao
        ) or sum(
            counts_name.get(d.apelido, 0)
            for d in [drivers_by_id[did]] if d.apelido
        )

    # 3. PFs que sobrepõem o período por driver
    pfs_qs = DriverPreInvoice.objects.filter(
        periodo_inicio__lte=date_to,
        periodo_fim__gte=date_from,
    ).order_by("driver_id", "-periodo_fim")
    pfs_by_driver = defaultdict(list)
    for pf in pfs_qs:
        pfs_by_driver[pf.driver_id].append(pf)

    # 4. Pricing
    cainiao = Partner.objects.filter(name__iexact="CAINIAO").first()

    # 5. Construir resultado
    results = []
    for driver_id, active_dates in driver_active_days.items():
        if not active_dates:
            continue
        driver = drivers_by_id.get(driver_id)
        if not driver:
            continue

        # Calcula dias cobertos por PFs no período
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

        delivered = driver_delivered.get(driver_id, 0)

        # Preço estimado (cascata)
        price_per_pkg, _src = resolve_driver_price(driver, cainiao)
        estimated = (price_per_pkg or Decimal("0")) * delivered

        # Última PF
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
            # Procura última PF de qualquer período
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
            "delivered_count": delivered,
            "active_days": active_days,
            "covered_days": covered_days,
            "gap_days": gap_days,
            "first_uncovered_date": first_uncovered,
            "last_uncovered_date": last_uncovered,
            "estimated_amount": estimated,
            "last_pf": last_pf_info,
        })

    # Ordena: maior gap primeiro, depois mais entregas
    results.sort(key=lambda r: (-r["gap_days"], -r["delivered_count"]))
    return results
