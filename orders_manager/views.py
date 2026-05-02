from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import json

from .forms import AssignDriverForm, OrderForm, OrderIncidentForm
from .models import Order, OrderIncident, OrderStatusHistory, GeocodingFailure


@login_required
def orders_dashboard(request):
    """Dashboard de pedidos com estatísticas e visão geral."""
    today = date.today()

    # Pedidos de hoje
    today_orders = Order.objects.filter(scheduled_delivery=today)

    # Estatísticas gerais
    stats = {
        "total_today": today_orders.count(),
        "pending": Order.objects.filter(current_status="PENDING").count(),
        "assigned": Order.objects.filter(current_status="ASSIGNED").count(),
        "in_transit": Order.objects.filter(current_status="IN_TRANSIT").count(),
        "delivered_today": today_orders.filter(current_status="DELIVERED").count(),
        "incidents": Order.objects.filter(current_status="INCIDENT").count(),
        "overdue": Order.objects.filter(
            scheduled_delivery__lt=today,
            current_status__in=["PENDING", "ASSIGNED", "IN_TRANSIT"],
        ).count(),
    }

    # Pedidos atrasados
    overdue_orders = Order.objects.filter(
        scheduled_delivery__lt=today,
        current_status__in=["PENDING", "ASSIGNED", "IN_TRANSIT"],
    ).select_related("partner", "assigned_driver")[:10]

    # Pedidos de hoje por status
    today_by_status = (
        today_orders.values("current_status")
        .annotate(count=Count("id"))
        .order_by("current_status")
    )

    # Próximos 7 dias
    end_date = today + timedelta(days=7)
    upcoming_orders = (
        Order.objects.filter(
            scheduled_delivery__gt=today,
            scheduled_delivery__lte=end_date,
            current_status="PENDING",
        )
        .select_related("partner")
        .order_by("scheduled_delivery")[:10]
    )

    context = {
        "stats": stats,
        "overdue_orders": overdue_orders,
        "today_by_status": today_by_status,
        "upcoming_orders": upcoming_orders,
        "today": today,
    }

    return render(request, "orders_manager/orders_dashboard.html", context)


@login_required
def order_list(request):
    """Lista de pedidos com filtros."""
    orders = Order.objects.select_related("partner", "assigned_driver").all()

    # Filtros
    status_filter = request.GET.get("status", "")
    partner_filter = request.GET.get("partner", "")
    driver_filter = request.GET.get("driver", "")
    date_filter = request.GET.get("date", "")
    search_query = request.GET.get("search", "")

    if status_filter:
        orders = orders.filter(current_status=status_filter)

    if partner_filter:
        orders = orders.filter(partner_id=partner_filter)

    if driver_filter:
        orders = orders.filter(assigned_driver_id=driver_filter)

    if date_filter:
        orders = orders.filter(scheduled_delivery=date_filter)

    if search_query:
        orders = orders.filter(
            Q(external_reference__icontains=search_query)
            | Q(recipient_name__icontains=search_query)
            | Q(postal_code__icontains=search_query)
        )

    # Ordenação
    orders = orders.order_by("-created_at")

    # Paginação
    paginator = Paginator(orders, 25)
    page_number = request.GET.get("page")
    orders_page = paginator.get_page(page_number)

    # Dados para filtros
    from core.models import Partner
    from drivers_app.models import DriverProfile

    all_partners = Partner.objects.filter(is_active=True).order_by("name")
    all_drivers = DriverProfile.objects.filter(is_active=True).order_by("nome_completo")

    context = {
        "orders": orders_page,
        "status_filter": status_filter,
        "partner_filter": partner_filter,
        "driver_filter": driver_filter,
        "date_filter": date_filter,
        "search_query": search_query,
        "all_partners": all_partners,
        "all_drivers": all_drivers,
        "status_choices": Order.STATUS_CHOICES,
    }

    return render(request, "orders_manager/order_list.html", context)


