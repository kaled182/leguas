"""Detector de motoristas com entregas mas sem pré-fatura no período.

Cruza `CainiaoOperationTask` (entregas) com `DriverPreInvoice` (PFs) para
encontrar motoristas que entregaram pacotes mas não têm PF que cubra esse
intervalo. Garante que ninguém fica sem ser pago.

──────────────────────────────────────────────────────────────────────
COMPOSIÇÃO DE UMA PF REAL (espelhada aqui o mais fielmente possível)
──────────────────────────────────────────────────────────────────────
Para cada driver, no período:

  1. Lista de LOGINS  = courier_id_cainiao/apelido do perfil  +
                        DriverCourierMapping (todos os couriers extra)
                        + (opcional) "↻ Transferências recebidas"
                        (waybills que o WaybillAttributionOverride
                         atribuiu a este driver vindos de outros logins).

  2. Para CADA login, query independente em CainiaoOperationTask:
        - filtrada por courier_id OU courier_name desse login
        - status == 'Delivered'
        - exclui waybills com WaybillAttributionOverride saindo
          (ie, atribuídos a outro driver)
        - exclui task_ids já vistos noutros logins (deduplicação)

  3. PRICING por waybill:
        - base = resolve_driver_price(driver, partner_cainiao)
        - se waybill ∈ PackagePriceOverride → preço especial (€1.30, …)
        - base_amount = Σ (preço aplicável de cada waybill)

  4. BÓNUS por login por dia (tier independente):
        - dia ∈ Holidays  OU  weekday == 6 (domingo)
        - n entregas no dia desse login >= 30  → €30
        - n entregas no dia desse login >= 60  → €50
        - regra crítica: cada LOGIN avalia o seu tier separadamente.
          Se o driver teve 35 pacotes em "Otavio_LF" e 30 em
          "Gabrielle_LF" no mesmo domingo, recebe €30 + €30 (não €50).

  5. Não modelados (delta vs PF real será residual):
        - ajuste_manual / penalizacoes_gerais (manuais)
        - pacotes perdidos (claims)
        - adiantamentos
        - comissões de indicação (DriverReferral)
        - DSR (na prática raramente usada nas PFs Cainiao)

──────────────────────────────────────────────────────────────────────
"""
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

MIN_GAP_DAYS = 7  # Só reporta motoristas com gap >= 7 dias

# Tiers oficiais do PreInvoiceBonus
LIMIAR_30 = 30
LIMIAR_60 = 60
BONUS_30 = Decimal("30.00")
BONUS_50 = Decimal("50.00")


def _collect_driver_logins(exclude_fleet=True):
    """Retorna driver_logins: dict driver_id → list[(cid, cname)].

    Inclui o login do perfil (courier_id_cainiao + apelido) e todos os
    DriverCourierMapping. Pares (cid, cname) duplicados são removidos.

    Se `exclude_fleet=True` (default), motoristas vinculados a uma
    `EmpresaParceira` são excluídos — a sua PF é gerada via lote da
    frota (FleetInvoice), não como pré-fatura individual.
    """
    from drivers_app.models import DriverProfile
    from settlements.models import DriverCourierMapping

    drivers = DriverProfile.objects.exclude(status="IRREGULAR")
    if exclude_fleet:
        drivers = drivers.filter(empresa_parceira__isnull=True)
    drivers_by_id = {d.id: d for d in drivers}

    driver_logins = defaultdict(list)
    seen_pair_per_driver = defaultdict(set)

    def _add(driver_id, cid, cname):
        cid = (cid or "").strip()
        cname = (cname or "").strip()
        if not cid and not cname:
            return
        key = (cid, cname.lower())
        if key in seen_pair_per_driver[driver_id]:
            return
        seen_pair_per_driver[driver_id].add(key)
        driver_logins[driver_id].append((cid, cname))

    # 1) Login do perfil
    for d in drivers:
        _add(d.id, d.courier_id_cainiao or "", d.apelido or "")

    # 2) Mappings extra (TODOS os couriers do mesmo driver)
    for m in DriverCourierMapping.objects.select_related("driver"):
        if not m.driver_id or m.driver_id not in drivers_by_id:
            continue
        _add(m.driver_id, m.courier_id or "", m.courier_name or "")

    return drivers_by_id, driver_logins


def _bonus_for_login_day(qty):
    if qty >= LIMIAR_60:
        return BONUS_50
    if qty >= LIMIAR_30:
        return BONUS_30
    return Decimal("0.00")


