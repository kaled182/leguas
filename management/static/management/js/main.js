/**
 * JavaScript principal para o app Management
 * Funcionalidades para dashboard e gerenciamento de motoristas
 */

// Variáveis globais
let darkMode = localStorage.getItem('darkMode') === 'true';
let charts = {};

// Inicialização
document.addEventListener('DOMContentLoaded', function() {
  console.log('Management app JS carregado');
  
  // Configurações gerais
  initializeDarkMode();
  initializeNotifications();
  
  // Detectar e inicializar funcionalidades específicas de página
  detectAndInitPage();
});

/**
 * Detecta a página atual e inicializa funcionalidades específicas
 */
function detectAndInitPage() {
  // Detectar página pelo URL ou elementos na página
  const path = window.location.pathname;
  
  if (path.includes('/dashboard')) {
    console.log('Dashboard detectado, inicializando...');
    initDashboard();
  } 
  else if (path.includes('/drivers')) {
    console.log('Gerenciamento de motoristas detectado, inicializando...');
    initDriversManagement();
  }
}

/**
 * Inicializa o modo escuro
 */
function initializeDarkMode() {
  // Aplicar modo escuro se estiver salvo
  if (darkMode) {
    document.documentElement.classList.add('dark');
  }
  
  // Listener para alternar modo escuro
  const darkModeToggle = document.getElementById('darkModeToggle');
  if (darkModeToggle) {
    darkModeToggle.addEventListener('click', toggleDarkMode);
  }
}

/**
 * Alterna entre modo claro e escuro
 */
function toggleDarkMode() {
  darkMode = !darkMode;
  localStorage.setItem('darkMode', darkMode);
  
  // Aplicar ou remover classe dark
  if (darkMode) {
    document.documentElement.classList.add('dark');
  } else {
    document.documentElement.classList.remove('dark');
  }
  
  // Atualizar gráficos para o tema correto
  updateChartsTheme();
  
  console.log('Modo escuro: ' + (darkMode ? 'ativado' : 'desativado'));
}

/**
 * Inicializa sistema de notificações
 */
function initializeNotifications() {
  // Criar área de notificações se não existir
  if (!document.getElementById('notification-area')) {
    const notificationArea = document.createElement('div');
    notificationArea.id = 'notification-area';
    notificationArea.className = 'fixed top-4 right-4 z-50 space-y-3 max-w-sm';
    document.body.appendChild(notificationArea);
  }
}

/**
 * Exibe uma notificação na interface
 * 
 * @param {string} message - Mensagem a ser exibida
 * @param {string} type - Tipo da notificação: 'success', 'error', 'warning', 'info'
 * @param {number} duration - Duração em ms (0 para não fechar automaticamente)
 * @returns {HTMLElement} O elemento de notificação criado
 */
function showNotification(message, type = 'info', duration = 5000) {
  const notificationArea = document.getElementById('notification-area');
  
  // Criar elemento de notificação
  const notification = document.createElement('div');
  notification.className = `transform transition-all duration-300 ease-out scale-95 opacity-0 flex items-center p-4 mb-3 rounded-lg shadow-lg max-w-sm text-sm`;
  
  // Definir estilos baseados no tipo
  let icon;
  switch (type) {
    case 'success':
      notification.classList.add('bg-green-100', 'border-l-4', 'border-green-500', 'text-green-700');
      icon = 'check-circle';
      break;
    case 'error':
      notification.classList.add('bg-red-100', 'border-l-4', 'border-red-500', 'text-red-700');
      icon = 'alert-circle';
      break;
    case 'warning':
      notification.classList.add('bg-yellow-100', 'border-l-4', 'border-yellow-500', 'text-yellow-700');
      icon = 'alert-triangle';
      break;
    default:
      notification.classList.add('bg-blue-100', 'border-l-4', 'border-blue-500', 'text-blue-700');
      icon = 'info';
  }
  
  // Montar conteúdo da notificação
  notification.innerHTML = `
    <i data-lucide="${icon}" class="w-5 h-5 mr-3 flex-shrink-0"></i>
    <span class="mr-2">${message}</span>
    <button class="ml-auto text-gray-400 hover:text-gray-500 focus:outline-none">
      <i data-lucide="x" class="w-4 h-4"></i>
    </button>
  `;
  
  notificationArea.appendChild(notification);
  
  // Inicializar ícones
  if (window.lucide) {
    lucide.createIcons();
  }
  
  // Adicionar funcionalidade de fechar
  const closeButton = notification.querySelector('button');
  closeButton.addEventListener('click', () => {
    hideNotification(notification);
  });
  
  // Animar entrada
  setTimeout(() => {
    notification.classList.remove('scale-95', 'opacity-0');
    notification.classList.add('scale-100', 'opacity-100');
  }, 10);
  
  // Auto fechar
  if (duration > 0) {
    setTimeout(() => {
      hideNotification(notification);
    }, duration);
  }
  
  return notification;
}

