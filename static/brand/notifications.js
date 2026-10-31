class NotificationManager {
    constructor() {
        this.container = document.getElementById('notification-area');
        this.maxNotifications = 5;
        this.notificationQueue = [];
        this.activeNotifications = 0;
        
        this.initialize();
    }
    
    initialize() {
        if (!this.container) {
            return;
        }
        
        // Garantir que o container tem a posição e estilo corretos
        this.container.classList.add('fixed', 'top-4', 'right-4', 'z-50', 'space-y-3', 'max-w-sm', 'pointer-events-none');
    }
    
    show(message, options = {}) {
        const defaults = {
            type: 'info',
            duration: 5000,
            icon: null,
            title: null,
            actions: []
        };
        
        const config = { ...defaults, ...options };
        
        // Se já temos muitas notificações, colocar na fila
        if (this.activeNotifications >= this.maxNotifications) {
            this.notificationQueue.push({ message, config });
            return;
        }
        
        this.createNotification(message, config);
    }
    
    createNotification(message, config) {
        if (!this.container) return;
        
        this.activeNotifications++;
        
        // Criar elemento da notificação
        const notification = document.createElement('div');
        
        // Aplicar classes base
        notification.className = `notification p-4 rounded-lg border shadow-lg backdrop-blur-sm transform transition-all duration-300 translate-x-full pointer-events-auto`;
        
        // Aplicar cores de acordo com o tipo
        const colors = {
            success: 'bg-success-50 dark:bg-success-900/20 border-success-200 dark:border-success-800 text-success-800 dark:text-success-200',
            error: 'bg-danger-50 dark:bg-danger-900/20 border-danger-200 dark:border-danger-800 text-danger-800 dark:text-danger-200',
            warning: 'bg-warning-50 dark:bg-warning-900/20 border-warning-200 dark:border-warning-800 text-warning-800 dark:text-warning-200',
            info: 'bg-primary-50 dark:bg-primary-900/20 border-primary-200 dark:border-primary-800 text-primary-800 dark:text-primary-200'
        };
        
        notification.classList.add(...(colors[config.type] || colors.info).split(' '));
        
        // Determinar o ícone
        let iconName = config.icon;
        if (!iconName) {
            iconName = {
                success: 'check-circle',
                error: 'alert-circle',
                warning: 'alert-triangle',
                info: 'info'
            }[config.type] || 'bell';
        }
        
        // Construir conteúdo
        const hasTitle = config.title !== null;
        
        notification.innerHTML = `
            <div class="flex items-start">
                <div class="flex-shrink-0 mr-3">
                    <i data-lucide="${iconName}" class="w-5 h-5"></i>
                </div>
                <div class="flex-1 pt-0.5">
                    ${hasTitle ? `<h4 class="font-bold text-sm">${config.title}</h4>` : ''}
                    <p class="text-sm ${hasTitle ? 'mt-1' : ''}">${message}</p>
                    
                    ${config.actions.length > 0 ? `
                    <div class="flex items-center justify-end gap-2 mt-2">
                        ${config.actions.map((action, index) => `
                            <button class="text-xs py-1 px-2 rounded ${action.primary ? 'bg-opacity-20 bg-current' : ''}" 
                                    data-action-index="${index}">
                                ${action.label}
                            </button>
                        `).join('')}
                    </div>
                    ` : ''}
                </div>
                <button class="flex-shrink-0 ml-3 text-current opacity-70 hover:opacity-100 close-notification">
                    <i data-lucide="x" class="w-4 h-4"></i>
                </button>
            </div>
        `;
        
        // Adicionar ao container
        this.container.appendChild(notification);
        
        // Inicializar ícones Lucide
        if (window.lucide) {
            lucide.createIcons({
                root: notification
            });
        }
        
        // Configurar evento de fechar
        const closeBtn = notification.querySelector('.close-notification');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.dismiss(notification));
        }
        
        // Configurar ações
        if (config.actions.length > 0) {
            const actionButtons = notification.querySelectorAll('[data-action-index]');
            actionButtons.forEach(button => {
                const index = parseInt(button.dataset.actionIndex, 10);
                if (index >= 0 && index < config.actions.length) {
                    const action = config.actions[index];
                    button.addEventListener('click', () => {
                        if (typeof action.onClick === 'function') {
                            action.onClick();
                        }
                        this.dismiss(notification);
                    });
                }
            });
        }
        
        // Animar entrada
        requestAnimationFrame(() => {
            notification.classList.remove('translate-x-full');
        });
        
        // Auto remover após duração
        if (config.duration > 0) {
            setTimeout(() => {
                this.dismiss(notification);
            }, config.duration);
        }
        
        // Retornar para referenciar se necessário
        return notification;
    }
    
    dismiss(notification) {
        if (!notification) return;
        
        // Adicionar classe para animar saída
        notification.classList.add('translate-x-full');
        
        // Remover após animação
        setTimeout(() => {
            notification.remove();
            this.activeNotifications--;
            
            // Processar próxima notificação na fila, se houver
            if (this.notificationQueue.length > 0) {
                const next = this.notificationQueue.shift();
                this.createNotification(next.message, next.config);
            }
        }, 300);
    }
}

// Inicializar o gerenciador de notificações globalmente
const notificationManager = new NotificationManager();

// Manter a função global para compatibilidade
function showNotification(message, type = 'info', duration = 5000) {
    notificationManager.show(message, { type, duration });
}

// Expor funções e objetos globais
window.showNotification = showNotification;
window.notifications = notificationManager;
