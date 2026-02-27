from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .models import Revenues, Expenses
from .forms import RevenueForm, ExpenseForm
import json
from datetime import datetime, date

# Create your views here.

@login_required
def dashboard(request):
    """Dashboard principal com resumo de receitas e despesas"""
    # Resumo de receitas
    total_revenues = Revenues.objects.aggregate(Sum('valor_com_iva'))['valor_com_iva__sum'] or 0
    recent_revenues = Revenues.objects.order_by('-data_entrada')[:5]
    
    # Resumo de despesas
    total_expenses = Expenses.objects.aggregate(Sum('valor_com_iva'))['valor_com_iva__sum'] or 0
    recent_expenses = Expenses.objects.order_by('-data_entrada')[:5]
    
    # Despesas pendentes
    pending_expenses = Expenses.objects.filter(pago=False).count()
    
    context = {
        'total_revenues': total_revenues,
        'total_expenses': total_expenses,
        'balance': total_revenues - total_expenses,
        'recent_revenues': recent_revenues,
        'recent_expenses': recent_expenses,
        'pending_expenses': pending_expenses,
    }
    return render(request, 'accounting/dashboard.html', context)


# ===== VIEWS PARA RECEITAS =====

@login_required
def revenue_list(request):
    """Lista todas as receitas com filtros e paginação"""
    revenues = Revenues.objects.all().order_by('-data_entrada')
    
    # Filtros
    search = request.GET.get('search')
    natureza = request.GET.get('natureza')
    fonte = request.GET.get('fonte')
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    
    if search:
        revenues = revenues.filter(
            Q(descricao__icontains=search) | 
            Q(referencia__icontains=search)
        )
    
    if natureza:
        revenues = revenues.filter(natureza=natureza)
    
    if fonte:
        revenues = revenues.filter(fonte=fonte)
    
    if data_inicio:
        revenues = revenues.filter(data_entrada__gte=data_inicio)
    
    if data_fim:
        revenues = revenues.filter(data_entrada__lte=data_fim)
    
    # Paginação
    paginator = Paginator(revenues, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Total filtrado
    total_filtered = revenues.aggregate(Sum('valor_com_iva'))['valor_com_iva__sum'] or 0
    
    context = {
        'page_obj': page_obj,
        'revenues': page_obj,
        'total_filtered': total_filtered,
        'natureza_choices': Revenues.NATUREZA_CHOICES,
        'fonte_choices': Revenues.FONTE_CHOICES,
        'filters': {
            'search': search,
            'natureza': natureza,
            'fonte': fonte,
            'data_inicio': data_inicio,
            'data_fim': data_fim,
        }
    }
    return render(request, 'accounting/revenue_list.html', context)


@login_required
def revenue_create(request):
    """Criar nova receita"""
    if request.method == 'POST':
        form = RevenueForm(request.POST, request.FILES)
        if form.is_valid():
            revenue = form.save(commit=False)
            revenue.user = request.user
            revenue.save()
            messages.success(request, 'Receita criada com sucesso!')
            return redirect('accounting:revenue_detail', pk=revenue.pk)
    else:
        form = RevenueForm()
    
    return render(request, 'accounting/revenue_form.html', {
        'form': form,
        'title': 'Nova Receita'
    })


@login_required
def revenue_detail(request, pk):
    """Visualizar detalhes de uma receita"""
    revenue = get_object_or_404(Revenues, pk=pk)
    
    context = {
        'revenue': revenue,
    }
    return render(request, 'accounting/revenue_detail.html', context)


@login_required
def revenue_edit(request, pk):
    """Editar receita existente"""
    revenue = get_object_or_404(Revenues, pk=pk)
    
    if request.method == 'POST':
        form = RevenueForm(request.POST, request.FILES, instance=revenue)
        if form.is_valid():
            form.save()
            messages.success(request, 'Receita atualizada com sucesso!')
            return redirect('accounting:revenue_detail', pk=revenue.pk)
    else:
        form = RevenueForm(instance=revenue)
    
    return render(request, 'accounting/revenue_form.html', {
        'form': form,
        'revenue': revenue,
        'title': 'Editar Receita'
    })


@login_required
@require_http_methods(["DELETE"])
def revenue_delete(request, pk):
    """Deletar receita (via AJAX)"""
    revenue = get_object_or_404(Revenues, pk=pk)
    revenue.delete()
    return JsonResponse({'success': True})


# ===== VIEWS PARA DESPESAS =====

@login_required
def expense_list(request):
    """Lista todas as despesas com filtros e paginação"""
    expenses = Expenses.objects.all().order_by('-data_entrada')
    
    # Filtros
    search = request.GET.get('search')
    natureza = request.GET.get('natureza')
    fonte = request.GET.get('fonte')
    pago = request.GET.get('pago')
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    
    if search:
        expenses = expenses.filter(
            Q(descricao__icontains=search) | 
            Q(referencia__icontains=search)
        )
    
    if natureza:
        expenses = expenses.filter(natureza=natureza)
    
    if fonte:
        expenses = expenses.filter(fonte=fonte)
    
    if pago == 'true':
        expenses = expenses.filter(pago=True)
    elif pago == 'false':
        expenses = expenses.filter(pago=False)
    
    if data_inicio:
        expenses = expenses.filter(data_entrada__gte=data_inicio)
    
    if data_fim:
        expenses = expenses.filter(data_entrada__lte=data_fim)
    
    # Paginação
    paginator = Paginator(expenses, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Total filtrado
    total_filtered = expenses.aggregate(Sum('valor_com_iva'))['valor_com_iva__sum'] or 0
    total_pending = expenses.filter(pago=False).aggregate(Sum('valor_com_iva'))['valor_com_iva__sum'] or 0
    
    context = {
        'page_obj': page_obj,
        'expenses': page_obj,
        'total_filtered': total_filtered,
        'total_pending': total_pending,
        'natureza_choices': Expenses.NATUREZA_CHOICES,
        'fonte_choices': Expenses.FONTE_CHOICES,
        'filters': {
            'search': search,
            'natureza': natureza,
            'fonte': fonte,
            'pago': pago,
            'data_inicio': data_inicio,
            'data_fim': data_fim,
        }
    }
    return render(request, 'accounting/expense_list.html', context)


@login_required
def expense_create(request):
    """Criar nova despesa"""
    if request.method == 'POST':
        form = ExpenseForm(request.POST, request.FILES)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.user = request.user
            expense.save()
            messages.success(request, 'Despesa criada com sucesso!')
            return redirect('accounting:expense_detail', pk=expense.pk)
    else:
        form = ExpenseForm()
    
    return render(request, 'accounting/expense_form.html', {
        'form': form,
        'title': 'Nova Despesa'
    })


@login_required
def expense_detail(request, pk):
    """Visualizar detalhes de uma despesa"""
    expense = get_object_or_404(Expenses, pk=pk)
    
    context = {
        'expense': expense,
    }
    return render(request, 'accounting/expense_detail.html', context)


@login_required
def expense_edit(request, pk):
    """Editar despesa existente"""
    expense = get_object_or_404(Expenses, pk=pk)
    
    if request.method == 'POST':
        form = ExpenseForm(request.POST, request.FILES, instance=expense)
        if form.is_valid():
            form.save()
            messages.success(request, 'Despesa atualizada com sucesso!')
            return redirect('accounting:expense_detail', pk=expense.pk)
    else:
        form = ExpenseForm(instance=expense)
    
    return render(request, 'accounting/expense_form.html', {
        'form': form,
        'expense': expense,
        'title': 'Editar Despesa'
    })


@login_required
@require_http_methods(["DELETE"])
def expense_delete(request, pk):
    """Deletar despesa (via AJAX)"""
    expense = get_object_or_404(Expenses, pk=pk)
    expense.delete()
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def expense_toggle_payment(request, pk):
    """Alternar status de pagamento da despesa (via AJAX)"""
    expense = get_object_or_404(Expenses, pk=pk)
    
    if expense.pago:
        expense.pago = False
        expense.data_pagamento = None
    else:
        expense.pago = True
        expense.data_pagamento = date.today()
    
    expense.save()
    
    return JsonResponse({
        'success': True,
        'pago': expense.pago,
        'data_pagamento': expense.data_pagamento.strftime('%d/%m/%Y') if expense.data_pagamento else None,
        'status_text': expense.status_pagamento
    })


# ===== VIEWS DE RELATÓRIOS =====

@login_required
def reports(request):
    """Página de relatórios com gráficos e estatísticas"""
    # Dados para gráficos (últimos 12 meses)
    from django.db.models import Q
    from datetime import datetime, timedelta
    
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=365)
    
    revenues_by_month = []
    expenses_by_month = []
    
    # Você pode implementar lógica mais complexa aqui para gerar dados mensais
    
    context = {
        'revenues_by_month': revenues_by_month,
        'expenses_by_month': expenses_by_month,
    }
    return render(request, 'accounting/reports.html', context)
