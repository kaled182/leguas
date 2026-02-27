/**
 * Sidebar Manager - Controla o comportamento da sidebar responsiva
 */
class SidebarManager {
    constructor(options = {}) {
        // Configurações com valores padrões
        this.config = {
            sidebarId: 'sidebar',
            toggleId: 'sidebar-toggle',
            closeId: 'sidebar-close',
            overlayId: 'sidebar-overlay',
            breakpoint: 1024, // Ponto de quebra para modo desktop (lg)
            collapseOnEscape: true,
            preventBodyScroll: true,
            animationDuration: 300, // em ms, deve corresponder ao CSS
            ...options
        };
        
        // Elementos DOM principais
        this.sidebar = document.getElementById(this.config.sidebarId);
        this.sidebarToggle = document.getElementById(this.config.toggleId);
        this.sidebarClose = document.getElementById(this.config.closeId);
        this.sidebarOverlay = document.getElementById(this.config.overlayId);

        // Estado atual
        this.isOpen = false;
        
        this.initialize();
    }

    initialize() {
        if (!this.sidebar || !this.sidebarToggle) {
            console.warn('Sidebar elements not found');
            return;
        }

        // Configurar ARIA para acessibilidade
        this.sidebar.setAttribute('aria-expanded', 'false');
        this.sidebar.setAttribute('aria-label', 'Menu de navegação lateral');
        this.sidebarToggle.setAttribute('aria-controls', 'sidebar');
        this.sidebarToggle.setAttribute('aria-label', 'Abrir menu lateral');
        
        if (this.sidebarClose) {
            this.sidebarClose.setAttribute('aria-controls', 'sidebar');
            this.sidebarClose.setAttribute('aria-label', 'Fechar menu lateral');
        }

        // Inicializar listeners
        this.sidebarToggle.addEventListener('click', () => this.open());
        
        if (this.sidebarClose) {
            this.sidebarClose.addEventListener('click', () => this.close());
        }
        
        if (this.sidebarOverlay) {
            this.sidebarOverlay.addEventListener('click', () => this.close());
        }
        
        // Evento de redimensionamento para responsive design
        window.addEventListener('resize', () => this.handleResize());
        
        // Tratar tecla ESC para fechar sidebar
        if (this.config.collapseOnEscape) {
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' && this.isOpen) {
                    this.close();
                }
            });
        }
        
        // Inicializar estado apropriado para o tamanho de tela atual
        this.handleResize();
        
        // Log de inicialização bem-sucedida
        console.log('✅ SidebarManager inicializado com sucesso');
    }

    open() {
        if (!this.sidebar) return;
        
        this.isOpen = true;
        
        // Ocultar o botão de toggle quando a sidebar estiver aberta em mobile
        // Usamos z-index negativo para garantir que o botão fique efetivamente atrás da sidebar
        this.sidebarToggle.classList.add('opacity-0', 'invisible');
        this.sidebarToggle.style.zIndex = '-1'; // Garantir que o botão fique atrás quando aberto
        
        // Abrir a sidebar
        this.sidebar.classList.remove('-translate-x-full');
        this.sidebar.setAttribute('aria-expanded', 'true');
        
        // Mostrar overlay
        if (this.sidebarOverlay) {
            this.sidebarOverlay.classList.remove('hidden');
            setTimeout(() => {
                this.sidebarOverlay.classList.remove('opacity-0');
            }, 10);
        }

        // Adicionar classe no body para evitar scroll
        if (this.config.preventBodyScroll) {
            document.body.classList.add('overflow-hidden', 'lg:overflow-auto');
        }
        
        // Notificar acessibilidade
        this.notify('Menu lateral aberto');
    }

    close() {
        if (!this.sidebar) return;
        
        this.isOpen = false;
        
        // Fechar a sidebar primeiro, para evitar sobreposição visual
        this.sidebar.classList.add('-translate-x-full');
        this.sidebar.setAttribute('aria-expanded', 'false');
        
        // Esconder overlay
        if (this.sidebarOverlay) {
            this.sidebarOverlay.classList.add('opacity-0');
            setTimeout(() => {
                this.sidebarOverlay.classList.add('hidden');
            }, this.config.animationDuration);
        }

        // Remover classe no body para restaurar scroll
        if (this.config.preventBodyScroll) {
            document.body.classList.remove('overflow-hidden');
        }
        
        // Pequeno atraso para mostrar o botão toggle depois que a sidebar começar a fechar
        // para evitar que ele apareça sobre a sidebar durante a animação de fechamento
        setTimeout(() => {
            // Restaurar botão de toggle quando a sidebar for fechada
            this.sidebarToggle.classList.remove('opacity-0', 'invisible');
            this.sidebarToggle.style.zIndex = '40'; // Restaurar z-index original
        }, this.config.animationDuration / 3); // Atraso menor que a duração da animação
        
        // Notificar acessibilidade
        this.notify('Menu lateral fechado');
    }

    handleResize() {
        // Em telas grandes (desktop), gerenciar a sidebar automaticamente
        if (window.innerWidth >= this.config.breakpoint) {
            // Se estiver em tela grande e a sidebar estiver aberta em modo mobile, feche
            if (this.isOpen) {
                this.close();
            }
            
            // Garantir que o botão de toggle esteja sempre invisível em desktop
            this.sidebarToggle.classList.add('opacity-0', 'invisible');
            this.sidebarToggle.style.zIndex = '-1';
        } else {
            // Em mobile, garantir que o botão de toggle esteja visível se a sidebar estiver fechada
            if (!this.isOpen) {
                this.sidebarToggle.classList.remove('opacity-0', 'invisible');
                this.sidebarToggle.style.zIndex = '40';
            }
        }
    }
    
    notify(message) {
        // Notificação acessível (Anúncio para leitores de tela)
        let announcer = document.getElementById('a11y-announcer');
        
        // Criar o announcer se não existir
        if (!announcer) {
            announcer = document.createElement('div');
            announcer.id = 'a11y-announcer';
            announcer.setAttribute('aria-live', 'polite');
            announcer.setAttribute('aria-atomic', 'true');
            announcer.classList.add('sr-only');
            document.body.appendChild(announcer);
        }
        
        // Atualizar o conteúdo para anunciar aos leitores de tela
        announcer.textContent = message;
    }
}

