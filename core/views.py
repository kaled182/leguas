from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import PartnerForm, PartnerIntegrationForm
from .models import Partner, PartnerIntegration


@login_required
def partner_list(request):
    """Lista de parceiros com filtros e paginação"""
    partners_qs = Partner.objects.all()

    # Filtros
    search = request.GET.get("search", "")
    status_filter = request.GET.get("status", "")

    if search:
        partners_qs = partners_qs.filter(
            Q(name__icontains=search)
            | Q(nif__icontains=search)
            | Q(contact_email__icontains=search)
        )

    if status_filter == "active":
        partners_qs = partners_qs.filter(is_active=True)
    elif status_filter == "inactive":
        partners_qs = partners_qs.filter(is_active=False)

    # Anotar com contagens
    partners_qs = partners_qs.annotate(
        integrations_count=Count("integrations"),
        active_integrations_count=Count(
            "integrations", filter=Q(integrations__is_active=True)
        ),
    )

    # Ordenação
    partners_qs = partners_qs.order_by("-is_active", "name")

    # Paginação
    paginator = Paginator(partners_qs, 25)
    page = request.GET.get("page", 1)

    try:
        partners = paginator.page(page)
    except PageNotAnInteger:
        partners = paginator.page(1)
    except EmptyPage:
        partners = paginator.page(paginator.num_pages)

    context = {
        "partners": partners,
        "search": search,
        "status_filter": status_filter,
        "total_count": partners_qs.count(),
    }

    return render(request, "core/partner_list.html", context)