/**
 * Esconde uma notificação com animação
 * @param {HTMLElement} notification - Elemento da notificação
 */
function hideNotification(notification) {
  // Animar saída
  notification.classList.remove('scale-100', 'opacity-100');
  notification.classList.add('scale-95', 'opacity-0');
  
  // Remover após animação
  setTimeout(() => {
    if (notification.parentNode) {
      notification.parentNode.removeChild(notification);
    }
  }, 300);
}

/**
 * Inicializa funcionalidades do dashboard
 */
function initDashboard() {
  // Inicializar gráficos
  initializeCharts();
  
  // Configurar navegação de data
  setupDateNavigation();
  
  // Botão de atualização de dados
  const refreshBtn = document.getElementById('refreshDataBtn');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', refreshDashboardData);
  }
  
  // Filtros de gráfico
  document.querySelectorAll('.chart-filter').forEach(button => {
    button.addEventListener('click', function() {
      document.querySelectorAll('.chart-filter').forEach(btn => {
        btn.classList.remove('active');
      });
      this.classList.add('active');
      
      updateChartsData(this.dataset.filter);
    });
  });
}

/**
 * Atualiza os dados do dashboard
 */
function refreshDashboardData() {
  const refreshBtn = document.getElementById('refreshDataBtn');
  
  if (refreshBtn) {
    // Iniciar animação de loading
    refreshBtn.classList.add('animate-spin');
    
    // Aqui seria uma chamada AJAX real
    setTimeout(() => {
      // Parar animação
      refreshBtn.classList.remove('animate-spin');
      
      // Mostrar notificação de sucesso
      showNotification('Dados atualizados com sucesso!', 'success');
    }, 1500);
  }
}

/**
 * Configura a navegação de data no dashboard
 */
function setupDateNavigation() {
  const datePicker = document.getElementById('datePickerInput');
  const prevBtn = document.getElementById('prevDateBtn');
  const nextBtn = document.getElementById('nextDateBtn');
  const todayBtn = document.getElementById('todayBtn');
  
  if (!datePicker) return;
  
  // Botão anterior
  if (prevBtn) {
    prevBtn.addEventListener('click', () => {
      const currentDate = new Date(datePicker.value);
      currentDate.setDate(currentDate.getDate() - 1);
      datePicker.value = formatDate(currentDate);
      navigateToDate(datePicker.value);
    });
  }
  
  // Botão próximo
  if (nextBtn) {
    nextBtn.addEventListener('click', () => {
      const currentDate = new Date(datePicker.value);
      currentDate.setDate(currentDate.getDate() + 1);
      datePicker.value = formatDate(currentDate);
      navigateToDate(datePicker.value);
    });
  }
  
  // Botão hoje
  if (todayBtn) {
    todayBtn.addEventListener('click', () => {
      const today = new Date();
      datePicker.value = formatDate(today);
      navigateToDate(datePicker.value);
    });
  }
  
  // Input de data
  if (datePicker) {
    datePicker.addEventListener('change', () => {
      navigateToDate(datePicker.value);
    });
  }
}

