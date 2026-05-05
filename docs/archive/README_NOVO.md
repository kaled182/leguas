# 📚 Documentação - Sistema Léguas Franzinas

**Versão**: 2.1.0 | **Última Atualização**: 28/02/2026

---

## 🎯 DOCUMENTO PRINCIPAL (Leia Primeiro)

### 📘 [SISTEMA_LEGUAS_COMPLETO.md](./SISTEMA_LEGUAS_COMPLETO.md)

**Documentação consolidada e atualizada de todo o sistema.**  
Este é o documento de referência principal que substitui múltiplos documentos antigos.

**Conteúdo**:
- ✅ Visão geral e arquitetura
- ✅ Módulos implementados (Financeiro, Analytics, Frota, etc.)
- ✅ Sistema Financeiro completo (Invoices, Settlements, Claims)
- ✅ Guia de uso detalhado
- ✅ Deployment e manutenção
- ✅ Roadmap atualizado
- ✅ Troubleshooting

---

## 📋 Documentação Complementar

### Por Área de Interesse

#### 💰 Sistema Financeiro
- **[ROADMAP.md](./ROADMAP.md)** - Status detalhado de implementação
- Ou veja seção "Sistema Financeiro" em SISTEMA_LEGUAS_COMPLETO.md

#### 🏗️  Infraestrutura
- **[DOCKER.md](./DOCKER.md)** - Setup Docker e comandos
- **[CRON_JOBS_GUIDE.md](./CRON_JOBS_GUIDE.md)** - Tarefas agendadas

#### 🔐 Acesso
- **[CREDENCIAIS_ACESSO.md](./CREDENCIAIS_ACESSO.md)** - Usuários e senhas

---

## 🚀 Status do Sistema (Atualizado: 28/02/2026)

| Módulo | Status | Descrição |
|--------|--------|-----------|
| **Sistema Financeiro** | ✅ 100% | Invoices, Settlements, Claims com paginação e filtros modernos |
| **Analytics** | ✅ 100% | Dashboards, forecasting, alertas automáticos |
| **Gestão de Frota** | ✅ 100% | Veículos, manutenções, incidentes |
| **Pricing** | ✅ 100% | 11 zonas postais + tarifas configuradas |
| **Route Allocation** | ✅ 100% | Turnos e alocação de motoristas |
| **Orders Manager** | 🔄 Transição | Dual write ativo (Paack + Genérico) |
| **WhatsApp** | ⚪ Parcial | Infraestrutura OK, automação pendente |

---

## 🎓 Guia de Leitura por Perfil

### 👨‍💻 Desenvolvedor
1. [SISTEMA_LEGUAS_COMPLETO.md](./SISTEMA_LEGUAS_COMPLETO.md) - Seção "Arquitetura"
2. [DOCKER.md](./DOCKER.md) - Setup local
3. Explorar código em `settlements/`, `analytics/`, `orders_manager/`

### 💼 Admin Financeiro
1. [SISTEMA_LEGUAS_COMPLETO.md](./SISTEMA_LEGUAS_COMPLETO.md) - Seção "Sistema Financeiro"
2. Acessar: https://app.leguasfranzinas.pt/settlements/
3. Ver "Workflow Semanal Típico" no doc principal

### 📊 Admin Operacional
1. Dashboard: https://app.leguasfranzinas.pt/analytics/
2. Gestão de frota: /fleet_management/
3. Turnos: /route_allocation/

### ⚙️  DevOps
1. [DOCKER.md](./DOCKER.md)
2. [CRON_JOBS_GUIDE.md](./CRON_JOBS_GUIDE.md)
3. [SISTEMA_LEGUAS_COMPLETO.md](./SISTEMA_LEGUAS_COMPLETO.md) - Seção "Deployment"

---

##  🔗 Links Rápidos

**Sistema**:
- 🌐 Produção: https://app.leguasfranzinas.pt
- 🔧 Admin: https://app.leguasfranzinas.pt/admin/
- 💰 Financeiro: https://app.leguasfranzinas.pt/settlements/
- 📊 Analytics: https://app.leguasfranzinas.pt/analytics/

**Código**:
- 📦 GitHub: https://github.com/kaled182/leguas

---

## 📞 Suporte

**Problemas Comuns**: Ver [SISTEMA_LEGUAS_COMPLETO.md](./SISTEMA_LEGUAS_COMPLETO.md) - Seção "Troubleshooting"

**Contato**: dev@leguasfranzinas.pt

---

## 📊 Métricas (28/02/2026)

- **Linhas de código**: ~15,000 (Python)
- **Templates**: ~50 (Django)
- **Models**: 25+
- **Dashboards**: 8
- **Management commands**: 15+
- **Coverage de testes**: ~40%

---

## 🗂️  Documentos Legacy (Referência Histórica)

Os seguintes documentos foram **consolidados** em SISTEMA_LEGUAS_COMPLETO.md:
- ~~ARCHITECTURE.md~~ (ver seção "Arquitetura")
- ~~FINANCIAL_SYSTEM_TESTING.md~~ (ver seção "Sistema Financeiro")
- ~~MIGRATION_GUIDE.md~~ (referência histórica)

---

**🎉 Sistema 100% funcional em produção!**
