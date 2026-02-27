from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.shortcuts import render, redirect
from django.db.models import Q
from django.urls import reverse
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from customauth.models import DriverAccess
from .models import DriverProfile, DriverDocument, Vehicle, VehicleDocument
from datetime import datetime
import re
from ordersmanager_paack.models import Driver
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import datetime
import openpyxl
from openpyxl.utils import get_column_letter
from geopy.geocoders import Nominatim
import folium
import re
import json
from django.contrib.auth.decorators import login_required


# ===== HELPER FUNCTIONS =====

def serialize_driver_data(driver):
    """Serializa os dados do motorista para JSON"""
    return {
        'id': driver.id,
        'nome_completo': driver.nome_completo,
        'nif': driver.nif,
        'niss': driver.niss or '',
        'data_nascimento': driver.data_nascimento.strftime('%d/%m/%Y') if driver.data_nascimento else '',
        'data_nascimento_iso': driver.data_nascimento.strftime('%Y-%m-%d') if driver.data_nascimento else '',
        'nacionalidade': driver.nacionalidade or '',
        'email': driver.email,
        'telefone': driver.telefone or '',
        'endereco_completo': f"{driver.endereco_residencia or ''}, {driver.codigo_postal or ''} {driver.cidade or ''}".strip(),
        'tipo_vinculo': driver.tipo_vinculo,
        'nome_frota': driver.nome_frota or '',
        'status': driver.status,
        'approved_at': driver.approved_at.strftime('%d/%m/%Y %H:%M') if driver.approved_at else '',
        'approved_by': str(driver.approved_by) if driver.approved_by else '',
        'documents': [
            {
                'id': doc.id,
                'tipo_display': doc.get_tipo_documento_display(),
                'validade': doc.data_validade.strftime('%d/%m/%Y') if doc.data_validade else '',
                'url': doc.arquivo.url,
                'file_extension': doc.file_extension,
                'is_expired': doc.is_expired,
                'expiring_soon': doc.days_until_expiration <= 30 and doc.days_until_expiration > 0 if doc.days_until_expiration else False
            }
            for doc in driver.documents.all()
        ],
        'vehicles': [
            {
                'id': vehicle.id,
                'matricula': vehicle.matricula,
                'marca': vehicle.marca,
                'modelo': vehicle.modelo,
                'tipo_display': vehicle.get_tipo_veiculo_display(),
                'documents': [
                    {
                        'id': vdoc.id,
                        'tipo_display': vdoc.get_tipo_documento_display(),
                        'validade': vdoc.data_validade.strftime('%d/%m/%Y') if vdoc.data_validade else '',
                        'url': vdoc.arquivo.url,
                        'file_extension': vdoc.file_extension
                    }
                    for vdoc in vehicle.vehicle_documents.all()
                ]
            }
            for vehicle in driver.vehicles.all()
        ]
    }


# ===== VIEWS =====

