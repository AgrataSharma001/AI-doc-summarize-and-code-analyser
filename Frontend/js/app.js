(() => {
  const $ = (id) => document.getElementById(id);
  const mobile = matchMedia('(max-width: 760px)');
  const MAX_FILES = 5, MAX_BYTES = 10 * 1024 * 1024;
  let mode = 'document', currentId = null, chats = [], files = [], active = null, user = null, storageKey = null;
  let toastTimer, sessionReady = false, loggingOut = false;
  const uid = () => crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const announce = (text) => { $('app-status').textContent = text; };
  function notify(text) { $('toast').textContent = text; $('toast').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => { $('toast').hidden = true; }, 4500); announce(text); }
  function error(text = '') { $('composer-error').textContent = text; $('composer-error').hidden = !text; }
  function persist() { if (!storageKey) return; try { sessionStorage.setItem(storageKey, JSON.stringify(chats.slice(0, 30))); } catch { notify('Session storage is full or unavailable. New messages will remain in memory.'); } }
  function loadHistory() {
    chats = [];
    try {
      const saved = JSON.parse(sessionStorage.getItem(storageKey) || '[]');
      if (Array.isArray(saved)) chats = saved.filter((chat) => chat && typeof chat.id === 'string' && typeof chat.title === 'string' && ['document', 'code'].includes(chat.mode) && Array.isArray(chat.messages)).slice(0, 30).map((chat) => ({ ...chat, messages: chat.messages.filter((m) => m && ['user','assistant','error'].includes(m.role) && typeof m.content === 'string').map((m) => ({ ...m, files: Array.isArray(m.files) ? m.files.filter((f) => f && typeof f.name === 'string') : [] })) }));
    } catch {}
    renderRecent();
  }
  function sidebar(open) { document.body.classList.toggle('sidebar-collapsed', !open); $('sidebar').inert = !open; $('main').inert = open && mobile.matches; $('open-sidebar').hidden = open && !mobile.matches; $('open-sidebar').setAttribute('aria-expanded', String(open)); $('sidebar-overlay').hidden = !open || !mobile.matches; }
  sidebar(!mobile.matches); mobile.addEventListener('change', () => sidebar(!mobile.matches));
  $('open-sidebar').addEventListener('click', () => { sidebar(true); if (mobile.matches) $('close-sidebar').focus(); });
  $('close-sidebar').addEventListener('click', () => { sidebar(false); $('open-sidebar').focus(); });
  $('sidebar-overlay').addEventListener('click', () => sidebar(false));
  function closeMenus() { $('account-menu').hidden = true; $('account-button').setAttribute('aria-expanded', 'false'); $('attach-menu').hidden = true; $('attach-button').setAttribute('aria-expanded', 'false'); }
  document.addEventListener('click', (event) => { if (!event.target.closest('.sidebar-bottom') && !event.target.closest('.attach-control')) closeMenus(); });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape') { if (!$('attach-menu').hidden) $('attach-button').focus(); else if (!$('account-menu').hidden) $('account-button').focus(); closeMenus(); if (mobile.matches && !document.querySelector('dialog[open]')) sidebar(false); } });
  function setMode(next) {
    mode = next;
    $('document-mode').classList.toggle('active', mode === 'document'); $('document-mode').setAttribute('aria-pressed', String(mode === 'document'));
    $('code-mode').classList.toggle('active', mode === 'code'); $('code-mode').setAttribute('aria-pressed', String(mode === 'code'));
    $('workspace-title').textContent = mode === 'document' ? 'Document workspace' : 'Code workspace';
    $('welcome-title').textContent = mode === 'document' ? 'What are we understanding today?' : 'Let’s make sense of your code.';
    $('welcome-description').textContent = mode === 'document' ? 'A long document. A tricky piece of code.\nLet’s make it make sense.' : 'Untangle the logic. Explore the edge cases.\nBuild a clearer picture, one question at a time.';
    $('prompt').placeholder = mode === 'document' ? 'Ask anything about your document, or drop a file here…' : 'Paste Python code, attach a .py file, or ask a follow-up…';
    $('mode-chip').querySelector('use').setAttribute('href', mode === 'document' ? '#i-doc' : '#i-code'); $('mode-chip').querySelector('span').textContent = mode === 'document' ? 'Document summary' : 'Python code analyzer';
  }
  function clearFiles() { files.forEach((item) => { if (item.url) URL.revokeObjectURL(item.url); }); files = []; renderFiles(); }
  function cancel() { if (!active) return; const request = active; active = null; request.controller.abort(); const chat = chats.find((c) => c.id === request.chatId); if (chat) chat.messages.push({ role: 'error', content: 'Request canceled. The server may still finish processing.' }); setBusy(false); persist(); }
  function newChat(next = mode) { cancel(); currentId = null; setMode(next); clearFiles(); $('prompt').value = ''; resize(); error(); render(); renderRecent(); if (mobile.matches) sidebar(false); closeMenus(); $('prompt').focus(); }
  $('new-chat').addEventListener('click', () => newChat()); $('document-mode').addEventListener('click', () => newChat('document')); $('code-mode').addEventListener('click', () => newChat('code'));
  function renderRecent() {
    $('recent-chats').replaceChildren(); $('no-chats').hidden = chats.length > 0;
    chats.forEach((chat) => { const button = document.createElement('button'); button.className = `recent-chat${chat.id === currentId ? ' selected' : ''}`; button.textContent = chat.title; button.title = chat.title; if (chat.id === currentId) button.setAttribute('aria-current', 'true'); button.addEventListener('click', () => { cancel(); clearFiles(); currentId = chat.id; setMode(chat.mode); $('prompt').value = ''; resize(); error(); render(); renderRecent(); if (mobile.matches) sidebar(false); }); $('recent-chats').append(button); });
  }
  function render() {
    const chat = chats.find((c) => c.id === currentId), hasMessages = Boolean(chat?.messages.length);
    document.body.classList.toggle('chat-active', hasMessages); $('welcome').hidden = hasMessages; $('messages').hidden = !hasMessages; $('suggestions').hidden = hasMessages; $('welcome-footer').hidden = hasMessages;
    $('messages').replaceChildren(); chat?.messages.forEach((message) => $('messages').append(window.DocodeResults.render(message, notify)));
    if (active?.chatId === currentId) { const pending = document.createElement('div'); pending.className = 'pending-text'; pending.id = 'pending'; const dot = document.createElement('span'); dot.className = 'pulse'; pending.append(dot, 'Reading, connecting, making sense of it…'); $('messages').append(pending); }
    $('messages').setAttribute('aria-busy', String(Boolean(active)));
  }
  function resize() { $('prompt').style.height = 'auto'; $('prompt').style.height = `${Math.min($('prompt').scrollHeight, 220)}px`; updateSend(); }
  function updateSend() { $('send-button').disabled = Boolean(active) || !sessionReady || loggingOut || (!$('prompt').value.trim() && files.length === 0); }
  function setBusy(busy) { $('send-button').hidden = busy; $('stop-button').hidden = !busy; $('prompt').disabled = busy; $('attach-button').disabled = busy; updateSend(); renderFiles(); }
  $('prompt').addEventListener('input', resize);
  $('prompt').addEventListener('keydown', (event) => { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && !mobile.matches) { event.preventDefault(); if (!$('send-button').disabled) $('chat-form').requestSubmit(); } });
  $('attach-button').addEventListener('click', () => { const opening = $('attach-menu').hidden; closeMenus(); $('attach-menu').hidden = !opening; $('attach-button').setAttribute('aria-expanded', String(opening)); if (opening) $('attach-documents').focus(); });
  for (const [id, accept] of Object.entries({ 'attach-documents': '.pdf,.docx,.txt', 'attach-photos': '.png,.jpg,.jpeg,.webp', 'attach-code': '.py' })) $(id).addEventListener('click', () => { $('file-input').accept = accept; closeMenus(); $('file-input').click(); });
  function addFiles(incoming) {
    if (active) return;
    error(); const problems = [];
    for (const file of incoming) {
      const ext = file.name.split('.').pop().toLowerCase();
      if (!['pdf','docx','txt','py','png','jpg','jpeg','webp'].includes(ext)) { problems.push(`${file.name}: unsupported file type.`); continue; }
      if (!file.size) { problems.push(`${file.name}: the file is empty.`); continue; }
      if (files.some((item) => item.file.name === file.name && item.file.size === file.size && item.file.lastModified === file.lastModified)) continue;
      if (files.length >= MAX_FILES || file.size + files.reduce((sum, item) => sum + item.file.size, 0) > MAX_BYTES) { problems.push('Attach up to 5 files, with a combined size of 10 MB.'); break; }
      const photo = ['png','jpg','jpeg','webp'].includes(ext); files.push({ id: uid(), file, url: photo ? URL.createObjectURL(file) : null });
    }
    renderFiles(); updateSend(); if (problems.length) error(problems.join(' '));
  }
  function renderFiles() {
    $('attachments').replaceChildren(); $('attachments').hidden = files.length === 0;
    files.forEach((item) => { const chip = document.createElement('div'); chip.className = 'attachment';
      if (item.url) { const img = document.createElement('img'); img.src = item.url; img.alt = ''; chip.append(img); }
      const info = document.createElement('span'); info.className = 'attachment-info'; const name = document.createElement('strong'); name.textContent = item.file.name; const size = document.createElement('span'); size.textContent = `${Math.ceil(item.file.size / 1024)} KB${item.url ? ' · image' : ''}`; info.append(name, size);
      const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'icon-button'; remove.textContent = '×'; remove.disabled = Boolean(active); remove.setAttribute('aria-label', `Remove ${item.file.name}`); remove.addEventListener('click', () => { if (item.url) URL.revokeObjectURL(item.url); files = files.filter((f) => f.id !== item.id); renderFiles(); updateSend(); }); chip.append(info, remove); $('attachments').append(chip);
    });
  }
  $('file-input').addEventListener('change', (event) => { addFiles([...event.target.files]); event.target.value = ''; });
  const composer = $('chat-form');
  ['dragenter','dragover'].forEach((name) => composer.addEventListener(name, (event) => { event.preventDefault(); if (!active) composer.classList.add('dragging'); }));
  ['dragleave','drop'].forEach((name) => composer.addEventListener(name, (event) => { event.preventDefault(); composer.classList.remove('dragging'); }));
  composer.addEventListener('drop', (event) => addFiles([...event.dataTransfer.files]));
  composer.addEventListener('submit', async (event) => {
    event.preventDefault(); if (active || !sessionReady || loggingOut) return;
    const text = $('prompt').value; if (!text.trim() && !files.length) return;
    if (text.length > 200000) { error('Keep your message under 200,000 characters.'); return; }
    error(); closeMenus();
    let chat = chats.find((c) => c.id === currentId);
    if (!chat) { chat = { id: uid(), title: (text.trim() || files[0].file.name).slice(0, 65), mode, messages: [] }; currentId = chat.id; }
    chats = [chat, ...chats.filter((item) => item.id !== chat.id)].slice(0, 30);
    const history = chat.messages.filter((m) => m.role !== 'error').map(({ role, content, files: attachments }) => ({ role, content, attachments: attachments || [] }));
    const attached = files.map((item) => item.file);
    chat.messages.push({ role: 'user', content: text.trim() ? text : (mode === 'code' ? 'Please explain the attached code.' : 'Please summarize the attached content.'), files: attached.map((file) => ({ name: file.name, size: file.size })) });
    const controller = new AbortController(), request = { controller, chatId: chat.id }; active = request; setBusy(true); render(); renderRecent(); persist(); announce('Processing your message.');
    requestAnimationFrame(() => $('composer-area').scrollIntoView({ block: 'end', behavior: 'instant' }));
    try {
      const data = await window.DocodeAPI.chat({ mode, message: chat.messages.at(-1).content, files: attached, history, conversationId: chat.id }, controller.signal);
      if (active !== request) return;
      chat.messages.push({ role: 'assistant', content: window.DocodeResults.normalize(data) });
      clearFiles(); $('prompt').value = ''; $('backend-note').hidden = true; announce('Your response is ready.');
    } catch (err) {
      if (active !== request) return;
      chat.messages.push({ role: 'error', content: err.name === 'AbortError' ? 'Request canceled.' : err.message }); announce('The request could not be completed. Your input is kept below so you can try again.');
    } finally {
      if (active === request) { active = null; setBusy(false); persist(); render(); resize(); $('prompt').focus(); }
    }
  });
  $('stop-button').addEventListener('click', () => { cancel(); render(); notify('Browser request canceled. Server processing may continue.'); });
  const templates = { summary: ['document', 'Summarize the attached document. Include the main ideas, key findings, and conclusion.'], insights: ['document', 'Find the key insights in the attached document. Separate supporting evidence from assumptions.'], code: ['code', 'Explain the attached Python code step by step, including its inputs, outputs, and edge cases.'], review: ['code', 'Review the attached Python code for potential bugs and suggest improvements with explanations.'] };
  document.querySelectorAll('[data-template]').forEach((button) => button.addEventListener('click', () => { const [next, prompt] = templates[button.dataset.template]; newChat(next); $('prompt').value = prompt; document.querySelectorAll('dialog[open]').forEach((dialog) => dialog.close()); resize(); $('prompt').focus(); }));
  $('explore-button').addEventListener('click', () => { closeMenus(); $('explore-dialog').showModal(); });
  document.querySelectorAll('[data-close]').forEach((button) => button.addEventListener('click', () => button.closest('dialog').close()));
  $('account-button').addEventListener('click', () => { const opening = $('account-menu').hidden; closeMenus(); $('account-menu').hidden = !opening; $('account-button').setAttribute('aria-expanded', String(opening)); });
  function syncTheme() { const value = window.DocodeTheme.get(); $('theme-select').value = value; $('theme-label').textContent = value[0].toUpperCase() + value.slice(1); }
  syncTheme();
  $('appearance-button').addEventListener('click', () => { window.DocodeTheme.set(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'); syncTheme(); });
  $('settings-button').addEventListener('click', () => { closeMenus(); $('clear-confirm').hidden = true; $('settings-dialog').showModal(); });
  $('theme-select').addEventListener('change', (event) => { window.DocodeTheme.set(event.target.value); syncTheme(); });
  $('clear-history').addEventListener('click', () => { $('clear-confirm').hidden = false; }); $('cancel-clear').addEventListener('click', () => { $('clear-confirm').hidden = true; });
  $('confirm-clear').addEventListener('click', () => { cancel(); chats = []; persist(); newChat(); $('clear-confirm').hidden = true; $('settings-dialog').close(); notify('Chat history cleared for this session.'); });
  async function logout(switching) {
    if (loggingOut) return; loggingOut = true; updateSend(); $('logout-button').disabled = true; $('switch-account').disabled = true;
    try { await window.DocodeAPI.logout(); cancel(); if (storageKey) { try { sessionStorage.removeItem(storageKey); } catch {} } chats = []; user = null; storageKey = 'docode-chats-guest'; newChat(); location.assign(switching ? 'login.html' : 'index.html'); }
    catch (err) { notify(`Could not log out: ${err.message}`); }
    finally { loggingOut = false; updateSend(); $('logout-button').disabled = false; $('switch-account').disabled = false; }
  }
  $('logout-button').addEventListener('click', () => logout(false)); $('switch-account').addEventListener('click', () => logout(true));
  async function initSession() {
    try { const result = await window.DocodeAPI.session(); if (result.user && typeof result.user.id === 'string' && typeof result.user.email === 'string') user = result.user; }
    catch { /* Guest workspace remains available when no session/backend exists. */ }
    storageKey = user ? `docode-chats-user-${user.id}` : 'docode-chats-guest';
    if (user) { const name = typeof user.name === 'string' && user.name.trim() ? user.name : user.email; $('account-name').textContent = name; $('account-subtitle').textContent = 'Account settings'; $('account-email').textContent = user.email; $('avatar').textContent = name.slice(0,2).toUpperCase(); $('login-link').hidden = true; $('top-login').hidden = true; $('logout-button').hidden = false; $('switch-account').hidden = false; }
    loadHistory(); sessionReady = true; updateSend();
  }
  setMode(mode); initSession();
})();