@login_required
def partner_detail(request, pk):
    """Detalhes de um parceiro"""
    partner = get_object_or_404(Partner, pk=pk)

    # Integrações do parceiro
    integrations = partner.integrations.all().order_by(
        "-is_active", "-last_sync_at"
    )
    active_integrations_count = integrations.filter(is_active=True).count()

    # Estatísticas (se o model Order existir e tiver FK para Partner)
    try:
        orders_stats = {
            "total": partner.orders.count(),
            "pending": partner.orders.filter(current_status="PENDING").count(),
            "in_progress": partner.orders.filter(
                current_status__in=["PICKED_UP", "IN_TRANSIT"]
            ).count(),
            "delivered": partner.orders.filter(
                current_status="DELIVERED"
            ).count(),
            "failed": partner.orders.filter(current_status="FAILED").count(),
        }
    except BaseException:
        orders_stats = None

    # Cainiao statistics (only for the CAINIAO partner)
    cainiao_data = None
    if partner.name.upper() == "CAINIAO":
        try:
            from datetime import date as date_cls, timedelta
            from django.db.models import Count, Q as _Q
            from django.db.models.functions import Substr
            from settlements.models import (
                CainiaoOperationTask, CainiaoOperationBatch,
                CainiaoHub,
            )

            T = CainiaoOperationTask

            today = date_cls.today()
            # Support range (date_from / date_to) or legacy single op_date
            op_date_str   = request.GET.get("op_date", "")
            date_from_str = request.GET.get("date_from", op_date_str)
            date_to_str   = request.GET.get("date_to",   op_date_str)
            try:
                date_from = date_cls.fromisoformat(date_from_str)
            except (ValueError, TypeError):
                date_from = today
            try:
                date_to = date_cls.fromisoformat(date_to_str)
            except (ValueError, TypeError):
                date_to = today
            if date_from > date_to:
                date_from, date_to = date_to, date_from
            selected_date = date_to  # kept for backward-compat labels

            # HUBs
            all_hubs = list(CainiaoHub.objects.prefetch_related("cp4_codes").order_by("name"))
            selected_hub_id = request.GET.get("hub_id", "")
            selected_hub = None
            if selected_hub_id:
                try:
                    selected_hub = next(h for h in all_hubs if h.id == int(selected_hub_id))
                except (StopIteration, ValueError):
                    pass

            STATUS_DELIVERED  = "Delivered"
            STATUS_EN_ROUTE   = "Driver_received"
            STATUS_FAILURE    = "Attempt Failure"
            STATUS_UNASSIGN   = "Unassign"
            STATUS_ASSIGNED   = "Assigned"
            VALID_STATUSES    = [STATUS_DELIVERED, STATUS_EN_ROUTE, STATUS_FAILURE, STATUS_UNASSIGN, STATUS_ASSIGNED]

            # Apenas status operacionais válidos — Cancel, etc. são ignorados
            tasks = T.objects.filter(task_date__range=(date_from, date_to), task_status__in=VALID_STATUSES)

            # Filter by HUB CP4 codes when a hub is selected
            cp4_list = []
            hub_q = _Q()
            cp4_filter_q = _Q()  # Q vazio se nenhum CP4 seleccionado
            fleet_courier_names = set()
            fleet_courier_ids = set()
            fleet_q = _Q()
            drv_courier_names = set()
            drv_courier_ids = set()
            drv_q = _Q()
            if selected_hub:
                cp4_list = list(selected_hub.cp4_codes.values_list("cp4", flat=True))
                if cp4_list:
                    for cp4 in cp4_list:
                        hub_q |= _Q(zip_code__startswith=cp4)
                    tasks = tasks.filter(hub_q)

            # CP4s disponíveis na data/hub actual (para o filtro multi-select)
            available_cp4s = sorted(
                tasks.exclude(zip_code="")
                .annotate(cp4=Substr("zip_code", 1, 4))
                .values_list("cp4", flat=True)
                .distinct()
            )

            # CP4 filter — multi-select via GET param ?cp4=XXXX&cp4=YYYY
            selected_cp4s = [c for c in request.GET.getlist("cp4") if c in available_cp4s]
            if selected_cp4s:
                cp4_filter_q = _Q()
                for cp4 in selected_cp4s:
                    cp4_filter_q |= _Q(zip_code__startswith=cp4)
                tasks = tasks.filter(cp4_filter_q)

            # Fleet filter — applied BEFORE all aggregations so that cards,
            # CP4 breakdown and driver breakdown all reflect the selected fleet.
            from drivers_app.models import DriverProfile, EmpresaParceira
            from settlements.models import DriverCourierMapping
            selected_fleet_id = request.GET.get("fleet_id", "")
            view_mode = request.GET.get("driver_view", "driver")  # driver|fleet

            if selected_fleet_id:
                try:
                    fleet_id_int = int(selected_fleet_id)
                    fleet_courier_names = set()  # apelido + mapping.courier_name
                    fleet_courier_ids = set()    # courier_id (Login ID) estável
                    fleet_drivers = DriverProfile.objects.filter(
                        empresa_parceira_id=fleet_id_int
                    )
                    for d in fleet_drivers:
                        if d.apelido:
                            fleet_courier_names.add(d.apelido)
                        if d.courier_id_cainiao:
                            fleet_courier_ids.add(d.courier_id_cainiao)
                    # Mappings cujo driver está na frota
                    for m in DriverCourierMapping.objects.filter(
                        partner=partner, driver__empresa_parceira_id=fleet_id_int,
                    ):
                        if m.courier_name:
                            fleet_courier_names.add(m.courier_name)
                        if m.courier_id:
                            fleet_courier_ids.add(m.courier_id)
                    if fleet_courier_names or fleet_courier_ids:
                        fleet_q = _Q()
                        if fleet_courier_ids:
                            fleet_q |= _Q(courier_id_cainiao__in=fleet_courier_ids)
                        if fleet_courier_names:
                            fleet_q |= _Q(courier_name__in=fleet_courier_names)
                        tasks = tasks.filter(fleet_q)
                    else:
                        tasks = tasks.none()
                except ValueError:
                    pass

            # Driver filter — courier_name (alias) ou courier_id_cainiao via
            # DriverProfile + mappings. Aplica antes das agregações.
            selected_driver_id = request.GET.get("driver_id", "")
            selected_courier_name = request.GET.get("courier", "")
            selected_driver = None
            if selected_driver_id:
                try:
                    selected_driver = DriverProfile.objects.filter(
                        id=int(selected_driver_id),
                    ).select_related("empresa_parceira").first()
                except ValueError:
                    selected_driver = None
                if selected_driver:
                    drv_courier_names = set()
                    drv_courier_ids = set()
                    if selected_driver.apelido:
                        drv_courier_names.add(selected_driver.apelido)
                    if selected_driver.courier_id_cainiao:
                        drv_courier_ids.add(
                            selected_driver.courier_id_cainiao,
                        )
                    for m in DriverCourierMapping.objects.filter(
                        partner=partner, driver=selected_driver,
                    ):
                        if m.courier_name:
                            drv_courier_names.add(m.courier_name)
                        if m.courier_id:
                            drv_courier_ids.add(m.courier_id)
                    if drv_courier_names or drv_courier_ids:
                        drv_q = _Q()
                        if drv_courier_ids:
                            drv_q |= _Q(
                                courier_id_cainiao__in=drv_courier_ids,
                            )
                        if drv_courier_names:
                            drv_q |= _Q(courier_name__in=drv_courier_names)
                        tasks = tasks.filter(drv_q)
                    else:
                        tasks = tasks.none()
            elif selected_courier_name:
                # Fallback: filtro só por courier_name (driver sem perfil)
                tasks = tasks.filter(courier_name=selected_courier_name)

            # Helper: reaplica todos os filtros não-data ao queryset.
            # Usado pelo histórico de 7 dias para respeitar HUB/CP4/Frota/Driver.
            def _apply_filters(qs):
                if selected_hub and cp4_list:
                    qs = qs.filter(hub_q)
                if selected_cp4s:
                    qs = qs.filter(cp4_filter_q)
                if selected_fleet_id:
                    if fleet_courier_names or fleet_courier_ids:
                        qs = qs.filter(fleet_q)
                    else:
                        qs = qs.none()
                if selected_driver_id and selected_driver:
                    if drv_courier_names or drv_courier_ids:
                        qs = qs.filter(drv_q)
                    else:
                        qs = qs.none()
                elif selected_courier_name and not selected_driver_id:
                    qs = qs.filter(courier_name=selected_courier_name)
                return qs

            # Pacotes com WaybillReturn fechada (RETURNED ou CLOSED) já têm
            # desfecho conhecido e não devem ser contados como pendentes.
            from settlements.models import WaybillReturn as _WR
            _returned_wbs = set(
                _WR.objects.filter(
                    return_status__in=(_WR.STATUS_RETURNED, _WR.STATUS_CLOSED),
                ).values_list("waybill_number", flat=True)
            )
            returned_count = (
                tasks.filter(waybill_number__in=_returned_wbs)
                .values("waybill_number").distinct().count()
            )
            tasks = tasks.exclude(waybill_number__in=_returned_wbs)

            # ── RESOLUÇÃO DE ESTADO ACTUAL ─────────────────────────────────
            # Cada waybill pode ter MÚLTIPLAS rows (uma por dia tocado).
            # Para evitar duplicação (mesmo pacote conta como Driver_received
            # de 27/04 + Delivered de 29/04 simultaneamente), pegamos a
            # ÚLTIMA row de cada waybill candidato. Os KPIs e breakdowns
            # passam a contar pelo estado actual real.
            _candidate_wbs = list(
                tasks.values_list("waybill_number", flat=True).distinct(),
            )
            period_objs = []
            if _candidate_wbs:
                _seen = set()
                for op in (
                    T.objects.filter(
                        waybill_number__in=_candidate_wbs,
                        task_status__in=VALID_STATUSES,
                    )
                    .order_by("waybill_number", "-task_date", "-id")
                ):
                    if op.waybill_number in _seen:
                        continue
                    _seen.add(op.waybill_number)
                    period_objs.append(op)

            total = len(period_objs)
            delivered = sum(
                1 for op in period_objs if op.task_status == STATUS_DELIVERED
            )
            en_route = sum(
                1 for op in period_objs if op.task_status == STATUS_EN_ROUTE
            )
            assigned = sum(
                1 for op in period_objs
                if op.task_status in (STATUS_ASSIGNED, STATUS_UNASSIGN)
            )
            failures = sum(
                1 for op in period_objs if op.task_status == STATUS_FAILURE
            )

            # Integer percentages (avoid locale decimal-comma in CSS)
            delivery_pct  = round(delivered / total * 100) if total else 0
            en_route_pct  = round(en_route  / total * 100) if total else 0
            assigned_pct  = round(assigned  / total * 100) if total else 0
            failure_pct   = round(failures  / total * 100) if total else 0
            # Label with 1 decimal for display only
            delivery_rate = round(delivered / total * 100, 1) if total else 0
            failure_rate  = round(failures  / total * 100, 1) if total else 0

            # CP4 breakdown — também por estado actual
            from collections import defaultdict
            _cp4_buckets = defaultdict(
                lambda: {
                    "total": 0, "delivered": 0,
                    "en_route": 0, "failures": 0,
                },
            )
            _cp4_cities = defaultdict(set)
            for op in period_objs:
                if not op.zip_code:
                    continue
                cp4 = op.zip_code[:4]
                b = _cp4_buckets[cp4]
                b["total"] += 1
                if op.task_status == STATUS_DELIVERED:
                    b["delivered"] += 1
                elif op.task_status == STATUS_EN_ROUTE:
                    b["en_route"] += 1
                elif op.task_status == STATUS_FAILURE:
                    b["failures"] += 1
                if op.destination_city:
                    _cp4_cities[cp4].add(op.destination_city)
            cp4_qs = sorted(
                ({"cp4": k, **v} for k, v in _cp4_buckets.items()),
                key=lambda r: -r["total"],
            )[:25]

            # ── Driver / Fleet breakdown ──────────────────────────────────
            # Build resolution maps. courier_name NUNCA bate com nome_completo
            # (nome_completo é nome real; courier_name é alias do parceiro).
            # Prioridade: courier_id_cainiao (estável) > courier_name (alias).
            mapping_obj_by_courier_id = {}  # current mapping (carrega courier_name atualizado)
            mapping_by_name = {}
            for m in DriverCourierMapping.objects.filter(partner=partner) \
                    .select_related("driver__empresa_parceira"):
                if m.courier_id:
                    mapping_obj_by_courier_id[m.courier_id] = m
                if m.courier_name:
                    mapping_by_name[m.courier_name] = m.driver
            profile_by_courier_id = {
                d.courier_id_cainiao: d for d in DriverProfile.objects
                .select_related("empresa_parceira").exclude(courier_id_cainiao="")
            }
            profile_by_apelido = {
                d.apelido: d for d in DriverProfile.objects
                .select_related("empresa_parceira").exclude(apelido="")
            }

            def _resolve_driver(courier_id, courier_name):
                if courier_id:
                    m = mapping_obj_by_courier_id.get(courier_id)
                    if m:
                        return m.driver
                    d = profile_by_courier_id.get(courier_id)
                    if d:
                        return d
                if courier_name:
                    return (mapping_by_name.get(courier_name)
                            or profile_by_apelido.get(courier_name))
                return None

            def _display_name(courier_id, courier_name):
                """Apelido/courier_name ATUAL via mapping (login ID estável)."""
                if courier_id:
                    m = mapping_obj_by_courier_id.get(courier_id)
                    if m and m.courier_name:
                        return m.courier_name
                    d = profile_by_courier_id.get(courier_id)
                    if d and d.apelido:
                        return d.apelido
                return courier_name

            # Driver breakdown — REGRA: só o courier ACTUAL conta.
            #
            # Cada waybill é atribuído apenas ao courier vigente na task
            # actual. A task do EPOD reflecte a ÚLTIMA actualização do
            # pacote (com courier em posse à data — o EPOD-update
            # sobrescreve a row anterior).
            #
            # Antes: o histórico de assinaturas (CainiaoOperationTask
            # History.change_type=signature) era cruzado e CADA courier
            # que tocou o pacote contava o waybill, com status do estado
            # actual. Isto inflava buckets de armazéns/transferidores
            # (ex.: ARMAZEM XPT recebia crédito de "delivered" só por
            # ter passado pelo armazém antes de ir para o driver real).
            #
            # Agora: só a task actual conta. Se XPT recebeu mas
            # Caio_Malta entregou, só Caio_Malta aparece na agregação.
            # As signatures continuam guardadas em
            # CainiaoOperationTaskHistory para drill-down de auditoria.
            _drv_buckets = defaultdict(
                lambda: {
                    "courier_name": "", "courier_id_cainiao": "",
                    "total": 0, "delivered": 0,
                    "en_route": 0, "failures": 0,
                    "_seen_waybills": set(),  # dedup por (courier, waybill)
                },
            )

            def _add_to_bucket(courier_name, courier_id, waybill, status):
                if not courier_name or not waybill:
                    return
                key = (courier_id or "", courier_name)
                b = _drv_buckets[key]
                if waybill in b["_seen_waybills"]:
                    return  # já contado para este courier
                b["_seen_waybills"].add(waybill)
                b["courier_name"] = courier_name
                b["courier_id_cainiao"] = courier_id or ""
                b["total"] += 1
                if status == STATUS_DELIVERED:
                    b["delivered"] += 1
                elif status == STATUS_EN_ROUTE:
                    b["en_route"] += 1
                elif status == STATUS_FAILURE:
                    b["failures"] += 1

            # Apenas estado vigente: cada waybill conta 1× no courier
            # que está actualmente em posse (última actualização EPOD).
            for op in period_objs:
                _add_to_bucket(
                    op.courier_name, op.courier_id_cainiao,
                    op.waybill_number, op.task_status,
                )
            # Limpar set auxiliar antes de serializar
            for b in _drv_buckets.values():
                b.pop("_seen_waybills", None)
            driver_qs_raw = sorted(
                _drv_buckets.values(), key=lambda r: -r["total"],
            )

            # Mesclar rows respeitando o driver REAL.
            #
            # Bug histórico: o EPOD da Cainiao por vezes envia o
            # courier_id do hub/armazém em entregas feitas por drivers
            # reais — várias rows acabavam com courier_id partilhado
            # mas courier_name diferentes (ex: courier_id=XPT_id +
            # cname=Andre_Queiroz_LF). Mergear apenas por courier_id
            # juntava 5+ drivers reais no bucket do XPT, inflando os
            # contadores do armazém com entregas alheias.
            #
            # Regra agora: resolver o driver real PRIMEIRO. Se houver
            # driver resolvido, mergear por driver_id (junta apelidos
            # antigos+novos do mesmo driver). Senão, fallback para
            # (courier_id, courier_name) — separa rows que partilham
            # courier_id mas pertencem a couriers distintos.
            merged_by_id = {}
            for r in driver_qs_raw:
                cid = (r.get("courier_id_cainiao") or "").strip()
                cname = r["courier_name"]
                drv = _resolve_driver(cid, cname)
                if drv:
                    key = f"DRV::{drv.id}"
                elif cid:
                    key = f"CID::{cid}::{cname}"
                else:
                    key = f"NAME::{cname}"
                if key not in merged_by_id:
                    merged_by_id[key] = {
                        "courier_name": cname,
                        "courier_id_cainiao": cid,
                        "total": 0, "delivered": 0,
                        "en_route": 0, "failures": 0,
                    }
                merged_by_id[key]["total"]     += r["total"]
                merged_by_id[key]["delivered"] += r["delivered"]
                merged_by_id[key]["en_route"]  += r["en_route"]
                merged_by_id[key]["failures"]  += r["failures"]
            driver_qs_raw = sorted(
                merged_by_id.values(), key=lambda r: -r["total"]
            )

            # Enrich each row with fleet info
            driver_qs = []
            fleet_agg = {}  # fleet_id -> {name, total, delivered, en_route, failures, drivers}
            independent_agg = {
                "name": "Independentes / Não atribuídos",
                "fleet_id": None,
                "total": 0, "delivered": 0, "en_route": 0, "failures": 0,
                "drivers_count": 0,
            }
            for row in driver_qs_raw:
                cid = row.get("courier_id_cainiao", "") or ""
                cname = row["courier_name"]
                drv = _resolve_driver(cid, cname)
                fleet = drv.empresa_parceira if drv else None
                # Display: apelido/courier_name ATUAL do mapping (via Login ID)
                display = _display_name(cid, cname)
                row["fleet_id"] = fleet.id if fleet else None
                row["fleet_name"] = fleet.nome if fleet else ""
                row["driver_id"] = drv.id if drv else None
                row["driver_name"] = display
                row["courier_name"] = display  # template usa drv.courier_name
                driver_qs.append(row)

                if fleet:
                    fk = fleet.id
                    if fk not in fleet_agg:
                        fleet_agg[fk] = {
                            "fleet_id": fk,
                            "name": fleet.nome,
                            "total": 0, "delivered": 0, "en_route": 0,
                            "failures": 0, "drivers_count": 0,
                        }
                    fleet_agg[fk]["total"]     += row["total"]
                    fleet_agg[fk]["delivered"] += row["delivered"]
                    fleet_agg[fk]["en_route"]  += row["en_route"]
                    fleet_agg[fk]["failures"]  += row["failures"]
                    fleet_agg[fk]["drivers_count"] += 1
                else:
                    independent_agg["total"]     += row["total"]
                    independent_agg["delivered"] += row["delivered"]
                    independent_agg["en_route"]  += row["en_route"]
                    independent_agg["failures"]  += row["failures"]
                    independent_agg["drivers_count"] += 1

            fleet_breakdown = sorted(
                fleet_agg.values(), key=lambda f: -f["total"]
            )
            if independent_agg["total"]:
                fleet_breakdown.append(independent_agg)

            # All fleets (for the dropdown)
            all_fleets = list(
                EmpresaParceira.objects.filter(ativo=True)
                .order_by("nome")
                .values("id", "nome")
            )

            # 7-day history — respeita TODOS os filtros (HUB, CP4, Frota, Driver).
            # Pacotes devolvidos (WaybillReturn fechada) são excluídos.
            #
            # REGRA: cada waybill conta UMA VEZ no histórico — atribuído ao
            # dia da sua ÚLTIMA actividade. O estado mostrado é o estado
            # actual. Isto evita que pacotes ainda pendentes hoje (29/04)
            # apareçam também como pendentes nos dias 27/04 e 28/04 só
            # porque tiveram rows nesses dias — o que inflava as contagens
            # por contar o mesmo pacote N vezes.
            from datetime import timedelta as _td
            period_start = selected_date - _td(days=6)
            period_end = selected_date

            # 1. Todos os waybills com actividade no período (filtros aplicados)
            period_qs = T.objects.filter(
                task_date__range=(period_start, period_end),
                task_status__in=VALID_STATUSES,
            )
            period_qs = _apply_filters(period_qs)
            period_qs = period_qs.exclude(waybill_number__in=_returned_wbs)
            period_wbs = list(
                period_qs.values_list(
                    "waybill_number", flat=True,
                ).distinct(),
            )

            # 2. Para cada waybill, descobrir a última row (qualquer data)
            # — usamos isso como estado e dia de atribuição.
            latest_by_wb = {}
            if period_wbs:
                for wb, td_, status in (
                    T.objects.filter(
                        waybill_number__in=period_wbs,
                        task_status__in=VALID_STATUSES,
                    )
                    .order_by("waybill_number", "-task_date", "-id")
                    .values_list(
                        "waybill_number", "task_date", "task_status",
                    )
                ):
                    if wb not in latest_by_wb:
                        latest_by_wb[wb] = (td_, status)

            # 3. Inicializar buckets por dia
            history_buckets = {}
            for offset in range(7):
                d = selected_date - _td(days=6 - offset)
                history_buckets[d] = {
                    "total": 0, "delivered": 0,
                    "en_route": 0, "assigned": 0, "failures": 0,
                }

            # 4. Atribuir cada waybill ao dia da última actividade (clamp ao período)
            for wb, (td_, status) in latest_by_wb.items():
                target_day = td_
                if target_day < period_start:
                    target_day = period_start
                elif target_day > period_end:
                    target_day = period_end
                bucket = history_buckets.get(target_day)
                if bucket is None:
                    continue
                bucket["total"] += 1
                if status == STATUS_DELIVERED:
                    bucket["delivered"] += 1
                elif status == STATUS_EN_ROUTE:
                    bucket["en_route"] += 1
                elif status in (STATUS_ASSIGNED, STATUS_UNASSIGN):
                    bucket["assigned"] += 1
                elif status == STATUS_FAILURE:
                    bucket["failures"] += 1

            # 5. Construir lista ordenada (omitindo dias vazios)
            history = []
            for offset in range(7):
                d = selected_date - _td(days=6 - offset)
                b = history_buckets[d]
                if b["total"]:
                    history.append({"date": d, **b})

            batches = list(
                CainiaoOperationBatch.objects
                .filter(task_date__range=(date_from, date_to))
                .order_by("-created_at")[:10]
            )

            cainiao_data = {
                "selected_date": selected_date,
                "date_from": date_from,
                "date_to": date_to,
                "all_hubs": all_hubs,
                "selected_hub": selected_hub,
                "total": total,
                "delivered": delivered,
                "en_route": en_route,
                "assigned": assigned,
                "failures": failures,
                "returned": returned_count,
                "delivery_pct": delivery_pct,
                "en_route_pct": en_route_pct,
                "assigned_pct": assigned_pct,
                "failure_pct": failure_pct,
                "delivery_rate": delivery_rate,
                "failure_rate": failure_rate,
                "cp4_breakdown": cp4_qs,
                "driver_breakdown": driver_qs,
                "fleet_breakdown": fleet_breakdown,
                "all_fleets": all_fleets,
                "selected_fleet_id": selected_fleet_id,
                "selected_driver": selected_driver,
                "selected_driver_id": selected_driver_id,
                "selected_courier_name": selected_courier_name,
                "view_mode": view_mode,
                "history": history,
                "batches": batches,
                "available_cp4s": available_cp4s,
                "selected_cp4s": selected_cp4s,
            }
        except Exception:
            cainiao_data = None

    context = {
        "partner": partner,
        "integrations": integrations,
        "active_integrations_count": active_integrations_count,
        "orders_stats": orders_stats,
        "cainiao_data": cainiao_data,
    }

    return render(request, "core/partner_detail.html", context)