def driver_dashboard_view(request):
    """
    Dashboard principal para motoristas autenticados.
    
    Mostra os pedidos do motorista com filtros por status e data.
    """
    # Verificar se é motorista autenticado
    if not request.session.get('is_driver_authenticated'):
        messages.error(request, 'Acesso negado. Faça login como motorista.')
        return redirect('customauth:login')
    
    try:
        driver_access_id = request.session.get('driver_access_id')
        driver_access = DriverAccess.objects.get(id=driver_access_id)
    except DriverAccess.DoesNotExist:
        messages.error(request, 'Motorista não encontrado.')
        return redirect('customauth:login')
    
    # Obter parâmetros de filtro
    status = request.GET.get('status', '')
    date_str = request.GET.get('date', '')
    today = timezone.now().date()
    
    # Usar data fornecida ou hoje
    if date_str:
        try:
            date = timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            date = today
    else:
        date = today
    
    # Obter rota do motorista
    route = driver_access.get_route()
    if not route:
        messages.warning(request, 'Nenhum motorista vinculado ao seu acesso.')
        orders_qs = []
        stats = {'to_attempt': 0, 'delivered': 0, 'failed': 0, 'total': 0}
    else:
        # Obter pedidos filtrados
        orders_qs = route.get_orders(date=date)
        if status:
            orders_qs = orders_qs.filter(simplified_order_status=status)
        
        # Calcular estatísticas
        stats = {
            'to_attempt': route.get_pending_count(date=date),
            'delivered': route.get_delivered_count(date=date),
            'failed': route.get_failed_count(date=date),
            'total': route.get_orders_count(date=date),
        }
    
    # Paginação
    paginator = Paginator(orders_qs, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Formatar dados dos pedidos
    orders = [
        {
            'order_id': order.order_id,
            'retailer': order.retailer,
            'client_address': order.client_address,
            'intended_delivery_date': order.intended_delivery_date,
            'status': order.simplified_order_status,
            'is_delivered': order.is_delivered,
            'is_failed': order.is_failed,
        }
        for order in page_obj.object_list
    ]
    
    context = {
        'welcome_name': driver_access.full_name,
        'orders': orders,
        'page_obj': page_obj,
        'stats': stats,
        'today': today,
        'selected_date': date,
        'selected_status': status,
        'driver_access': driver_access,
    }
    
    return render(request, 'drivers_app/driver_dashboard.html', context)

def driver_export_xlsx(request):
    """
    Exporta os pedidos do motorista para XLSX.
    """
    # Verificar autenticação
    if not request.session.get('is_driver_authenticated'):
        return JsonResponse({'error': 'Não autorizado'}, status=401)
    
    try:
        driver_access_id = request.session.get('driver_access_id')
        driver_access = DriverAccess.objects.get(id=driver_access_id)
        route = driver_access.get_route()
        
        if not route:
            return JsonResponse({'error': 'Motorista não vinculado'}, status=400)
        
        # Obter data do filtro
        date_str = request.GET.get('date', '')
        if date_str:
            try:
                date = timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                date = timezone.now().date()
        else:
            date = timezone.now().date()
        
        # Criar workbook
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="pedidos_{driver_access.first_name}_{date}.xlsx"'
        
        workbook = openpyxl.Workbook()
        worksheet = workbook.active
        worksheet.title = f'Pedidos {date}'
        
        # Headers
        headers = [
            'ID Pedido', 'Varejista', 'Endereço', 
            'Data Prevista', 'Status', 'Entregue', 'Falhado'
        ]
        
        for col_num, header in enumerate(headers, 1):
            cell = worksheet.cell(row=1, column=col_num)
            cell.value = header
            cell.font = openpyxl.styles.Font(bold=True)
        
        # Dados
        orders = route.get_orders(date=date)
        for row_num, order in enumerate(orders, 2):
            worksheet.cell(row=row_num, column=1, value=order.order_id)
            worksheet.cell(row=row_num, column=2, value=order.retailer)
            worksheet.cell(row=row_num, column=3, value=order.client_address)
            worksheet.cell(row=row_num, column=4, value=order.intended_delivery_date)
            worksheet.cell(row=row_num, column=5, value=order.simplified_order_status)
            worksheet.cell(row=row_num, column=6, value='Sim' if order.is_delivered else 'Não')
            worksheet.cell(row=row_num, column=7, value='Sim' if order.is_failed else 'Não')
        
        # Ajustar largura das colunas
        for column in worksheet.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)
            for cell in column:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
        
        workbook.save(response)
        return response
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def driver_logout_view(request):
    """
    Logout específico para motoristas.
    """
    # Limpar sessão do motorista
    request.session.pop('driver_access_id', None)
    request.session.pop('driver_name', None)
    request.session.pop('is_driver_authenticated', None)
    
    messages.success(request, 'Você foi desconectado com sucesso.')
    return redirect('customauth:login')


@csrf_exempt
@require_http_methods(["POST"])
def register_driver_typebot(request):
    """
    Endpoint API para registro de motoristas via Typebot.
    
    Recebe dados do Typebot e cria um registro de motorista pendente.
    
    Body JSON:
    {
        "nif": "123456789",
        "nome": "João Silva",
        "telefone": "+351911111111",
        "email": "joao@example.com"
    }
    
    Retorna JSON:
    - Sucesso: {"success": true, "driver_id": "ID"}
    - Erro: {"success": false, "error": "mensagem"}
    """
    try:
        # Parse JSON body
        data = json.loads(request.body)
        
        # Validar campos obrigatórios
        required_fields = ['nif', 'nome', 'telefone', 'email']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            return JsonResponse({
                'success': False,
                'error': f'Campos obrigatórios faltando: {", ".join(missing_fields)}'
            }, status=400)
        
        nif = data['nif'].strip()
        nome = data['nome'].strip()
        telefone = data['telefone'].strip()
        email = data['email'].strip().lower()
        
        # Validar NIF (9 dígitos)
        if not re.match(r'^\d{9}$', nif):
            return JsonResponse({
                'success': False,
                'error': 'NIF inválido. Deve conter exatamente 9 dígitos.'
            }, status=400)
        
        # Validar email
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            return JsonResponse({
                'success': False,
                'error': 'Email inválido.'
            }, status=400)
        
        # Verificar se NIF já existe
        if Driver.objects.filter(driver_id=nif).exists():
            return JsonResponse({
                'success': False,
                'error': 'Este NIF já está registrado no sistema.'
            }, status=409)
        
        # Criar Driver com status pendente
        driver = Driver.objects.create(
            driver_id=nif,
            name=nome,
            vehicle='PENDENTE',
            vehicle_norm='PENDENTE',
            is_active=False  # Inativo até aprovação manual
        )
        
        return JsonResponse({
            'success': True,
            'driver_id': driver.driver_id,
            'message': 'Cadastro recebido com sucesso! Aguarde aprovação da equipe.'
        }, status=201)
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'JSON inválido no corpo da requisição.'
        }, status=400)
    
    except Exception as e:
        # Log error (consider using proper logging in production)
        return JsonResponse({
            'success': False,
            'error': f'Erro ao processar cadastro: {str(e)}'
        }, status=500)

