from datetime import date

from django import forms

from .models import Order, OrderIncident


class OrderForm(forms.ModelForm):
    """Formulário para criar e editar pedidos."""

    class Meta:
        model = Order
        fields = [
            "partner",
            "external_reference",
            "recipient_name",
            "recipient_phone",
            "recipient_email",
            "recipient_address",
            "postal_code",
            "declared_value",
            "weight_kg",
            "scheduled_delivery",
            "delivery_window_start",
            "delivery_window_end",
            "special_instructions",
            "notes",
        ]
        widgets = {
            "partner": forms.Select(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 dark:bg-gray-700 dark:text-white"
                }
            ),
            "external_reference": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 dark:bg-gray-700 dark:text-white",
                    "placeholder": "Tracking code do parceiro",
                }
            ),
            "recipient_name": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 dark:bg-gray-700 dark:text-white",
                    "placeholder": "Nome completo do destinatário",
                }
            ),
            "recipient_phone": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 dark:bg-gray-700 dark:text-white",
                    "placeholder": "+351 910 000 000",
                }
            ),
            "recipient_email": forms.EmailInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 dark:bg-gray-700 dark:text-white",
                    "placeholder": "email@exemplo.com",
                }
            ),
            "recipient_address": forms.Textarea(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 dark:bg-gray-700 dark:text-white",
                    "rows": 3,
                    "placeholder": "Rua, número, andar, porta...",
                }
            ),
            "postal_code": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 dark:bg-gray-700 dark:text-white",
                    "placeholder": "4000-123",
                }
            ),
            "declared_value": forms.NumberInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 dark:bg-gray-700 dark:text-white",
                    "placeholder": "0.00",
                    "step": "0.01",
                }
            ),
            "weight_kg": forms.NumberInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 dark:bg-gray-700 dark:text-white",
                    "placeholder": "0.00",
                    "step": "0.01",
                }
            ),
            "scheduled_delivery": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 dark:bg-gray-700 dark:text-white",
                }
            ),
            "delivery_window_start": forms.TimeInput(
                attrs={
                    "type": "time",
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 dark:bg-gray-700 dark:text-white",
                }
            ),
            "delivery_window_end": forms.TimeInput(
                attrs={
                    "type": "time",
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 dark:bg-gray-700 dark:text-white",
                }
            ),
            "special_instructions": forms.Textarea(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 dark:bg-gray-700 dark:text-white",
                    "rows": 3,
                    "placeholder": "Instruções especiais de entrega (código porta, andar, etc.)",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 dark:bg-gray-700 dark:text-white",
                    "rows": 3,
                    "placeholder": "Observações internas...",
                }
            ),
        }
        labels = {
            "partner": "Parceiro",
            "external_reference": "Referência Externa",
            "recipient_name": "Nome do Destinatário",
            "recipient_phone": "Telefone",
            "recipient_email": "Email",
            "recipient_address": "Morada de Entrega",
            "postal_code": "Código Postal",
            "declared_value": "Valor Declarado (€)",
            "weight_kg": "Peso (kg)",
            "scheduled_delivery": "Data de Entrega",
            "delivery_window_start": "Janela - Início",
            "delivery_window_end": "Janela - Fim",
            "special_instructions": "Instruções Especiais",
            "notes": "Observações Internas",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Filtrar apenas parceiros ativos
        from core.models import Partner

        self.fields["partner"].queryset = Partner.objects.filter(
            is_active=True
        ).order_by("name")

        # Pré-preencher data de entrega com amanhã se for novo pedido
        if not self.instance.pk:
            from datetime import date, timedelta

            self.fields["scheduled_delivery"].initial = date.today() + timedelta(days=1)

    def clean_postal_code(self):
        """Validar formato do código postal."""
        postal_code = self.cleaned_data.get("postal_code")
        if postal_code:
            postal_code = postal_code.strip()
            # Adicionar hífen se não tiver
            if len(postal_code) == 7 and "-" not in postal_code:
                postal_code = f"{postal_code[:4]}-{postal_code[4:]}"
        return postal_code

    def clean(self):
        """Validações customizadas."""
        cleaned_data = super().clean()

        # Validar janela de entrega
        start = cleaned_data.get("delivery_window_start")
        end = cleaned_data.get("delivery_window_end")

        if start and end and start >= end:
            self.add_error(
                "delivery_window_end", "Fim da janela deve ser após o início"
            )

        # Validar data de entrega
        scheduled = cleaned_data.get("scheduled_delivery")
        if scheduled and scheduled < date.today():
            self.add_error(
                "scheduled_delivery", "Data de entrega não pode ser no passado"
            )

        return cleaned_data


class AssignDriverForm(forms.ModelForm):
    """Formulário para atribuir motorista a um pedido."""

    class Meta:
        model = Order
        fields = ["assigned_driver"]
        widgets = {
            "assigned_driver": forms.Select(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 dark:bg-gray-700 dark:text-white"
                }
            ),
        }
        labels = {
            "assigned_driver": "Motorista",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Filtrar apenas motoristas ativos
        from drivers_app.models import DriverProfile

        self.fields["assigned_driver"].queryset = DriverProfile.objects.filter(
            is_active=True
        ).order_by("nome_completo")


class OrderIncidentForm(forms.ModelForm):
    """Formulário para reportar incidentes em pedidos."""

    class Meta:
        model = OrderIncident
        fields = [
            "incident_type",
            "description",
            "resolution_notes",
        ]
        widgets = {
            "incident_type": forms.Select(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 dark:bg-gray-700 dark:text-white"
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 dark:bg-gray-700 dark:text-white",
                    "rows": 4,
                    "placeholder": "Descreva o incidente em detalhes...",
                }
            ),
            "resolution_notes": forms.Textarea(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 dark:bg-gray-700 dark:text-white",
                    "rows": 3,
                    "placeholder": "Como foi resolvido ou ações tomadas...",
                }
            ),
        }
        labels = {
            "incident_type": "Tipo de Incidente",
            "description": "Descrição",
            "resolution_notes": "Resolução",
        }
