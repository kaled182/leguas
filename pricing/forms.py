from django import forms

from .models import PartnerTariff, PostalZone


class PostalZoneForm(forms.ModelForm):
    """Formulário para criar/editar zonas postais"""

    class Meta:
        model = PostalZone
        fields = [
            "name",
            "code",
            "postal_code_pattern",
            "region",
            "center_latitude",
            "center_longitude",
            "is_urban",
            "average_delivery_time_hours",
            "is_active",
            "notes",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                    "placeholder": "Ex: Lisboa Centro, Porto Norte",
                }
            ),
            "code": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                    "placeholder": "Ex: LIS-CENTRO, PORTO-NORTE",
                }
            ),
            "postal_code_pattern": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white font-mono",
                    "placeholder": "^11\\d{2} (regex para Lisboa)",
                }
            ),
            "region": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
                }
            ),
            "center_latitude": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                    "step": "0.000001",
                    "placeholder": "38.736946",
                }
            ),
            "center_longitude": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                    "step": "0.000001",
                    "placeholder": "-9.142685",
                }
            ),
            "is_urban": forms.CheckboxInput(
                attrs={
                    "class": "w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500"
                }
            ),
            "average_delivery_time_hours": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                    "min": "1",
                }
            ),
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500"
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                    "rows": "3",
                }
            ),
        }


class PartnerTariffForm(forms.ModelForm):
    """Formulário para criar/editar tarifas"""

    class Meta:
        model = PartnerTariff
        fields = [
            "partner",
            "postal_zone",
            "base_price",
            "success_bonus",
            "failure_penalty",
            "late_delivery_penalty",
            "weekend_multiplier",
            "express_multiplier",
            "valid_from",
            "valid_until",
            "is_active",
            "notes",
        ]
        widgets = {
            "partner": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
                }
            ),
            "postal_zone": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
                }
            ),
            "base_price": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                    "step": "0.01",
                    "min": "0",
                }
            ),
            "success_bonus": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                    "step": "0.01",
                    "min": "0",
                }
            ),
            "failure_penalty": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                    "step": "0.01",
                    "min": "0",
                }
            ),
            "late_delivery_penalty": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                    "step": "0.01",
                    "min": "0",
                }
            ),
            "weekend_multiplier": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                    "step": "0.01",
                    "min": "0",
                }
            ),
            "express_multiplier": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                    "step": "0.01",
                    "min": "0",
                }
            ),
            "valid_from": forms.DateInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                    "type": "date",
                }
            ),
            "valid_until": forms.DateInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                    "type": "date",
                }
            ),
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500"
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                    "rows": "3",
                }
            ),
        }


class CSVUploadForm(forms.Form):
    """Formulário para upload de ficheiro CSV"""

    csv_file = forms.FileField(
        label="Ficheiro CSV",
        help_text="Selecione um ficheiro CSV para importar",
        widget=forms.FileInput(
            attrs={
                "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                "accept": ".csv",
            }
        ),
    )

    def clean_csv_file(self):
        """Valida que o ficheiro é CSV"""
        csv_file = self.cleaned_data.get("csv_file")

        if csv_file:
            # Verifica extensão
            if not csv_file.name.endswith(".csv"):
                raise forms.ValidationError("O ficheiro deve ter extensão .csv")

            # Verifica tamanho (máximo 5MB)
            if csv_file.size > 5 * 1024 * 1024:
                raise forms.ValidationError("O ficheiro não pode exceder 5MB")

        return csv_file