@require_http_methods(["GET", "POST"])
def public_driver_register(request):
    """
    Pagina publica de cadastro de motoristas (formulario web).
    
    GET: Renderiza formulario HTML
    POST: Processa cadastro e cria Driver pendente
    """
    if request.method == 'GET':
        # Renderizar formulario
        return render(request, 'drivers_app/driver_public_register.html', {
            'current_year': datetime.now().year
        })
    
    # POST - Processar formulario
    try:
        # Obter dados do formulario
        nif = request.POST.get('nif', '').strip()
        nome = request.POST.get('nome', '').strip()
        telefone = request.POST.get('telefone', '').strip()
        email = request.POST.get('email', '').strip().lower()
        terms_accepted = request.POST.get('terms') == 'on'
        
        # Validar campos obrigatorios
        if not all([nif, nome, telefone, email]):
            messages.error(request, 'Todos os campos sao obrigatorios.')
            return render(request, 'drivers_app/driver_public_register.html', {
                'current_year': datetime.now().year
            })
        
        # Validar termos
        if not terms_accepted:
            messages.error(request, 'Voce deve concordar com os termos para continuar.')
            return render(request, 'drivers_app/driver_public_register.html', {
                'current_year': datetime.now().year
            })
        
        # Validar NIF (9 digitos)
        if not re.match(r'^\d{9}$', nif):
            messages.error(request, 'NIF invalido. Deve conter exatamente 9 digitos numericos.')
            return render(request, 'drivers_app/driver_public_register.html', {
                'current_year': datetime.now().year
            })
        
        # Validar email
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            messages.error(request, 'Email invalido. Verifique o formato.')
            return render(request, 'drivers_app/driver_public_register.html', {
                'current_year': datetime.now().year
            })
        
        # Validar telefone
        if not re.match(r'^\+?[0-9]{9,15}$', telefone):
            messages.error(request, 'Telefone invalido. Use formato internacional (ex: +351911111111).')
            return render(request, 'drivers_app/driver_public_register.html', {
                'current_year': datetime.now().year
            })
        
        # Verificar se NIF ja existe
        if DriverProfile.objects.filter(nif=nif).exists():
            messages.error(request, 'Este NIF ja esta registrado no sistema. Entre em contato conosco se houver algum problema.')
            return render(request, 'drivers_app/driver_public_register.html', {
                'current_year': datetime.now().year
            })
        
        # Criar DriverProfile com status pendente
        driver_profile = DriverProfile.objects.create(
            nif=nif,
            nome_completo=nome,
            telefone=telefone,
            email=email,
            status='PENDENTE',
            is_active=False
        )
        
        # Mensagem de sucesso
        messages.success(
            request,
            f'Cadastro enviado com sucesso, {nome.split()[0]}! '
            f'Voce recebera um email em {email} com os proximos passos em ate 48 horas uteis. '
            f'Seu codigo de referencia e: {nif}. '
            f'Status atual: PENDENTE (aguardando analise da equipe).'
        )
        
        # Redirecionar para evitar reenvio ao atualizar
        return redirect('drivers_app:public_register')
        
    except Exception as e:
        messages.error(request, f'Erro ao processar cadastro: {str(e)}. Por favor, tente novamente ou entre em contato.')
        return render(request, 'drivers_app/driver_public_register.html', {
            'current_year': datetime.now().year
        })


