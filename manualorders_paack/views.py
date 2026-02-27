import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import (
    Count, Sum, Case, When, IntegerField, Q, Avg, F, FloatField
)
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView

from ordersmanager_paack.models import Order as apiOrder, Order
from ordersmanager_paack.models import Dispatch as apiDispatch, Dispatch
from ordersmanager_paack.models import Driver
from .models import ManualCorrection
from .services import ManualCorrectionService


# ========================
# UTILITY CLASSES
# ========================

class DriverClass:
    """Simple driver data structure"""
    def __init__(self, name, id):
        self.name = name
        self.id = id


class DriverWrapper:
    """Wrapper for driver objects with performance metrics"""
    
    def __init__(self, driver_obj, best_driver_data=None):
        clean_name = self._extract_driver_name(driver_obj.driver.name)
        self.driver = DriverClass(clean_name, driver_obj.driver.id)
        
        if best_driver_data:
            self.success_rate = best_driver_data.get('driver_success_rate', 0)
            self.total_dispatches = best_driver_data.get('total_dispatches', 0)
            self.total_delivered = best_driver_data.get('total_delivered', 0)
    
    def _extract_driver_name(self, full_name):
        """Extract clean driver name from full name"""
        if not full_name:
            return "N/A"
        
        # Remove common codes and prefixes
        parts = full_name.split()
        if len(parts) <= 2:
            return full_name
        
        # Pattern to identify proper names
        # Filter components that appear to be proper names
        name_parts = [
            p for p in parts 
            if len(p) > 2 and p[0].isupper() 
            and not p.isupper() 
            and p not in ['OPO', 'LF', 'SC', 'LMO']
        ]
        
        # If no proper names identified, use last 2 words
        if not name_parts:
            return ' '.join(parts[-2:])
        
        return ' '.join(name_parts)


# ========================
# DATA SERVICE CLASS
# ========================

