from django import forms
from django.core.exceptions import ValidationError

from .models import (
    Bill, BillAttachment, CostCenter, ExpenseCategory, Expenses,
    Fornecedor, FornecedorTag, Imposto, Revenues,
)


class BillForm(forms.ModelForm):
    class Meta:
        model = Bill
        fields = [
            "description", "fornecedor",
            "supplier", "supplier_nif", "invoice_number",
            "category", "cost_center",
            "amount_net", "iva_rate", "amount_total",
            "issue_date", "due_date", "paid_date",
            "status", "recurrence",
            "paid_by_source", "paid_by_lender",
            "payment_method", "card_last4",
            "driver", "driver_advance_tipo",
            "notes",
        ]
        widgets = {
            "description": forms.TextInput(attrs={
                "class": "fld",
                "placeholder": "ex: Aluguer Setembro 2026",
            }),
            "fornecedor": forms.Select(attrs={
                "class": "fld",
                "data-fornecedor-select": "1",
            }),
            "supplier": forms.TextInput(attrs={
                "class": "fld",
                "placeholder": "Vazio se Fornecedor seleccionado acima",
            }),
            "supplier_nif": forms.TextInput(attrs={"class": "fld"}),
            "invoice_number": forms.TextInput(attrs={"class": "fld"}),
            "category": forms.Select(attrs={"class": "fld"}),
            "cost_center": forms.Select(attrs={"class": "fld"}),
            "amount_net": forms.NumberInput(attrs={
                "class": "fld", "step": "0.01", "min": "0",
            }),
            "iva_rate": forms.NumberInput(attrs={
                "class": "fld", "step": "0.01", "min": "0", "max": "30",
            }),
            "amount_total": forms.NumberInput(attrs={
                "class": "fld", "step": "0.01", "min": "0",
            }),
            "issue_date": forms.DateInput(
                attrs={"class": "fld", "type": "date"},
            ),
            "due_date": forms.DateInput(
                attrs={"class": "fld", "type": "date"},
            ),
            "paid_date": forms.DateInput(
                attrs={"class": "fld", "type": "date"},
            ),
            "status": forms.Select(attrs={"class": "fld"}),
            "recurrence": forms.Select(attrs={"class": "fld"}),
            "paid_by_source": forms.Select(attrs={
                "class": "fld",
                "data-paid-by-source": "1",
            }),
            "paid_by_lender": forms.Select(attrs={"class": "fld"}),
            "driver": forms.Select(attrs={
                "class": "fld",
                "data-bill-driver": "1",
            }),
            "driver_advance_tipo": forms.Select(attrs={"class": "fld"}),
            "payment_method": forms.Select(attrs={
                "class": "fld",
                "data-payment-method": "1",
            }),
            "card_last4": forms.TextInput(attrs={
                "class": "fld",
                "maxlength": "4",
                "pattern": r"\d{0,4}",
                "inputmode": "numeric",
                "placeholder": "ex: 9113",
            }),
            "notes": forms.Textarea(attrs={"class": "fld", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Limita driver dropdown a motoristas activos
        try:
            from drivers_app.models import DriverProfile
            self.fields["driver"].queryset = (
                DriverProfile.objects.filter(status="ATIVO")
                .order_by("nome_completo")
            )
            self.fields["driver"].empty_label = "— sem motorista —"
        except Exception:
            pass

    def clean(self):
        cleaned = super().clean()
        net = cleaned.get("amount_net") or 0
        total = cleaned.get("amount_total") or 0
        if total < net:
            raise ValidationError(
                "Valor com IVA não pode ser menor que valor sem IVA.",
            )
        status = cleaned.get("status")
        paid = cleaned.get("paid_date")
        if status == Bill.STATUS_PAID and not paid:
            raise ValidationError(
                "Conta marcada como paga precisa ter Data de Pagamento.",
            )
        # Pelo menos um dos dois (FK fornecedor ou string supplier)
        if not cleaned.get("fornecedor") and not (cleaned.get("supplier") or "").strip():
            raise ValidationError(
                "Indica um Fornecedor (cadastro) ou preenche o campo livre.",
            )
        # Se fornecedor (FK) está definido, copia dados em falta para os
        # campos legados (mantém retrocompatibilidade com queries antigas).
        f = cleaned.get("fornecedor")
        if f is not None:
            if not (cleaned.get("supplier") or "").strip():
                cleaned["supplier"] = f.name
            if not (cleaned.get("supplier_nif") or "").strip() and f.nif:
                cleaned["supplier_nif"] = f.nif
        # Se pago por sócio, lender é obrigatório
        if (
            cleaned.get("paid_by_source") == Bill.PAID_BY_SOURCE_TERCEIRO
            and not cleaned.get("paid_by_lender")
        ):
            self.add_error(
                "paid_by_lender",
                "Selecciona qual sócio adiantou o pagamento desta conta.",
            )
        # card_last4 só aceita dígitos. Se método != CARD, ignora qualquer
        # valor (limpa silenciosamente).
        last4 = (cleaned.get("card_last4") or "").strip()
        if cleaned.get("payment_method") != Bill.PAYMENT_METHOD_CARD:
            cleaned["card_last4"] = ""
        elif last4:
            import re
            digits = re.sub(r"\D", "", last4)
            if len(digits) > 4:
                digits = digits[-4:]
            if len(digits) != 4:
                self.add_error(
                    "card_last4",
                    "Os últimos 4 dígitos do cartão devem ter exactamente 4 dígitos.",
                )
            cleaned["card_last4"] = digits

        # Duplicado: (fornecedor, invoice_number) já existe?
        # Ignora se algum dos dois está vazio (factura sem nº é raro mas
        # legítimo, ex: recibo de café). Exclui o próprio em edição.
        f = cleaned.get("fornecedor")
        inv = (cleaned.get("invoice_number") or "").strip()
        if f and inv:
            qs = Bill.objects.filter(fornecedor=f, invoice_number=inv)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            existing = qs.first()
            if existing:
                self.add_error(
                    "invoice_number",
                    (
                        f"Já existe a Bill #{existing.id} para "
                        f"{f.name} com o nº de fatura '{inv}' "
                        f"(estado: {existing.get_status_display()}). "
                        f"Edita esse registo em vez de criar duplicado."
                    ),
                )
        return cleaned


class FornecedorForm(forms.ModelForm):
    """Cadastro / edição de Fornecedor."""

    class Meta:
        model = Fornecedor
        fields = [
            "name", "nif", "tipo", "tags",
            "default_categoria", "default_centro_custo",
            "default_iva_rate", "iva_dedutivel",
            "forma_pagamento", "iban", "mb_entidade", "mb_referencia",
            "recorrencia_default", "dia_vencimento",
            "data_inicio_contrato", "data_fim_contrato",
            "email", "telefone", "morada",
            "notas", "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "fld"}),
            "nif": forms.TextInput(attrs={
                "class": "fld", "maxlength": "20",
                "placeholder": "9 dígitos (PT) ou vazio",
            }),
            "tipo": forms.Select(attrs={"class": "fld"}),
            "tags": forms.SelectMultiple(attrs={
                "class": "fld", "data-fornecedor-tags": "1",
                "size": "5",
            }),
            "default_categoria": forms.Select(attrs={"class": "fld"}),
            "default_centro_custo": forms.Select(attrs={"class": "fld"}),
            "default_iva_rate": forms.NumberInput(attrs={
                "class": "fld", "step": "0.01", "min": "0", "max": "30",
            }),
            "iva_dedutivel": forms.CheckboxInput(),
            "forma_pagamento": forms.Select(attrs={"class": "fld"}),
            "iban": forms.TextInput(attrs={
                "class": "fld", "placeholder": "PT50 ...",
            }),
            "mb_entidade": forms.TextInput(attrs={
                "class": "fld", "placeholder": "5 dígitos",
            }),
            "mb_referencia": forms.TextInput(attrs={
                "class": "fld", "placeholder": "9-15 dígitos",
            }),
            "recorrencia_default": forms.Select(attrs={"class": "fld"}),
            "dia_vencimento": forms.NumberInput(attrs={
                "class": "fld", "min": "1", "max": "31",
            }),
            "data_inicio_contrato": forms.DateInput(attrs={
                "class": "fld", "type": "date",
            }),
            "data_fim_contrato": forms.DateInput(attrs={
                "class": "fld", "type": "date",
            }),
            "email": forms.EmailInput(attrs={"class": "fld"}),
            "telefone": forms.TextInput(attrs={"class": "fld"}),
            "morada": forms.Textarea(attrs={"class": "fld", "rows": 2}),
            "notas": forms.Textarea(attrs={"class": "fld", "rows": 2}),
            "is_active": forms.CheckboxInput(),
        }

    def clean_nif(self):
        nif = (self.cleaned_data.get("nif") or "").strip()
        if not nif:
            return ""
        # Unicidade: MySQL não suporta partial unique constraint, por isso
        # validamos aqui em Python (excluindo o próprio registo em edição).
        qs = Fornecedor.objects.filter(nif=nif)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError(
                f"Já existe outro fornecedor com NIF {nif} ({qs.first().name}).",
            )
        return nif

    def clean(self):
        cleaned = super().clean()
        forma = cleaned.get("forma_pagamento")
        # Coerência mínima: se forma=MULTIBANCO, sugere preencher entidade.
        if forma == Fornecedor.FORMA_MULTIBANCO:
            if not cleaned.get("mb_entidade"):
                self.add_error(
                    "mb_entidade",
                    "Preenche a entidade MB (forma de pagamento = Multibanco).",
                )
        return cleaned


class ImpostoForm(forms.ModelForm):
    """Form para criar imposto. Em modo PARCELADO, mostra campos extra
    para configurar a geração das prestações filhas.
    """
    # Campo só usado quando modalidade=PARCELADO no momento de criar
    # — não persiste no modelo, controla a geração de N parcelas.
    n_prestacoes = forms.IntegerField(
        label="Nº de Prestações", required=False, min_value=2, max_value=120,
        widget=forms.NumberInput(attrs={"class": "fld", "placeholder": "ex: 6"}),
        help_text="Para PARCELADO: gera N prestações filhas mensais.",
    )
    primeira_prestacao_em = forms.DateField(
        label="Vencimento da 1ª Prestação", required=False,
        widget=forms.DateInput(attrs={"class": "fld", "type": "date"}),
        help_text="As seguintes ficam mês-a-mês a partir desta data.",
    )

    class Meta:
        model = Imposto
        fields = [
            "nome", "tipo", "modalidade", "fornecedor",
            "periodo_ano", "periodo_mes",
            "valor",
            "mb_entidade", "mb_referencia", "guia_pagamento",
            "data_vencimento", "data_pagamento", "status",
            "notas",
        ]
        widgets = {
            "nome": forms.TextInput(attrs={
                "class": "fld",
                "placeholder": "ex: IVA Janeiro 2026",
            }),
            "tipo": forms.Select(attrs={"class": "fld"}),
            "modalidade": forms.Select(attrs={
                "class": "fld", "data-imposto-modalidade": "1",
            }),
            "fornecedor": forms.Select(attrs={"class": "fld"}),
            "periodo_ano": forms.NumberInput(attrs={
                "class": "fld", "min": "2020", "max": "2099",
            }),
            "periodo_mes": forms.NumberInput(attrs={
                "class": "fld", "min": "1", "max": "12",
            }),
            "valor": forms.NumberInput(attrs={
                "class": "fld", "step": "0.01", "min": "0",
            }),
            "mb_entidade": forms.TextInput(attrs={"class": "fld"}),
            "mb_referencia": forms.TextInput(attrs={"class": "fld"}),
            "guia_pagamento": forms.ClearableFileInput(attrs={"class": "fld"}),
            "data_vencimento": forms.DateInput(attrs={
                "class": "fld", "type": "date",
            }),
            "data_pagamento": forms.DateInput(attrs={
                "class": "fld", "type": "date",
            }),
            "status": forms.Select(attrs={"class": "fld"}),
            "notas": forms.Textarea(attrs={"class": "fld", "rows": 2}),
        }

    def clean(self):
        cleaned = super().clean()
        modalidade = cleaned.get("modalidade")
        is_create = self.instance.pk is None
        if modalidade == Imposto.MODALIDADE_PARCELADO and is_create:
            n = cleaned.get("n_prestacoes")
            primeira = cleaned.get("primeira_prestacao_em")
            if not n or n < 2:
                self.add_error(
                    "n_prestacoes",
                    "Indica o número de prestações (>= 2).",
                )
            if not primeira:
                self.add_error(
                    "primeira_prestacao_em",
                    "Indica a data de vencimento da primeira prestação.",
                )
        # Estado PAGO precisa de data de pagamento
        if cleaned.get("status") == Imposto.STATUS_PAGO and not cleaned.get(
            "data_pagamento"
        ):
            self.add_error(
                "data_pagamento",
                "Para marcar PAGO, preenche a data de pagamento.",
            )
        return cleaned


class ExpenseCategoryForm(forms.ModelForm):
    """Categoria de despesa (DRE)."""

    class Meta:
        model = ExpenseCategory
        fields = ["code", "name", "nature", "icon", "is_active", "sort_order"]
        widgets = {
            "code": forms.TextInput(attrs={
                "class": "fld",
                "placeholder": "ex: COMB, RENDA, PEC, INT",
            }),
            "name": forms.TextInput(attrs={"class": "fld"}),
            "nature": forms.Select(attrs={"class": "fld"}),
            "icon": forms.TextInput(attrs={
                "class": "fld",
                "placeholder": "ex: fuel, wrench, building, wifi",
            }),
            "is_active": forms.CheckboxInput(),
            "sort_order": forms.NumberInput(attrs={"class": "fld"}),
        }

    def clean_code(self):
        code = (self.cleaned_data.get("code") or "").strip().upper()
        if not code:
            raise ValidationError("Código obrigatório.")
        qs = ExpenseCategory.objects.filter(code=code)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError(
                f"Já existe categoria com código {code}.",
            )
        return code


class CostCenterForm(forms.ModelForm):
    """Cadastro / edição de Centro de Custo. HUB FK opcional."""

    class Meta:
        model = CostCenter
        fields = [
            "code", "name", "type", "cainiao_hub",
            "is_active", "notes",
        ]
        widgets = {
            "code": forms.TextInput(attrs={
                "class": "fld",
                "placeholder": "ex: HUB-AVEIRO, FROTA-1, ADMIN",
            }),
            "name": forms.TextInput(attrs={"class": "fld"}),
            "type": forms.Select(attrs={"class": "fld"}),
            "cainiao_hub": forms.Select(attrs={"class": "fld"}),
            "is_active": forms.CheckboxInput(),
            "notes": forms.Textarea(attrs={"class": "fld", "rows": 2}),
        }

    def clean_code(self):
        code = (self.cleaned_data.get("code") or "").strip().upper()
        if not code:
            raise ValidationError("Código obrigatório.")
        qs = CostCenter.objects.filter(code=code)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError(
                f"Já existe centro de custo com código {code}.",
            )
        return code


class FornecedorTagForm(forms.ModelForm):
    class Meta:
        model = FornecedorTag
        fields = ["name", "color", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "fld"}),
            "color": forms.TextInput(attrs={
                "class": "fld",
                "placeholder": "violet, emerald, amber, blue, red...",
            }),
            "is_active": forms.CheckboxInput(),
        }


class BillAttachmentForm(forms.ModelForm):
    class Meta:
        model = BillAttachment
        fields = ["kind", "file", "description"]
        widgets = {
            "kind": forms.Select(attrs={"class": "fld"}),
            "file": forms.ClearableFileInput(attrs={"class": "fld"}),
            "description": forms.TextInput(attrs={"class": "fld"}),
        }


class RevenueForm(forms.ModelForm):
    """Formulário para criar e editar receitas"""

    class Meta:
        model = Revenues
        fields = [
            "natureza",
            "valor_sem_iva",
            "valor_com_iva",
            "data_entrada",
            "fonte",
            "descricao",
            "referencia",
            "documento",
        ]
        widgets = {
            "natureza": forms.Select(attrs={"class": "form-control", "required": True}),
            "valor_sem_iva": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0",
                    "required": True,
                }
            ),
            "valor_com_iva": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0",
                    "required": True,
                }
            ),
            "data_entrada": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                    "required": True,
                }
            ),
            "fonte": forms.Select(attrs={"class": "form-control", "required": True}),
            "descricao": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Descrição detalhada da receita...",
                }
            ),
            "referencia": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Número de fatura, contrato, etc.",
                }
            ),
            "documento": forms.FileInput(
                attrs={
                    "class": "form-control",
                    "accept": ".pdf,.jpg,.jpeg,.png,.xlsx,.xls,.doc,.docx",
                }
            ),
        }
        labels = {
            "natureza": "Natureza da Receita",
            "valor_sem_iva": "Valor sem IVA (€)",
            "valor_com_iva": "Valor com IVA (€)",
            "data_entrada": "Data da Receita",
            "fonte": "Fonte da Receita",
            "descricao": "Descrição",
            "referencia": "Referência",
            "documento": "Documento Comprobativo",
        }

    def clean(self):
        cleaned_data = super().clean()
        valor_sem_iva = cleaned_data.get("valor_sem_iva")
        valor_com_iva = cleaned_data.get("valor_com_iva")

        if valor_sem_iva and valor_com_iva:
            if valor_com_iva < valor_sem_iva:
                raise ValidationError(
                    "O valor com IVA deve ser maior ou igual ao valor sem IVA."
                )

        return cleaned_data


