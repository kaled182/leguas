from django import forms

from .models import (
    Vehicle,
    VehicleAssignment,
    VehicleIncident,
    VehicleMaintenance,
)


class VehicleForm(forms.ModelForm):
    """Formulário para criação e edição de veículos."""

    class Meta:
        model = Vehicle
        fields = [
            "license_plate",
            "brand",
            "model",
            "year",
            "vehicle_type",
            "owner",
            "max_load_kg",
            "fuel_type",
            "inspection_expiry",
            "insurance_expiry",
            "insurance_policy_number",
            "status",
            "current_odometer_km",
            "notes",
        ]
        widgets = {
            "license_plate": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white",
                    "placeholder": "AA-00-BB",
                }
            ),
            "brand": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white",
                    "placeholder": "Ex: Mercedes, Renault, Peugeot",
                }
            ),
            "model": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white",
                    "placeholder": "Ex: Sprinter, Master, Boxer",
                }
            ),
            "year": forms.NumberInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white",
                    "placeholder": "2020",
                    "min": "1990",
                    "max": "2030",
                }
            ),
            "vehicle_type": forms.Select(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white"
                }
            ),
            "owner": forms.Select(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white"
                }
            ),
            "max_load_kg": forms.NumberInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white",
                    "placeholder": "1000",
                    "step": "0.01",
                }
            ),
            "fuel_type": forms.Select(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white"
                }
            ),
            "inspection_expiry": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white",
                }
            ),
            "insurance_expiry": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white",
                }
            ),
            "insurance_policy_number": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white",
                    "placeholder": "Nº da apólice",
                }
            ),
            "status": forms.Select(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white"
                }
            ),
            "current_odometer_km": forms.NumberInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white",
                    "placeholder": "0",
                    "step": "0.01",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white",
                    "rows": 4,
                    "placeholder": "Notas adicionais sobre o veículo...",
                }
            ),
        }
        labels = {
            "license_plate": "Matrícula",
            "brand": "Marca",
            "model": "Modelo",
            "year": "Ano",
            "vehicle_type": "Tipo de Veículo",
            "owner": "Proprietário",
            "max_load_kg": "Carga Máxima (kg)",
            "fuel_type": "Tipo de Combustível",
            "inspection_expiry": "Validade da Inspeção",
            "insurance_expiry": "Validade do Seguro",
            "insurance_policy_number": "Nº da Apólice",
            "status": "Estado",
            "current_odometer_km": "Quilometragem Atual (km)",
            "notes": "Notas",
        }

    def clean_license_plate(self):
        """Valida o formato da matrícula."""
        license_plate = self.cleaned_data.get("license_plate", "").upper()

        # Remove espaços e traços
        license_plate = license_plate.replace(" ", "").replace("-", "")

        # Formato português: XX-00-XX ou XX-00-00
        if len(license_plate) == 6:
            if not (
                license_plate[:2].isalpha()
                and license_plate[2:4].isdigit()
                and (license_plate[4:].isalpha() or license_plate[4:].isdigit())
            ):
                raise forms.ValidationError(
                    "Formato inválido. Use: AA-00-BB ou AA-00-00"
                )
            # Formata com traços
            return f"{license_plate[:2]}-{license_plate[2:4]}-{license_plate[4:]}"

        # Retorna sem alteração se não tiver 6 caracteres (deixa Django validar)
        return license_plate

    def clean_year(self):
        """Valida o ano do veículo."""
        year = self.cleaned_data.get("year")
        if year:
            from datetime import datetime

            current_year = datetime.now().year
            if year < 1990:
                raise forms.ValidationError("O ano não pode ser anterior a 1990.")
            if year > current_year + 1:
                raise forms.ValidationError(
                    f"O ano não pode ser superior a {current_year + 1}."
                )
        return year

    def clean(self):
        """Validações cruzadas."""
        cleaned_data = super().clean()
        inspection_expiry = cleaned_data.get("inspection_expiry")
        insurance_expiry = cleaned_data.get("insurance_expiry")

        # Verifica se as datas de validade não estão no passado (apenas para novos
        # veículos)
        if not self.instance.pk:
            from datetime import date

            today = date.today()

            if inspection_expiry and inspection_expiry < today:
                self.add_error(
                    "inspection_expiry",
                    "A data de validade da inspeção não pode estar no passado.",
                )

            if insurance_expiry and insurance_expiry < today:
                self.add_error(
                    "insurance_expiry",
                    "A data de validade do seguro não pode estar no passado.",
                )

        return cleaned_data