class ManualOrdersDataService:
    """Service class to handle data operations for manual orders dashboard"""
    
    def __init__(self, request):
        self.request = request
        self.date_params = self._get_date_params()
        self.filter_date = self.date_params['filter_date']
        self.start_date = self.date_params['start_date']
        self.end_date = self.date_params['end_date']
        self.date_range_mode = self.date_params['date_range_mode']
        self.is_today = self._check_is_today()
        self.filter_date_obj = self._get_filter_date_as_date()
        self.start_date_obj = self._get_start_date_as_date()
        self.end_date_obj = self._get_end_date_as_date()

    def _get_date_params(self):
        """Extract and validate date parameters from request"""
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        filter_date = self.request.GET.get('filter_date')
        
        date_range_mode = bool(start_date or end_date)
        
        if date_range_mode:
            if not start_date:
                start_date = timezone.now().date().strftime('%Y-%m-%d')
            if not end_date:
                end_date = start_date
            filter_date = None
        else:
            if not filter_date:
                filter_date = timezone.now().date().strftime('%Y-%m-%d')
            start_date = None
            end_date = None
        
        return {
            'filter_date': filter_date,
            'start_date': start_date,
            'end_date': end_date,
            'date_range_mode': date_range_mode
        }

    def _check_is_today(self):
        """Check if filtered date(s) represent today"""
        today = timezone.now().date().strftime('%Y-%m-%d')
        if self.date_range_mode:
            return self.start_date == today and self.end_date == today
        else:
            return self.filter_date == today

    def _get_filter_date_as_date(self):
        """Convert filter_date string to date object"""
        if self.filter_date:
            return timezone.datetime.strptime(self.filter_date, '%Y-%m-%d').date()
        return timezone.now().date()

    def _get_start_date_as_date(self):
        """Convert start_date string to date object"""
        if self.start_date:
            return timezone.datetime.strptime(self.start_date, '%Y-%m-%d').date()
        return None

    def _get_end_date_as_date(self):
        """Convert end_date string to date object"""
        if self.end_date:
            return timezone.datetime.strptime(self.end_date, '%Y-%m-%d').date()
        return None

    def _get_date_filter_for_queries(self):
        """Build date filter dictionary for database queries"""
        if self.date_range_mode:
            return {
                'dispatch_time__date__range': [self.start_date_obj, self.end_date_obj]
            }
        else:
            return {
                'dispatch_time__date': self.filter_date_obj
            }

    def get_dispatch_metrics(self):
        """Return dispatch metrics for filtered date(s)"""
        # Use the same date filter approach as the fixed paack_dashboard
        if self.date_range_mode:
            start_date = self.start_date_obj
            end_date = self.end_date_obj
        else:
            start_date = self.filter_date_obj
            end_date = self.filter_date_obj
        
        # Use extra() with DATE() function like the working paack_dashboard
        metrics = apiDispatch.objects.extra(
            where=["DATE(dispatch_time) BETWEEN %s AND %s"],
            params=[start_date, end_date]
        ).aggregate(
            total=Count('id'),
            delivered=Count(
                Case(
                    When(order__status='delivered', then=1),
                    output_field=IntegerField()
                )
            ),
            failed=Count(
                Case(
                    When(order__simplified_order_status__in=['failed', 'undelivered'], then=1),
                    output_field=IntegerField()
                )
            ),
            pending=Count(
                Case(
                    When(order__simplified_order_status='to_attempt', then=1),
                    output_field=IntegerField()
                )
            ),
            recovered=Count(
                Case(
                    When(recovered=True, then=1),
                    output_field=IntegerField()
                )
            )
        )
        
        if metrics['total'] > 0:
            metrics['success_rate'] = round((metrics['delivered'] / metrics['total']) * 100, 2)
        else:
            metrics['success_rate'] = 0
            
        return metrics

    def get_total_orders_description(self):
        """Generate human-readable description for order totals"""
        if self.date_range_mode:
            if self.start_date_obj == self.end_date_obj:
                return f"Pedidos em {self.start_date_obj.strftime('%d/%m/%Y')}"
            else:
                return (f"Pedidos do período ({self.start_date_obj.strftime('%d/%m')} "
                       f"a {self.end_date_obj.strftime('%d/%m')})")
        elif self.is_today:
            return "Pedidos de hoje"
        else:
            return f"Pedidos em {self.filter_date_obj.strftime('%d/%m/%Y')}"

    def get_weekly_efficiency(self):
        """Calculate weekly efficiency metrics"""
        if self.date_range_mode:
            start_date = self.start_date_obj
            end_date = self.end_date_obj
        else:
            start_date = self.filter_date_obj - timedelta(days=6)
            end_date = self.filter_date_obj
        
        # Use the same date filter approach as other functions
        daily_stats = (
            apiDispatch.objects
            .extra(
                where=["DATE(dispatch_time) BETWEEN %s AND %s"],
                params=[start_date, end_date]
            )
            .annotate(date=TruncDate('dispatch_time'))
            .values('date')
            .annotate(
                total=Count('id'),
                delivered=Count(
                    Case(When(order__status='delivered', then=1), output_field=IntegerField())
                )
            )
            .annotate(
                success_rate=Case(
                    When(total__gt=0, then=(100.0 * F('delivered') / F('total'))),
                    default=0,
                    output_field=FloatField()
                )
            )
        )
        
        if not daily_stats:
            return 0
        
        total_success_rate = sum(day['success_rate'] for day in daily_stats)
        return round(total_success_rate / len(daily_stats), 2)

    def get_manual_corrections(self):
        """Get manual corrections for the filtered period with clean driver names"""
        try:
            # Check total number of corrections in the database first (for debugging)
            total_corrections = ManualCorrection.objects.all().count()
            print(f"Total de correções no banco de dados: {total_corrections}")
            
            # Get all corrections without any filtering to check if there are records
            all_corrections = ManualCorrection.objects.all()
            if not all_corrections.exists():
                print("Não existem correções manuais no banco de dados")
                return all_corrections
            
            # Apply date filters
            if self.date_range_mode:
                corrections_filter = {
                    'correction_date__range': [self.start_date_obj, self.end_date_obj]
                }
                print(f"Aplicando filtro de data: {self.start_date_obj} até {self.end_date_obj}")
            else:
                corrections_filter = {
                    'correction_date': self.filter_date_obj
                }
                print(f"Aplicando filtro para data: {self.filter_date_obj}")
            
            corrections = ManualCorrection.objects.filter(
                **corrections_filter
            ).select_related(
                'driver', 'order', 'created_by', 'dispatch'
            ).order_by('-created_at')
            
            print(f"Correções após filtro de data: {corrections.count()}")
            
            return corrections
        except Exception as e:
            print(f"Erro ao buscar correções manuais: {str(e)}")  # Debug
            import traceback
            print(traceback.format_exc())  # Adiciona stack trace para melhor debug
            return ManualCorrection.objects.none()  # Retorna queryset vazio em caso de erro

    def _extract_driver_name(self, full_name):
        """Extract driver name removing codes and prefixes"""
        if not full_name:
            return "N/A"
            
        prefixes = ['SC', 'OPO', 'LF', 'M', 'D', 'LX', 'Porto', 'Lisboa', 'FCO', 'PRT']
        suffixes = ['LMO', 'XYZ', 'ABC', 'IJK']
        
        parts = full_name.split()
        name_candidate = []
        started_name = False
        
        for part in parts:
            if part in prefixes:
                continue
                
            is_proper_name = len(part) > 2 and part[0].isupper() and not part.isupper()
            
            if started_name or is_proper_name:
                started_name = True
                name_candidate.append(part)
        
        if name_candidate:
            # Remove uppercase suffixes
            if name_candidate and name_candidate[-1].isupper() and len(name_candidate[-1]) <= 3:
                name_candidate.pop()
                
            if name_candidate and name_candidate[-1] in suffixes:
                name_candidate.pop()
                
            clean_name = ' '.join(name_candidate)
        else:
            cleaned_parts = [p for p in parts if p not in prefixes and len(p) > 1]
            if len(cleaned_parts) > 3:
                clean_name = ' '.join(cleaned_parts[-3:])
            else:
                clean_name = ' '.join(cleaned_parts)
        
        return clean_name.strip()
        
    def get_driver_profile_image(self, driver_id):
        """Placeholder for driver profile image URL"""
        # You can implement the real logic here if you have an image system
        return None

    def get_driver_success_chart_data(self):
        """Return data for driver success chart"""
        # Use the same date filter approach as the fixed metrics
        if self.date_range_mode:
            start_date = self.start_date_obj
            end_date = self.end_date_obj
        else:
            start_date = self.filter_date_obj
            end_date = self.filter_date_obj
        
        driver_success_data = (
            apiDispatch.objects
            .extra(
                where=["DATE(dispatch_time) BETWEEN %s AND %s"],
                params=[start_date, end_date]
            )
            .values('driver', 'driver__name')
            .annotate(
                total_attempts=Count('id'),
                deliveries=Count(
                    Case(When(order__status='delivered', then=1), output_field=IntegerField())
                ),
                fails=Count(
                    Case(When(order__simplified_order_status__in=['failed', 'undelivered'], then=1),
                        output_field=IntegerField())
                )
            )
            .annotate(
                success_rate=Case(
                    When(total_attempts__gt=0, then=(100.0 * F('deliveries') / F('total_attempts'))),
                    default=0,
                    output_field=FloatField()
                )
            )
            .filter(total_attempts__gte=1)
            .order_by('-success_rate')
        )

        formatted_data = []
        for data in driver_success_data:
            driver_name = self._extract_driver_name(data['driver__name'])

            # Get pending count with same date filter
            pending_count = apiDispatch.objects.extra(
                where=["DATE(dispatch_time) BETWEEN %s AND %s"],
                params=[start_date, end_date]
            ).filter(
                driver=data['driver'],
                order__simplified_order_status='to_attempt'
            ).count()

            # Real total attempts
            real_total_attempts = data['deliveries'] + data['fails'] + pending_count

            if real_total_attempts > 0:
                success_pct = 100.0 * data['deliveries'] / real_total_attempts
                fails_pct = 100.0 * data['fails'] / real_total_attempts
                pending_pct = 100.0 * pending_count / real_total_attempts
            else:
                success_pct = fails_pct = pending_pct = 0

            # Get profile image
            profile_img_url = self.get_driver_profile_image(data['driver'])
            
            formatted_data.append({
                'name': driver_name,
                'deliveries': data['deliveries'],
                'fails': data['fails'],
                'pending': pending_count,
                'real_total_attempts': real_total_attempts,
                'success_pct': round(success_pct, 2),
                'fails_pct': round(fails_pct, 2),
                'pending_pct': round(pending_pct, 2),
                'driver_id': data['driver'],
                'profile_picture': profile_img_url
            })

        return formatted_data