@login_required
def order_detail(request, pk):
    """Detalhes de um pedido com histórico."""
    order = get_object_or_404(
        Order.objects.select_related("partner", "assigned_driver"), pk=pk
    )

    # Histórico de status
    status_history = (
        OrderStatusHistory.objects.filter(order=order)
        .select_related("changed_by")
        .order_by("-changed_at")
    )

    # Incidentes
    incidents = (
        OrderIncident.objects.filter(order=order)
        .select_related("created_by")
        .order_by("-created_at")
    )

    context = {
        "order": order,
        "status_history": status_history,
        "incidents": incidents,
    }

    return render(request, "orders_manager/order_detail.html", context)


@login_required
def order_create(request):
    """Criar novo pedido."""
    if request.method == "POST":
        form = OrderForm(request.POST)
        if form.is_valid():
            order = form.save()

            # Registrar histórico inicial
            OrderStatusHistory.objects.create(
                order=order,
                status=order.current_status,
                changed_by=request.user,
                notes="Pedido criado",
            )

            messages.success(
                request,
                f"Pedido {order.external_reference} criado com sucesso!",
            )
            return redirect("orders:order_detail", pk=order.pk)
    else:
        form = OrderForm()

    context = {"form": form, "order": None}
    return render(request, "orders_manager/order_form.html", context)


@login_required
def order_edit(request, pk):
    """Editar pedido existente."""
    order = get_object_or_404(Order, pk=pk)

    if request.method == "POST":
        form = OrderForm(request.POST, instance=order)
        if form.is_valid():
            form.save()
            messages.success(request, "Pedido atualizado com sucesso!")
            return redirect("orders:order_detail", pk=order.pk)
    else:
        form = OrderForm(instance=order)

    context = {"form": form, "order": order}
    return render(request, "orders_manager/order_form.html", context)


@login_required
def order_assign_driver(request, pk):
    """Atribuir motorista a um pedido."""
    order = get_object_or_404(Order, pk=pk)
    order.current_status

    if request.method == "POST":
        form = AssignDriverForm(request.POST, instance=order)
        if form.is_valid():
            order = form.save(commit=False)
            order.assigned_at = timezone.now()
            if order.current_status == "PENDING":
                order.current_status = "ASSIGNED"
            order.save()

            # Registrar no histórico
            OrderStatusHistory.objects.create(
                order=order,
                status=order.current_status,
                changed_by=request.user,
                notes=f"Atribuído a {order.assigned_driver.nome_completo}",
            )

            messages.success(
                request,
                f"Pedido atribuído a {order.assigned_driver.nome_completo}!",
            )
            return redirect("orders:order_detail", pk=order.pk)
    else:
        form = AssignDriverForm(instance=order)

    context = {"form": form, "order": order}
    return render(request, "orders_manager/assign_driver.html", context)


@login_required
def order_change_status(request, pk):
    """Alterar status de um pedido."""
    if request.method != "POST":
        return redirect("orders:order_detail", pk=pk)

    order = get_object_or_404(Order, pk=pk)
    new_status = request.POST.get("new_status")
    notes = request.POST.get("notes", "")

    if new_status not in dict(Order.STATUS_CHOICES):
        messages.error(request, "Status inválido")
        return redirect("orders:order_detail", pk=pk)

    order.current_status
    order.current_status = new_status

    # Atualizar data de entrega se applicable
    if new_status == "DELIVERED" and not order.delivered_at:
        order.delivered_at = timezone.now()

    order.save()

    # Registrar no histórico
    OrderStatusHistory.objects.create(
        order=order, status=new_status, changed_by=request.user, notes=notes
    )

    messages.success(
        request, f"Status alterado para {order.get_current_status_display()}!"
    )
    return redirect("orders:order_detail", pk=pk)


@login_required
def order_report_incident(request, pk):
    """Reportar incidente em um pedido."""
    order = get_object_or_404(Order, pk=pk)

    if request.method == "POST":
        form = OrderIncidentForm(request.POST)
        if form.is_valid():
            incident = form.save(commit=False)
            incident.order = order
            incident.created_by = request.user
            incident.save()

            # Atualizar status do pedido
            if order.current_status != "INCIDENT":
                order.current_status
                order.current_status = "INCIDENT"
                order.save()

                OrderStatusHistory.objects.create(
                    order=order,
                    status="INCIDENT",
                    changed_by=request.user,
                    notes=f"Incidente reportado: {incident.get_incident_type_display()}",
                )

            messages.success(request, "Incidente reportado com sucesso!")
            return redirect("orders:order_detail", pk=order.pk)
    else:
        form = OrderIncidentForm()

    context = {"form": form, "order": order}
    return render(request, "orders_manager/incident_form.html", context)