class VehicleAssignmentForm(forms.ModelForm):
    """Formulário para atribuição de veículos a motoristas."""

    class Meta:
        model = VehicleAssignment
        fields = [
            "vehicle",
            "driver",
            "date",
            "start_time",
            "end_time",
            "odometer_start",
            "odometer_end",
            "notes",
        ]
        widgets = {
            "vehicle": forms.Select(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white"
                }
            ),
            "driver": forms.Select(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white"
                }
            ),
            "date": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white",
                }
            ),
            "start_time": forms.TimeInput(
                attrs={
                    "type": "time",
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white",
                }
            ),
            "end_time": forms.TimeInput(
                attrs={
                    "type": "time",
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white",
                }
            ),
            "odometer_start": forms.NumberInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white",
                    "step": "1",
                }
            ),
            "odometer_end": forms.NumberInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white",
                    "step": "1",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white",
                    "rows": 3,
                }
            ),
        }
        labels = {
            "vehicle": "Veículo",
            "driver": "Motorista",
            "date": "Data",
            "start_time": "Hora de Início",
            "end_time": "Hora de Fim",
            "odometer_start": "Quilometragem Inicial",
            "odometer_end": "Quilometragem Final",
            "notes": "Notas",
        }


class VehicleMaintenanceForm(forms.ModelForm):
    """Formulário para registar manutenções de veículos."""

    class Meta:
        model = VehicleMaintenance
        fields = [
            "vehicle",
            "maintenance_type",
            "scheduled_date",
            "completed_date",
            "workshop",
            "cost",
            "invoice_number",
            "odometer_at_service",
            "description",
            "is_completed",
            "notes",
        ]
        widgets = {
            "vehicle": forms.Select(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white"
                }
            ),
            "maintenance_type": forms.Select(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white"
                }
            ),
            "scheduled_date": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white",
                }
            ),
            "completed_date": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white",
                }
            ),
            "workshop": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white",
                    "placeholder": "Nome da oficina",
                }
            ),
            "cost": forms.NumberInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white",
                    "step": "0.01",
                    "placeholder": "0.00",
                }
            ),
            "invoice_number": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white",
                    "placeholder": "Número da fatura",
                }
            ),
            "odometer_at_service": forms.NumberInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white",
                    "step": "1",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white",
                    "rows": 3,
                    "placeholder": "Descrição da manutenção...",
                }
            ),
            "is_completed": forms.CheckboxInput(
                attrs={
                    "class": "rounded border-gray-300 dark:border-gray-600 text-teal-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700"
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white",
                    "rows": 2,
                    "placeholder": "Notas adicionais...",
                }
            ),
        }
        labels = {
            "vehicle": "Veículo",
            "maintenance_type": "Tipo de Manutenção",
            "scheduled_date": "Data Agendada",
            "completed_date": "Data de Conclusão",
            "workshop": "Oficina",
            "cost": "Custo (€)",
            "invoice_number": "Número da Fatura",
            "odometer_at_service": "Quilometragem no Serviço",
            "description": "Descrição",
            "is_completed": "Concluído",
            "notes": "Notas",
        }


class VehicleIncidentForm(forms.ModelForm):
    """Formulário para registar incidentes com veículos."""

    class Meta:
        model = VehicleIncident
        fields = [
            "vehicle",
            "driver",
            "incident_date",
            "incident_type",
            "description",
            "location",
            "fine_amount",
            "driver_responsible",
            "claim_amount",
            "police_report_number",
            "resolved",
            "resolution_notes",
        ]
        widgets = {
            "vehicle": forms.Select(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white"
                }
            ),
            "driver": forms.Select(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white"
                }
            ),
            "incident_date": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white",
                }
            ),
            "incident_type": forms.Select(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white"
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white",
                    "rows": 4,
                    "placeholder": "Descrição detalhada do incidente...",
                }
            ),
            "location": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white",
                    "placeholder": "Local do incidente",
                }
            ),
            "fine_amount": forms.NumberInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white",
                    "step": "0.01",
                    "placeholder": "0.00",
                }
            ),
            "driver_responsible": forms.CheckboxInput(
                attrs={
                    "class": "rounded border-gray-300 dark:border-gray-600 text-teal-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700"
                }
            ),
            "claim_amount": forms.NumberInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white",
                    "step": "0.01",
                    "placeholder": "0.00",
                }
            ),
            "police_report_number": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white",
                    "placeholder": "Nº de participação policial",
                }
            ),
            "resolved": forms.CheckboxInput(
                attrs={
                    "class": "rounded border-gray-300 dark:border-gray-600 text-teal-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700"
                }
            ),
            "resolution_notes": forms.Textarea(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-teal-500 focus:ring-teal-500 dark:bg-gray-700 dark:text-white",
                    "rows": 3,
                    "placeholder": "Notas sobre a resolução...",
                }
            ),
        }
        labels = {
            "vehicle": "Veículo",
            "driver": "Motorista",
            "incident_date": "Data do Incidente",
            "incident_type": "Tipo de Incidente",
            "description": "Descrição",
            "location": "Local",
            "fine_amount": "Valor da Multa/Dano (€)",
            "driver_responsible": "Motorista Responsável",
            "claim_amount": "Valor a Reclamar (€)",
            "police_report_number": "Nº Participação Policial",
            "resolved": "Resolvido",
            "resolution_notes": "Notas de Resolução",
        }