# ========================
# MAIN DASHBOARD VIEW
# ========================

@method_decorator(login_required, name='dispatch')
class ManualOrdersDashboardView(TemplateView):
    """Main dashboard view for manual orders management"""
    
    template_name = 'manualorders_paack/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        data_service = ManualOrdersDataService(self.request)
        
        # Date parameters
        context['filter_date'] = data_service.filter_date
        context['start_date'] = data_service.start_date
        context['end_date'] = data_service.end_date
        context['date_range_mode'] = data_service.date_range_mode
        context['is_today'] = data_service.is_today
        
        # Manual corrections - Force showing all corrections for debugging
        from .models import ManualCorrection
        all_corrections = ManualCorrection.objects.all().select_related(
            'driver', 'order', 'created_by', 'dispatch'
        ).order_by('-created_at')
        
        print(f"=== DEBUG MANUAL CORRECTIONS ===")
        print(f"Total de correções no banco: {all_corrections.count()}")
        
        # Process corrections and create list with clean names
        corrections_with_clean_names = []
        for correction in all_corrections:
            clean_name = data_service._extract_driver_name(correction.driver.name)
            print(f"Correção ID {correction.id}: {clean_name} - {correction.status}")
            # Add clean name as a temporary attribute without setting it on the model
            setattr(correction, 'temp_clean_driver_name', clean_name)
            corrections_with_clean_names.append(correction)
        
        # Use processed corrections
        corrections = corrections_with_clean_names
        
        context['manual_corrections'] = corrections
        
        # Debug info
        print(f"Total de correções encontradas (finalmente): {len(corrections)}")
        print(f"Data do filtro: {data_service.filter_date}")
        print(f"Range de datas: {data_service.start_date} até {data_service.end_date}")

        # Main metrics
        context['dispatch_metrics'] = data_service.get_dispatch_metrics()
        context['total_orders_description'] = data_service.get_total_orders_description()
        context['week_efficiency'] = data_service.get_weekly_efficiency()

        # Active drivers list for modals
        context['drivers'] = (
            Driver.objects
            .filter(is_active=True)
            .values('driver_id', 'name')
            .order_by('name')
        )
        
        # Lista de status válidos para correções manuais
        from .services import ManualCorrectionService
        context['status_options'] = [
            {'value': status, 'label': status.replace('_', ' ').title()} 
            for status in ManualCorrectionService.VALID_STATUSES
        ]

        # Driver success chart data
        driver_success_data = data_service.get_driver_success_chart_data()
        context['driver_success_chart'] = driver_success_data
        
        # Prepare data for chart in JSON format
        serializable_data = []
        for item in driver_success_data:
            serializable_item = {
                'name': item['name'],
                'deliveries': item['deliveries'],
                'fails': item['fails'],
                'pending': item['pending'],
                'total_attempts': item['real_total_attempts'],
                'success_rate': float(item['success_pct']),
                'success_rate_display': f"{item['success_pct']:.1f}%",
                'fails_pct': float(item['fails_pct']),
                'pending_pct': float(item['pending_pct']),
                'driver_id': item['driver_id'],
                'profile_picture': item['profile_picture']
            }
            serializable_data.append(serializable_item)
        
        # Add JSON data for template
        context['driver_success_chart_json'] = json.dumps(
            serializable_data,
            ensure_ascii=False,
            separators=(',', ':')
        )

        return context