@login_required
def partner_create(request):
    """Criar novo parceiro"""
    if request.method == "POST":
        form = PartnerForm(request.POST)
        if form.is_valid():
            partner = form.save()
            messages.success(
                request, f'Parceiro "{partner.name}" criado com sucesso!'
            )
            return redirect("core:partner-detail", pk=partner.pk)
    else:
        form = PartnerForm()

    context = {
        "form": form,
        "title": "Novo Parceiro",
        "button_text": "Criar Parceiro",
    }

    return render(request, "core/partner_form.html", context)


@login_required
def partner_edit(request, pk):
    """Editar parceiro existente"""
    partner = get_object_or_404(Partner, pk=pk)

    if request.method == "POST":
        form = PartnerForm(request.POST, instance=partner)
        if form.is_valid():
            partner = form.save()
            messages.success(
                request, f'Parceiro "{partner.name}" atualizado com sucesso!'
            )
            return redirect("core:partner-detail", pk=partner.pk)
    else:
        form = PartnerForm(instance=partner)

    context = {
        "form": form,
        "partner": partner,
        "title": f"Editar {partner.name}",
        "button_text": "Salvar Alterações",
    }

    return render(request, "core/partner_form.html", context)


@login_required
def partner_toggle_status(request, pk):
    """Ativar/desativar parceiro"""
    partner = get_object_or_404(Partner, pk=pk)
    partner.is_active = not partner.is_active
    partner.save()

    status = "ativado" if partner.is_active else "desativado"
    messages.success(request, f'Parceiro "{partner.name}" {status}!')

    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
    if next_url:
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(next_url)
    return redirect("core:partner-list")


@login_required
def partner_delete(request, pk):
    """Apagar parceiro permanentemente"""
    from django.db.models.deletion import ProtectedError

    partner = get_object_or_404(Partner, pk=pk)

    if request.method == "POST":
        name = partner.name
        try:
            partner.delete()
            messages.success(
                request, f'Parceiro "{name}" apagado com sucesso.'
            )
        except ProtectedError as e:
            types = ", ".join(
                sorted(set(obj.__class__.__name__ for obj in e.protected_objects))
            )
            messages.error(
                request,
                f'Não é possível apagar "{name}": existem registos '
                f'associados ({types}). Desative o parceiro em vez de apagar.',
            )
        return redirect("core:partner-list")

    return redirect("core:partner-list")


@login_required
def integration_create(request, partner_pk):
    """Criar nova integração para um parceiro"""
    partner = get_object_or_404(Partner, pk=partner_pk)

    if request.method == "POST":
        form = PartnerIntegrationForm(request.POST)
        if form.is_valid():
            integration = form.save(commit=False)
            integration.partner = partner
            integration.save()
            messages.success(request, "Integração criada com sucesso!")
            return redirect("core:partner-detail", pk=partner.pk)
    else:
        form = PartnerIntegrationForm()

    context = {
        "form": form,
        "partner": partner,
        "title": f"Nova Integração - {partner.name}",
        "button_text": "Criar Integração",
    }

    return render(request, "core/integration_form.html", context)


@login_required
def integration_edit(request, pk):
    """Editar integração existente"""
    integration = get_object_or_404(PartnerIntegration, pk=pk)

    if request.method == "POST":
        form = PartnerIntegrationForm(request.POST, instance=integration)
        if form.is_valid():
            integration = form.save()
            messages.success(request, "Integração atualizada com sucesso!")
            return redirect("core:partner-detail", pk=integration.partner.pk)
    else:
        form = PartnerIntegrationForm(instance=integration)

    context = {
        "form": form,
        "integration": integration,
        "partner": integration.partner,
        "title": f"Editar Integração - {integration.partner.name}",
        "button_text": "Salvar Alterações",
    }

    return render(request, "core/integration_form.html", context)


@login_required
def integration_toggle_status(request, pk):
    """Ativar/desativar integração"""
    integration = get_object_or_404(PartnerIntegration, pk=pk)
    integration.is_active = not integration.is_active
    integration.save()

    status = "ativada" if integration.is_active else "desativada"
    messages.success(request, f"Integração {status}!")

    return redirect("core:partner-detail", pk=integration.partner.pk)


@login_required
def integrations_dashboard(request):
    """Dashboard de integrações - status geral"""
    integrations = (
        PartnerIntegration.objects.select_related("partner")
        .filter(is_active=True)
        .order_by("-last_sync_at")
    )

    # Estatísticas
    total_integrations = integrations.count()

    # Integrações com sincronização atrasada (2x a frequência esperada)
    overdue_integrations = [i for i in integrations if i.is_sync_overdue]

    # Últimas 10 sincronizações com erro
    error_integrations = PartnerIntegration.objects.filter(
        last_sync_status="ERROR"
    ).order_by("-last_sync_at")[:10]

    context = {
        "integrations": integrations,
        "total_integrations": total_integrations,
        "overdue_integrations": overdue_integrations,
        "error_integrations": error_integrations,
        "overdue_count": len(overdue_integrations),
    }

    return render(request, "core/integrations_dashboard.html", context)


@login_required
@require_POST
def partner_sync_manual(request, integration_id):
    """
    Sincronização manual de dados de um parceiro.
    Retorna JSON com resultado da sincronização.
    """
    try:
        integration = get_object_or_404(
            PartnerIntegration,
            pk=integration_id,
            is_active=True
        )

        # Importar serviço
        from core.services import get_sync_service

        # Verificar se última sync foi há menos de 1 minuto
        # (proteção contra spam)
        if integration.last_sync_at:
            time_since_last_sync = timezone.now() - integration.last_sync_at
            if time_since_last_sync.total_seconds() < 60:
                wait_seconds = int(
                    60 - time_since_last_sync.total_seconds()
                )
                return JsonResponse({
                    "success": False,
                    "error": (
                        "Aguarde pelo menos 1 minuto entre sincronizações"
                    ),
                    "wait_seconds": wait_seconds
                }, status=429)

        # Executar sincronização
        sync_service = get_sync_service(integration)
        
        # Obter parâmetros extras do request body JSON (para Delnext por exemplo)
        import json
        try:
            body_data = json.loads(request.body.decode('utf-8')) if request.body else {}
        except json.JSONDecodeError:
            body_data = {}
        
        date = body_data.get('date')  # YYYY-MM-DD
        zone = body_data.get('zone')
        
        # Executar sync
        if integration.partner.name == "Delnext":
            result = sync_service.sync(date=date, zone=zone)
        else:
            result = sync_service.sync()

        messages.success(
            request,
            f"Sincronização com {integration.partner.name} concluída! "
            f"{result.get('total', 0)} pedidos processados, "
            f"{result.get('created', 0)} criados, "
            f"{result.get('updated', 0)} atualizados."
        )
        
        return JsonResponse({
            "success": True,
            "message": "Sincronização concluída com sucesso",
            "stats": result
        })

    except PartnerIntegration.DoesNotExist:
        return JsonResponse({
            "success": False,
            "error": "Integração não encontrada ou inativa"
        }, status=404)
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Erro na sincronização manual: {e}", exc_info=True)
        
        messages.error(request, f"Erro na sincronização: {str(e)}")
        
        return JsonResponse({
            "success": False,
            "error": str(e)
        }, status=500)