/**
 * Formata data para string YYYY-MM-DD
 * @param {Date} date - Objeto de data
 * @returns {string} Data formatada YYYY-MM-DD
 */
function formatDate(date) {
  return date.toISOString().split('T')[0];
}

/**
 * Navega para uma data específica
 * @param {string} dateString - Data no formato YYYY-MM-DD
 */
function navigateToDate(dateString) {
  window.location.href = `/management/dashboard/?date=${dateString}`;
}

/**
 * Inicializa os gráficos do dashboard
 */
function initializeCharts() {
  // Verificar se Chart.js está disponível
  if (!window.Chart) {
    console.log('Chart.js não encontrado - gráficos desabilitados');
    return;
  }
  
  console.log('Chart.js disponível - inicializando gráficos');
  // Inicializar gráfico de estatísticas
  initDeliveryStatsChart();
}

/**
 * Inicializa o gráfico de estatísticas de entregas
 */
function initDeliveryStatsChart() {
  const ctx = document.getElementById('deliveryStatsChart');
  if (!ctx) return;
  
  // Definir cores baseadas no tema atual
  const isDark = document.documentElement.classList.contains('dark');
  const textColor = isDark ? '#e5e7eb' : '#4b5563';
  const gridColor = isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.05)';
  
  // Dados de exemplo
  const chartData = {
    labels: ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'],
    datasets: [
      {
        label: 'Entregas Realizadas',
        data: [65, 59, 80, 81, 56, 55, 40],
        backgroundColor: 'rgba(99, 102, 241, 0.2)',
        borderColor: 'rgba(99, 102, 241, 1)',
        borderWidth: 2,
        tension: 0.4,
        fill: true
      },
      {
        label: 'Entregas Totais',
        data: [70, 65, 90, 97, 60, 60, 50],
        backgroundColor: 'rgba(209, 213, 219, 0.2)',
        borderColor: 'rgba(156, 163, 175, 1)',
        borderWidth: 2,
        tension: 0.4,
        fill: true
      }
    ]
  };
  
  // Configurações
  const config = {
    type: 'line',
    data: chartData,
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'top',
          labels: {
            color: textColor,
            usePointStyle: true,
            padding: 20
          }
        },
        tooltip: {
          mode: 'index',
          intersect: false,
          backgroundColor: isDark ? '#374151' : '#ffffff',
          titleColor: isDark ? '#e5e7eb' : '#1f2937',
          bodyColor: isDark ? '#d1d5db' : '#4b5563',
          borderColor: isDark ? '#4b5563' : '#e5e7eb',
          borderWidth: 1,
          padding: 12,
          boxPadding: 6,
          usePointStyle: true
        }
      },
      scales: {
        x: {
          grid: {
            display: true,
            color: gridColor
          },
          ticks: {
            color: textColor
          }
        },
        y: {
          grid: {
            display: true,
            color: gridColor
          },
          ticks: {
            color: textColor
          },
          beginAtZero: true
        }
      },
      elements: {
        point: {
          radius: 3,
          hoverRadius: 6
        }
      }
    }
  };
  
  // Criar gráfico
  charts.deliveryStats = new Chart(ctx, config);
}

/**
 * Atualiza gráficos para o tema atual
 */