@require_http_methods(["GET", "POST"])
def public_driver_register_full(request):
    """
    Formulario completo de cadastro de motoristas com todos os dados e documentos.
    Multiplos steps, uploads de arquivos e validacao completa.
    """
    if request.method == 'GET':
        return render(request, 'drivers_app/driver_public_register_full.html', {
            'current_year': datetime.now().year
        })
    
    # POST - Processar formulario completo
    try:
        # === VALIDAR TERMOS ===
        if not request.POST.get('terms'):
            messages.error(request, 'Voce deve concordar com os termos para continuar.')
            return redirect('drivers_app:public_register_full')
        
        # === A. DADOS PESSOAIS ===
        nif = request.POST.get('nif', '').strip()
        nome_completo = request.POST.get('nome_completo', '').strip()
        niss = request.POST.get('niss', '').strip()
        data_nascimento = request.POST.get('data_nascimento')
        nacionalidade = request.POST.get('nacionalidade', '').strip()
        telefone = request.POST.get('telefone', '').strip()
        email = request.POST.get('email', '').strip().lower()
        endereco_residencia = request.POST.get('endereco_residencia', '').strip()
        codigo_postal = request.POST.get('codigo_postal', '').strip()
        cidade = request.POST.get('cidade', '').strip()
        tipo_vinculo = request.POST.get('tipo_vinculo')
        nome_frota = request.POST.get('nome_frota', '').strip()
        
        # Validar campos obrigatorios
        if not all([nif, nome_completo, niss, data_nascimento, nacionalidade, telefone, email, 
                    endereco_residencia, codigo_postal, cidade, tipo_vinculo]):
            messages.error(request, 'Todos os campos obrigatorios devem ser preenchidos.')
            return redirect('drivers_app:public_register_full')
        
        # Validar NIF
        if not re.match(r'^\d{9}$', nif):
            messages.error(request, 'NIF invalido. Deve conter exatamente 9 digitos.')
            return redirect('drivers_app:public_register_full')
        
        # Validar NISS
        if not re.match(r'^\d{11}$', niss):
            messages.error(request, 'NISS invalido. Deve conter exatamente 11 digitos.')
            return redirect('drivers_app:public_register_full')
        
        # Verificar se NIF ja existe
        if DriverProfile.objects.filter(nif=nif).exists():
            messages.error(request, 'Este NIF ja esta registrado no sistema.')
            return redirect('drivers_app:public_register_full')
        
        # === CRIAR PERFIL DO MOTORISTA ===
        driver_profile = DriverProfile.objects.create(
            nif=nif,
            nome_completo=nome_completo,
            niss=niss,
            data_nascimento=data_nascimento,
            nacionalidade=nacionalidade,
            telefone=telefone,
            email=email,
            endereco_residencia=endereco_residencia,
            codigo_postal=codigo_postal,
            cidade=cidade,
            tipo_vinculo=tipo_vinculo,
            nome_frota=nome_frota if tipo_vinculo == 'PARCEIRO' else '',
            status='PENDENTE',
            is_active=False
        )
        
        # === B. PROCESSAR DOCUMENTOS DO MOTORISTA ===
        
        # Documento de Identificacao
        if 'doc_identificacao' in request.FILES:
            tipo_doc_id = request.POST.get('tipo_doc_id')
            validade_doc_id = request.POST.get('validade_doc_id') or None
            DriverDocument.objects.create(
                motorista=driver_profile,
                tipo_documento=tipo_doc_id,
                arquivo=request.FILES['doc_identificacao'],
                data_validade=validade_doc_id
            )
        
        # Carta de Conducao - Frente
        if 'cnh_frente' in request.FILES:
            categoria_cnh = request.POST.get('categoria_cnh', '').strip()
            validade_cnh = request.POST.get('validade_cnh')
            DriverDocument.objects.create(
                motorista=driver_profile,
                tipo_documento='CNH_FRENTE',
                arquivo=request.FILES['cnh_frente'],
                data_validade=validade_cnh,
                categoria_cnh=categoria_cnh
            )
        
        # Carta de Conducao - Verso
        if 'cnh_verso' in request.FILES:
            categoria_cnh = request.POST.get('categoria_cnh', '').strip()
            validade_cnh = request.POST.get('validade_cnh')
            DriverDocument.objects.create(
                motorista=driver_profile,
                tipo_documento='CNH_VERSO',
                arquivo=request.FILES['cnh_verso'],
                data_validade=validade_cnh,
                categoria_cnh=categoria_cnh
            )
        
        # Registo Criminal
        if 'registo_criminal' in request.FILES:
            DriverDocument.objects.create(
                motorista=driver_profile,
                tipo_documento='RC',
                arquivo=request.FILES['registo_criminal']
            )
        
        # Certificado ADR (Opcional)
        if 'certificado_adr' in request.FILES:
            DriverDocument.objects.create(
                motorista=driver_profile,
                tipo_documento='ADR',
                arquivo=request.FILES['certificado_adr']
            )
        
        # Declaracao de Atividade (apenas para DIRETO)
        if tipo_vinculo == 'DIRETO' and 'declaracao_atividade' in request.FILES:
            DriverDocument.objects.create(
                motorista=driver_profile,
                tipo_documento='DECLARACAO_ATIVIDADE',
                arquivo=request.FILES['declaracao_atividade']
            )
        
        # === C. DADOS DO VEICULO ===
        matricula = request.POST.get('matricula', '').strip().upper()
        marca = request.POST.get('marca', '').strip()
        modelo = request.POST.get('modelo', '').strip()
        tipo_veiculo = request.POST.get('tipo_veiculo')
        ano = request.POST.get('ano') or None
        
        if all([matricula, marca, modelo, tipo_veiculo]):
            # Criar veiculo
            vehicle = Vehicle.objects.create(
                motorista=driver_profile,
                matricula=matricula,
                marca=marca,
                modelo=modelo,
                tipo_veiculo=tipo_veiculo,
                ano=ano,
                is_active=True
            )
            
            # DUA
            if 'dua' in request.FILES:
                VehicleDocument.objects.create(
                    veiculo=vehicle,
                    tipo_documento='DUA',
                    arquivo=request.FILES['dua']
                )
            
            # IPO
            if 'ipo' in request.FILES:
                validade_ipo = request.POST.get('validade_ipo') or None
                VehicleDocument.objects.create(
                    veiculo=vehicle,
                    tipo_documento='IPO',
                    arquivo=request.FILES['ipo'],
                    data_validade=validade_ipo
                )
            
            # Seguro
            if 'seguro' in request.FILES:
                validade_seguro = request.POST.get('validade_seguro')
                VehicleDocument.objects.create(
                    veiculo=vehicle,
                    tipo_documento='SEGURO',
                    arquivo=request.FILES['seguro'],
                    data_validade=validade_seguro
                )
        
        # === MENSAGEM DE SUCESSO ===
        messages.success(
            request,
            f'Cadastro completo enviado com sucesso, {nome_completo.split()[0]}! '
            f'Voce recebera um email em {email} com os proximos passos em ate 48 horas uteis. '
            f'Seu codigo de referencia e: {nif}. '
            f'Status atual: PENDENTE (aguardando analise da equipe).'
        )
        
        # Atualizar status para EM_ANALISE se todos os documentos foram enviados
        if driver_profile.documents.count() >= 4:  # Minimo de docs esperados
            driver_profile.status = 'EM_ANALISE'
            driver_profile.save()
        
        return redirect('drivers_app:public_register_full')
        
    except Exception as e:
        messages.error(request, f'Erro ao processar cadastro: {str(e)}. Por favor, tente novamente.')
        return redirect('drivers_app:public_register_full')


