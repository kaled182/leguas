"""
Feature Flags para controlar rollout gradual da nova arquitetura multi-partner.

Este arquivo centraliza todas as feature flags que controlam o comportamento
do sistema durante a migração de Paack-only para multi-partner.

Referência: docs/MIGRATION_GUIDE.md - Fase 2: Read/Write em Paralelo
"""

# ============================================================================
# FEATURE FLAGS - FASE 1-2: MIGRAÇÃO GRADUAL
# ============================================================================

# --- ORDERS (Pedidos) ---
# Controla se novos pedidos devem ser escritos no sistema novo (orders_manager)
# ou apenas no sistema antigo (ordersmanager_paack)
USE_GENERIC_ORDERS_WRITE = False  # False = Escreve apenas em ordersmanager_paack
                                   # True = Escreve em orders_manager (+ Paack se DUAL)

# Controla se leituras devem vir do sistema novo ou antigo
USE_GENERIC_ORDERS_READ = False   # False = Lê de ordersmanager_paack
                                   # True = Lê de orders_manager

# Modo dual write: escrever nos dois sistemas simultaneamente
DUAL_WRITE_ORDERS = False  # True = Escreve em ambos os sistemas (útil para validação)


# --- FLEET MANAGEMENT (Frota) ---
# Controla se gestão de veículos está ativa
USE_FLEET_MANAGEMENT = False  # False = Não usa fleet_management
                               # True = Ativa gestão de frota

# --- PRICING (Tarifação) ---
# Controla se cálculo de preços deve usar novo sistema de zonas postais
USE_POSTAL_ZONE_PRICING = False  # False = Usa pricing antigo
                                  # True = Usa PostalZone + PartnerTariff

# --- ROUTE ALLOCATION (Alocação de rotas) ---
# Controla se auto-atribuição de turnos está ativa
USE_AUTO_ROUTE_ALLOCATION = False  # False = Alocação manual
                                    # True = Usa RouteOptimizer para auto-atribuir

# --- ANALYTICS (Análise de dados) ---
# Controla se dashboards de analytics estão disponíveis
USE_ANALYTICS_DASHBOARD = False  # False = Dashboards antigos
                                  # True = Novos dashboards com forecasting


# --- SETTLEMENTS (Liquidações) ---
# Controla se liquidações devem ser calculadas usando novo sistema
USE_GENERIC_SETTLEMENTS = False  # False = Usa settlements antigos (Paack-only)
                                  # True = Calcula settlements por partner


# --- WHATSAPP NOTIFICATIONS ---
# Controla se notificações WhatsApp para motoristas estão ativas
USE_WHATSAPP_NOTIFICATIONS = False  # False = Sem notificações
                                    # True = Envia notificações via wppconnect


# ============================================================================
# CONFIGURAÇÕES DE MIGRAÇÃO
# ============================================================================

# Número de dias para manter dados duplicados antes de limpar
MIGRATION_RETENTION_DAYS = 30  # Após validação, limpar dados antigos

# Validação automática de consistência entre sistemas
ENABLE_MIGRATION_VALIDATION = True  # True = Valida dados ao escrever em dual mode

# Log de auditoria durante migração
LOG_MIGRATION_OPERATIONS = True  # True = Registra todas operações de migração


# ============================================================================
# HELPERS
# ============================================================================

def is_migrated_to_generic_orders():
    """Verifica se sistema já foi migrado para orders genéricos"""
    return USE_GENERIC_ORDERS_READ and USE_GENERIC_ORDERS_WRITE


def is_in_migration_phase():
    """Verifica se está em fase de migração (dual write)"""
    return DUAL_WRITE_ORDERS or (USE_GENERIC_ORDERS_WRITE != USE_GENERIC_ORDERS_READ)


def get_active_flags():
    """Retorna dicionário com todas as flags ativas"""
    import sys
    module = sys.modules[__name__]
    
    flags = {}
    for name in dir(module):
        if name.isupper() and not name.startswith('_'):
            flags[name] = getattr(module, name)
    
    return flags


def print_flag_status():
    """Imprime status de todas as feature flags (útil para debugging)"""
    flags = get_active_flags()
    
    print("\n" + "="*60)
    print(" FEATURE FLAGS STATUS")
    print("="*60)
    
    for name, value in sorted(flags.items()):
        status = "✅ ON" if value else "❌ OFF"
        if isinstance(value, bool):
            print(f"{status:<10} {name}")
        else:
            print(f"{'⚙️ VALUE':<10} {name} = {value}")
    
    print("="*60)
    print(f"Migration Phase: {'YES' if is_in_migration_phase() else 'NO'}")
    print(f"Fully Migrated: {'YES' if is_migrated_to_generic_orders() else 'NO'}")
    print("="*60 + "\n")


# ============================================================================
# ROADMAP DE ATIVAÇÃO (planejado)
# ============================================================================
"""
FASE 1 (Semanas 1-6): Preparação
- Todas as flags = False
- Criar apps, models, migrations
- Migrar dados históricos
- Validar integridade

FASE 2 (Semanas 7-8): Dual Write
- DUAL_WRITE_ORDERS = True
- USE_GENERIC_ORDERS_READ = False (ainda lê do antigo)
- Validar consistência por 1-2 semanas

FASE 3 (Semanas 9-10): Dual Read
- DUAL_WRITE_ORDERS = True
- USE_GENERIC_ORDERS_READ = True (começa a ler do novo)
- Comparar resultados por 1 semana

FASE 4 (Semana 11): Cutover
- USE_GENERIC_ORDERS_WRITE = True
- USE_GENERIC_ORDERS_READ = True
- DUAL_WRITE_ORDERS = False
- Sistema migrado!

FASE 5 (Semanas 12-16): Funcionalidades avançadas
- USE_FLEET_MANAGEMENT = True
- USE_POSTAL_ZONE_PRICING = True
- USE_AUTO_ROUTE_ALLOCATION = True
- USE_WHATSAPP_NOTIFICATIONS = True
- USE_ANALYTICS_DASHBOARD = True
- USE_GENERIC_SETTLEMENTS = True
"""