function updateChartsTheme() {
  const isDark = document.documentElement.classList.contains('dark');
  const textColor = isDark ? '#e5e7eb' : '#4b5563';
  const gridColor = isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.05)';
  
  // Atualizar cada gráfico
  Object.values(charts).forEach(chart => {
    if (!chart) return;
    
    // Atualizar cores de legendas
    if (chart.options.plugins && chart.options.plugins.legend) {
      chart.options.plugins.legend.labels.color = textColor;
    }
    
    // Atualizar cores de tooltip
    if (chart.options.plugins && chart.options.plugins.tooltip) {
      chart.options.plugins.tooltip.backgroundColor = isDark ? '#374151' : '#ffffff';
      chart.options.plugins.tooltip.titleColor = isDark ? '#e5e7eb' : '#1f2937';
      chart.options.plugins.tooltip.bodyColor = isDark ? '#d1d5db' : '#4b5563';
      chart.options.plugins.tooltip.borderColor = isDark ? '#4b5563' : '#e5e7eb';
    }
    
    // Atualizar cores de escalas
    if (chart.options.scales) {
      if (chart.options.scales.x) {
        chart.options.scales.x.grid.color = gridColor;
        chart.options.scales.x.ticks.color = textColor;
      }
      if (chart.options.scales.y) {
        chart.options.scales.y.grid.color = gridColor;
        chart.options.scales.y.ticks.color = textColor;
      }
    }
    
    // Atualizar gráfico
    chart.update();
  });
}

/**
 * Atualiza dados dos gráficos baseado no filtro
 * @param {string} filter - Filtro a ser aplicado ('week', 'month', 'year')
 */
function updateChartsData(filter) {
  // Exemplo - aqui seria uma chamada AJAX real
  console.log(`Atualizando gráficos com filtro: ${filter}`);
  
  // Simulação de dados novos
  setTimeout(() => {
    if (charts.deliveryStats) {
      const newData = {
        labels: filter === 'week' 
          ? ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb']
          : ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'],
        datasets: [
          {
            label: 'Entregas Realizadas',
            data: filter === 'week' 
              ? [65, 59, 80, 81, 56, 55, 40]
              : [300, 270, 350, 400, 380, 410, 430, 380, 320, 390, 410, 350],
            backgroundColor: 'rgba(99, 102, 241, 0.2)',
            borderColor: 'rgba(99, 102, 241, 1)',
            borderWidth: 2,
            tension: 0.4,
            fill: true
          },
          {
            label: 'Entregas Totais',
            data: filter === 'week' 
              ? [70, 65, 90, 97, 60, 60, 50]
              : [320, 290, 390, 450, 400, 440, 460, 410, 350, 420, 430, 380],
            backgroundColor: 'rgba(209, 213, 219, 0.2)',
            borderColor: 'rgba(156, 163, 175, 1)',
            borderWidth: 2,
            tension: 0.4,
            fill: true
          }
        ]
      };
      
      // Atualizar dados e redesenhar
      charts.deliveryStats.data = newData;
      charts.deliveryStats.update();
    }
  }, 300);
}

/**
 * Inicializa o gerenciamento de motoristas
 */
function initDriversManagement() {
  setupDriversTable();
  setupDriverModal();
  setupBulkActions();
  
  // Verificar mensagens de sucesso na URL
  const urlParams = new URLSearchParams(window.location.search);
  const successMsg = urlParams.get('success');
  if (successMsg) {
    showNotification(decodeURIComponent(successMsg), 'success');
  }
}

/**
 * Configura a tabela de motoristas
 */
function setupDriversTable() {
  // Filtro de busca
  const searchInput = document.getElementById('searchDriver');
  if (searchInput) {
    searchInput.addEventListener('input', filterDriversTable);
  }
  
  // Filtro de status
  const statusFilter = document.getElementById('statusFilter');
  if (statusFilter) {
    statusFilter.addEventListener('change', filterDriversTable);
  }
}

/**
 * Filtra a tabela de motoristas
 */
function filterDriversTable() {
  const searchInput = document.getElementById('searchDriver');
  const statusFilter = document.getElementById('statusFilter');
  const rows = document.querySelectorAll('#driversTableBody tr');
  
  if (!searchInput || !rows.length) return;
  
  const searchTerm = searchInput.value.toLowerCase();
  const statusValue = statusFilter ? statusFilter.value : 'all';
  
  rows.forEach(row => {
    const nameElement = row.querySelector('td:nth-child(2)');
    const statusElement = row.querySelector('td:nth-child(4) .status-pill');
    
    if (!nameElement) return;
    
    const name = nameElement.textContent.toLowerCase();
    const status = statusElement ? statusElement.textContent.toLowerCase() : '';
    
    const nameMatch = name.includes(searchTerm);
    const statusMatch = statusValue === 'all' || 
                        (statusValue === 'active' && status === 'ativo') ||
                        (statusValue === 'inactive' && status === 'inativo') ||
                        (statusValue === 'on_leave' && status === 'de folga');
    
    if (nameMatch && statusMatch) {
      row.style.display = '';
    } else {
      row.style.display = 'none';
    }
  });
}