# ========================
# API VIEWS
# ========================

@login_required
def get_drivers(request):
    """Return list of active drivers"""
    drivers = Driver.objects.filter(is_active=True).values('driver_id', 'name')
    return JsonResponse(list(drivers), safe=False)


@login_required
def check_manual_orders(request):
    """Check available manual orders for removal"""
    date = request.GET.get('date')
    driver_id = request.GET.get('driver_id')
    
    if not date:
        return JsonResponse({
            'success': False,
            'error': 'Data é obrigatória'
        }, status=400)
    
    try:
        result = ManualCorrectionService.check_manual_orders(date, driver_id)
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
def get_manual_corrections_by_date(request):
    """Return manual corrections for a specific date"""
    date = request.GET.get('date')
    driver_id = request.GET.get('driver_id')

    if not date:
        return JsonResponse({
            'success': False,
            'error': 'Data é obrigatória'
        }, status=400)

    corrections = ManualCorrection.objects.filter(
        created_at__date=date
    ).select_related('driver', 'order', 'created_by')

    if driver_id:
        corrections = corrections.filter(driver__driver_id=driver_id)

    data = []
    for correction in corrections:
        data.append({
            'id': correction.id,
            'type': correction.get_correction_type_display(),
            'status': correction.get_status_display(),
            'reason': correction.reason,
            'driver_name': correction.driver.name,
            'created_by': correction.created_by.username,
            'created_at': correction.created_at.strftime('%H:%M:%S'),
            'order_id': correction.order.order_id
        })

    return JsonResponse({
        'success': True,
        'corrections': data
    })


# ========================
# ACTION VIEWS
# ========================