# ========== MAPAS ==========


@login_required
def orders_map(request):
    """Mapa visual de pedidos em tempo real (Leaflet.js) com geocodificação"""
    from pricing.models import PostalZone
    from .geocoding import GeocodingService, AddressNormalizer
    from .models import GeocodedAddress

    # Filtros de status - agora busca todos os status para permitir filtragem no frontend
    all_statuses = ["PENDING", "ASSIGNED", "IN_TRANSIT", "DELIVERED", "INCIDENT", "RETURNED", "CANCELLED"]

    # Buscar pedidos com todos os status (sem slice ainda para poder filtrar)
    orders_qs_full = (
        Order.objects.filter(current_status__in=all_statuses)
        .select_related("partner", "assigned_driver")
        .order_by("-created_at")
    )

    # Estatísticas (antes do slice)
    total_count = orders_qs_full.count()
    pending_count = orders_qs_full.filter(current_status="PENDING").count()
    assigned_count = orders_qs_full.filter(current_status="ASSIGNED").count()
    in_transit_count = orders_qs_full.filter(current_status="IN_TRANSIT").count()
    delivered_count = orders_qs_full.filter(current_status="DELIVERED").count()
    incident_count = orders_qs_full.filter(current_status="INCIDENT").count()
    returned_count = orders_qs_full.filter(current_status="RETURNED").count()
    cancelled_count = orders_qs_full.filter(current_status="CANCELLED").count()

    # Limitar aos últimos 300 pedidos para performance (reduzido devido a geocodificação)
    orders_qs = orders_qs_full[:300]

    # Carregar coordenadas (usar cache, sem geocodificação em tempo real)
    orders_with_coords = []
    orders_without_coords = []

    for order in orders_qs:
        coords = None
        quality = None
        zone_name = "Desconhecida"
        
        try:
            # Extrair localidade do endereço ou usar código postal
            locality = order.recipient_address.split()[-1] if order.recipient_address else "Portugal"
            if len(locality) < 3:  # Se for muito curto, usar default
                locality = "Portugal"
            
            # Normalizar endereço
            normalized = AddressNormalizer.normalize(
                order.recipient_address,
                order.postal_code,
                locality
            )
            
            # Verificar APENAS cache (não geocodificar durante requisição HTTP)
            cached = GeocodedAddress.objects.filter(
                normalized_address=normalized
            ).first()
            
            if cached and cached.latitude and cached.longitude:
                # Usar coordenadas do cache
                coords = (float(cached.latitude), float(cached.longitude))
                quality = cached.geocode_quality
            else:
                # Fallback: usar zona postal (não geocodificar agora)
                zone = PostalZone.find_zone_for_postal_code(order.postal_code)
                if zone and zone.center_latitude and zone.center_longitude:
                    coords = (float(zone.center_latitude), float(zone.center_longitude))
                    quality = 'POSTAL_CODE'
                    zone_name = zone.name
            
            if coords:
                # Tentar pegar nome da zona
                if quality != 'POSTAL_CODE':
                    zone = PostalZone.find_zone_for_postal_code(order.postal_code)
                    if zone:
                        zone_name = zone.name
                
                orders_with_coords.append({
                    "order": order,
                    "lat": coords[0],
                    "lng": coords[1],
                    "zone": type('obj', (object,), {'name': zone_name})(),  # Mock zone object
                    "quality": quality or 'UNKNOWN'
                })
            else:
                orders_without_coords.append(order)
                
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Erro ao processar pedido {order.external_reference}: {e}")
            orders_without_coords.append(order)

    # Calcular centro do mapa
    if orders_with_coords:
        avg_lat = sum(o["lat"] for o in orders_with_coords) / len(orders_with_coords)
        avg_lng = sum(o["lng"] for o in orders_with_coords) / len(orders_with_coords)
        map_center = [avg_lat, avg_lng]
        map_zoom = 8
    else:
        # Portugal centro
        map_center = [39.5, -8.0]
        map_zoom = 7

    # Estatísticas
    stats = {
        "total": total_count,
        "with_coords": len(orders_with_coords),
        "without_coords": len(orders_without_coords),
        "pending": pending_count,
        "assigned": assigned_count,
        "in_transit": in_transit_count,
        "delivered": delivered_count,
        "incident": incident_count,
        "returned": returned_count,
        "cancelled": cancelled_count,
    }

    context = {
        "orders_with_coords": orders_with_coords,
        "orders_without_coords": orders_without_coords,
        "map_center": map_center,
        "map_zoom": map_zoom,
        "stats": stats,
    }

    return render(request, "orders_manager/orders_map.html", context)