@login_required
def delnext_dashboard(request):
    """
    Dashboard específico para pedidos Delnext com filtros e estatísticas.
    """
    from orders_manager.models import Order
    from django.db.models import Count, Q
    from datetime import timedelta
    
    try:
        partner = Partner.objects.get(name="Delnext")
    except Partner.DoesNotExist:
        messages.warning(request, "Parceiro Delnext não encontrado.")
        return redirect("core:partner-list")
    
    # Filtros
    status_filter = request.GET.get('status', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    search = request.GET.get('search', '')
    
    # Query base
    orders = Order.objects.filter(partner=partner)
    
    # Aplicar filtros
    if status_filter:
        orders = orders.filter(current_status=status_filter)
    
    if date_from:
        try:
            from datetime import datetime
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            orders = orders.filter(created_at__gte=date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            from datetime import datetime
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            # Adicionar 1 dia para incluir todo o dia
            date_to_obj = date_to_obj + timedelta(days=1)
            orders = orders.filter(created_at__lt=date_to_obj)
        except ValueError:
            pass
    
    if search:
        orders = orders.filter(
            Q(external_reference__icontains=search) |
            Q(recipient_name__icontains=search) |
            Q(postal_code__icontains=search) |
            Q(recipient_address__icontains=search)
        )
    
    # Estatísticas gerais
    total_orders = Order.objects.filter(partner=partner).count()
    stats_by_status = Order.objects.filter(
        partner=partner
    ).values('current_status').annotate(count=Count('id'))
    
    # Converter para dict para fácil acesso no template
    stats_dict = {
        'total': total_orders,
        'PENDING': 0,
        'IN_TRANSIT': 0,
        'DELIVERED': 0,
        'RETURNED': 0,
        'CANCELLED': 0,
    }
    
    for stat in stats_by_status:
        stats_dict[stat['current_status']] = stat['count']
    
    # Últimos 7 dias
    seven_days_ago = timezone.now() - timedelta(days=7)
    stats_dict['last_7_days'] = Order.objects.filter(
        partner=partner,
        created_at__gte=seven_days_ago
    ).count()
    
    # Última sincronização
    last_integration = partner.integrations.filter(
        is_active=True
    ).first()
    stats_dict['last_sync'] = (
        last_integration.last_sync_at if last_integration else None
    )
    stats_dict['last_sync_status'] = (
        last_integration.last_sync_status if last_integration else None
    )
    stats_dict['last_sync_message'] = (
        last_integration.last_sync_message if last_integration else ""
    )
    
    # Paginação
    from django.core.paginator import Paginator
    # 25 pedidos por página
    paginator = Paginator(orders.order_by('-created_at'), 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Choices de status para filtro
    status_choices = Order.STATUS_CHOICES
    
    context = {
        'partner': partner,
        'stats': stats_dict,
        'page_obj': page_obj,
        'total_filtered': orders.count(),
        'status_choices': status_choices,
        'current_filters': {
            'status': status_filter,
            'date_from': date_from,
            'date_to': date_to,
            'search': search,
        },
    }
    
    return render(request, 'core/delnext_dashboard.html', context)


# ============================================================================
# FINANCEIRO DO PARCEIRO
# ============================================================================

@login_required
def partner_financial_dashboard(request, pk):
    """Dashboard financeiro do parceiro.

    Consome CainiaoOperationTask para calcular entregas reais por motorista
    e frota (Empresa Parceira). Mostra KPIs, margem e permite gerar
    pré-faturas em lote.
    """
    from datetime import date as _date, timedelta
    from decimal import Decimal
    from django.db.models import Count, Q as _Q, Sum
    from django.db.models.functions import Substr
    from settlements.models import (
        CainiaoOperationTask, DriverPreInvoice, DriverClaim, FinancialAlert,
    )
    from drivers_app.models import DriverProfile, EmpresaParceira

    partner = get_object_or_404(Partner, pk=pk)

    # Date range (default: month-to-date)
    today = _date.today()
    default_from = today.replace(day=1)
    try:
        date_from = _date.fromisoformat(request.GET.get("date_from", "")) \
                    or default_from
    except ValueError:
        date_from = default_from
    try:
        date_to = _date.fromisoformat(request.GET.get("date_to", "")) or today
    except ValueError:
        date_to = today
    if date_from > date_to:
        date_from, date_to = date_to, date_from

    # Cainiao tasks in range (the only partner with operational data today)
    tasks_qs = CainiaoOperationTask.objects.filter(
        task_date__range=(date_from, date_to),
        task_status__in=("Delivered", "Driver_received", "Attempt Failure",
                         "Unassign", "Assigned"),
    )

    total_tasks = tasks_qs.count()
    delivered = tasks_qs.filter(task_status="Delivered").count()
    failures = tasks_qs.filter(task_status="Attempt Failure").count()
    assigned = tasks_qs.filter(task_status__in=("Assigned", "Unassign")).count()
    in_route = tasks_qs.filter(task_status="Driver_received").count()
    success_rate = round(delivered / total_tasks * 100, 1) if total_tasks else 0

    # Receita bruta = delivered × price_per_package do parceiro
    price_pkg = partner.price_per_package or Decimal("0")
    gross_receivable = price_pkg * delivered

    # ── Driver breakdown (consumindo task_date + courier_name) ────────────
    # Agrupar primeiro por courier_id_cainiao (chave estável) — quando
    # disponível agrega todas as variações de courier_name no mesmo driver.
    # Para entregas sem courier_id_cainiao resolvido cai no fallback por
    # courier_name (raw).
    driver_rows = list(
        tasks_qs.exclude(courier_name="")
        .values("courier_name", "courier_id_cainiao")
        .annotate(
            total=Count("id"),
            delivered=Count("id", filter=_Q(task_status="Delivered")),
            failures=Count("id", filter=_Q(task_status="Attempt Failure")),
        )
        .order_by("-delivered")
    )
    # Resolução de driver — courier_name NUNCA bate com nome_completo
    # (nome_completo é o nome real da pessoa, courier_name é o alias do
    # parceiro; o link é feito via DriverCourierMapping ou apelido).
    #   1. DriverCourierMapping (partner, courier_id_cainiao OU courier_name)
    #   2. DriverProfile.courier_id_cainiao == courier_id
    #   3. DriverProfile.apelido == courier_name
    from settlements.models import DriverCourierMapping
    profile_by_courier_id = {
        d.courier_id_cainiao: d for d in DriverProfile.objects
        .select_related("empresa_parceira").exclude(courier_id_cainiao="")
    }
    profile_by_apelido = {
        d.apelido: d for d in DriverProfile.objects
        .select_related("empresa_parceira").exclude(apelido="")
    }
    mapping_by_courier_id = {}
    mapping_by_name = {}
    for m in DriverCourierMapping.objects.filter(partner=partner) \
            .select_related("driver__empresa_parceira"):
        mapping_by_courier_id[m.courier_id] = m.driver
        if m.courier_name:
            mapping_by_name[m.courier_name] = m.driver

    def _resolve_driver(courier_id, courier_name):
        # Prioridade: courier_id_cainiao (estável) > courier_name (alias)
        if courier_id:
            d = mapping_by_courier_id.get(courier_id) or \
                profile_by_courier_id.get(courier_id)
            if d:
                return d
        if courier_name:
            return (mapping_by_name.get(courier_name)
                    or profile_by_apelido.get(courier_name))
        return None

    # Combinar rows com mesmo courier_id (mesmo driver com nomes diferentes)
    merged_by_id = {}
    for r in driver_rows:
        cid = r["courier_id_cainiao"] or ""
        cname = r["courier_name"]
        # key: courier_id se existe, senão courier_name
        key = cid if cid else f"NAME::{cname}"
        if key not in merged_by_id:
            merged_by_id[key] = {
                "courier_name": cname, "courier_id_cainiao": cid,
                "total": 0, "delivered": 0, "failures": 0,
                "courier_names": set(),
            }
        merged_by_id[key]["total"]     += r["total"]
        merged_by_id[key]["delivered"] += r["delivered"]
        merged_by_id[key]["failures"]  += r["failures"]
        merged_by_id[key]["courier_names"].add(cname)
    driver_rows = list(merged_by_id.values())
    driver_rows.sort(key=lambda r: -r["delivered"])

    drivers = []
    fleets_agg = {}  # fleet_id -> accumulator
    total_driver_cost = Decimal("0")

    for row in driver_rows:
        name = row["courier_name"]
        cid = row.get("courier_id_cainiao", "") or ""
        profile = _resolve_driver(cid, name)
        delivered_n = row["delivered"]
        fleet = profile.empresa_parceira if profile else None
        effective_price = (
            (profile.price_per_package if profile and profile.price_per_package is not None else None)
            or price_pkg
        )
        driver_cost = effective_price * delivered_n
        total_driver_cost += driver_cost

        # Display name: prefer canonical driver name; if multiple courier_names
        # mapped to same driver, mostra-os em badges
        display_name = profile.nome_completo if profile else name
        alt_names = sorted(row.get("courier_names", set()) - {display_name})

        entry = {
            "name": display_name,
            "alt_names": alt_names,
            "courier_id_cainiao": cid,
            "profile": profile,
            "fleet": fleet,
            "total": row["total"],
            "delivered": delivered_n,
            "failures": row["failures"],
            "success_rate": round(delivered_n / row["total"] * 100, 1) if row["total"] else 0,
            "price": effective_price,
            "value": driver_cost,
        }
        if fleet:
            fleets_agg.setdefault(fleet.id, {
                "fleet": fleet, "total": 0, "delivered": 0, "failures": 0,
                "drivers": [], "value": Decimal("0"),
            })
            f = fleets_agg[fleet.id]
            f["total"] += entry["total"]
            f["delivered"] += entry["delivered"]
            f["failures"] += entry["failures"]
            f["drivers"].append(entry)
            f["value"] += entry["value"]
        else:
            drivers.append(entry)

    fleets = list(fleets_agg.values())
    # Success rates for aggregates
    for f in fleets:
        f["success_rate"] = round(
            f["delivered"] / f["total"] * 100, 1
        ) if f["total"] else 0
    drivers.sort(key=lambda d: -d["delivered"])
    fleets.sort(key=lambda f: -f["delivered"])

    # Claims in range for this partner's drivers
    claims_qs = DriverClaim.objects.filter(
        occurred_at__date__gte=date_from,
        occurred_at__date__lte=date_to,
    )
    total_claims_value = claims_qs.aggregate(s=Sum("amount"))["s"] or Decimal("0")
    claims_count = claims_qs.count()

    # Margem bruta
    margin_gross = gross_receivable - total_driver_cost

    # Alerts pendentes
    alerts = FinancialAlert.objects.filter(
        resolved=False, partner=partner
    ).order_by("-created_at")[:10]

    context = {
        "partner": partner,
        "date_from": date_from,
        "date_to": date_to,
        "kpis": {
            "total_tasks": total_tasks,
            "delivered": delivered,
            "failures": failures,
            "assigned": assigned,
            "in_route": in_route,
            "success_rate": success_rate,
            "gross_receivable": gross_receivable,
            "total_driver_cost": total_driver_cost,
            "margin_gross": margin_gross,
            "claims_count": claims_count,
            "claims_value": total_claims_value,
        },
        "drivers": drivers,
        "fleets": fleets,
        "alerts": alerts,
    }
    return render(request, "core/partner_financial.html", context)


def _collect_pre_invoice_data(partner, date_from, date_to):
    """Core logic: agrupa entregas por driver/frota e calcula valores.

    Lookup courier_name → DriverProfile em 2 fases:
      1. DriverCourierMapping (partner, courier_name) — preferido (flexível)
      2. DriverProfile.nome_completo == courier_name — fallback
    """
    from decimal import Decimal
    from django.db.models import Count, Q as _Q
    from settlements.models import CainiaoOperationTask, DriverCourierMapping
    from drivers_app.models import DriverProfile

    price_partner = partner.price_per_package or Decimal("0")

    rows = list(
        CainiaoOperationTask.objects.filter(
            task_date__range=(date_from, date_to),
            task_status__in=("Delivered", "Driver_received", "Attempt Failure",
                             "Unassign", "Assigned"),
        )
        .exclude(courier_name="")
        .values("courier_name", "courier_id_cainiao")
        .annotate(
            total=Count("id"),
            delivered=Count("id", filter=_Q(task_status="Delivered")),
            failures=Count("id", filter=_Q(task_status="Attempt Failure")),
        )
    )

    # Lookups para resolver driver — courier_name → APELIDO (não nome_completo)
    mapping_by_courier_id = {}
    mapping_by_name = {}
    for m in DriverCourierMapping.objects.filter(partner=partner) \
            .select_related("driver__empresa_parceira"):
        mapping_by_courier_id[m.courier_id] = m.driver
        if m.courier_name:
            mapping_by_name[m.courier_name] = m.driver
    profile_by_courier_id = {
        d.courier_id_cainiao: d for d in DriverProfile.objects
        .select_related("empresa_parceira").exclude(courier_id_cainiao="")
    }
    profile_by_apelido = {
        d.apelido: d for d in DriverProfile.objects
        .select_related("empresa_parceira").exclude(apelido="")
    }

    def _resolve(courier_id, courier_name):
        # Prioridade: courier_id (estável) > apelido. nome_completo NUNCA bate.
        if courier_id:
            d = mapping_by_courier_id.get(courier_id) or \
                profile_by_courier_id.get(courier_id)
            if d:
                return d
        if courier_name:
            return (mapping_by_name.get(courier_name)
                    or profile_by_apelido.get(courier_name))
        return None

    # Combinar rows com mesmo driver (vários courier_names → mesmo courier_id)
    merged = {}
    for r in rows:
        cid = r["courier_id_cainiao"] or ""
        cname = r["courier_name"]
        prof = _resolve(cid, cname)
        # key: id do driver se resolvido, senão fallback courier_name
        key = f"D::{prof.id}" if prof else f"N::{cname}"
        if key not in merged:
            merged[key] = {
                "courier_name": cname, "courier_id_cainiao": cid,
                "profile": prof,
                "total": 0, "delivered": 0, "failures": 0,
            }
        merged[key]["total"]     += r["total"]
        merged[key]["delivered"] += r["delivered"]
        merged[key]["failures"]  += r["failures"]

    drivers_out = []
    fleets_agg = {}
    unmapped = []

    for row in merged.values():
        name = row["courier_name"]
        prof = row["profile"]
        if not prof:
            unmapped.append({
                "name": name,
                "delivered": row["delivered"],
                "total": row["total"],
            })
            continue
        effective_price = (
            prof.price_per_package if prof.price_per_package is not None
            else price_partner
        )
        delivered_n = row["delivered"]
        amount = effective_price * delivered_n
        entry = {
            "driver_id": prof.id,
            "driver_name": prof.nome_completo,
            "fleet_id": prof.empresa_parceira.id if prof.empresa_parceira else None,
            "fleet_name": prof.empresa_parceira.nome if prof.empresa_parceira else "",
            "delivered": delivered_n,
            "total": row["total"],
            "failures": row["failures"],
            "price": str(effective_price),
            "amount": str(amount),
        }
        if prof.empresa_parceira:
            fid = prof.empresa_parceira.id
            fleets_agg.setdefault(fid, {
                "fleet_id": fid,
                "fleet_name": prof.empresa_parceira.nome,
                "drivers": [],
                "total_delivered": 0,
                "total_amount": Decimal("0"),
            })
            f = fleets_agg[fid]
            f["drivers"].append(entry)
            f["total_delivered"] += delivered_n
            f["total_amount"] += amount
        else:
            drivers_out.append(entry)

    fleets_out = [
        {
            **f,
            "total_amount": str(f["total_amount"]),
        }
        for f in fleets_agg.values()
    ]

    return {
        "drivers": drivers_out,
        "fleets": fleets_out,
        "unmapped": unmapped,
        "partner_price": str(price_partner),
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
    }


@login_required
def partner_financial_preview(request, pk):
    """AJAX: preview antes de gerar pré-faturas em lote."""
    from datetime import date as _date
    from django.http import JsonResponse

    partner = get_object_or_404(Partner, pk=pk)
    try:
        date_from = _date.fromisoformat(request.GET.get("date_from", ""))
        date_to = _date.fromisoformat(request.GET.get("date_to", ""))
    except ValueError:
        return JsonResponse(
            {"success": False, "error": "Datas inválidas."}, status=400,
        )
    if date_from > date_to:
        date_from, date_to = date_to, date_from
    if partner.price_per_package is None or partner.price_per_package == 0:
        return JsonResponse({
            "success": False,
            "error": "Configure o 'Valor por Pacote' do parceiro antes de gerar.",
        }, status=400)
    data = _collect_pre_invoice_data(partner, date_from, date_to)
    return JsonResponse({"success": True, **data})


@login_required
@require_POST
def partner_financial_generate(request, pk):
    """Cria efectivamente as pré-faturas (driver individual ou lançamento da frota)."""
    import json
    from datetime import date as _date
    from decimal import Decimal
    from django.db import transaction
    from django.http import JsonResponse
    from settlements.models import (
        DriverPreInvoice, PreInvoiceLine, PreInvoiceAuditLog,
    )
    from drivers_app.models import (
        DriverProfile, EmpresaParceira, EmpresaParceiraLancamento,
    )

    partner = get_object_or_404(Partner, pk=pk)
    try:
        body = json.loads(request.body or b"{}")
        date_from = _date.fromisoformat(body["date_from"])
        date_to = _date.fromisoformat(body["date_to"])
    except (KeyError, ValueError, json.JSONDecodeError):
        return JsonResponse(
            {"success": False, "error": "Datas inválidas."}, status=400,
        )
    if date_from > date_to:
        date_from, date_to = date_to, date_from

    data = _collect_pre_invoice_data(partner, date_from, date_to)
    created_drivers = 0
    created_fleets = 0

    with transaction.atomic():
        # 1) Pré-faturas de motoristas independentes
        for entry in data["drivers"]:
            driver = DriverProfile.objects.get(pk=entry["driver_id"])
            pre = DriverPreInvoice.objects.create(
                driver=driver,
                periodo_inicio=date_from,
                periodo_fim=date_to,
                dsp_empresa="LÉGUAS FRANZINAS",
                status="CALCULADO",
                created_by=request.user,
            )
            PreInvoiceLine.objects.create(
                pre_invoice=pre,
                parceiro=partner,
                total_pacotes=entry["delivered"],
                taxa_por_entrega=Decimal(entry["price"]),
            )
            # Recalcular totais
            pre.recalculate_totals() if hasattr(pre, "recalculate_totals") else None
            pre.save()
            PreInvoiceAuditLog.objects.create(
                pre_invoice=pre, action="CREATED",
                summary=f"Gerada automaticamente para {partner.name}",
                user=request.user,
                diff={
                    "driver": driver.nome_completo,
                    "delivered": entry["delivered"],
                    "price": entry["price"],
                    "amount": entry["amount"],
                },
            )
            created_drivers += 1

        # 2) Lançamentos para frotas
        for f in data["fleets"]:
            fleet = EmpresaParceira.objects.get(pk=f["fleet_id"])
            lancamento = EmpresaParceiraLancamento.objects.create(
                empresa=fleet,
                descricao=(
                    f"Serviço de Distribuição {partner.name} "
                    f"({date_from:%d/%m} → {date_to:%d/%m})"
                ),
                qtd_entregas=f["total_delivered"],
                valor_por_entrega=partner.price_per_package or Decimal("0"),
                valor_base=Decimal(f["total_amount"]),
                periodo_inicio=date_from,
                periodo_fim=date_to,
                status="RASCUNHO",
                taxa_iva=partner.vat_rate_override or Decimal("23.00"),
            )
            created_fleets += 1

    return JsonResponse({
        "success": True,
        "drivers_created": created_drivers,
        "fleets_created": created_fleets,
        "unmapped": len(data["unmapped"]),
    })


# ============================================================================
# FASE 5 — Preços ad-hoc (override em pré-fatura)
# ============================================================================

@login_required
@require_POST
def pre_invoice_price_override_create(request, pre_invoice_id):
    """AJAX: cria um override de preço granular numa pré-fatura.

    Body JSON: { scope, line_id?, waybill?, date_from?, date_to?, cp4?,
                 new_price, reason }
    """
    import json
    from datetime import date as _date
    from decimal import Decimal, InvalidOperation
    from django.http import JsonResponse
    from settlements.models import (
        DriverPreInvoice, PreInvoiceLine, PreInvoicePriceOverride,
        PreInvoiceAuditLog,
    )

    pre = get_object_or_404(DriverPreInvoice, pk=pre_invoice_id)
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "JSON inválido"}, status=400)

    scope = body.get("scope")
    if scope not in ("LINE", "WAYBILL", "DAY_RANGE", "ZONE"):
        return JsonResponse({"success": False, "error": "scope inválido"}, status=400)

    try:
        new_price = Decimal(str(body.get("new_price", "0")))
    except InvalidOperation:
        return JsonResponse({"success": False, "error": "new_price inválido"}, status=400)

    kwargs = {
        "pre_invoice": pre,
        "scope": scope,
        "new_price": new_price,
        "reason": body.get("reason", "").strip(),
        "created_by": request.user,
    }
    if scope == "LINE":
        line = get_object_or_404(PreInvoiceLine, pk=body.get("line_id"))
        kwargs["line"] = line
        # Aplica imediatamente: atualiza a linha em questão
        old_price = line.taxa_por_entrega
        line.taxa_por_entrega = new_price
        line.save()
    elif scope == "WAYBILL":
        kwargs["waybill_number"] = (body.get("waybill") or "").strip()
    elif scope == "DAY_RANGE":
        kwargs["date_from"] = _date.fromisoformat(body["date_from"])
        kwargs["date_to"]   = _date.fromisoformat(body["date_to"])
    elif scope == "ZONE":
        kwargs["cp4"] = (body.get("cp4") or "").strip()[:4]

    override = PreInvoicePriceOverride.objects.create(**kwargs)
    PreInvoiceAuditLog.objects.create(
        pre_invoice=pre, action="PRICE_OVR",
        summary=f"Override {scope} · €{new_price}",
        user=request.user,
        diff={**{k: (v.isoformat() if hasattr(v, "isoformat") else str(v))
                  for k, v in kwargs.items() if k not in ("pre_invoice", "created_by")}},
    )
    return JsonResponse({"success": True, "override_id": override.id})


# ============================================================================
# FASE 6 — Claims auto-detecção
# ============================================================================

@login_required
@require_POST
def cainiao_detect_lost_packages(request):
    """Varre CainiaoOperationTask e cria DriverClaims automáticos para
    pacotes em Attempt Failure há mais de N dias sem re-tentativa.

    Body JSON: { days_threshold?: int = 7,
                 gap_threshold_m?: int = 500,
                 default_amount?: float = 50 }
    """
    import json
    from datetime import date as _date, timedelta
    from decimal import Decimal
    from django.http import JsonResponse
    from django.db import transaction
    from settlements.models import CainiaoOperationTask, DriverClaim
    from drivers_app.models import DriverProfile

    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        body = {}

    days = int(body.get("days_threshold", 7))
    gap = int(body.get("gap_threshold_m", 500))
    default_amount = Decimal(str(body.get("default_amount", "50")))

    today = _date.today()
    cutoff = today - timedelta(days=days)

    # Critério 1: Attempt Failure há +N dias cujo waybill não aparece
    # depois como Delivered noutra data mais recente
    all_statuses = CainiaoOperationTask.objects.filter(
        task_date__lte=cutoff, task_status="Attempt Failure",
    ).values_list("waybill_number", "task_date", "courier_name", "zip_code")

    # Waybills que eventualmente foram entregues (descartar)
    delivered_wb = set(
        CainiaoOperationTask.objects.filter(task_status="Delivered")
        .values_list("waybill_number", flat=True)
    )
    already_claimed = set(
        DriverClaim.objects.filter(
            claim_type="ORDER_LOSS", waybill_number__isnull=False,
        ).exclude(waybill_number="")
        .values_list("waybill_number", flat=True)
    )

    driver_map = {d.nome_completo: d for d in DriverProfile.objects.all()}
    created = 0

    with transaction.atomic():
        for wb, tdate, courier, zip_code in all_statuses:
            if wb in delivered_wb or wb in already_claimed:
                continue
            driver = driver_map.get(courier)
            if not driver:
                continue
            DriverClaim.objects.create(
                driver=driver,
                claim_type="ORDER_LOSS",
                amount=default_amount,
                description=(
                    f"Auto-deteção: pacote {wb} em Attempt Failure desde "
                    f"{tdate:%d/%m/%Y} sem entrega posterior. "
                    f"Zip {zip_code or '—'}."
                ),
                occurred_at=tdate,
                status="PENDING",
                waybill_number=wb,
                operation_task_date=tdate,
                auto_detected=True,
                created_by=request.user,
            )
            already_claimed.add(wb)
            created += 1

    return JsonResponse({"success": True, "created": created})


# ============================================================================
# FASE 7 — Bónus / Penalties (CRUD + aplicação)
# ============================================================================

@login_required
def partner_bonus_rules(request, pk):
    """Página de gestão de regras de bónus/penalties de um parceiro."""
    from settlements.models import PerformanceBonusRule

    partner = get_object_or_404(Partner, pk=pk)
    rules = partner.bonus_rules.all().order_by("name")
    return render(request, "core/partner_bonus_rules.html", {
        "partner": partner,
        "rules": rules,
        "condition_choices": PerformanceBonusRule.CONDITION_CHOICES,
        "effect_choices": PerformanceBonusRule.EFFECT_CHOICES,
        "scope_choices": PerformanceBonusRule.SCOPE_CHOICES,
    })


@login_required
@require_POST
def partner_bonus_rule_save(request, pk):
    """Cria ou actualiza uma regra."""
    import json
    from decimal import Decimal
    from django.http import JsonResponse
    from settlements.models import PerformanceBonusRule

    partner = get_object_or_404(Partner, pk=pk)
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "JSON inválido"}, status=400)

    rule_id = body.get("id")
    rule = (PerformanceBonusRule.objects.get(pk=rule_id, partner=partner)
            if rule_id else PerformanceBonusRule(partner=partner))
    rule.name = body.get("name", "Regra")[:120]
    rule.enabled = bool(body.get("enabled", True))
    rule.condition = body.get("condition", "SUCCESS_RATE_GTE")
    rule.condition_value = Decimal(str(body.get("condition_value", "0")))
    rule.effect = body.get("effect", "PCT_BONUS")
    rule.effect_value = Decimal(str(body.get("effect_value", "0")))
    rule.scope_period = body.get("scope_period", "WEEKLY")
    rule.applies_to_fleets_only = bool(body.get("applies_to_fleets_only", False))
    rule.applies_to_independent_only = bool(body.get("applies_to_independent_only", False))
    rule.notes = body.get("notes", "")
    rule.save()
    return JsonResponse({"success": True, "id": rule.id})


