from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg
from django.shortcuts import get_object_or_404, redirect, render

from .forms import DriverShiftForm
from .models import DriverShift


@login_required
def shift_list(request):
    """Lista de turnos com filtros."""
    shifts = DriverShift.objects.select_related("driver", "created_by").all()

    # Filtros
    date_filter = request.GET.get("date", "")
    driver_filter = request.GET.get("driver", "")
    status_filter = request.GET.get("status", "")

    if date_filter:
        shifts = shifts.filter(date=date_filter)

    if driver_filter:
        shifts = shifts.filter(driver_id=driver_filter)

    if status_filter:
        shifts = shifts.filter(status=status_filter)

    # Se nenhuma data especificada, mostrar próximo 7 dias
    if not date_filter:
        today = date.today()
        end_date = today + timedelta(days=7)
        shifts = shifts.filter(date__gte=today, date__lte=end_date)

    # Estatísticas
    stats = {
        "total": shifts.count(),
        "scheduled": shifts.filter(status="SCHEDULED").count(),
        "in_progress": shifts.filter(status="IN_PROGRESS").count(),
        "completed": shifts.filter(status="COMPLETED").count(),
    }

    # Paginação
    paginator = Paginator(shifts, 25)
    page_number = request.GET.get("page")
    shifts_page = paginator.get_page(page_number)

    # Buscar motoristas para filtro
    from drivers_app.models import DriverProfile

    all_drivers = DriverProfile.objects.filter(is_active=True)

    context = {
        "shifts": shifts_page,
        "stats": stats,
        "date_filter": date_filter,
        "driver_filter": driver_filter,
        "status_filter": status_filter,
        "all_drivers": all_drivers,
    }

    return render(request, "route_allocation/shift_list.html", context)


@login_required
def shift_detail(request, pk):
    """Detalhes de um turno."""
    shift = get_object_or_404(
        DriverShift.objects.select_related("driver", "created_by").prefetch_related(
            "assigned_postal_zones"
        ),
        pk=pk,
    )

    # Calcular duração se houver horários reais
    duration = None
    if shift.actual_start_time and shift.actual_end_time:
        duration = shift.actual_end_time - shift.actual_start_time

    # Buscar pedidos relacionados (se existir o modelo)
    orders = []
    try:
        from orders_manager.models import Order

        orders = Order.objects.filter(
            assigned_driver=shift.driver, scheduled_delivery=shift.date
        ).select_related("driver")[:10]
    except BaseException:
        pass

    context = {
        "shift": shift,
        "duration": duration,
        "orders": orders,
    }

    return render(request, "route_allocation/shift_detail.html", context)


@login_required
def shift_create(request):
    """Criar novo turno."""
    if request.method == "POST":
        form = DriverShiftForm(request.POST)
        if form.is_valid():
            shift = form.save(commit=False)
            shift.created_by = request.user
            shift.save()
            form.save_m2m()  # Salvar ManyToMany (assigned_postal_zones)
            messages.success(
                request,
                f"Turno criado para {shift.driver.user.get_full_name()} em {shift.date}!",
            )
            return redirect("routes:shift_detail", pk=shift.pk)
    else:
        # Pré-preencher com data de hoje
        initial = {"date": date.today()}
        form = DriverShiftForm(initial=initial)

    context = {"form": form, "shift": None}
    return render(request, "route_allocation/shift_form.html", context)


@login_required
def shift_edit(request, pk):
    """Editar turno existente."""
    shift = get_object_or_404(DriverShift, pk=pk)

    if request.method == "POST":
        form = DriverShiftForm(request.POST, instance=shift)
        if form.is_valid():
            form.save()
            messages.success(request, "Turno atualizado com sucesso!")
            return redirect("routes:shift_detail", pk=shift.pk)
    else:
        form = DriverShiftForm(instance=shift)

    context = {"form": form, "shift": shift}
    return render(request, "route_allocation/shift_form.html", context)


@login_required
def shift_start(request, pk):
    """Iniciar turno (check-in)."""
    if request.method == "POST":
        shift = get_object_or_404(DriverShift, pk=pk)
        shift.start_shift()
        messages.success(
            request,
            f'Turno iniciado às {shift.actual_start_time.strftime("%H:%M")}!',
        )
        return redirect("routes:shift_detail", pk=shift.pk)

    return redirect("routes:shift_list")