def _is_bonus_day(d, holidays_set, region=None):
    """Domingo OU feriado (incluindo recorrentes anuais via Holiday)."""
    if d.weekday() == 6:
        return True
    if d in holidays_set:
        return True
    # Holidays recorrentes anuais: usa Holiday.is_holiday se necessário.
    # holidays_set já inclui recorrências expandidas (ver caller).
    return False


def _expand_holidays(date_from, date_to):
    """Devolve set de datas que são feriado no período, incluindo
    feriados recorrentes anuais (ex: 25/12 todos os anos).
    """
    from settlements.models import Holiday

    holidays = set()
    # Datas explícitas dentro do range
    holidays.update(
        Holiday.objects.filter(
            date__range=(date_from, date_to), region="",
        ).values_list("date", flat=True)
    )
    # Recorrentes anuais: expandir para datas dentro do range
    cur = date_from
    while cur <= date_to:
        if Holiday.objects.filter(
            is_recurring_yearly=True,
            date__day=cur.day,
            date__month=cur.month,
            region="",
        ).exists():
            holidays.add(cur)
        cur += timedelta(days=1)
    return holidays


def find_drivers_without_pf(date_from, date_to, min_gap_days=MIN_GAP_DAYS,
                            include_all=False):
    """Devolve lista de motoristas com gap entre entregas e PFs no período.

    Mirror da lógica em settlements.views.driver_pre_invoice_create:
      - Pricing por waybill (PackagePriceOverride respeitada)
      - Outgoing transfers excluídas
      - Bónus PER LOGIN PER DIA (tier independente)
      - Transferências recebidas como pseudo-login com bónus próprio
    """
    from settlements.models import (
        CainiaoOperationTask, DriverPreInvoice,
        WaybillAttributionOverride, PackagePriceOverride,
    )
    from core.models import Partner
    from core.finance import resolve_driver_price
    from django.db.models import Q

    drivers_by_id, driver_logins = _collect_driver_logins()
    cainiao = Partner.objects.filter(name__iexact="CAINIAO").first()
    holidays_set = _expand_holidays(date_from, date_to)

    # Outgoing transfers no período (sair do driver "natural" do waybill)
    # → mapear waybill → driver_id ATRIBUÍDO (incoming) e
    #   waybill → set de drivers que perderam a atribuição (outgoing).
    incoming_by_driver = defaultdict(set)  # driver_id → {waybill, ...}
    outgoing_waybills = set()  # qualquer override remove o waybill
    for ov in WaybillAttributionOverride.objects.filter(
        task_date__range=(date_from, date_to),
    ).values("waybill_number", "attributed_to_driver_id"):
        wb = ov["waybill_number"]
        outgoing_waybills.add(wb)
        if ov["attributed_to_driver_id"]:
            incoming_by_driver[ov["attributed_to_driver_id"]].add(wb)

    # Cache de price overrides
    price_overrides_map = {
        po.waybill_number: po
        for po in PackagePriceOverride.objects.filter(
            task_date__range=(date_from, date_to),
        )
    }

    # PFs que sobrepõem o período por driver
    pfs_qs = DriverPreInvoice.objects.filter(
        periodo_inicio__lte=date_to,
        periodo_fim__gte=date_from,
    ).order_by("driver_id", "-periodo_fim")
    pfs_by_driver = defaultdict(list)
    for pf in pfs_qs:
        pfs_by_driver[pf.driver_id].append(pf)

    # ── Iterar drivers e calcular ────────────────────────────────────
    results = []
    for driver_id, logins in driver_logins.items():
        driver = drivers_by_id.get(driver_id)
        if not driver:
            continue

        # Preço base do driver (cascata: override → frota → parceiro)
        base_price, _src = resolve_driver_price(driver, cainiao)
        base_price = base_price or Decimal("0")

        # Acumuladores
        delivered_total = 0
        active_dates = set()  # dias com qq entrega (qualquer login)
        base_amount = Decimal("0")
        bonus_amount = Decimal("0")
        bonus_days_count = 0
        seen_task_ids = set()

        # Helper que processa um conjunto de tasks (rows) como um
        # "login" — agrega base + bónus por dia desse login isolado.
        def _process_login(rows):
            nonlocal delivered_total, base_amount
            nonlocal bonus_amount, bonus_days_count
            if not rows:
                return
            # base por waybill (com override de preço)
            day_count = defaultdict(int)
            for r in rows:
                wb = r["waybill_number"]
                d = r["task_date"]
                po = price_overrides_map.get(wb)
                unit = po.price if po else base_price
                base_amount += unit
                day_count[d] += 1
                delivered_total += 1
                active_dates.add(d)
            # bónus deste login por dia (tier independente)
            for d, n in day_count.items():
                if not _is_bonus_day(d, holidays_set):
                    continue
                b = _bonus_for_login_day(n)
                if b > 0:
                    bonus_amount += b
                    bonus_days_count += 1

        # 1) Cada login do driver, isolado, com dedupe global de task_ids
        for cid, cname in logins:
            login_q = Q()
            if cid:
                login_q |= Q(courier_id_cainiao=cid)
            if cname:
                login_q |= Q(courier_name=cname)
            if not login_q:
                continue
            qs = CainiaoOperationTask.objects.filter(
                task_date__range=(date_from, date_to),
                task_status="Delivered",
            ).filter(login_q)
            if outgoing_waybills:
                qs = qs.exclude(waybill_number__in=outgoing_waybills)
            if seen_task_ids:
                qs = qs.exclude(id__in=seen_task_ids)
            rows = list(qs.values("id", "waybill_number", "task_date"))
            if not rows:
                continue
            seen_task_ids.update(r["id"] for r in rows)
            _process_login(rows)

        # 2) Transferências recebidas — pseudo-login extra com bónus próprio
        wbs_in = incoming_by_driver.get(driver_id, set())
        if wbs_in:
            qs_inc = CainiaoOperationTask.objects.filter(
                task_date__range=(date_from, date_to),
                task_status="Delivered",
                waybill_number__in=wbs_in,
            )
            if seen_task_ids:
                qs_inc = qs_inc.exclude(id__in=seen_task_ids)
            rows_inc = list(qs_inc.values(
                "id", "waybill_number", "task_date",
            ))
            if rows_inc:
                seen_task_ids.update(r["id"] for r in rows_inc)
                _process_login(rows_inc)

        # 3) Caso o driver não tenha entregas, ignorar
        if delivered_total == 0:
            continue

        # 4) Cobertura por PFs existentes
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

        estimated = base_amount + bonus_amount
        # IVA estimado se driver é regime Normal
        vat_regime = (
            getattr(driver, "vat_regime", "isento") or "isento"
        )
        if vat_regime == "normal":
            estimated_vat = (estimated * Decimal("0.23")).quantize(
                Decimal("0.01"),
            )
        else:
            estimated_vat = Decimal("0.00")
        estimated_total = estimated + estimated_vat

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
            "estimated_vat": estimated_vat,
            "estimated_total_com_iva": estimated_total,
            "vat_regime": vat_regime,
            "bonus_days_count": bonus_days_count,
            "logins_count": len(logins) + (1 if wbs_in else 0),
            "last_pf": last_pf_info,
        })

    results.sort(key=lambda r: (-r["gap_days"], -r["delivered_count"]))
    return results


