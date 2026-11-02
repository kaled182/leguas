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
    'Cancel': 'Retirado da rota', 'Baixa': 'Baixa', 'Driver_received_incidence': 'Recebido anormal',
    'Return to seller success': 'Devolvido ao remetente',
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

  // ─── Avisos: modal da marca no lugar de alert/confirm/prompt ───
  const DANGER = /\b(apagar|eliminar|remover|rejeitar|irrevers|definitiv|desfazer|cancelar est|desconectar|desactivar|desativar)/i;
  const ERROR = /^[\s❌⚠️]*(erro|falh)|^[\s]*[❌⚠]/i;
  const SUCCESS = /^[\s]*[✅✓]|^[\s]*(sucesso|guardad|criad|enviad|importad|conclu)/i;

  function cleanText(text) {
    return String(text ?? '').replace(/\\n/g, '\n').replace(/^[\s✅❌⚠️✓✔ℹ]+/u, '');
  }

  function openDialog({ title, message, input, confirmLabel, cancelLabel, variant }) {
    return new Promise((resolve) => {
      const dialog = document.createElement('dialog');
      dialog.className = 'lf-modal';
      dialog.setAttribute('aria-labelledby', 'lf-dialog-title');
      dialog.innerHTML = `
        <div class="lf-modal-head"><span id="lf-dialog-title"></span></div>
        <div class="lf-modal-body"><p style="margin:0;white-space:pre-line;overflow-wrap:anywhere"></p></div>
        <div class="lf-modal-foot"></div>`;
      dialog.querySelector('#lf-dialog-title').textContent = title;
      dialog.querySelector('.lf-modal-body p').textContent = message;
      const asks = input !== undefined;
      let field = null;
      if (asks) {
        field = document.createElement('input');
        field.type = 'text';
        field.value = input ?? '';
        field.style.cssText = 'width:100%;margin-top:var(--space-3);padding:var(--space-2) var(--space-3);border:1px solid var(--color-border);border-radius:var(--radius-md);background:var(--color-bg);color:var(--color-text);font:inherit';
        dialog.querySelector('.lf-modal-body').appendChild(field);
      }
      const foot = dialog.querySelector('.lf-modal-foot');
      let result = asks ? null : false;
      if (cancelLabel) {
        const cancel = document.createElement('button');
        cancel.type = 'button';
        cancel.className = 'lf-btn lf-btn-ghost';
        cancel.textContent = cancelLabel;
        cancel.addEventListener('click', () => dialog.close());
        foot.appendChild(cancel);
      }
      const ok = document.createElement('button');
      ok.type = 'button';
      ok.className = `lf-btn lf-btn-${variant}`;
      ok.textContent = confirmLabel;
      ok.addEventListener('click', () => { result = field ? field.value : true; dialog.close(); });
      foot.appendChild(ok);
      if (field) field.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); ok.click(); } });
      dialog.addEventListener('click', (e) => { if (e.target === dialog && cancelLabel) dialog.close(); });
      dialog.addEventListener('close', () => { dialog.remove(); resolve(result); });
      document.body.appendChild(dialog);
      dialog.showModal();
      (field || ok).focus();
    });
  }

  // Devolve true ou false. Substitui confirm().
  window.lfConfirm = (message, opts = {}) => {
    const text = cleanText(message);
    const danger = opts.danger ?? DANGER.test(text);
    return openDialog({
      title: opts.title || (danger ? 'Confirmar ação' : 'Confirmar'),
      message: text,
      confirmLabel: opts.confirmLabel || 'Confirmar',
      cancelLabel: 'Cancelar',
      variant: danger ? 'danger' : 'primary',
    });
  };

  // Devolve o texto escrito, ou null se cancelar. Substitui prompt().
  window.lfPrompt = (message, value = '', opts = {}) => openDialog({
    title: opts.title || 'Preencher',
    message: cleanText(message),
    input: value ?? '',
    confirmLabel: opts.confirmLabel || 'OK',
    cancelLabel: 'Cancelar',
    variant: 'primary',
  });

  // Aviso com um só botão. Substitui alert(), que deixa de bloquear a página.
  const PENDING_KEY = 'lf-pending-alert';
  const openAlerts = new Set();
  window.lfAlert = (message, opts = {}) => {
    const raw = String(message ?? '');
    const text = cleanText(raw);
    const item = { text, title: opts.title || (ERROR.test(raw) ? 'Erro' : SUCCESS.test(raw) ? 'Concluído' : 'Aviso') };
    openAlerts.add(item);
    return openDialog({ title: item.title, message: text, confirmLabel: 'OK', variant: 'primary' })
      .then(() => { openAlerts.delete(item); });
  };
  window.alert = (message) => { window.lfAlert(message); };

  // Se a página mudar com um aviso aberto, o aviso aparece na página seguinte.
  window.addEventListener('pagehide', () => {
    const [item] = openAlerts;
    if (!item) return;
    try { sessionStorage.setItem(PENDING_KEY, JSON.stringify({ ...item, at: Date.now() })); } catch (e) { /* sem armazenamento */ }
  });

  document.addEventListener('DOMContentLoaded', () => {
    let pending = null;
    try { pending = JSON.parse(sessionStorage.getItem(PENDING_KEY) || 'null'); } catch (e) { /* sem armazenamento */ }
    try { sessionStorage.removeItem(PENDING_KEY); } catch (e) { /* sem armazenamento */ }
    if (pending && Date.now() - pending.at < 15000) window.lfAlert(pending.text, { title: pending.title });
  });

  // Botões, ligações e formulários com data-confirm="Texto".
  document.addEventListener('click', (event) => {
    const el = event.target.closest('[data-confirm]:not(form)');
    if (!el) return;
    if (el.dataset.confirmed === '1') { delete el.dataset.confirmed; return; }
    event.preventDefault();
    event.stopImmediatePropagation();
    window.lfConfirm(el.dataset.confirm).then((ok) => {
      if (!ok) return;
      if (el.form && el.type === 'submit') { el.form.dataset.confirmed = '1'; el.form.requestSubmit(el); return; }
      el.dataset.confirmed = '1';
      el.click();
    });
  }, true);
  document.addEventListener('submit', (event) => {
    const form = event.target;
    if (!form.matches('form[data-confirm]')) return;
    if (form.dataset.confirmed === '1') { delete form.dataset.confirmed; return; }
    event.preventDefault();
    event.stopImmediatePropagation();
    const submitter = event.submitter;
    window.lfConfirm(form.dataset.confirm).then((ok) => {
      if (!ok) return;
      form.dataset.confirmed = '1';
      form.requestSubmit(submitter && submitter.form === form ? submitter : undefined);
    });
  }, true);
})();