# === VIEWS ADMINISTRATIVAS ===

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q as QueryQ

@login_required
def admin_create_driver(request):
    """
    Pagina administrativa para criar motorista ou frota diretamente (sem formulario publico).
    Acesso apenas para equipe interna autenticada.
    """
    if request.method == 'POST':
        try:
            # Criar perfil
            nif = request.POST.get('nif', '').strip()
            nome_completo = request.POST.get('nome_completo', '').strip()
            email = request.POST.get('email', '').strip().lower()
            telefone = request.POST.get('telefone', '').strip()
            tipo_vinculo = request.POST.get('tipo_vinculo', 'DIRETO')
            nome_frota = request.POST.get('nome_frota', '').strip()
            
            # Validar NIF unico
            if DriverProfile.objects.filter(nif=nif).exists():
                messages.error(request, f'NIF {nif} ja cadastrado no sistema.')
                return redirect('drivers_app:admin_create_driver')
            
            # Criar perfil com status ATIVO (criacao interna ja e aprovada)
            driver_profile = DriverProfile.objects.create(
                nif=nif,
                nome_completo=nome_completo,
                email=email,
                telefone=telefone,
                tipo_vinculo=tipo_vinculo,
                nome_frota=nome_frota if tipo_vinculo == 'PARCEIRO' else '',
                status='ATIVO',
                is_active=True,
                approved_at=timezone.now(),
                approved_by=request.user.username
            )
            
            messages.success(request, f'Motorista {nome_completo} criado com sucesso! Status: ATIVO')
            return redirect('drivers_app:admin_active_drivers')
            
        except Exception as e:
            messages.error(request, f'Erro ao criar motorista: {str(e)}')
            return redirect('drivers_app:admin_create_driver')
    
    return render(request, 'drivers_app/admin_create_driver.html', {
        'current_year': datetime.now().year
    })