/**
 * Configura o modal de motoristas
 */
function setupDriverModal() {
  const addDriverBtn = document.getElementById('addDriverBtn');
  const emptyStateAddBtn = document.getElementById('emptyStateAddBtn');
  const closeModalBtn = document.getElementById('closeModalBtn');
  const saveDriverBtn = document.getElementById('saveDriverBtn');
  const driverModal = document.getElementById('driverModal');
  
  if (!driverModal) return;
  
  // Abrir modal para adicionar
  if (addDriverBtn) {
    addDriverBtn.addEventListener('click', () => openDriverModal());
  }
  
  if (emptyStateAddBtn) {
    emptyStateAddBtn.addEventListener('click', () => openDriverModal());
  }
  
  // Fechar modal
  if (closeModalBtn) {
    closeModalBtn.addEventListener('click', () => {
      driverModal.classList.add('hidden');
    });
  }
  
  // Salvar motorista
  if (saveDriverBtn) {
    saveDriverBtn.addEventListener('click', saveDriver);
  }
  
  // Modal de exclusão
  const cancelDeleteBtn = document.getElementById('cancelDeleteBtn');
  const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');
  const deleteModal = document.getElementById('deleteConfirmModal');
  
  if (cancelDeleteBtn && deleteModal) {
    cancelDeleteBtn.addEventListener('click', () => {
      deleteModal.classList.add('hidden');
    });
  }
  
  if (confirmDeleteBtn && deleteModal) {
    confirmDeleteBtn.addEventListener('click', deleteDriver);
  }
}

/**
 * Abre o modal de motorista para adicionar/editar
 * @param {string|null} driverId - ID do motorista para editar (null para novo)
 */
function openDriverModal(driverId = null) {
  const driverModal = document.getElementById('driverModal');
  const modalTitle = document.getElementById('modalTitle');
  const driverForm = document.getElementById('driverForm');
  
  if (!driverModal || !modalTitle || !driverForm) return;
  
  // Reset form
  driverForm.reset();
  document.getElementById('driver_id').value = '';
  
  if (driverId) {
    // Editar existente
    modalTitle.textContent = 'Editar Motorista';
    document.getElementById('driver_id').value = driverId;
    
    // Aqui seria uma chamada AJAX para obter dados do motorista
    // Simulação:
    document.getElementById('driver_name').value = 'Nome do Motorista';
    document.getElementById('driver_email').value = 'email@exemplo.com';
    document.getElementById('driver_phone').value = '(11) 98765-4321';
    document.getElementById('driver_paack_id').value = 'PAACK123';
    document.getElementById('driver_status').value = 'active';
  } else {
    // Novo motorista
    modalTitle.textContent = 'Adicionar Motorista';
  }
  
  // Mostrar modal
  driverModal.classList.remove('hidden');
}

/**
 * Salva os dados do motorista
 */
function saveDriver() {
  const driverModal = document.getElementById('driverModal');
  const driverId = document.getElementById('driver_id').value;
  const isNewDriver = !driverId;
  
  // Validar formulário
  const form = document.getElementById('driverForm');
  const allInputs = form.querySelectorAll('input[required]');
  let isValid = true;
  
  allInputs.forEach(input => {
    if (!input.value.trim()) {
      isValid = false;
      input.classList.add('border-red-500');
    } else {
      input.classList.remove('border-red-500');
    }
  });
  
  if (!isValid) {
    showNotification('Por favor, preencha todos os campos obrigatórios.', 'error');
    return;
  }
  
  // Aqui seria uma chamada AJAX para salvar o motorista
  // Simulação de sucesso:
  const actionText = isNewDriver ? 'adicionado' : 'atualizado';
  driverModal.classList.add('hidden');
  showNotification(`Motorista ${actionText} com sucesso!`, 'success');
}