// Inicializar ícones e sidebar quando DOM estiver pronto
document.addEventListener('DOMContentLoaded', () => {
    // Inicializar ícones
    if (window.lucide) {
        lucide.createIcons();
    }
    
    // Inicializar sidebar com configurações avançadas
    const sidebarManager = new SidebarManager({
        breakpoint: 1024, // lg breakpoint
        collapseOnEscape: true,
        preventBodyScroll: true,
        animationDuration: 300
    });
    
    // Expor para debugging e acesso via console
    window.sidebarManager = sidebarManager;
    
    console.log('🧭 Sistema de navegação lateral inicializado');
});

/**
 * Theme Manager - Gerencia o tema claro/escuro
 */
class ThemeManager {
    constructor() {
        this.toggleButton = document.getElementById('darkModeToggle');
        this.htmlElement = document.documentElement;
        this.themeKey = 'management-theme';
        
        this.initialize();
    }
    
    initialize() {
        if (!this.toggleButton) return;
        
        // Aplicar tema salvo
        this.applyTheme();
        
        // Adicionar evento de toggle
        this.toggleButton.addEventListener('click', () => this.toggle());
        
        // Observar preferência do sistema
        this.watchSystemPreference();
    }
    
    toggle() {
        const currentTheme = this.getTheme();
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        
        this.setTheme(newTheme);
        
        // Animar ícones
        this.animateIcons();
    }
    
    getTheme() {
        return this.htmlElement.classList.contains('dark') ? 'dark' : 'light';
    }
    
    setTheme(theme) {
        if (theme === 'dark') {
            this.htmlElement.classList.add('dark');
        } else {
            this.htmlElement.classList.remove('dark');
        }
        
        localStorage.setItem(this.themeKey, theme);
    }
    
    applyTheme() {
        const savedTheme = localStorage.getItem(this.themeKey);
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        
        if (savedTheme === 'dark' || (!savedTheme && prefersDark)) {
            this.setTheme('dark');
        } else {
            this.setTheme('light');
        }
    }
    
    watchSystemPreference() {
        // Se o usuário não definiu tema, acompanhar preferência do sistema
        const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
        mediaQuery.addEventListener('change', (e) => {
            if (!localStorage.getItem(this.themeKey)) {
                this.setTheme(e.matches ? 'dark' : 'light');
            }
        });
    }
    
    animateIcons() {
        const sunIcon = this.toggleButton.querySelector('.sun-icon');
        const moonIcon = this.toggleButton.querySelector('.moon-icon');
        
        if (sunIcon && moonIcon) {
            if (this.getTheme() === 'dark') {
                sunIcon.classList.add('scale-0');
                moonIcon.classList.remove('scale-0');
            } else {
                sunIcon.classList.remove('scale-0');
                moonIcon.classList.add('scale-0');
            }
        }
    }
}

/**
 * Notification Manager - Sistema de notificações melhorado
 */
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
            console.warn('Notification container not found');
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

// Inicializar quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', function () {
    console.log('🌟 DOM carregado, inicializando aplicação...');
    
    // Inicializar ícones Lucide
    if (window.lucide) {
        lucide.createIcons();
        console.log('🎨 Ícones Lucide inicializados');
    } else {
        console.warn('⚠️ Lucide não está disponível');
    }
    
    // Inicializar temas
    const themeManager = new ThemeManager();
    window.themeManager = themeManager;
    console.log('🔆 Sistema de temas inicializado');
    
    console.log('✅ Inicialização completa!');
});