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
            # Financeiro
            "price_per_package",
            "driver_default_price_per_package",
            "bonus_performance_enabled",
            "bonus_sunday_holiday_enabled",
            "bonus_volume_enabled",
            # PUDO
            "pudo_enabled",
            "pudo_first_delivery_price",
            "pudo_additional_delivery_price",
            "pudo_fake_delivery_penalty",
            "pudo_geo_tolerance_meters",
            # Fiscal
            "vat_regime",
            "vat_rate_override",
            "irs_retention_pct",
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
            # Financeiro
            "price_per_package": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                    "step": "0.0001",
                    "placeholder": "Ex: 0.9000",
                }
            ),
            "driver_default_price_per_package": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                    "step": "0.0001",
                    "placeholder": "Ex: 1.3000 (opcional, default global)",
                }
            ),
            "bonus_performance_enabled": forms.CheckboxInput(
                attrs={"class": "w-4 h-4 text-blue-600 rounded focus:ring-2 dark:bg-gray-700 dark:border-gray-600"}
            ),
            "bonus_sunday_holiday_enabled": forms.CheckboxInput(
                attrs={"class": "w-4 h-4 text-blue-600 rounded focus:ring-2 dark:bg-gray-700 dark:border-gray-600"}
            ),
            "bonus_volume_enabled": forms.CheckboxInput(
                attrs={"class": "w-4 h-4 text-blue-600 rounded focus:ring-2 dark:bg-gray-700 dark:border-gray-600"}
            ),
            "pudo_enabled": forms.CheckboxInput(
                attrs={"class": "w-4 h-4 text-violet-600 rounded focus:ring-2 dark:bg-gray-700 dark:border-gray-600"}
            ),
            "pudo_first_delivery_price": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-violet-500 dark:bg-gray-700 dark:text-white",
                    "step": "0.0001",
                    "placeholder": "1.0000",
                }
            ),
            "pudo_additional_delivery_price": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-violet-500 dark:bg-gray-700 dark:text-white",
                    "step": "0.0001",
                    "placeholder": "0.2000",
                }
            ),
            "pudo_fake_delivery_penalty": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-rose-500 dark:bg-gray-700 dark:text-white",
                    "step": "0.0001",
                    "placeholder": "1.3000",
                }
            ),
            "pudo_geo_tolerance_meters": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-violet-500 dark:bg-gray-700 dark:text-white",
                    "step": "10",
                    "min": "10",
                    "placeholder": "200",
                }
            ),
            "vat_regime": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                }
            ),
            "vat_rate_override": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                    "step": "0.01",
                    "placeholder": "deixar vazio para usar taxa do regime",
                }
            ),
            "irs_retention_pct": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                    "step": "0.01",
                    "placeholder": "0, 11.5 ou 25",
                }
            ),
        }


class PartnerIntegrationForm(forms.ModelForm):
    """Formulário para criar/editar integrações"""

    # Campos adicionais para configuração de autenticação
    auth_type = forms.ChoiceField(
        label="Tipo de Autenticação",
        choices=[
            ("", "Selecione..."),
            ("bearer", "Bearer Token"),
            ("basic", "Basic Auth"),
            ("oauth2", "OAuth 2.0"),
            ("api_key", "API Key"),
            ("custom_paack", "Paack/AppSheet (Custom)"),
        ],
        required=False,
        widget=forms.Select(
            attrs={
                "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                "onchange": "toggleAuthFields(this.value)"
            }
        ),
    )

    # Campos genéricos
    api_key = forms.CharField(
        label="API Key",
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                "placeholder": "Sua chave de API",
            }
        ),
    )

    api_secret = forms.CharField(
        label="API Secret",
        required=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                "placeholder": "Segredo da API (opcional)",
            }
        ),
    )

    username = forms.CharField(
        label="Usuário",
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                "placeholder": "Para Basic Auth",
            }
        ),
    )

    password = forms.CharField(
        label="Senha",
        required=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                "placeholder": "Para Basic Auth",
            }
        ),
    )
    
    # Campos específicos para Paack/AppSheet
    paack_api_url = forms.URLField(
        label="API URL (AppSheet)",
        required=False,
        widget=forms.URLInput(
            attrs={
                "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                "placeholder": "https://www.appsheet.com/api/template/...",
            }
        ),
    )
    
    paack_cookie_key = forms.CharField(
        label="Cookie Key",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white font-mono text-xs",
                "placeholder": ".JEENEEATH-3P=...",
                "rows": "3",
            }
        ),
    )
    
    paack_sync_token = forms.CharField(
        label="Sync Token (JWT)",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white font-mono text-xs",
                "placeholder": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "rows": "3",
            }
        ),
    )

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Se estiver editando, preencher campos de autenticação
        if self.instance and self.instance.pk and self.instance.auth_config:
            auth_config = self.instance.auth_config
            self.fields["auth_type"].initial = auth_config.get("type", "")
            
            # Campos genéricos
            self.fields["api_key"].initial = auth_config.get("api_key", "")
            self.fields["api_secret"].initial = auth_config.get("api_secret", "")
            self.fields["username"].initial = auth_config.get("username", "")
            
            # Campos específicos Paack
            self.fields["paack_api_url"].initial = auth_config.get("api_url", "")
            self.fields["paack_cookie_key"].initial = auth_config.get("cookie_key", "")
            self.fields["paack_sync_token"].initial = auth_config.get("sync_token", "")
            
            # Não preenche password por segurança

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Montar configuração de autenticação
        auth_config = {}
        
        auth_type = self.cleaned_data.get("auth_type")
        if auth_type:
            auth_config["type"] = auth_type
            
            if auth_type in ["bearer", "api_key"]:
                api_key = self.cleaned_data.get("api_key")
                if api_key:
                    auth_config["api_key"] = api_key
                    
                api_secret = self.cleaned_data.get("api_secret")
                if api_secret:
                    auth_config["api_secret"] = api_secret
                    
            elif auth_type == "custom_paack":
                # Configuração específica Paack/AppSheet
                api_url = self.cleaned_data.get("paack_api_url")
                cookie_key = self.cleaned_data.get("paack_cookie_key")
                sync_token = self.cleaned_data.get("paack_sync_token")
                
                if api_url:
                    auth_config["api_url"] = api_url
                if cookie_key:
                    auth_config["cookie_key"] = cookie_key
                if sync_token:
                    auth_config["sync_token"] = sync_token
                    
                auth_config["description"] = "AppSheet API - Paack Integration"
                    
            elif auth_type == "basic":
                username = self.cleaned_data.get("username")
                password = self.cleaned_data.get("password")
                if username:
                    auth_config["username"] = username
                if password:
                    auth_config["password"] = password
        
        instance.auth_config = auth_config
        
        if commit:
            instance.save()
        
        return instance
