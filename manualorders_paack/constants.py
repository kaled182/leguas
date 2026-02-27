# constants.py - Arquivo com constantes do sistema

# Mapeamento de status em português para melhor apresentação na UI
STATUS_LABELS = {
    'delivered': 'Entregue',
    'on_course': 'Em Rota',
    'picked_up': 'Coletado',
    'reached_picked_up': 'Chegou ao Ponto de Coleta',
    'return_in_progress': 'Retorno em Andamento',
    'undelivered': 'Não Entregue',
}

# Mapeamento de cores para status
STATUS_COLORS = {
    'delivered': 'text-green-600',
    'on_course': 'text-yellow-600',
    'picked_up': 'text-blue-600',
    'reached_picked_up': 'text-indigo-600',
    'return_in_progress': 'text-orange-600',
    'undelivered': 'text-red-600',
}