/**
 * Confirma a exclusão de um motorista
 * @param {string} driverId - ID do motorista
 */
function confirmDelete(driverId) {
  const deleteModal = document.getElementById('deleteConfirmModal');
  const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');
  
  if (!deleteModal || !confirmDeleteBtn) return;
  
  confirmDeleteBtn.dataset.driverId = driverId;
  deleteModal.classList.remove('hidden');
}

/**
 * Exclui um motorista
 */
function deleteDriver() {
  const deleteModal = document.getElementById('deleteConfirmModal');
  const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');
  const driverId = confirmDeleteBtn.dataset.driverId;
  
  // Aqui seria uma chamada AJAX para excluir o motorista
  // Simulação de sucesso:
  deleteModal.classList.add('hidden');
  showNotification('Motorista excluído com sucesso!', 'success');
}

/**
 * Configura ações em lote para a tabela de motoristas
 */
function setupBulkActions() {
  const selectAllCheckbox = document.getElementById('selectAll');
  const bulkActionBar = document.getElementById('bulkActionBar');
  const selectedCount = document.getElementById('selectedCount');
  const selectedCountLg = document.getElementById('selectedCountLg');
  const cancelBulkBtn = document.getElementById('cancelBulkSelection');
  
  if (!selectAllCheckbox || !bulkActionBar) return;
  
  // Select all
  selectAllCheckbox.addEventListener('change', () => {
    const isChecked = selectAllCheckbox.checked;
    document.querySelectorAll('.driver-checkbox').forEach(checkbox => {
      checkbox.checked = isChecked;
    });
    updateBulkActionBar();
  });
  
  // Individual checkboxes
  document.querySelectorAll('.driver-checkbox').forEach(checkbox => {
    checkbox.addEventListener('change', updateBulkActionBar);
  });
  
  // Cancelar seleção
  if (cancelBulkBtn) {
    cancelBulkBtn.addEventListener('click', () => {
      selectAllCheckbox.checked = false;
      document.querySelectorAll('.driver-checkbox').forEach(checkbox => {
        checkbox.checked = false;
      });
      bulkActionBar.classList.add('hidden');
    });
  }
  
  // Ações em lote
  document.querySelectorAll('.bulk-action-btn').forEach(button => {
    button.addEventListener('click', executeBulkAction);
  });
  
  /**
   * Atualiza a barra de ações em lote
   */
  function updateBulkActionBar() {
    const checkedBoxes = document.querySelectorAll('.driver-checkbox:checked');
    const count = checkedBoxes.length;
    
    if (count > 0) {
      bulkActionBar.classList.remove('hidden');
      selectedCount.textContent = `${count} selecionados`;
      selectedCountLg.textContent = `${count} motoristas selecionados`;
    } else {
      bulkActionBar.classList.add('hidden');
    }
  }
  
  /**
   * Executa uma ação em lote
   */
  function executeBulkAction() {
    const action = this.dataset.action;
    const checkedBoxes = document.querySelectorAll('.driver-checkbox:checked');
    const selectedIds = Array.from(checkedBoxes).map(cb => cb.value);
    
    if (!selectedIds.length) return;
    
    // Aqui seria uma chamada AJAX para executar a ação
    let actionText = '';
    switch(action) {
      case 'activate':
        actionText = 'ativados';
        break;
      case 'deactivate':
        actionText = 'desativados';
        break;
      case 'delete':
        actionText = 'excluídos';
        break;
    }
    
    // Simulação de sucesso
    selectAllCheckbox.checked = false;
    checkedBoxes.forEach(cb => {
      cb.checked = false;
    });
    bulkActionBar.classList.add('hidden');
    
    showNotification(`${selectedIds.length} motoristas ${actionText} com sucesso!`, 'success');
  }
}
