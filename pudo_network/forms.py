"""Formulários da gestão interna da Rede PUDO (staff)."""
from django import forms

from .models import PudoStore

# Classes Tailwind partilhadas pelos inputs (padrão do dashboard).
_INPUT = (
    "w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 "
    "bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm "
    "focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition"
)


class PudoStoreForm(forms.ModelForm):
    class Meta:
        model = PudoStore
        fields = [
            "nome", "status", "nif", "morada", "codigo_postal", "cidade",
            "email", "telefone", "contacto_nome", "iban", "taxa_iva",
            "latitude", "longitude", "capacidade_max",
            "preco_1a_entrega", "preco_adicional", "ciclo_pagamento",
            "partner", "notas",
        ]
        widgets = {
            "morada": forms.Textarea(attrs={"rows": 2}),
            "notas": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            css = _INPUT
            if isinstance(field.widget, forms.CheckboxInput):
                css = ""
            field.widget.attrs["class"] = (
                field.widget.attrs.get("class", "") + " " + css
            ).strip()
            field.required = name in ("nome",)
