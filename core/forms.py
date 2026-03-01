from django import forms

from .models import Partner, PartnerIntegration


class PartnerForm(forms.ModelForm):
    """Formulário para criar/editar parceiros"""

    class Meta:
        model = Partner
        fields = [
            "name",
            "nif",
            "contact_email",
            "contact_phone",
            "default_delivery_time_days",
            "auto_assign_orders",
            "is_active",
            "notes",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                    "placeholder": "Ex: Paack, Amazon Logistics, DPD",
                }
            ),
            "nif": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                    "placeholder": "PT123456789 ou 123456789",
                }
            ),
            "contact_email": forms.EmailInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                    "placeholder": "contato@parceiro.com",
                }
            ),
            "contact_phone": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                    "placeholder": "+351 912 345 678",
                }
            ),
            "default_delivery_time_days": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                    "min": "1",
                    "max": "10",
                }
            ),
            "auto_assign_orders": forms.CheckboxInput(
                attrs={
                    "class": "w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500 dark:focus:ring-blue-600 dark:ring-offset-gray-800 focus:ring-2 dark:bg-gray-700 dark:border-gray-600"
                }
            ),
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500 dark:focus:ring-blue-600 dark:ring-offset-gray-800 focus:ring-2 dark:bg-gray-700 dark:border-gray-600"
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                    "rows": "4",
                    "placeholder": "Observações internas sobre o parceiro...",
                }
            ),
        }


class PartnerIntegrationForm(forms.ModelForm):
    """Formulário para criar/editar integrações"""

    class Meta:
        model = PartnerIntegration
        fields = [
            "integration_type",
            "endpoint_url",
            "sync_frequency_minutes",
            "is_active",
        ]
        widgets = {
            "integration_type": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
                }
            ),
            "endpoint_url": forms.URLInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                    "placeholder": "https://api.partner.com/v1",
                }
            ),
            "sync_frequency_minutes": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                    "min": "5",
                    "max": "1440",
                }
            ),
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500 dark:focus:ring-blue-600 dark:ring-offset-gray-800 focus:ring-2 dark:bg-gray-700 dark:border-gray-600"
                }
            ),
        }
