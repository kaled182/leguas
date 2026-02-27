from django import forms
from django.core.exceptions import ValidationError
from .models import Revenues, Expenses


class RevenueForm(forms.ModelForm):
    """Formulário para criar e editar receitas"""
    
    class Meta:
        model = Revenues
        fields = [
            'natureza', 'valor_sem_iva', 'valor_com_iva', 'data_entrada',
            'fonte', 'descricao', 'referencia', 'documento'
        ]
        widgets = {
            'natureza': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'valor_sem_iva': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'required': True
            }),
            'valor_com_iva': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'required': True
            }),
            'data_entrada': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'required': True
            }),
            'fonte': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descrição detalhada da receita...'
            }),
            'referencia': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Número de fatura, contrato, etc.'
            }),
            'documento': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.jpeg,.png,.xlsx,.xls,.doc,.docx'
            })
        }
        labels = {
            'natureza': 'Natureza da Receita',
            'valor_sem_iva': 'Valor sem IVA (€)',
            'valor_com_iva': 'Valor com IVA (€)',
            'data_entrada': 'Data da Receita',
            'fonte': 'Fonte da Receita',
            'descricao': 'Descrição',
            'referencia': 'Referência',
            'documento': 'Documento Comprobativo'
        }
    
    def clean(self):
        cleaned_data = super().clean()
        valor_sem_iva = cleaned_data.get('valor_sem_iva')
        valor_com_iva = cleaned_data.get('valor_com_iva')
        
        if valor_sem_iva and valor_com_iva:
            if valor_com_iva < valor_sem_iva:
                raise ValidationError('O valor com IVA deve ser maior ou igual ao valor sem IVA.')
        
        return cleaned_data


class ExpenseForm(forms.ModelForm):
    """Formulário para criar e editar despesas"""
    
    class Meta:
        model = Expenses
        fields = [
            'natureza', 'valor_sem_iva', 'valor_com_iva', 'data_entrada',
            'fonte', 'descricao', 'referencia', 'documento', 'pago', 'data_pagamento'
        ]
        widgets = {
            'natureza': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'valor_sem_iva': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'required': True
            }),
            'valor_com_iva': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'required': True
            }),
            'data_entrada': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'required': True
            }),
            'fonte': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descrição detalhada da despesa...'
            }),
            'referencia': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Número de fatura, recibo, etc.'
            }),
            'documento': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.jpeg,.png,.xlsx,.xls,.doc,.docx'
            }),
            'pago': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'data_pagamento': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            })
        }
        labels = {
            'natureza': 'Natureza da Despesa',
            'valor_sem_iva': 'Valor sem IVA (€)',
            'valor_com_iva': 'Valor com IVA (€)',
            'data_entrada': 'Data da Despesa',
            'fonte': 'Fonte da Despesa',
            'descricao': 'Descrição',
            'referencia': 'Referência',
            'documento': 'Documento Comprobativo',
            'pago': 'Já foi pago?',
            'data_pagamento': 'Data do Pagamento'
        }
    
    def clean(self):
        cleaned_data = super().clean()
        valor_sem_iva = cleaned_data.get('valor_sem_iva')
        valor_com_iva = cleaned_data.get('valor_com_iva')
        pago = cleaned_data.get('pago')
        data_pagamento = cleaned_data.get('data_pagamento')
        
        if valor_sem_iva and valor_com_iva:
            if valor_com_iva < valor_sem_iva:
                raise ValidationError('O valor com IVA deve ser maior ou igual ao valor sem IVA.')
        
        if pago and not data_pagamento:
            raise ValidationError('Se a despesa foi paga, deve informar a data do pagamento.')
        
        if not pago and data_pagamento:
            cleaned_data['data_pagamento'] = None
        
        return cleaned_data


class RevenueFilterForm(forms.Form):
    """Formulário para filtros na listagem de receitas"""
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar por descrição ou referência...'
        })
    )
    
    natureza = forms.ChoiceField(
        choices=[('', 'Todas as naturezas')] + Revenues.NATUREZA_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    fonte = forms.ChoiceField(
        choices=[('', 'Todas as fontes')] + Revenues.FONTE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    data_inicio = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    data_fim = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )


class ExpenseFilterForm(forms.Form):
    """Formulário para filtros na listagem de despesas"""
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar por descrição ou referência...'
        })
    )
    
    natureza = forms.ChoiceField(
        choices=[('', 'Todas as naturezas')] + Expenses.NATUREZA_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    fonte = forms.ChoiceField(
        choices=[('', 'Todas as fontes')] + Expenses.FONTE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    pago = forms.ChoiceField(
        choices=[('', 'Todos'), ('true', 'Pago'), ('false', 'Pendente')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    data_inicio = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    data_fim = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )