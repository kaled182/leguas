import csv
import io
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from core.models import Partner

from .forms import CSVUploadForm, PartnerTariffForm, PostalZoneForm
from .models import PartnerTariff, PostalZone

# ========== ZONAS POSTAIS ==========


@login_required
def zone_list(request):
    """Lista de zonas postais com filtros"""
    zones_qs = PostalZone.objects.all()

    # Filtros
    search = request.GET.get("search", "")
    region_filter = request.GET.get("region", "")
    status_filter = request.GET.get("status", "")

    if search:
        zones_qs = zones_qs.filter(
            Q(name__icontains=search)
            | Q(code__icontains=search)
            | Q(postal_code_pattern__icontains=search)
        )

    if region_filter:
        zones_qs = zones_qs.filter(region=region_filter)

    if status_filter == "active":
        zones_qs = zones_qs.filter(is_active=True)
    elif status_filter == "inactive":
        zones_qs = zones_qs.filter(is_active=False)

    # Anotar com contagens de tarifas
    zones_qs = zones_qs.annotate(
        tariffs_count=Count("tariffs"),
        active_tariffs_count=Count("tariffs", filter=Q(tariffs__is_active=True)),
    )

    # Paginação
    paginator = Paginator(zones_qs, 25)
    page = request.GET.get("page", 1)

    try:
        zones = paginator.page(page)
    except PageNotAnInteger:
        zones = paginator.page(1)
    except EmptyPage:
        zones = paginator.page(paginator.num_pages)

    context = {
        "zones": zones,
        "search": search,
        "region_filter": region_filter,
        "status_filter": status_filter,
        "total_count": zones_qs.count(),
        "regions": PostalZone._meta.get_field("region").choices,
    }

    return render(request, "pricing/zone_list.html", context)


@login_required
def zone_detail(request, pk):
    """Detalhes de uma zona postal"""
    zone = get_object_or_404(PostalZone, pk=pk)

    # Tarifas associadas
    tariffs = zone.tariffs.select_related("partner").order_by(
        "-is_active", "partner__name"
    )

    context = {
        "zone": zone,
        "tariffs": tariffs,
    }

    return render(request, "pricing/zone_detail.html", context)


@login_required
def zone_create(request):
    """Criar nova zona postal"""
    if request.method == "POST":
        form = PostalZoneForm(request.POST)
        if form.is_valid():
            zone = form.save()
            messages.success(request, f'Zona postal "{zone.name}" criada com sucesso!')
            return redirect("pricing:zone-detail", pk=zone.pk)
    else:
        form = PostalZoneForm()

    context = {
        "form": form,
        "title": "Nova Zona Postal",
        "button_text": "Criar Zona",
    }

    return render(request, "pricing/zone_form.html", context)


@login_required
def zone_edit(request, pk):
    """Editar zona postal existente"""
    zone = get_object_or_404(PostalZone, pk=pk)

    if request.method == "POST":
        form = PostalZoneForm(request.POST, instance=zone)
        if form.is_valid():
            zone = form.save()
            messages.success(
                request, f'Zona postal "{zone.name}" atualizada com sucesso!'
            )
            return redirect("pricing:zone-detail", pk=zone.pk)
    else:
        form = PostalZoneForm(instance=zone)

    context = {
        "form": form,
        "zone": zone,
        "title": f"Editar {zone.name}",
        "button_text": "Salvar Alterações",
    }

    return render(request, "pricing/zone_form.html", context)


@login_required
def zone_toggle_status(request, pk):
    """Ativar/desativar zona"""
    zone = get_object_or_404(PostalZone, pk=pk)
    zone.is_active = not zone.is_active
    zone.save()

    status = "ativada" if zone.is_active else "desativada"
    messages.success(request, f'Zona postal "{zone.name}" {status}!')

    return redirect("pricing:zone-detail", pk=zone.pk)


# ========== TARIFAS ==========