@login_required
def manual_correction(request):
    """Handle manual correction creation and removal"""
    if request.method == 'POST':
        try:
            driver_id = request.POST.get('driver_id')
            reason = request.POST.get('reason')
            is_addition = request.POST.get('is_addition') == 'true'
            status = request.POST.get('status', 'delivered')
            date = request.POST.get('date')
            
            if is_addition:
                # Validate quantity
                quantity = int(request.POST.get('quantity', 1))
                if not 1 <= quantity <= 100:
                    messages.error(request, 'A quantidade deve estar entre 1 e 100')
                    return redirect('manualorders_paack:manual_management')
                
                # Validate required fields
                if not all([driver_id, reason, status, date]):
                    messages.error(request, 'Todos os campos são obrigatórios')
                    return redirect('manualorders_paack:manual_management')
                
                # Create records using the new service
                result = ManualCorrectionService.create_manual_correction(
                    driver_id=driver_id,
                    target_date=date,
                    status=status,
                    reason=reason,
                    quantity=quantity,
                    created_by_user=request.user,
                    correction_type='ADD'
                )
            else:
                date = request.POST.get('date')
                if not all([date, reason]):
                    messages.error(request, 'Data e motivo são obrigatórios')
                    return redirect('manualorders_paack:manual_management')
                    
                result = ManualCorrectionService.remove_manual_records(
                    date=date,
                    driver_id=driver_id,
                    reason=reason,
                    user=request.user
                )
            
            if result['success']:
                messages.success(request, result['message'])
            else:
                messages.error(request, result.get('error', 'Erro ao processar a operação'))
                
        except Exception as e:
            messages.error(request, f'Erro ao processar a operação: {str(e)}')
    
    return redirect('manualorders_paack:manual_management')


@login_required
@require_http_methods(["POST"])
def delete_manual_corrections(request):
    """Remove selected manual corrections and their associated dispatches"""
    try:
        correction_ids = request.POST.getlist("correction_ids")
        if not correction_ids:
            messages.error(request, "Nenhum registro selecionado.")
            return redirect("manualorders_paack:manual_management")

        # Get corrections with their related dispatches
        corrections = ManualCorrection.objects.filter(
            id__in=correction_ids
        ).select_related('dispatch')

        # Collect dispatch IDs
        dispatch_ids = [c.dispatch.id for c in corrections if c.dispatch]
        
        # First delete dispatches (this will cascade delete orders due to OneToOne relationship)
        deleted_dispatches = 0
        if dispatch_ids:
            deleted_dispatches, _ = Dispatch.objects.filter(id__in=dispatch_ids).delete()

        # Then delete corrections
        deleted_corrections, _ = corrections.delete()

        messages.success(
            request, 
            f"{deleted_corrections} correção(ões) e {deleted_dispatches} dispatch(es) deletado(s) com sucesso!"
        )
        
    except Exception as e:
        messages.error(request, f"Erro ao deletar registros: {str(e)}")
    
    return redirect("manualorders_paack:manual_management")


@login_required
@require_http_methods(["POST"])
def edit_manual_correction(request):
    """Edit an existing manual correction"""
    try:
        correction_id = request.POST.get('correction_id')
        driver_id = request.POST.get('driver_id')
        date = request.POST.get('date')
        status = request.POST.get('status')
        reason = request.POST.get('reason')

        if not all([correction_id, driver_id, date, status, reason]):
            messages.error(request, "Todos os campos são obrigatórios.")
            return redirect("manualorders_paack:manual_management")

        # Get the correction to edit
        correction = ManualCorrection.objects.select_related('dispatch', 'order').get(
            id=correction_id
        )

        # Get the driver
        driver = Driver.objects.get(driver_id=driver_id)

        # Update the order
        if correction.order:
            correction.order.status = status
            correction.order.simplified_order_status = status
            correction.order.save()

        # Update the dispatch
        if correction.dispatch:
            correction.dispatch.driver = driver
            correction.dispatch.save()

        # Update the correction record
        correction.driver = driver
        correction.correction_date = date
        correction.status = status
        correction.reason = reason
        correction.save()

        messages.success(request, f"Registro manual editado com sucesso!")
        
    except ManualCorrection.DoesNotExist:
        messages.error(request, "Registro não encontrado.")
    except Driver.DoesNotExist:
        messages.error(request, "Motorista não encontrado.")
    except Exception as e:
        messages.error(request, f"Erro ao editar registro: {str(e)}")
    
    return redirect("manualorders_paack:manual_management")


@login_required
def get_correction_data(request, correction_id):
    """Get correction data for editing via AJAX"""
    try:
        correction = ManualCorrection.objects.select_related('dispatch', 'order').get(
            id=correction_id
        )
        
        data = {
            'success': True,
            'driver_id': correction.driver.driver_id,
            'target_date': correction.correction_date.strftime('%Y-%m-%d') if correction.correction_date else '',
            'status': correction.status,
            'reason': correction.reason,
        }
        
        return JsonResponse(data)
        
    except ManualCorrection.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Registro não encontrado'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ========================
# MAIN ENTRY POINT
# ========================

@login_required
def manual_management(request):
    """Main entry point for manual management dashboard"""
    view = ManualOrdersDashboardView.as_view()
    return view(request)