class ExpenseForm(forms.ModelForm):
    """Formulário para criar e editar despesas"""

    class Meta:
        model = Expenses
        fields = [
            "natureza",
            "valor_sem_iva",
            "valor_com_iva",
            "data_entrada",
            "fonte",
            "descricao",
            "referencia",
            "documento",
            "pago",
            "data_pagamento",
        ]
        widgets = {
            "natureza": forms.Select(attrs={"class": "form-control", "required": True}),
            "valor_sem_iva": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0",
                    "required": True,
                }
            ),
            "valor_com_iva": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0",
                    "required": True,
                }
            ),
            "data_entrada": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                    "required": True,
                }
            ),
            "fonte": forms.Select(attrs={"class": "form-control", "required": True}),
            "descricao": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Descrição detalhada da despesa...",
                }
            ),
            "referencia": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Número de fatura, recibo, etc.",
                }
            ),
            "documento": forms.FileInput(
                attrs={
                    "class": "form-control",
                    "accept": ".pdf,.jpg,.jpeg,.png,.xlsx,.xls,.doc,.docx",
                }
            ),
            "pago": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "data_pagamento": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
        }
        labels = {
            "natureza": "Natureza da Despesa",
            "valor_sem_iva": "Valor sem IVA (€)",
            "valor_com_iva": "Valor com IVA (€)",
            "data_entrada": "Data da Despesa",
            "fonte": "Fonte da Despesa",
            "descricao": "Descrição",
            "referencia": "Referência",
            "documento": "Documento Comprobativo",
            "pago": "Já foi pago?",
            "data_pagamento": "Data do Pagamento",
        }

    def clean(self):
        cleaned_data = super().clean()
        valor_sem_iva = cleaned_data.get("valor_sem_iva")
        valor_com_iva = cleaned_data.get("valor_com_iva")
        pago = cleaned_data.get("pago")
        data_pagamento = cleaned_data.get("data_pagamento")

        if valor_sem_iva and valor_com_iva:
            if valor_com_iva < valor_sem_iva:
                raise ValidationError(
                    "O valor com IVA deve ser maior ou igual ao valor sem IVA."
                )

        if pago and not data_pagamento:
            raise ValidationError(
                "Se a despesa foi paga, deve informar a data do pagamento."
            )

        if not pago and data_pagamento:
            cleaned_data["data_pagamento"] = None

        return cleaned_data


class RevenueFilterForm(forms.Form):
    """Formulário para filtros na listagem de receitas"""

    search = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Buscar por descrição ou referência...",
            }
        ),
    )

    natureza = forms.ChoiceField(
        choices=[("", "Todas as naturezas")] + Revenues.NATUREZA_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    fonte = forms.ChoiceField(
        choices=[("", "Todas as fontes")] + Revenues.FONTE_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    data_inicio = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )

    data_fim = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )


class ExpenseFilterForm(forms.Form):
    """Formulário para filtros na listagem de despesas"""

    search = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Buscar por descrição ou referência...",
            }
        ),
    )

    natureza = forms.ChoiceField(
        choices=[("", "Todas as naturezas")] + Expenses.NATUREZA_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    fonte = forms.ChoiceField(
        choices=[("", "Todas as fontes")] + Expenses.FONTE_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    pago = forms.ChoiceField(
        choices=[("", "Todos"), ("true", "Pago"), ("false", "Pendente")],
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    data_inicio = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )

    data_fim = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