@login_required
def tariff_list(request):
    """Lista de tarifas com filtros"""
    tariffs_qs = PartnerTariff.objects.select_related("partner", "postal_zone").all()

    # Filtros
    partner_filter = request.GET.get("partner", "")
    zone_filter = request.GET.get("zone", "")
    status_filter = request.GET.get("status", "")

    if partner_filter:
        tariffs_qs = tariffs_qs.filter(partner_id=partner_filter)

    if zone_filter:
        tariffs_qs = tariffs_qs.filter(postal_zone_id=zone_filter)

    if status_filter == "active":
        tariffs_qs = tariffs_qs.filter(is_active=True)
    elif status_filter == "inactive":
        tariffs_qs = tariffs_qs.filter(is_active=False)
    elif status_filter == "expired":
        tariffs_qs = tariffs_qs.filter(valid_until__lt=date.today())

    # Ordenação
    tariffs_qs = tariffs_qs.order_by("-is_active", "partner__name", "postal_zone__name")

    # Paginação
    paginator = Paginator(tariffs_qs, 25)
    page = request.GET.get("page", 1)

    try:
        tariffs = paginator.page(page)
    except PageNotAnInteger:
        tariffs = paginator.page(1)
    except EmptyPage:
        tariffs = paginator.page(paginator.num_pages)

    # Dados para filtros
    partners = Partner.objects.filter(is_active=True).order_by("name")
    zones = PostalZone.objects.filter(is_active=True).order_by("name")

    context = {
        "tariffs": tariffs,
        "partners": partners,
        "zones": zones,
        "partner_filter": partner_filter,
        "zone_filter": zone_filter,
        "status_filter": status_filter,
        "total_count": tariffs_qs.count(),
    }

    return render(request, "pricing/tariff_list.html", context)


@login_required
def tariff_detail(request, pk):
    """Detalhes de uma tarifa"""
    tariff = get_object_or_404(
        PartnerTariff.objects.select_related("partner", "postal_zone"), pk=pk
    )

    # Calcular preços de exemplo
    example_prices = {
        "normal": tariff.calculate_price(is_express=False, is_weekend=False),
        "weekend": tariff.calculate_price(is_express=False, is_weekend=True),
        "express": tariff.calculate_price(is_express=True, is_weekend=False),
        "express_weekend": tariff.calculate_price(is_express=True, is_weekend=True),
    }

    context = {
        "tariff": tariff,
        "example_prices": example_prices,
    }

    return render(request, "pricing/tariff_detail.html", context)


@login_required
def tariff_create(request):
    """Criar nova tarifa"""
    if request.method == "POST":
        form = PartnerTariffForm(request.POST)
        if form.is_valid():
            tariff = form.save()
            messages.success(request, f"Tarifa criada com sucesso!")
            return redirect("pricing:tariff-detail", pk=tariff.pk)
    else:
        form = PartnerTariffForm()

    context = {
        "form": form,
        "title": "Nova Tarifa",
        "button_text": "Criar Tarifa",
    }

    return render(request, "pricing/tariff_form.html", context)


@login_required
def tariff_edit(request, pk):
    """Editar tarifa existente"""
    tariff = get_object_or_404(PartnerTariff, pk=pk)

    if request.method == "POST":
        form = PartnerTariffForm(request.POST, instance=tariff)
        if form.is_valid():
            tariff = form.save()
            messages.success(request, f"Tarifa atualizada com sucesso!")
            return redirect("pricing:tariff-detail", pk=tariff.pk)
    else:
        form = PartnerTariffForm(instance=tariff)

    context = {
        "form": form,
        "tariff": tariff,
        "title": f"Editar Tarifa",
        "button_text": "Salvar Alterações",
    }

    return render(request, "pricing/tariff_form.html", context)


@login_required
def tariff_toggle_status(request, pk):
    """Ativar/desativar tarifa"""
    tariff = get_object_or_404(PartnerTariff, pk=pk)
    tariff.is_active = not tariff.is_active
    tariff.save()

    status = "ativada" if tariff.is_active else "desativada"
    messages.success(request, f"Tarifa {status}!")

    return redirect("pricing:tariff-detail", pk=tariff.pk)


# ========== CALCULADORA ==========


