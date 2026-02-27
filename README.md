# Leguas Franzinas - Sistema de Gestão de Entregas

Sistema completo de gestão de motoristas e entregas com integração Paack API e WhatsApp.

## 🚀 Funcionalidades

### Gestão de Motoristas
- ✅ Modal AJAX completo com 3 abas (Informações, Documentos, Veículos)
- ✅ Sistema de aprovação de novos motoristas
- ✅ Upload e visualização de documentos (PDF e imagens)
- ✅ Gestão de veículos e documentos de veículos
- ✅ Ativação/Desativação dinâmica de motoristas
- ✅ Modal de confirmação customizado
- ✅ Notificações toast em tempo real
- ✅ Sem reload de página (AJAX completo)

### Integrações
- 📦 Paack API - Gestão de entregas
- 💬 WhatsApp via WPPConnect - Comunicação com motoristas
- 🤖 TypeBot - Automação de conversas
- 📊 Dashboard com estatísticas em tempo real

### Autenticação
- 🔐 Sistema de autenticação customizado
- 👥 Perfis diferenciados (Admin, Motorista)
- 🖼️ Upload de foto de perfil

## 🛠️ Tecnologias

- **Backend**: Django 4.2.22
- **Frontend**: Alpine.js, Tailwind CSS, Lucide Icons
- **Database**: MySQL
- **Containerização**: Docker & Docker Compose
- **Servidor**: Gunicorn
- **Proxy**: Nginx (via Docker)

## 📦 Instalação

### Pré-requisitos
- Docker
- Docker Compose

### Configuração

1. Clone o repositório:
```bash
git clone https://github.com/kaled182/leguas.git
cd leguas
```

2. Configure as variáveis de ambiente:
```bash
cp .env.docker.example .env.docker
# Edite .env.docker com suas credenciais
```

3. Inicie os containers:
```bash
docker-compose up -d
```

4. Rode as migrações:
```bash
docker-compose exec web python manage.py migrate
```

5. Crie um superusuário:
```bash
docker-compose exec web python manage.py createsuperuser
```

6. Acesse o sistema:
- Frontend: http://localhost:8000
- Admin Django: http://localhost:8000/admin

## 📁 Estrutura do Projeto

```
├── drivers_app/          # App principal de gestão de motoristas
├── paack_dashboard/      # Dashboard e integrações Paack
├── customauth/          # Sistema de autenticação customizado
├── accounting/          # Módulo de contabilidade
├── converter/           # Conversor de dados
├── ordersmanager_paack/ # Gestão de pedidos Paack
├── settlements/         # Liquidações
├── wppconnect-chatwoot-bridge/ # Integração WhatsApp
├── templates/           # Templates globais
├── static/             # Arquivos estáticos
└── my_project/         # Configurações Django
```

## 🔧 Comandos Úteis

```bash
# Ver logs
docker-compose logs -f web

# Restart do servidor
docker-compose restart web

# Collectstatic
docker-compose exec web python manage.py collectstatic --noinput

# Shell Django
docker-compose exec web python manage.py shell
```

## 📝 Licença

Proprietário - Leguas Franzinas

## 👥 Autores

- **Admin Team** - *Initial work* - Leguas Franzinas

## 🌟 Features Recentes

### v1.0.0 (27/02/2026)
- ✨ Sistema completo de gestão de motoristas com modal AJAX
- ✨ Visualizador de documentos integrado
- ✨ Modal de confirmação customizado
- ✨ Sistema de notificações toast
- ✨ Configuração Docker completa
- ✨ Integração WhatsApp via WPPConnect
- ✨ Dashboard com estatísticas