# ─────────────────────────────────────────────────────────────────────
# Detector análogo para FROTAS (EmpresaParceira)
# ─────────────────────────────────────────────────────────────────────

def find_fleets_without_invoice(date_from, date_to,
                                min_gap_days=MIN_GAP_DAYS,
                                include_all=False):
    """Devolve lista de frotas com entregas no período sem FleetInvoice
    a cobrir todos os dias activos.

    Espelha a lógica em settlements.views.empresa_lote_emit:
      - Itera DriverProfile.filter(empresa_parceira=empresa, is_active=True)
      - Cada driver: bónus per-login per-day (tier independente)
      - Não modela claims/penalizações (residual aceitável)
      - Cobertura por FleetInvoice no período
    """
    from settlements.models import (
        CainiaoOperationTask, FleetInvoice, Holiday,
    )
    from drivers_app.models import EmpresaParceira, DriverProfile
    from core.models import Partner
    from core.finance import resolve_driver_price
    from django.db.models import Q

    cainiao = Partner.objects.filter(name__iexact="CAINIAO").first()
    holidays_set = _expand_holidays(date_from, date_to)

    # Empresas activas
    empresas = list(EmpresaParceira.objects.filter(ativo=True))
    if not empresas:
        return []

    # FleetInvoices que sobrepõem o período por empresa
    ffs_qs = FleetInvoice.objects.filter(
        periodo_inicio__lte=date_to,
        periodo_fim__gte=date_from,
    ).exclude(status="CANCELADO").order_by("empresa_id", "-periodo_fim")
    ffs_by_empresa = defaultdict(list)
    for ff in ffs_qs:
        ffs_by_empresa[ff.empresa_id].append(ff)

    results = []
    for empresa in empresas:
        # Drivers activos da frota
        drivers = list(
            DriverProfile.objects.filter(
                empresa_parceira=empresa, is_active=True,
            )
        )
        if not drivers:
            continue

        active_dates = set()
        delivered_total = 0
        base_amount = Decimal("0")
        bonus_amount = Decimal("0")
        bonus_days_count = 0
        drivers_with_deliveries = 0

        for d in drivers:
            # Logins deste driver
            logins = []
            seen_pairs = set()

            def _add(cid, cname):
                cid = (cid or "").strip()
                cname = (cname or "").strip()
                if not cid and not cname:
                    return
                key = (cid, cname.lower())
                if key in seen_pairs:
                    return
                seen_pairs.add(key)
                logins.append((cid, cname))

            _add(d.courier_id_cainiao or "", d.apelido or "")
            for m in d.courier_mappings.filter(partner=cainiao):
                _add(m.courier_id or "", m.courier_name or "")
            if not logins:
                continue

            base_price, _src = resolve_driver_price(d, cainiao)
            base_price = base_price or Decimal("0")

            seen_task_ids = set()
            d_delivered = 0
            d_active_dates = set()

            for cid, cname in logins:
                login_q = Q()
                if cid:
                    login_q |= Q(courier_id_cainiao=cid)
                if cname:
                    login_q |= Q(courier_name=cname)
                if not login_q:
                    continue
                qs = CainiaoOperationTask.objects.filter(
                    task_date__range=(date_from, date_to),
                    task_status="Delivered",
                ).filter(login_q)
                if seen_task_ids:
                    qs = qs.exclude(id__in=seen_task_ids)
                rows = list(qs.values("id", "task_date"))
                if not rows:
                    continue
                seen_task_ids.update(r["id"] for r in rows)

                # Base: aqui não modelamos PackagePriceOverride (a
                # FleetInvoice usa price uniforme do driver — ver
                # empresa_lote_emit linha 4570: base = price * n)
                day_count = defaultdict(int)
                for r in rows:
                    base_amount += base_price
                    day_count[r["task_date"]] += 1
                    d_delivered += 1
                    d_active_dates.add(r["task_date"])

                # Bónus per login per day
                for day, n in day_count.items():
                    if not _is_bonus_day(day, holidays_set):
                        continue
                    b = _bonus_for_login_day(n)
                    if b > 0:
                        bonus_amount += b
                        bonus_days_count += 1

            if d_delivered > 0:
                drivers_with_deliveries += 1
                delivered_total += d_delivered
                active_dates.update(d_active_dates)

        if delivered_total == 0:
            continue

        # IVA da frota — taxa_iva guardada na EmpresaParceira
        vat_rate = (
            getattr(empresa, "taxa_iva", Decimal("23.00")) or Decimal("0")
        )

        # Cobertura por FleetInvoices existentes
        covered_dates = set()
        for ff in ffs_by_empresa.get(empresa.id, []):
            cur = max(ff.periodo_inicio, date_from)
            end = min(ff.periodo_fim, date_to)
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

        estimated = base_amount + bonus_amount
        # IVA estimado (frota = sempre cobra IVA)
        if vat_rate:
            estimated_vat = (
                estimated * vat_rate / Decimal("100")
            ).quantize(Decimal("0.01"))
        else:
            estimated_vat = Decimal("0.00")
        estimated_total_com_iva = estimated + estimated_vat

        # Última FleetInvoice (qualquer)
        last_ff_info = None
        if ffs_by_empresa.get(empresa.id):
            lff = ffs_by_empresa[empresa.id][0]
            last_ff_info = {
                "numero": lff.numero,
                "periodo_fim": lff.periodo_fim.isoformat(),
                "status": lff.status,
                "status_display": lff.get_status_display(),
            }
        else:
            any_ff = (
                FleetInvoice.objects.filter(empresa=empresa)
                .exclude(status="CANCELADO")
                .order_by("-periodo_fim").first()
            )
            if any_ff:
                last_ff_info = {
                    "numero": any_ff.numero,
                    "periodo_fim": any_ff.periodo_fim.isoformat(),
                    "status": any_ff.status,
                    "status_display": any_ff.get_status_display(),
                }

        results.append({
            "empresa_id": empresa.id,
            "empresa_nome": empresa.nome,
            "n_drivers": len(drivers),
            "n_drivers_with_deliveries": drivers_with_deliveries,
            "delivered_count": delivered_total,
            "active_days": active_days,
            "covered_days": covered_days,
            "gap_days": gap_days,
            "first_uncovered_date": first_uncovered,
            "last_uncovered_date": last_uncovered,
            "estimated_amount": estimated,
            "estimated_base": base_amount,
            "estimated_bonus": bonus_amount,
            "estimated_vat": estimated_vat,
            "estimated_total_com_iva": estimated_total_com_iva,
            "vat_rate": vat_rate,
            "bonus_days_count": bonus_days_count,
            "last_ff": last_ff_info,
        })

    results.sort(key=lambda r: (-r["gap_days"], -r["delivered_count"]))
    return results