@login_required
def price_calculator(request):
    """Calculadora de preços"""
    result = None

    if request.method == "POST":
        partner_id = request.POST.get("partner")
        postal_code = request.POST.get("postal_code")
        is_express = request.POST.get("is_express") == "on"
        is_weekend = request.POST.get("is_weekend") == "on"

        if partner_id and postal_code:
            try:
                partner = Partner.objects.get(pk=partner_id)
                tariff = PartnerTariff.get_tariff_for_order(
                    partner=partner,
                    postal_code=postal_code,
                    delivery_date=date.today(),
                )

                if tariff:
                    price = tariff.calculate_price(
                        delivery_date=date.today(),
                        is_express=is_express,
                        is_weekend=is_weekend,
                    )

                    result = {
                        "success": True,
                        "partner": partner,
                        "zone": tariff.postal_zone,
                        "base_price": tariff.base_price,
                        "success_bonus": tariff.success_bonus,
                        "final_price": price,
                        "is_express": is_express,
                        "is_weekend": is_weekend,
                        "express_multiplier": (
                            tariff.express_multiplier if is_express else None
                        ),
                        "weekend_multiplier": (
                            tariff.weekend_multiplier if is_weekend else None
                        ),
                    }
                else:
                    result = {
                        "success": False,
                        "error": f"Nenhuma tarifa encontrada para {partner.name} na zona do código postal {postal_code}",
                    }
            except Partner.DoesNotExist:
                result = {"success": False, "error": "Parceiro não encontrado"}

    # Dados para formulário
    partners = Partner.objects.filter(is_active=True).order_by("name")

    context = {
        "partners": partners,
        "result": result,
    }

    return render(request, "pricing/price_calculator.html", context)


# ========== IMPORT CSV ==========


@login_required
def zone_import_csv(request):
    """Import de zonas postais via CSV"""
    preview_data = None
    errors = []

    if request.method == "POST":
        # Passo 2: Confirmar importação
        if "confirm_import" in request.POST:
            preview_data = request.session.get("zone_import_preview", [])

            if preview_data:
                created_count = 0
                errors_count = 0

                for row in preview_data:
                    if row.get("is_valid", False):
                        try:
                            PostalZone.objects.create(
                                name=row["name"],
                                code=row["code"],
                                postal_code_pattern=row["postal_code_pattern"],
                                region=row["region"],
                                center_latitude=row.get("center_latitude"),
                                center_longitude=row.get("center_longitude"),
                                is_urban=row.get("is_urban", False),
                                average_delivery_time_hours=row.get(
                                    "average_delivery_time_hours", 24
                                ),
                                is_active=row.get("is_active", True),
                                notes=row.get("notes", ""),
                            )
                            created_count += 1
                        except Exception as e:
                            errors_count += 1
                            errors.append(
                                f"Erro ao criar zona {row.get('code', 'N/A')}: {str(e)}"
                            )

                # Limpa sessão
                if "zone_import_preview" in request.session:
                    del request.session["zone_import_preview"]

                if errors_count == 0:
                    messages.success(
                        request,
                        f"{created_count} zonas postais importadas com sucesso!",
                    )
                    return redirect("pricing:zone-list")
                else:
                    messages.warning(
                        request,
                        f"{created_count} zonas criadas, {errors_count} erros encontrados.",
                    )

        # Passo 1: Upload e preview
        else:
            form = CSVUploadForm(request.POST, request.FILES)

            if form.is_valid():
                csv_file = request.FILES["csv_file"]

                try:
                    # Lê CSV
                    decoded_file = csv_file.read().decode("utf-8")
                    io_string = io.StringIO(decoded_file)
                    reader = csv.DictReader(io_string)

                    preview_data = []
                    row_number = 1

                    for row in reader:
                        row_number += 1
                        row_errors = []

                        # Validações
                        if not row.get("name"):
                            row_errors.append("Nome é obrigatório")
                        if not row.get("code"):
                            row_errors.append("Código é obrigatório")
                        if not row.get("postal_code_pattern"):
                            row_errors.append("Padrão de código postal é obrigatório")
                        if not row.get("region"):
                            row_errors.append("Região é obrigatória")

                        # Verifica se código já existe
                        if (
                            row.get("code")
                            and PostalZone.objects.filter(code=row["code"]).exists()
                        ):
                            row_errors.append(
                                f"Zona com código '{row['code']}' já existe"
                            )

                        # Valida região
                        valid_regions = [
                            "NORTE",
                            "CENTRO",
                            "LISBOA",
                            "ALENTEJO",
                            "ALGARVE",
                            "MADEIRA",
                            "AÇORES",
                        ]
                        if (
                            row.get("region")
                            and row["region"].upper() not in valid_regions
                        ):
                            row_errors.append(
                                f"Região inválida. Use: {', '.join(valid_regions)}"
                            )

                        preview_data.append(
                            {
                                "row_number": row_number,
                                "name": row.get("name", ""),
                                "code": row.get("code", ""),
                                "postal_code_pattern": row.get(
                                    "postal_code_pattern", ""
                                ),
                                "region": row.get("region", "").upper(),
                                "center_latitude": row.get("center_latitude", ""),
                                "center_longitude": row.get("center_longitude", ""),
                                "is_urban": row.get("is_urban", "").lower()
                                in ["true", "1", "sim", "yes"],
                                "average_delivery_time_hours": row.get(
                                    "average_delivery_time_hours", "24"
                                ),
                                "is_active": row.get("is_active", "true").lower()
                                in ["true", "1", "sim", "yes"],
                                "notes": row.get("notes", ""),
                                "errors": row_errors,
                                "is_valid": len(row_errors) == 0,
                            }
                        )

                    # Guarda na sessão para confirmação
                    request.session["zone_import_preview"] = preview_data

                except Exception as e:
                    errors.append(f"Erro ao processar CSV: {str(e)}")
            else:
                errors.append("Formulário inválido")
    else:
        form = CSVUploadForm()

    # Calcula totais para o template
    total_rows = len(preview_data) if preview_data else 0
    valid_rows = (
        sum(1 for row in preview_data if row.get("is_valid", False))
        if preview_data
        else 0
    )
    invalid_rows = total_rows - valid_rows

    context = {
        "form": form,
        "preview_data": preview_data,
        "errors": errors,
        "total_rows": total_rows,
        "valid_rows": valid_rows,
        "invalid_rows": invalid_rows,
    }

    return render(request, "pricing/zone_import.html", context)


