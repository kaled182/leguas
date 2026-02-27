/**
 * Base JavaScript - Dashboard Management
 * Moderno, responsivo, clean, integrado ao design customauth
 * - Sidebar funcional (desktop/mobile)
 * - Darkmode independente
 * - Botão de sincronização funcional
 * - Notificações toast
 */

let syncInProgress = false;

document.addEventListener('DOMContentLoaded', function() {
    initializeLucideIcons();
    initializeSidebar();
    initializeMobileMenu();
    initializeDarkMode();
    initializeSyncButton();
});

// ========== DARK MODE ========== //
function initializeDarkMode() {
    const savedTheme = localStorage.getItem('darkMode');
    if (savedTheme === 'true') {
        document.body.classList.add('dark-mode');
    }
    const darkBtn = document.getElementById('darkModeToggle');
    if (darkBtn) {
        darkBtn.onclick = function() {
            document.body.classList.toggle('dark-mode');
            localStorage.setItem('darkMode', document.body.classList.contains('dark-mode'));
        };
    }
}

// ========== SIDEBAR ========== //
function initializeSidebar() {
    // Collapse/expand logic pode ser implementado aqui se necessário
}

function initializeMobileMenu() {
    const mobileMenuBtn = document.getElementById('mobileMenuBtn');
    const mobileSidebar = document.getElementById('mobileSidebar');
    const mobileBackdrop = document.getElementById('mobileBackdrop');
    if (mobileMenuBtn && mobileSidebar && mobileBackdrop) {
        mobileMenuBtn.onclick = function() {
            mobileSidebar.classList.toggle('-translate-x-full');
            mobileBackdrop.classList.toggle('hidden');
        };
        mobileBackdrop.onclick = function() {
            mobileSidebar.classList.add('-translate-x-full');
            mobileBackdrop.classList.add('hidden');
        };
    }
}

// ========== SYNC FUNCTIONALITY ========== //
function initializeSyncButton() {
    const syncButton = document.getElementById('syncButton');
    const syncButtonMobile = document.getElementById('syncButtonMobile');
    function syncAction(btn, iconId) {
        if (!btn) return;
        btn.onclick = function(e) {
            e.preventDefault();
            if (syncInProgress) return;
            syncInProgress = true;
            const icon = document.getElementById(iconId);
            if (icon) icon.classList.remove('hidden');
            btn.disabled = true;
            fetch('/paack/sync/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': (document.cookie.match(/csrftoken=([^;]+)/)||[])[1] || ''
                },
                body: JSON.stringify({ force_refresh: true })
            })
            .then(res => res.json())
            .then(result => {
                if (result.success) {
                    showNotification('Sincronização concluída!', 'success');
                    setTimeout(() => window.location.reload(), 1200);
                } else {
                    showNotification('Erro: ' + (result.message || 'Falha na sincronização'), 'error');
                }
            })
            .catch(err => showNotification('Erro de rede: ' + err.message, 'error'))
            .finally(() => {
                if (icon) icon.classList.add('hidden');
                btn.disabled = false;
                syncInProgress = false;
            });
        };
    }
    syncAction(syncButton, 'syncIcon');
    syncAction(syncButtonMobile, 'syncIconMobile');
}

// ========== NOTIFICAÇÕES ========== //
function showNotification(message, type = "info") {
    const area = document.getElementById("notification-area");
    if (!area) return;
    const colors = {
        success: 'bg-green-500',
        error: 'bg-red-500',
        info: 'bg-blue-500'
    };
    const notif = document.createElement("div");
    notif.className = `px-4 py-2 rounded text-white shadow ${colors[type] || 'bg-gray-500'} mb-2 animate-fade-in`;
    notif.textContent = message;
    area.appendChild(notif);
    setTimeout(() => notif.remove(), 3500);
}

// ========== LUCIDE ICONS ========== //
function initializeLucideIcons() {
    if (typeof lucide !== 'undefined') lucide.createIcons();
}
// ========== TOOLTIP (opcional) ========== //
function setupTooltips() {
    // Implemente tooltips se necessário
}