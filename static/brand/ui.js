// Comportamento dos componentes base. Sem dependências.
(function () {
  function toast(message, tone) {
    const region = document.getElementById('lf-toasts');
    if (!region) return;
    const item = document.createElement('div');
    item.className = 'lf-toast lf-tone-' + (tone || 'success');
    item.setAttribute('role', 'status');
    item.textContent = message;
    region.appendChild(item);
    setTimeout(() => item.remove(), 5000);
  }

  document.addEventListener('click', (event) => {
    const opener = event.target.closest('[data-modal-open]');
    if (opener) document.getElementById(opener.dataset.modalOpen)?.showModal();
    const closer = event.target.closest('[data-modal-close]');
    if (closer) closer.closest('dialog')?.close();
    const theme = event.target.closest('[data-theme-toggle]');
    if (theme) {
      const dark = document.documentElement.classList.toggle('dark');
      try { localStorage.setItem('lf-theme', dark ? 'dark' : 'light'); } catch (e) { /* sem armazenamento */ }
    }
    const sidebar = event.target.closest('[data-sidebar-toggle]');
    if (sidebar) {
      const el = document.getElementById('lf-sidebar');
      const collapsed = el.dataset.collapsed !== 'true';
      el.dataset.collapsed = String(collapsed);
      try { localStorage.setItem('lf-sidebar', String(collapsed)); } catch (e) { /* sem armazenamento */ }
    }
  });

  document.addEventListener('click', (event) => {
    const shell = document.getElementById('lf-shell');
    if (!shell) return;
    if (event.target.closest('[data-drawer-open]')) shell.dataset.drawer = 'open';
    if (event.target.closest('[data-drawer-close]')) delete shell.dataset.drawer;
    const results = document.getElementById('lf-search-results');
    if (results && !event.target.closest('.lf-search')) results.hidden = true;
  });

  function escapeHtml(text) {
    const box = document.createElement('div');
    box.textContent = text;
    return box.innerHTML;
  }

  function renderSearch(results, data) {
    if (!data.groups.length) {
      results.innerHTML = '<p class="lf-search-group">Sem resultados.</p>';
    } else {
      results.innerHTML = data.groups.map((group) => `
        <p class="lf-search-group">${escapeHtml(group.label)}</p>
        ${group.results.map((item) => `
          <a class="lf-search-item" href="${escapeHtml(item.url)}">${escapeHtml(item.label)}
            ${item.note ? `<span class="lf-search-note">${escapeHtml(item.note)}</span>` : ''}
          </a>`).join('')}`).join('');
    }
    results.hidden = false;
  }

  function setupSearch() {
    const input = document.getElementById('lf-global-search');
    const results = document.getElementById('lf-search-results');
    if (!input || !results || !input.dataset.searchUrl) return;
    let timer;
    input.addEventListener('input', () => {
      clearTimeout(timer);
      const q = input.value.trim();
      if (q.length < 2) { results.hidden = true; return; }
      timer = setTimeout(async () => {
        const response = await fetch(`${input.dataset.searchUrl}?q=${encodeURIComponent(q)}`);
        if (response.ok && input.value.trim() === q) renderSearch(results, await response.json());
      }, 200);
    });
    input.addEventListener('keydown', (event) => {
      const links = [...results.querySelectorAll('a')];
      if (event.key === 'Escape') results.hidden = true;
      if (event.key === 'Enter' && links.length) { event.preventDefault(); links[0].click(); }
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    setupSearch();
    let collapsed = false;
    try { collapsed = localStorage.getItem('lf-sidebar') === 'true'; } catch (e) { /* sem armazenamento */ }
    const sidebar = document.getElementById('lf-sidebar');
    if (sidebar && collapsed && window.innerWidth >= 1024) sidebar.dataset.collapsed = 'true';
  });

  document.addEventListener('keydown', (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
      const search = document.getElementById('lf-global-search');
      if (search) { event.preventDefault(); search.focus(); }
    }
  });

  const STATUS_LABELS = {
    'Delivered': 'Entregue', 'Attempt Failure': 'Falhada', 'Driver_received': 'Em distribuição',
    'Assigned': 'Atribuído', 'Unassign': 'Por atribuir', 'Stale_Armazem': 'Parado no armazém',
    'Wrong HUB': 'Hub errado', 'Exception': 'Exceção',
  };

  // Datas ISO da API passam a dd/mm/aaaa, com a hora quando existe.
  window.lfDate = (value) => {
    const match = String(value || '').match(/^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}:\d{2}))?/);
    if (!match) return value || '';
    return `${match[3]}/${match[2]}/${match[1]}${match[4] ? ` ${match[4]}` : ''}`;
  };
  // Formato pt-PT: 1 234,56 €
  window.lfEur = (value) => {
    const number = Number(value);
    if (!Number.isFinite(number)) return '';
    const [whole, cents] = Math.abs(number).toFixed(2).split('.');
    return `${number < 0 ? '−' : ''}${whole.replace(/\B(?=(\d{3})+(?!\d))/g, '\u00a0')},${cents}\u00a0€`;
  };
  window.lfStatus = (value) => STATUS_LABELS[value] || value;
  window.lfToast = toast;
})();