@login_required
def tariff_import_csv(request):
    """Import de tarifas via CSV"""
    preview_data = None
    errors = []

    if request.method == "POST":
        # Passo 2: Confirmar importação
        if "confirm_import" in request.POST:
            preview_data = request.session.get("tariff_import_preview", [])

            if preview_data:
                created_count = 0
                errors_count = 0

                for row in preview_data:
                    if row.get("is_valid", False):
                        try:
                            PartnerTariff.objects.create(
                                partner=row["partner_obj"],
                                postal_zone=row["zone_obj"],
                                base_price=row["base_price"],
                                success_bonus=row.get("success_bonus", 0),
                                failure_penalty=row.get("failure_penalty", 0),
                                late_delivery_penalty=row.get(
                                    "late_delivery_penalty", 0
                                ),
                                weekend_multiplier=row.get("weekend_multiplier", 1.0),
                                express_multiplier=row.get("express_multiplier", 1.0),
                                valid_from=row.get("valid_from"),
                                valid_until=row.get("valid_until"),
                                is_active=row.get("is_active", True),
                                notes=row.get("notes", ""),
                            )
                            created_count += 1
                        except Exception as e:
                            errors_count += 1
                            errors.append(f"Erro ao criar tarifa: {str(e)}")

                # Limpa sessão
                if "tariff_import_preview" in request.session:
                    del request.session["tariff_import_preview"]

                if errors_count == 0:
                    messages.success(
                        request,
                        f"{created_count} tarifas importadas com sucesso!",
                    )
                    return redirect("pricing:tariff-list")
                else:
                    messages.warning(
                        request,
                        f"{created_count} tarifas criadas, {errors_count} erros encontrados.",
                    )

        # Passo 1: Upload e preview
        else:
            form = CSVUploadForm(request.POST, request.FILES)

            if form.is_valid():
                csv_file = request.FILES["csv_file"]

                try:
                    # Lê CSV
                    decoded_file = csv_file.read().decode("utf-8")
                    io_string = io.StringIO(decoded_file)
                    reader = csv.DictReader(io_string)

                    preview_data = []
                    row_number = 1

                    for row in reader:
                        row_number += 1
                        row_errors = []
                        partner_obj = None
                        zone_obj = None

                        # Validações básicas
                        if not row.get("partner_name"):
                            row_errors.append("Nome do parceiro é obrigatório")
                        else:
                            try:
                                partner_obj = Partner.objects.get(
                                    name=row["partner_name"]
                                )
                            except Partner.DoesNotExist:
                                row_errors.append(
                                    f"Parceiro '{row['partner_name']}' não encontrado"
                                )

                        if not row.get("zone_code"):
                            row_errors.append("Código da zona é obrigatório")
                        else:
                            try:
                                zone_obj = PostalZone.objects.get(code=row["zone_code"])
                            except PostalZone.DoesNotExist:
                                row_errors.append(
                                    f"Zona '{row['zone_code']}' não encontrada"
                                )

                        if not row.get("base_price"):
                            row_errors.append("Preço base é obrigatório")

                        # Verifica duplicação
                        if partner_obj and zone_obj:
                            if PartnerTariff.objects.filter(
                                partner=partner_obj, postal_zone=zone_obj
                            ).exists():
                                row_errors.append(
                                    f"Tarifa para {row['partner_name']} + {row['zone_code']} já existe"
                                )

                        from datetime import datetime

                        valid_from = None
                        valid_until = None

                        try:
                            if row.get("valid_from"):
                                valid_from = datetime.strptime(
                                    row["valid_from"], "%Y-%m-%d"
                                ).date()
                        except BaseException:
                            row_errors.append(
                                "Data valid_from inválida (use YYYY-MM-DD)"
                            )

                        try:
                            if row.get("valid_until"):
                                valid_until = datetime.strptime(
                                    row["valid_until"], "%Y-%m-%d"
                                ).date()
                        except BaseException:
                            row_errors.append(
                                "Data valid_until inválida (use YYYY-MM-DD)"
                            )

                        preview_data.append(
                            {
                                "row_number": row_number,
                                "partner_name": row.get("partner_name", ""),
                                "zone_code": row.get("zone_code", ""),
                                "base_price": row.get("base_price", ""),
                                "success_bonus": row.get("success_bonus", "0"),
                                "failure_penalty": row.get("failure_penalty", "0"),
                                "late_delivery_penalty": row.get(
                                    "late_delivery_penalty", "0"
                                ),
                                "weekend_multiplier": row.get(
                                    "weekend_multiplier", "1.0"
                                ),
                                "express_multiplier": row.get(
                                    "express_multiplier", "1.0"
                                ),
                                "valid_from": valid_from,
                                "valid_until": valid_until,
                                "is_active": row.get("is_active", "true").lower()
                                in ["true", "1", "sim", "yes"],
                                "notes": row.get("notes", ""),
                                "partner_obj": partner_obj,
                                "zone_obj": zone_obj,
                                "errors": row_errors,
                                "is_valid": len(row_errors) == 0,
                            }
                        )

                    # Guarda na sessão para confirmação
                    request.session["tariff_import_preview"] = preview_data

                except Exception as e:
                    errors.append(f"Erro ao processar CSV: {str(e)}")
            else:
                errors.append("Formulário inválido")
    else:
        form = CSVUploadForm()

    # Calcula totais para o template
    total_rows = len(preview_data) if preview_data else 0
    valid_rows = (
        sum(1 for row in preview_data if row.get("is_valid", False))
        if preview_data
        else 0
    )
    invalid_rows = total_rows - valid_rows

    context = {
        "form": form,
        "preview_data": preview_data,
        "errors": errors,
        "total_rows": total_rows,
        "valid_rows": valid_rows,
        "invalid_rows": invalid_rows,
    }

    return render(request, "pricing/tariff_import.html", context)


# ========== MAPAS ==========


@login_required
def zones_map(request):
    """Mapa visual de zonas postais com Leaflet.js"""
    zones = PostalZone.objects.filter(
        is_active=True,
        center_latitude__isnull=False,
        center_longitude__isnull=False,
    ).select_related()

    # Calcula centro do mapa (média das coordenadas)
    if zones.exists():
        avg_lat = (
            sum(float(z.center_latitude) for z in zones if z.center_latitude)
            / zones.count()
        )
        avg_lng = (
            sum(float(z.center_longitude) for z in zones if z.center_longitude)
            / zones.count()
        )
        map_center = [avg_lat, avg_lng]
        map_zoom = 7
    else:
        # Portugal centro
        map_center = [39.5, -8.0]
        map_zoom = 7

    # Estatísticas
    zones_urbanas = zones.filter(is_urban=True).count()
    zones_rurais = zones.filter(is_urban=False).count()
    num_regioes = zones.values("region").distinct().count()

    context = {
        "zones": zones,
        "map_center": map_center,
        "map_zoom": map_zoom,
        "zones_urbanas": zones_urbanas,
        "zones_rurais": zones_rurais,
        "num_regioes": num_regioes,
    }

    return render(request, "pricing/zones_map.html", context)
