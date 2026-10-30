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

  document.addEventListener('keydown', (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
      const search = document.getElementById('lf-global-search');
      if (search) { event.preventDefault(); search.focus(); }
    }
  });

  window.lfToast = toast;
})();