@login_required
def shift_end(request, pk):
    """Finalizar turno (check-out)."""
    if request.method == "POST":
        shift = get_object_or_404(DriverShift, pk=pk)
        shift.end_shift()
        messages.success(
            request,
            f'Turno finalizado às {shift.actual_end_time.strftime("%H:%M")}!',
        )
        return redirect("routes:shift_detail", pk=shift.pk)

    return redirect("routes:shift_list")


@login_required
def shift_calendar(request):
    """Visualização em calendário dos turnos."""

    # Pegar mês/ano dos parâmetros ou usar atual
    year = int(request.GET.get("year", date.today().year))
    month = int(request.GET.get("month", date.today().month))
    today = date.today()

    # Primeira e última data do mês
    first_day = date(year, month, 1)
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)

    # Buscar turnos do mês (incluindo alguns dias antes/depois para preencher semana)
    calendar_start = first_day - timedelta(
        days=first_day.weekday() + 1
    )  # Começar no domingo
    calendar_end = last_day + timedelta(days=(6 - last_day.weekday()))

    shifts = DriverShift.objects.filter(
        date__gte=calendar_start, date__lte=calendar_end
    ).select_related("driver")

    # Agrupar por data
    shifts_by_date = {}
    for shift in shifts:
        date_key = shift.date.strftime("%Y-%m-%d")
        if date_key not in shifts_by_date:
            shifts_by_date[date_key] = []
        shifts_by_date[date_key].append(shift)

    # Gerar dias do calendário
    calendar_days = []
    current_date = calendar_start
    while current_date <= calendar_end:
        calendar_days.append(
            {
                "date": current_date.strftime("%Y-%m-%d"),
                "day": current_date.day,
                "is_today": current_date == today,
                "is_other_month": current_date.month != month,
            }
        )
        current_date += timedelta(days=1)

    # Calcular mês anterior e próximo
    if month == 1:
        prev_month, prev_year = 12, year - 1
    else:
        prev_month, prev_year = month - 1, year

    if month == 12:
        next_month, next_year = 1, year + 1
    else:
        next_month, next_year = month + 1, year

    # Nome do mês em português
    month_names = {
        1: "Janeiro",
        2: "Fevereiro",
        3: "Março",
        4: "Abril",
        5: "Maio",
        6: "Junho",
        7: "Julho",
        8: "Agosto",
        9: "Setembro",
        10: "Outubro",
        11: "Novembro",
        12: "Dezembro",
    }

    context = {
        "year": year,
        "month": month,
        "month_name": month_names[month],
        "calendar_days": calendar_days,
        "shifts_by_date": shifts_by_date,
        "prev_month": prev_month,
        "prev_year": prev_year,
        "next_month": next_month,
        "next_year": next_year,
    }

    return render(request, "route_allocation/shift_calendar.html", context)


@login_required
def routes_dashboard(request):
    """Dashboard de alocação de rotas."""
    today = date.today()

    # Turnos de hoje
    today_shifts = DriverShift.objects.filter(date=today).select_related("driver")

    # Estatísticas gerais
    today_stats = {
        "total": today_shifts.count(),
        "in_progress": today_shifts.filter(status="IN_PROGRESS").count(),
        "completed": today_shifts.filter(status="COMPLETED").count(),
        "scheduled": today_shifts.filter(status="SCHEDULED").count(),
    }

    # Próximos 7 dias
    end_date = today + timedelta(days=7)
    upcoming_shifts = (
        DriverShift.objects.filter(
            date__gt=today, date__lte=end_date, status="SCHEDULED"
        )
        .select_related("driver")
        .order_by("date", "start_time")[:10]
    )

    # Estatísticas de performance (último mês)
    last_month = today - timedelta(days=30)
    completed_shifts = DriverShift.objects.filter(
        date__gte=last_month, status="COMPLETED"
    )

    performance = {
        "total_shifts": completed_shifts.count(),
        "total_deliveries": sum([s.total_deliveries or 0 for s in completed_shifts]),
        "avg_success_rate": completed_shifts.aggregate(
            avg=Avg("successful_deliveries")
        )["avg"]
        or 0,
    }

    context = {
        "today": today,
        "today_shifts": today_shifts,
        "today_stats": today_stats,
        "upcoming_shifts": upcoming_shifts,
        "performance": performance,
    }

    return render(request, "route_allocation/routes_dashboard.html", context)