@login_required
def admin_approve_drivers(request):
    """
    Area para aprovacao de motoristas pendentes e em analise.
    Permite visualizar documentos, aprovar ou rejeitar cadastros.
    """
    # Filtrar motoristas pendentes e em analise
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('q', '')
    
    drivers = DriverProfile.objects.filter(
        status__in=['PENDENTE', 'EM_ANALISE']
    ).select_related().prefetch_related('documents', 'vehicles')
    
    if status_filter:
        drivers = drivers.filter(status=status_filter)
    
    if search_query:
        drivers = drivers.filter(
            Q(nif__icontains=search_query) |
            Q(nome_completo__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    drivers = drivers.order_by('-created_at')
    
    # Paginacao
    paginator = Paginator(drivers, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Contadores
    total_pendentes = DriverProfile.objects.filter(status='PENDENTE').count()
    total_em_analise = DriverProfile.objects.filter(status='EM_ANALISE').count()
    
    return render(request, 'drivers_app/admin_approve_drivers.html', {
        'page_obj': page_obj,
        'total_pendentes': total_pendentes,
        'total_em_analise': total_em_analise,
        'status_filter': status_filter,
        'search_query': search_query
    })


@login_required
def admin_approve_driver_action(request, driver_id):
    """
    Acao para aprovar ou rejeitar um motorista.
    POST com action=approve ou action=reject
    """
    if request.method != 'POST':
        return redirect('drivers_app:admin_approve_drivers')
    
    try:
        driver = DriverProfile.objects.get(id=driver_id)
        action = request.POST.get('action')
        
        if action == 'approve':
            driver.status = 'ATIVO'
            driver.is_active = True
            driver.approved_at = timezone.now()
            driver.approved_by = request.user.username
            driver.save()
            messages.success(request, f'Motorista {driver.nome_completo} aprovado com sucesso!')
            
        elif action == 'reject':
            observacao = request.POST.get('observacao', 'Cadastro rejeitado pela equipe')
            driver.status = 'IRREGULAR'
            driver.is_active = False
            driver.observacoes = observacao
            driver.save()
            messages.warning(request, f'Motorista {driver.nome_completo} rejeitado.')
            
        return redirect('drivers_app:admin_approve_drivers')
        
    except DriverProfile.DoesNotExist:
        messages.error(request, 'Motorista nao encontrado.')
        return redirect('drivers_app:admin_approve_drivers')


@login_required
def admin_active_drivers(request):
    """
    Lista de motoristas aprovados e ativos.
    Permite buscar, filtrar e gerenciar motoristas ativos.
    """
    search_query = request.GET.get('q', '')
    tipo_vinculo = request.GET.get('tipo_vinculo', '')
    status_filter = request.GET.get('status_filter', '')
    
    # Filtro base - mostrar motoristas aprovados (ATIVO, BLOQUEADO, IRREGULAR)
    # Excluir apenas PENDENTE e EM_ANALISE
    drivers = DriverProfile.objects.exclude(
        status__in=['PENDENTE', 'EM_ANALISE']
    ).select_related().prefetch_related('documents', 'vehicles')
    
    # Filtro de status específico
    if status_filter:
        drivers = drivers.filter(status=status_filter)
    
    if search_query:
        drivers = drivers.filter(
            Q(nif__icontains=search_query) |
            Q(nome_completo__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(telefone__icontains=search_query)
        )
    
    if tipo_vinculo:
        drivers = drivers.filter(tipo_vinculo=tipo_vinculo)
    
    drivers = drivers.order_by('-approved_at')
    
    # Paginacao
    paginator = Paginator(drivers, 30)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Estatisticas
    total_ativos = DriverProfile.objects.filter(status='ATIVO', is_active=True).count()
    total_diretos = DriverProfile.objects.filter(status='ATIVO', tipo_vinculo='DIRETO').count()
    total_parceiros = DriverProfile.objects.filter(status='ATIVO', tipo_vinculo='PARCEIRO').count()
    
    # Alertas de documentos proximos a vencer
    drivers_with_expiring_docs = []
    for driver in drivers[:10]:  # Verificar primeiros 10
        expiring = driver.get_documents_expiring_soon(days=30)
        if expiring.exists():
            drivers_with_expiring_docs.append({
                'driver': driver,
                'docs': expiring
            })
    
    return render(request, 'drivers_app/admin_active_drivers.html', {
        'page_obj': page_obj,
        'total_ativos': total_ativos,
        'total_diretos': total_diretos,
        'total_parceiros': total_parceiros,
        'drivers_with_expiring_docs': drivers_with_expiring_docs,
        'search_query': search_query,
        'tipo_vinculo': tipo_vinculo,
        'status_filter': status_filter
    })


# === VIEWS DE GESTÃO DE MOTORISTAS ATIVOS ===

@login_required
@require_http_methods(["POST"])
def admin_edit_driver_personal(request, driver_id):
    """Editar dados pessoais de um motorista"""
    try:
        driver = DriverProfile.objects.get(id=driver_id)
        
        driver.nif = request.POST.get('nif', driver.nif)
        driver.niss = request.POST.get('niss', driver.niss)
        driver.nome_completo = request.POST.get('nome_completo', driver.nome_completo)
        driver.data_nascimento = request.POST.get('data_nascimento') or driver.data_nascimento
        driver.nacionalidade = request.POST.get('nacionalidade', driver.nacionalidade)
        driver.email = request.POST.get('email', driver.email)
        driver.telefone = request.POST.get('telefone', driver.telefone)
        
        # Parse endereço completo (simplificado)
        endereco = request.POST.get('endereco', '')
        if endereco:
            driver.endereco_residencia = endereco
        
        driver.save()
        messages.success(request, f'Dados pessoais de {driver.nome_completo} atualizados com sucesso!')
        
    except DriverProfile.DoesNotExist:
        messages.error(request, 'Motorista não encontrado.')
    except Exception as e:
        messages.error(request, f'Erro ao atualizar dados: {str(e)}')
    
    # Se for AJAX, retornar JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        driver = DriverProfile.objects.filter(id=driver_id).first()
        if driver:
            return JsonResponse({
                'success': True,
                'message': f'Dados atualizados com sucesso!',
                'driver_id': driver.id,
                'driver_data': serialize_driver_data(driver)
            })
        return JsonResponse({'success': False, 'message': 'Erro ao atualizar'}, status=400)
    
    return redirect('drivers_app:admin_active_drivers')


@login_required
def admin_get_driver_data(request, driver_id):
    """API para obter dados atualizados do motorista"""
    try:
        driver = DriverProfile.objects.get(id=driver_id)
        return JsonResponse(serialize_driver_data(driver))
    except DriverProfile.DoesNotExist:
        return JsonResponse({'error': 'Motorista não encontrado'}, status=404)


@login_required
@require_http_methods(["POST"])
def admin_edit_driver_professional(request, driver_id):
    """Editar dados profissionais de um motorista"""
    try:
        driver = DriverProfile.objects.get(id=driver_id)
        
        driver.tipo_vinculo = request.POST.get('tipo_vinculo', driver.tipo_vinculo)
        driver.nome_frota = request.POST.get('nome_frota', driver.nome_frota)
        
        driver.save()
        messages.success(request, f'Dados profissionais de {driver.nome_completo} atualizados!')
        
    except DriverProfile.DoesNotExist:
        messages.error(request, 'Motorista não encontrado.')
    except Exception as e:
        messages.error(request, f'Erro ao atualizar: {str(e)}')
    
    # Se for AJAX, retornar JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        driver = DriverProfile.objects.filter(id=driver_id).first()
        if driver:
            return JsonResponse({
                'success': True,
                'message': 'Dados profissionais atualizados!',
                'driver_id': driver.id,
                'driver_data': serialize_driver_data(driver)
            })
        return JsonResponse({'success': False, 'message': 'Erro'}, status=400)
    
    return redirect('drivers_app:admin_active_drivers')


@login_required
@require_http_methods(["POST"])
def admin_attach_document(request, driver_id):
    """Anexar novo documento a um motorista"""
    try:
        driver = DriverProfile.objects.get(id=driver_id)
        
        tipo_documento = request.POST.get('tipo_documento')
        data_validade = request.POST.get('data_validade') or None
        arquivo = request.FILES.get('arquivo')
        
        if not arquivo:
            messages.error(request, 'Nenhum arquivo foi enviado.')
            return redirect('drivers_app:admin_active_drivers')
        
        DriverDocument.objects.create(
            motorista=driver,
            tipo_documento=tipo_documento,
            arquivo=arquivo,
            data_validade=data_validade
        )
        
        messages.success(request, f'Documento "{DriverDocument.TIPO_DOCUMENTO_CHOICES[0][1]}" anexado com sucesso!')
        
    except DriverProfile.DoesNotExist:
        messages.error(request, 'Motorista não encontrado.')
    except Exception as e:
        messages.error(request, f'Erro ao anexar documento: {str(e)}')
    
    # Se for AJAX, retornar JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        driver = DriverProfile.objects.filter(id=driver_id).first()
        if driver:
            return JsonResponse({
                'success': True,
                'message': 'Documento anexado com sucesso!',
                'driver_id': driver.id,
                'driver_data': serialize_driver_data(driver)
            })
        return JsonResponse({'success': False, 'message': 'Erro ao anexar'}, status=400)
    
    return redirect('drivers_app:admin_active_drivers')


@login_required
@require_http_methods(["POST"])
def admin_delete_document(request, document_id):
    """Deletar documento de motorista"""
    try:
        documento = DriverDocument.objects.get(id=document_id)
        tipo = documento.get_tipo_documento_display()
        
        # Deletar arquivo físico
        if documento.arquivo:
            documento.arquivo.delete()
        
        documento.delete()
        messages.success(request, f'Documento "{tipo}" deletado com sucesso!')
        driver_id = documento.motorista.id
        
    except DriverDocument.DoesNotExist:
        messages.error(request, 'Documento não encontrado.')
        driver_id = None
    except Exception as e:
        messages.error(request, f'Erro ao deletar documento: {str(e)}')
        driver_id = None
    
    # Se for AJAX, retornar JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and driver_id:
        driver = DriverProfile.objects.filter(id=driver_id).first()
        if driver:
            return JsonResponse({
                'success': True,
                'message': f'Documento "{tipo}" deletado!',
                'driver_id': driver.id,
                'driver_data': serialize_driver_data(driver)
            })
    
    return redirect('drivers_app:admin_active_drivers')


@login_required
@require_http_methods(["POST"])
def admin_add_vehicle(request, driver_id):
    """Adicionar novo veículo a um motorista"""
    try:
        driver = DriverProfile.objects.get(id=driver_id)
        
        matricula = request.POST.get('matricula', '').strip().upper()
        marca = request.POST.get('marca', '').strip()
        modelo = request.POST.get('modelo', '').strip()
        tipo_veiculo = request.POST.get('tipo_veiculo')
        ano = request.POST.get('ano') or None
        
        # Verificar se matrícula já existe
        if Vehicle.objects.filter(matricula=matricula).exists():
            messages.error(request, f'A matrícula {matricula} já está cadastrada.')
            return redirect('drivers_app:admin_active_drivers')
        
        Vehicle.objects.create(
            motorista=driver,
            matricula=matricula,
            marca=marca,
            modelo=modelo,
            tipo_veiculo=tipo_veiculo,
            ano=ano,
            is_active=True
        )
        
        messages.success(request, f'Veículo {matricula} ({marca} {modelo}) adicionado com sucesso!')
        
    except DriverProfile.DoesNotExist:
        messages.error(request, 'Motorista não encontrado.')
    except Exception as e:
        messages.error(request, f'Erro ao adicionar veículo: {str(e)}')
    
    # Se for AJAX, retornar JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        driver = DriverProfile.objects.filter(id=driver_id).first()
        if driver:
            return JsonResponse({
                'success': True,
                'message': 'Veículo adicionado com sucesso!',
                'driver_id': driver.id,
                'driver_data': serialize_driver_data(driver)
            })
        return JsonResponse({'success': False, 'message': 'Erro'}, status=400)
    
    return redirect('drivers_app:admin_active_drivers')


@login_required
@require_http_methods(["POST"])
def admin_delete_vehicle(request, vehicle_id):
    """Deletar veículo de motorista"""
    try:
        veiculo = Vehicle.objects.get(id=vehicle_id)
        matricula = veiculo.matricula
        
        # Deletar documentos do veículo
        for doc in veiculo.vehicle_documents.all():
            if doc.arquivo:
                doc.arquivo.delete()
        
        veiculo.delete()
        messages.success(request, f'Veículo {matricula} deletado com sucesso!')
        driver_id = veiculo.motorista.id
        
    except Vehicle.DoesNotExist:
        messages.error(request, 'Veículo não encontrado.')
        driver_id = None
    except Exception as e:
        messages.error(request, f'Erro ao deletar veículo: {str(e)}')
        driver_id = None
    
    # Se for AJAX, retornar JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and driver_id:
        driver = DriverProfile.objects.filter(id=driver_id).first()
        if driver:
            return JsonResponse({
                'success': True,
                'message': f'Veículo {matricula} deletado!',
                'driver_id': driver.id,
                'driver_data': serialize_driver_data(driver)
            })
    
    return redirect('drivers_app:admin_active_drivers')


@login_required
@require_http_methods(["POST"])
def admin_delete_vehicle_document(request, document_id):
    """Deletar documento de veículo"""
    try:
        documento = VehicleDocument.objects.get(id=document_id)
        tipo = documento.get_tipo_documento_display()
        
        if documento.arquivo:
            documento.arquivo.delete()
        
        documento.delete()
        messages.success(request, f'Documento "{tipo}" do veículo deletado!')
        
    except VehicleDocument.DoesNotExist:
        messages.error(request, 'Documento não encontrado.')
    except Exception as e:
        messages.error(request, f'Erro ao deletar: {str(e)}')
    
    return redirect('drivers_app:admin_active_drivers')


@login_required
@require_http_methods(["POST"])
def admin_deactivate_driver(request, driver_id):
    """Desativar motorista"""
    try:
        driver = DriverProfile.objects.get(id=driver_id)
        
        driver.status = 'BLOQUEADO'
        driver.is_active = False
        driver.observacoes = f'Desativado por {request.user.username} em {timezone.now().strftime("%d/%m/%Y %H:%M")}'
        driver.save()
        
        messages.warning(request, f'Motorista {driver.nome_completo} desativado.')
        
    except DriverProfile.DoesNotExist:
        messages.error(request, 'Motorista não encontrado.')
    except Exception as e:
        messages.error(request, f'Erro ao desativar: {str(e)}')
    
    return redirect('drivers_app:admin_active_drivers')


@login_required
@require_http_methods(["POST"])
def admin_activate_driver(request, driver_id):
    """Ativar motorista (reverter bloqueio)"""
    try:
        driver = DriverProfile.objects.get(id=driver_id)
        
        driver.status = 'ATIVO'
        driver.is_active = True
        driver.observacoes = f'Reativado por {request.user.username} em {timezone.now().strftime("%d/%m/%Y %H:%M")}'
        driver.save()
        
        messages.success(request, f'Motorista {driver.nome_completo} reativado com sucesso!')
        
    except DriverProfile.DoesNotExist:
        messages.error(request, 'Motorista não encontrado.')
    except Exception as e:
        messages.error(request, f'Erro ao ativar: {str(e)}')
    
    return redirect('drivers_app:admin_active_drivers')


@login_required
@require_http_methods(["POST"])
def admin_delete_driver(request, driver_id):
    """Excluir permanentemente um motorista e todos os seus dados"""
    try:
        driver = DriverProfile.objects.get(id=driver_id)
        nome = driver.nome_completo
        
        # Deletar todos os arquivos de documentos
        for doc in driver.documents.all():
            if doc.arquivo:
                doc.arquivo.delete()
        
        # Deletar todos os arquivos de documentos de veículos
        for vehicle in driver.vehicles.all():
            for vdoc in vehicle.vehicle_documents.all():
                if vdoc.arquivo:
                    vdoc.arquivo.delete()
        
        # Django vai deletar em cascata: documents, vehicles, vehicle_documents
        driver.delete()
        
        messages.success(request, f'Motorista {nome} e todos os seus dados foram excluídos permanentemente.')
        
    except DriverProfile.DoesNotExist:
        messages.error(request, 'Motorista não encontrado.')
    except Exception as e:
        messages.error(request, f'Erro ao excluir: {str(e)}')
    
    return redirect('drivers_app:admin_active_drivers')
