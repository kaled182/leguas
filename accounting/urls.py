from django.urls import path
from . import views

app_name = 'accounting'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # URLs para Receitas
    path('receitas/', views.revenue_list, name='revenue_list'),
    path('receitas/nova/', views.revenue_create, name='revenue_create'),
    path('receitas/<int:pk>/', views.revenue_detail, name='revenue_detail'),
    path('receitas/<int:pk>/editar/', views.revenue_edit, name='revenue_edit'),
    path('receitas/<int:pk>/deletar/', views.revenue_delete, name='revenue_delete'),
    
    # URLs para Despesas
    path('despesas/', views.expense_list, name='expense_list'),
    path('despesas/nova/', views.expense_create, name='expense_create'),
    path('despesas/<int:pk>/', views.expense_detail, name='expense_detail'),
    path('despesas/<int:pk>/editar/', views.expense_edit, name='expense_edit'),
    path('despesas/<int:pk>/deletar/', views.expense_delete, name='expense_delete'),
    path('despesas/<int:pk>/toggle-pagamento/', views.expense_toggle_payment, name='expense_toggle_payment'),
    
    # Relatórios
    path('relatorios/', views.reports, name='reports'),
]