@login_required
@require_POST
def partner_bonus_rule_delete(request, pk, rule_id):
    """Remove uma regra."""
    from django.http import JsonResponse
    from settlements.models import PerformanceBonusRule

    partner = get_object_or_404(Partner, pk=pk)
    PerformanceBonusRule.objects.filter(pk=rule_id, partner=partner).delete()
    return JsonResponse({"success": True})


# ============================================================================
# FASE 8 — EXTRAS
# ============================================================================

@login_required
@require_POST
def partner_link_courier(request, pk):
    """Vincula um courier_name (do ficheiro Cainiao) a um DriverProfile existente.

    Body JSON: { courier_name: str, driver_id: int }
    Cria um DriverCourierMapping único para o (partner, courier_name).
    """
    import json
    from django.http import JsonResponse
    from settlements.models import DriverCourierMapping
    from drivers_app.models import DriverProfile

    partner = get_object_or_404(Partner, pk=pk)
    try:
        body = json.loads(request.body or b"{}")
        courier_name = (body.get("courier_name") or "").strip()
        driver_id = int(body.get("driver_id"))
    except (ValueError, json.JSONDecodeError, TypeError):
        return JsonResponse(
            {"success": False, "error": "parâmetros inválidos"}, status=400,
        )
    if not courier_name or not driver_id:
        return JsonResponse(
            {"success": False, "error": "courier_name e driver_id obrigatórios"},
            status=400,
        )
    try:
        driver = DriverProfile.objects.get(pk=driver_id)
    except DriverProfile.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "driver não encontrado"}, status=404,
        )
    mapping, created = DriverCourierMapping.objects.update_or_create(
        partner=partner,
        courier_id=courier_name,
        defaults={"driver": driver, "courier_name": courier_name},
    )
    return JsonResponse({
        "success": True,
        "created": created,
        "mapping_id": mapping.id,
        "driver": {
            "id": driver.id, "name": driver.nome_completo,
            "fleet": driver.empresa_parceira.nome if driver.empresa_parceira else "",
        },
    })


