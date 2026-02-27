/*
// ===================== SYNC BUTTON =====================
function getCookie(name) {
  // Primeiro tenta pegar do meta tag
  const metaToken = document.querySelector('meta[name="csrf-token"]');
  if (metaToken && name === 'csrftoken') {
    console.log('🔑 CSRF token obtido do meta tag');
    return metaToken.getAttribute('content');
  }
  
  // Se não encontrar, tenta pegar do cookie
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        console.log('🔑 CSRF token obtido do cookie');
        break;
      }
    }
  }
  
  if (!cookieValue) {
    console.warn('⚠️ CSRF token não encontrado!');
  }
  
  return cookieValue;
}

function updateSyncButtonState(button, isLoading) {
  if (!button) return;
  
  const icon = button.querySelector('[data-lucide]');
  const text = button.querySelector('.sync-text');
  
  if (isLoading) {
    button.disabled = true;
    button.classList.add('opacity-75', 'cursor-not-allowed');
    if (icon) {
      icon.setAttribute('data-lucide', 'loader-2');
      icon.classList.add('animate-spin');
    }
    if (text) text.textContent = 'Sincronizando...';
  } else {
    button.disabled = false;
    button.classList.remove('opacity-75', 'cursor-not-allowed');
    if (icon) {
      icon.setAttribute('data-lucide', 'refresh-cw');
      icon.classList.remove('animate-spin');
    }
    if (text) text.textContent = 'Sincronizar';
    lucide.createIcons();
  }
}

function performSync() {
  console.log('🔄 Iniciando sincronização...');
  
  const syncBtn = document.getElementById('syncButton');
  const syncBtnMobile = document.getElementById('syncButtonMobile');
  
  // Verificar se os botões existem
  console.log('Botões encontrados:', { syncBtn: !!syncBtn, syncBtnMobile: !!syncBtnMobile });
  
  // Atualizar estado dos botões
  updateSyncButtonState(syncBtn, true);
  updateSyncButtonState(syncBtnMobile, true);
  
  showNotification('Iniciando sincronização...', 'info');
  
  fetch('/paack/sync/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCookie('csrftoken')
    },
    body: JSON.stringify({ 
      force_refresh: true,
      timestamp: new Date().getTime()
    })
  })
  .then(response => {
    console.log('📡 Resposta recebida:', response.status, response.statusText);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    return response.json();
  })
  .then(result => {
    console.log('✅ Resultado da sincronização:', result);
    if (result.success) {
      const message = result.message || `Sincronização concluída! ${result.new_orders || 0} novos pedidos processados.`;
      showNotification(message, 'success');
      
      // Recarregar página após delay
      setTimeout(() => {
        console.log('🔄 Recarregando página...');
        window.location.reload();
      }, 2000);
    } else {
      throw new Error(result.error || result.message || 'Falha na sincronização');
    }
  })
  .catch(error => {
    console.error('❌ Erro na sincronização:', error);
    showNotification(
      `Erro na sincronização: ${error.message}`, 
      'error',
      8000
    );
  })
  .finally(() => {
    console.log('🔄 Restaurando estado dos botões...');
    // Restaurar estado dos botões
    updateSyncButtonState(syncBtn, false);
    updateSyncButtonState(syncBtnMobile, false);
  });
}

function initSyncButton() {
  console.log('🚀 Inicializando botão de sincronização...');
  
  const syncBtn = document.getElementById('syncButton');
  const syncBtnMobile = document.getElementById('syncButtonMobile');
  
  console.log('Botões encontrados na inicialização:', { 
    syncBtn: !!syncBtn, 
    syncBtnMobile: !!syncBtnMobile 
  });
  
  if (syncBtn) {
    console.log('✅ Adicionando event listener ao botão principal');
    syncBtn.addEventListener('click', function(e) {
      e.preventDefault();
      console.log('🖱️ Botão de sincronização clicado!');
      performSync();
    });
  } else {
    console.warn('⚠️ Botão de sincronização principal não encontrado');
  }
  
  if (syncBtnMobile) {
    console.log('✅ Adicionando event listener ao botão mobile');
    syncBtnMobile.addEventListener('click', function(e) {
      e.preventDefault();
      console.log('🖱️ Botão de sincronização mobile clicado!');
      performSync();
    });
  } else {
    console.log('ℹ️ Botão de sincronização mobile não encontrado (normal se não houver)');
  }
}
*/