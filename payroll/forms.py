from django import forms

from .models import Employee, PayrollComponent


class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = [
            "nome", "nif", "niss", "iban", "email", "telefone",
            "contrato_tipo", "part_time_pct",
            "data_admissao", "data_saida", "ativo",
            "vencimento_base", "diuturnidades",
            "subs_alimentacao_dia", "dias_uteis_mes_default",
            "irs_tabela", "dependentes_irs",
            "subsidios_mode", "cost_center", "notas",
        ]
        widgets = {
            "data_admissao": forms.DateInput(attrs={"type": "date"}),
            "data_saida": forms.DateInput(attrs={"type": "date"}),
            "notas": forms.Textarea(attrs={"rows": 3}),
        }


class PayrollComponentForm(forms.ModelForm):
    class Meta:
        model = PayrollComponent
        fields = ["tipo", "descricao", "valor", "quantidade"]


class PayrollGenerateForm(forms.Form):
    ano = forms.IntegerField(
        label="Ano", min_value=2024, max_value=2100,
    )
    mes = forms.IntegerField(label="Mês", min_value=1, max_value=12)
    dias_uteis = forms.IntegerField(
        label="Dias úteis (opcional)", min_value=1, max_value=31,
        required=False,
        help_text="Sobrescreve o default de cada funcionário.",
    )
    recreate = forms.BooleanField(
        label="Regenerar folhas existentes (apenas rascunhos)",
        required=False,
    )