@login_required
def partner_drivers_search(request, pk):
    """AJAX: procura DriverProfiles por nome/NIF para dropdown de vincular.

    Estratégia:
      1. Match exacto em NIF
      2. Match icontains em nome_completo / email (por token)
      3. Match SOUNDEX (fonético) em nome_completo — apanha "Rondineli" ↔
         "Rondinelli", "Mateus" ↔ "Matheus", etc.
    Inclui motoristas PENDENTE / EM_ANALISE para que possam ser vinculados
    antes de aprovados. Só exclui IRREGULAR.
    """
    from django.db import connection
    from django.db.models import Q
    from django.http import JsonResponse
    from drivers_app.models import DriverProfile

    q = (request.GET.get("q") or "").strip()
    base_qs = DriverProfile.objects.exclude(status="IRREGULAR")
    if not q:
        drivers = base_qs[:30]
    else:
        tokens = [t for t in q.replace("_", " ").split() if len(t) >= 2]
        ids = set()

        # 1+2: match em apelido / courier_id / NIF / nome_completo / email
        token_qs = base_qs
        for tok in tokens[:5]:
            token_qs = token_qs.filter(
                _or_q(
                    ["apelido", "courier_id_cainiao", "nif",
                     "nome_completo", "email"],
                    tok,
                )
            )
        ids.update(token_qs.values_list("id", flat=True)[:30])

        # 3: match em DriverCourierMapping (logins secundários — drivers com
        # múltiplos logins por parceiro têm courier_ids extras lá)
        from settlements.models import DriverCourierMapping
        from django.db.models import Q as _QQ
        for tok in tokens[:5]:
            ids.update(
                DriverCourierMapping.objects.filter(
                    _QQ(courier_id__icontains=tok)
                    | _QQ(courier_name__icontains=tok)
                ).values_list("driver_id", flat=True)[:30]
            )

        # 4: SOUNDEX fonético (só para tokens com 4+ chars, evitar ruído)
        long_tokens = [t for t in tokens if len(t) >= 4]
        if long_tokens:
            with connection.cursor() as c:
                placeholders = " OR ".join(
                    ["SOUNDEX(nome_completo) = SOUNDEX(%s)"] * len(long_tokens)
                )
                c.execute(
                    f"SELECT id FROM drivers_app_driverprofile "
                    f"WHERE status != 'IRREGULAR' AND ({placeholders}) LIMIT 30",
                    long_tokens,
                )
                ids.update(row[0] for row in c.fetchall())

        drivers = base_qs.filter(id__in=ids)[:30]

    rows = [{
        "id": d.id,
        "name": d.nome_completo,
        "apelido": d.apelido or "",
        "courier_id_cainiao": d.courier_id_cainiao or "",
        "nif": d.nif,
        "status": d.status,
        "fleet": d.empresa_parceira.nome if d.empresa_parceira else "",
    } for d in drivers]
    return JsonResponse({"success": True, "drivers": rows})


def _or_q(fields, value):
    """Helper: OR over several __icontains lookups."""
    from django.db.models import Q
    q = Q()
    for f in fields:
        q |= Q(**{f"{f}__icontains": value})
    return q


@login_required
def driver_courier_logins_list(request, driver_id):
    """AJAX: lista os logins (DriverCourierMapping) deste motorista por parceiro."""
    from django.http import JsonResponse
    from drivers_app.models import DriverProfile
    from settlements.models import DriverCourierMapping
    from core.models import Partner

    driver = get_object_or_404(DriverProfile, pk=driver_id)
    mappings = DriverCourierMapping.objects.filter(driver=driver) \
        .select_related("partner").order_by("partner__name", "courier_id")

    rows = [{
        "id": m.id,
        "partner_id": m.partner_id,
        "partner_name": m.partner.name,
        "courier_id": m.courier_id,
        "courier_name": m.courier_name,
    } for m in mappings]

    partners = list(
        Partner.objects.filter(is_active=True).values("id", "name").order_by("name")
    )

    return JsonResponse({
        "success": True,
        "driver_id": driver.id,
        "driver_name": driver.nome_completo,
        "rows": rows,
        "partners": partners,
    })


