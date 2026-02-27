# System Config - Configurações do Sistema

## Descrição

App Django para gerenciar configurações centralizadas do sistema Leguas Franzinas. Importado do projeto provemaps, excluindo funcionalidades de Zabbix e monitoramento de dispositivos.

## Funcionalidades

### 1. Configurações da Empresa
- Nome da empresa
- Logotipo

### 2. Configurações de Mapas
- **Google Maps**: API Key
- **Mapbox**: Access Token
- **OpenStreetMap**: Tile Server customizado
- Coordenadas padrão (latitude/longitude)
- Nível de zoom padrão
- Seleção de provedor de mapas preferencial

### 3. Google Drive
- Client ID OAuth
- Client Secret OAuth
- Folder ID para armazenamento
- Refresh Token

### 4. FTP
- Host e porta
- Credenciais (usuário/senha)
- Diretório de trabalho

### 5. E-mail (SMTP)
- Servidor SMTP (host/porta)
- Credenciais de autenticação
- E-mail de envio
- Opção TLS

### 6. SMS
- Suporte para múltiplos provedores:
  - Twilio
  - Nexmo
  - AWS SNS
  - Infobip
- Account SID e Auth Token
- Número de envio
- API Key

### 7. WhatsApp (Evolution API)
- URL da Evolution API
- API Key
- Nome da instância

## Modelos

### SystemConfiguration
- Modelo singleton (apenas uma instância)
- Campos sensíveis criptografados com `EncryptedCharField`
- Método estático `get_config()` para obter a configuração

### ConfigurationAudit
- Rastreamento de alterações
- Registra: usuário, timestamp, ação, campo, valores antigos/novos, IP

## URLs

- `/system/` - Página de configurações
- `/system/save/` - Endpoint para salvar (POST)

## Segurança

- Apenas usuários autenticados podem acessar (`@login_required`)
- Campos sensíveis (senhas, tokens, API keys) criptografados
- Auditoria completa de alterações
- Registro de IP do usuário

## Admin

Disponível em `/admin/system_config/` com:
- 6 fieldsets organizados por categoria
- Apenas edição (sem adicionar/excluir - singleton)
- Visualização de histórico de auditoria

## Uso

```python
from system_config.models import SystemConfiguration

# Obter configuração (cria automaticamente se não existir)
config = SystemConfiguration.get_config()

# Acessar valores
maps_key = config.google_maps_api_key
smtp_host = config.smtp_host
whatsapp_url = config.whatsapp_evolution_api_url

# Atualizar
config.company_name = "Nova Empresa"
config.save()
```

## Dependências

- `cryptography` - Para criptografia de campos sensíveis
- Django 4.2+
- PIL/Pillow - Para upload de logotipo

## Próximos Passos

Possíveis melhorias futuras:
1. Service para carregar configurações em runtime (runtime_settings.py)
2. Cache de configurações para performance
3. Validação de campos (ex: testar conexão SMTP, FTP)
4. Interface de teste de APIs (WhatsApp, SMS)
5. Importação/exportação de configurações
6. Versionamento de configurações
