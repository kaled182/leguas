from django import forms

from .models import DriverShift


class DriverShiftForm(forms.ModelForm):
    """Formulário para criação e edição de turnos de motoristas."""

    class Meta:
        model = DriverShift
        fields = [
            "driver",
            "date",
            "assigned_postal_zones",
            "start_time",
            "end_time",
            "status",
            "notes",
        ]
        widgets = {
            "driver": forms.Select(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-amber-500 focus:ring-amber-500 dark:bg-gray-700 dark:text-white"
                }
            ),
            "date": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-amber-500 focus:ring-amber-500 dark:bg-gray-700 dark:text-white",
                }
            ),
            "assigned_postal_zones": forms.SelectMultiple(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-amber-500 focus:ring-amber-500 dark:bg-gray-700 dark:text-white",
                    "size": "8",
                }
            ),
            "start_time": forms.TimeInput(
                attrs={
                    "type": "time",
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-amber-500 focus:ring-amber-500 dark:bg-gray-700 dark:text-white",
                }
            ),
            "end_time": forms.TimeInput(
                attrs={
                    "type": "time",
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-amber-500 focus:ring-amber-500 dark:bg-gray-700 dark:text-white",
                }
            ),
            "status": forms.Select(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-amber-500 focus:ring-amber-500 dark:bg-gray-700 dark:text-white"
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-amber-500 focus:ring-amber-500 dark:bg-gray-700 dark:text-white",
                    "rows": 4,
                    "placeholder": "Notas sobre o turno...",
                }
            ),
        }
        labels = {
            "driver": "Motorista",
            "date": "Data do Turno",
            "assigned_postal_zones": "Zonas Postais Atribuídas",
            "start_time": "Hora de Início",
            "end_time": "Hora de Fim",
            "status": "Estado",
            "notes": "Notas",
        }
        help_texts = {
            "assigned_postal_zones": "Selecione as zonas onde o motorista deve fazer entregas (Ctrl/Cmd + clique para múltiplas seleções)",
            "start_time": "Hora de início prevista do turno",
            "end_time": "Hora de fim prevista do turno",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Filtrar apenas motoristas ativos
        from drivers_app.models import DriverProfile

        self.fields["driver"].queryset = DriverProfile.objects.filter(is_active=True)

        # Filtrar apenas zonas ativas
        from pricing.models import PostalZone

        self.fields["assigned_postal_zones"].queryset = PostalZone.objects.filter(
            is_active=True
        ).order_by("code")

        # Se for edição e turno já iniciado, desabilitar alguns campos
        if (
            self.instance
            and self.instance.pk
            and self.instance.status in ["IN_PROGRESS", "COMPLETED"]
        ):
            self.fields["driver"].disabled = True
            self.fields["date"].disabled = True

    def clean(self):
        """Validações customizadas."""
        cleaned_data = super().clean()
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")
        driver = cleaned_data.get("driver")
        date = cleaned_data.get("date")

        # Validar horários
        if start_time and end_time:
            if start_time >= end_time:
                self.add_error("end_time", "Hora de fim deve ser após hora de início.")

        # Verificar se motorista já tem turno nesta data (apenas para novo turno)
        if driver and date and not self.instance.pk:
            existing = DriverShift.objects.filter(driver=driver, date=date).exists()
            if existing:
                self.add_error(
                    "driver",
                    f'{driver.nome_completo} já tem um turno agendado para {date.strftime("%d/%m/%Y")}.',
                )

        return cleaned_data