@login_required
def geocoding_failures_report(request):
    """Relatório de endereços que falharam na geocodificação"""
    from .models import GeocodingFailure, GeocodedAddress
    from django.http import JsonResponse
    from django.views.decorators.http import require_POST
    import json
    
    # Filtros
    show_resolved = request.GET.get('show_resolved', 'false') == 'true'
    partner_filter = request.GET.get('partner', '')
    
    # Query base
    failures_qs = GeocodingFailure.objects.select_related(
        'order__partner',
        'resolved_by'
    )
    
    if not show_resolved:
        failures_qs = failures_qs.filter(resolved=False)
    
    if partner_filter:
        failures_qs = failures_qs.filter(order__partner__name__icontains=partner_filter)
    
    failures_qs = failures_qs.order_by('-attempted_at')
    
    # Paginação
    paginator = Paginator(failures_qs, 50)
    page_number = request.GET.get('page')
    failures = paginator.get_page(page_number)
    
    # Estatísticas
    total_failures = GeocodingFailure.objects.count()
    unresolved_count = GeocodingFailure.objects.filter(resolved=False).count()
    resolved_count = GeocodingFailure.objects.filter(resolved=True).count()
    total_geocoded = GeocodedAddress.objects.count()
    
    # Top códigos postais com falhas
    top_postal_codes = (
        GeocodingFailure.objects
        .filter(resolved=False)
        .values('postal_code')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )
    
    context = {
        'failures': failures,
        'show_resolved': show_resolved,
        'partner_filter': partner_filter,
        'stats': {
            'total_failures': total_failures,
            'unresolved': unresolved_count,
            'resolved': resolved_count,
            'total_geocoded': total_geocoded,
            'success_rate': round((total_geocoded / (total_geocoded + unresolved_count) * 100), 1) 
                if (total_geocoded + unresolved_count) > 0 else 0
        },
        'top_postal_codes': top_postal_codes
    }
    
    return render(request, "orders_manager/geocoding_failures_final.html", context)


@login_required
@require_POST
def resolve_geocoding_failure(request, failure_id):
    """Resolve a geocoding failure by saving manual coordinates (AJAX).

    Expects POST with 'latitude' and 'longitude' (can be form or JSON).
    """
    try:
        lat = None
        lng = None

        # Prefer form-encoded POST if present
        if request.POST and (request.POST.get('latitude') or request.POST.get('longitude')):
            lat = request.POST.get('latitude')
            lng = request.POST.get('longitude')
        else:
            # Try parse JSON body
            try:
                body = request.body.decode('utf-8') or '{}'
                data = json.loads(body)
            except Exception:
                data = {}

            lat = data.get('latitude') or data.get('lat')
            lng = data.get('longitude') or data.get('lng')

        if lat is None or lng is None:
            return JsonResponse({'error': 'Missing latitude/longitude'}, status=400)

        failure = GeocodingFailure.objects.get(pk=failure_id)
        # mark resolved (stores manual coords and creates GeocodedAddress)
        # convert to float/Decimal acceptable by model
        try:
            lat_val = float(lat)
            lng_val = float(lng)
        except Exception:
            return JsonResponse({'error': 'Invalid latitude/longitude format'}, status=400)

        failure.mark_resolved(lat_val, lng_val, user=request.user)

        return JsonResponse({'ok': True, 'message': 'Marked resolved'})
    except GeocodingFailure.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