@login_required
@require_POST
def driver_courier_login_save(request, driver_id):
    """AJAX: cria ou actualiza um DriverCourierMapping.

    Body JSON: { id?: int, partner_id: int, courier_id: str, courier_name: str }
    """
    import json
    from django.http import JsonResponse
    from drivers_app.models import DriverProfile
    from settlements.models import DriverCourierMapping
    from core.models import Partner

    driver = get_object_or_404(DriverProfile, pk=driver_id)
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "JSON inválido"}, status=400)

    mapping_id = body.get("id")
    courier_id = (body.get("courier_id") or "").strip()
    courier_name = (body.get("courier_name") or "").strip()
    partner_id = body.get("partner_id")

    if not courier_id or not partner_id:
        return JsonResponse(
            {"success": False, "error": "courier_id e partner_id obrigatórios"},
            status=400,
        )

    try:
        partner = Partner.objects.get(pk=int(partner_id))
    except (Partner.DoesNotExist, ValueError):
        return JsonResponse({"success": False, "error": "parceiro inválido"}, status=400)

    if mapping_id:
        try:
            m = DriverCourierMapping.objects.get(pk=int(mapping_id), driver=driver)
        except DriverCourierMapping.DoesNotExist:
            return JsonResponse(
                {"success": False, "error": "mapping não existe"}, status=404,
            )
        m.partner = partner
        m.courier_id = courier_id
        m.courier_name = courier_name
        m.save()
        created = False
    else:
        # Procurar conflito (partner+courier_id já existe noutro driver)
        existing = DriverCourierMapping.objects.filter(
            partner=partner, courier_id=courier_id
        ).exclude(driver=driver).first()
        if existing:
            return JsonResponse({
                "success": False,
                "error": (
                    f"Conflito: este Courier ID já está vinculado a "
                    f"{existing.driver.nome_completo}."
                ),
            }, status=409)
        m, created = DriverCourierMapping.objects.update_or_create(
            partner=partner, courier_id=courier_id,
            defaults={"driver": driver, "courier_name": courier_name},
        )

    # Se for Cainiao e o driver ainda não tem courier_id_cainiao/apelido, sincroniza
    if partner.name.upper() == "CAINIAO":
        changed = []
        if not driver.courier_id_cainiao:
            driver.courier_id_cainiao = courier_id
            changed.append("courier_id_cainiao")
        if not driver.apelido and courier_name:
            driver.apelido = courier_name
            changed.append("apelido")
        if changed:
            driver.save(update_fields=changed)

    return JsonResponse({
        "success": True,
        "id": m.id,
        "created": created,
    })


@login_required
@require_POST
def driver_courier_login_delete(request, driver_id, mapping_id):
    """AJAX: remove um DriverCourierMapping."""
    from django.http import JsonResponse
    from drivers_app.models import DriverProfile
    from settlements.models import DriverCourierMapping

    driver = get_object_or_404(DriverProfile, pk=driver_id)
    deleted, _ = DriverCourierMapping.objects.filter(
        pk=mapping_id, driver=driver,
    ).delete()
    return JsonResponse({"success": True, "deleted": deleted})


@login_required
def driver_account_statement(request, driver_id):
    """Extra 8.1 — Conta-corrente do motorista: saldo, histórico, pendentes."""
    from decimal import Decimal
    from django.db.models import Sum
    from drivers_app.models import DriverProfile

    driver = get_object_or_404(DriverProfile, pk=driver_id)

    # Aggregates on the FULL queryset (no slice yet)
    all_pre = driver.pre_invoices.all()
    all_claims = driver.claims.all()

    total_to_receive = all_pre.filter(
        status__in=("APROVADO", "PENDENTE", "CALCULADO")
    ).aggregate(s=Sum("total_a_receber"))["s"] or Decimal("0")
    total_paid = all_pre.filter(status="PAGO").aggregate(
        s=Sum("total_a_receber"))["s"] or Decimal("0")
    total_claims = all_claims.filter(status="APPROVED").aggregate(
        s=Sum("amount"))["s"] or Decimal("0")

    # Display lists (sliced AFTER aggregates)
    pre_invoices = all_pre.order_by("-periodo_fim")[:24]
    claims = all_claims.order_by("-occurred_at")[:24]

    context = {
        "driver": driver,
        "pre_invoices": pre_invoices,
        "claims": claims,
        "kpis": {
            "to_receive": total_to_receive,
            "paid": total_paid,
            "claims": total_claims,
            "net": total_to_receive - total_claims,
        },
    }
    return render(request, "core/driver_account.html", context)


def pre_invoice_remote_sign(request, token):
    """Extra 8.3 — Página pública de aceitação via token único.

    Acede-se SEM login: /pre-invoice/sign/<token>/ (o token é o credencial).
    """
    from django.shortcuts import render
    from django.utils import timezone
    from settlements.models import DriverPreInvoice, PreInvoiceAuditLog

    pre = get_object_or_404(DriverPreInvoice, signed_token=token)

    if request.method == "POST":
        pre.signed_at = timezone.now()
        pre.signed_ip = request.META.get("REMOTE_ADDR", "")[:45]
        pre.status = "APROVADO"
        pre.save()
        PreInvoiceAuditLog.objects.create(
            pre_invoice=pre, action="SIGNED",
            summary=f"Aceite remotamente de {pre.signed_ip}",
            diff={"ip": pre.signed_ip, "ts": pre.signed_at.isoformat()},
        )

    return render(request, "core/pre_invoice_sign.html", {"pre": pre})


@login_required
@require_POST
def pre_invoice_send_whatsapp(request, pre_invoice_id):
    """Extra 8.3 — Gera token, envia link via WhatsApp (WPPConnect)."""
    import secrets
    from django.utils import timezone
    from django.http import JsonResponse
    from settlements.models import DriverPreInvoice, PreInvoiceAuditLog

    pre = get_object_or_404(DriverPreInvoice, pk=pre_invoice_id)
    if not pre.signed_token:
        pre.signed_token = secrets.token_urlsafe(32)
    pre.whatsapp_sent_at = timezone.now()
    pre.save()

    sign_url = request.build_absolute_uri(
        f"/pre-invoice/sign/{pre.signed_token}/"
    )
    driver_phone = (pre.driver.telefone or "").strip()

    PreInvoiceAuditLog.objects.create(
        pre_invoice=pre, action="WHATSAPP",
        summary=f"Link de assinatura enviado para {driver_phone}",
        user=request.user,
        diff={"url": sign_url, "phone": driver_phone},
    )
    # TODO: integração real com WPPConnect; por agora retorna link para copiar
    return JsonResponse({
        "success": True,
        "sign_url": sign_url,
        "phone": driver_phone,
    })


@login_required
def pre_invoice_saft_export(request, partner_id):
    """Extra 8.9 — Export SAF-T PT (stub XML inicial)."""
    from django.http import HttpResponse
    from datetime import date as _date

    partner = get_object_or_404(Partner, pk=partner_id)
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")

    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<AuditFile xmlns="urn:OECD:StandardAuditFile-Tax:PT_1.04_01">
  <Header>
    <AuditFileVersion>1.04_01</AuditFileVersion>
    <CompanyID>{partner.nif}</CompanyID>
    <TaxRegistrationNumber>{partner.nif[2:] if partner.nif.startswith("PT") else partner.nif}</TaxRegistrationNumber>
    <CompanyName>{partner.name}</CompanyName>
    <FiscalYear>{_date.today().year}</FiscalYear>
    <StartDate>{date_from}</StartDate>
    <EndDate>{date_to}</EndDate>
    <CurrencyCode>EUR</CurrencyCode>
    <DateCreated>{_date.today().isoformat()}</DateCreated>
  </Header>
  <!-- Documentos facturados: implementação completa numa versão futura -->
</AuditFile>
'''
    resp = HttpResponse(xml, content_type="application/xml")
    resp["Content-Disposition"] = (
        f'attachment; filename="saft-{partner.nif}-{date_from}-{date_to}.xml"'
    )
    return resp


@login_required
def financial_alerts_list(request):
    """Extra 8.8 — Dashboard geral de alertas financeiros."""
    from settlements.models import FinancialAlert

    only_unresolved = request.GET.get("all") != "1"
    qs = FinancialAlert.objects.all()
    if only_unresolved:
        qs = qs.filter(resolved=False)
    qs = qs.order_by("-created_at")[:100]
    return render(request, "core/financial_alerts.html", {
        "alerts": qs,
        "only_unresolved": only_unresolved,
    })


@login_required
@require_POST
def financial_alert_resolve(request, alert_id):
    """Extra 8.8 — Marcar alerta como resolvido."""
    from django.http import JsonResponse
    from django.utils import timezone
    from settlements.models import FinancialAlert

    alert = get_object_or_404(FinancialAlert, pk=alert_id)
    alert.resolved = True
    alert.resolved_at = timezone.now()
    alert.resolved_by = request.user
    alert.resolution_notes = request.POST.get("notes", "")
    alert.save()
    return JsonResponse({"success": True})

