(() => {
  const $ = (id) => document.getElementById(id);
  const MAX_FILE_BYTES = 10 * 1024 * 1024;
  const MAX_TEXT_LENGTH = 200000;
  let mode = 'document';
  let selectedFile = null;
  let activeController = null;
  let readingCode = false;
  const tabs = [...document.querySelectorAll('[role="tab"]')];

  const announce = (message) => { $('app-status').textContent = message; };
  function count(id, output) { $(output).textContent = `${$(id).value.length.toLocaleString()} characters`; }

  function switchMode(next) {
    if (next === mode) return;
    activeController?.abort();
    activeController = null;
    setBusy(false);
    mode = next;
    tabs.forEach((tab) => {
      const selected = tab.dataset.mode === mode;
      tab.setAttribute('aria-selected', String(selected));
      tab.tabIndex = selected ? 0 : -1;
    });
    $('document-panel').hidden = mode !== 'document';
    $('code-panel').hidden = mode !== 'code';
    window.DocodeResults.empty();
    announce(`${mode === 'document' ? 'Document summarizer' : 'Code analyzer'} selected.`);
  }

  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => switchMode(tab.dataset.mode));
    tab.addEventListener('keydown', (event) => {
      let target;
      if (event.key === 'ArrowRight') target = tabs[(index + 1) % tabs.length];
      if (event.key === 'ArrowLeft') target = tabs[(index - 1 + tabs.length) % tabs.length];
      if (event.key === 'Home') target = tabs[0];
      if (event.key === 'End') target = tabs[tabs.length - 1];
      if (target) { event.preventDefault(); target.focus(); switchMode(target.dataset.mode); }
    });
  });

  function fileError(file, extensions) {
    if (!file || file.size === 0) return 'Choose a file that contains some content.';
    if (file.size > MAX_FILE_BYTES) return 'This file is larger than 10 MB. Choose a smaller file.';
    const extension = file.name.split('.').pop().toLowerCase();
    if (!extensions.includes(extension)) return `Choose a ${extensions.map((ext) => ext.toUpperCase()).join(', ')} file.`;
    return null;
  }

  function selectDocument(file) {
    if (activeController) return;
    const message = fileError(file, ['pdf', 'docx', 'txt']);
    if (message) { $('document-file').value = ''; window.DocodeResults.error(message); return; }
    selectedFile = file;
    $('selected-file').hidden = false;
    $('file-name').textContent = `${file.name} · ${(file.size / 1024).toFixed(1)} KB`;
    $('document-text').disabled = true;
    $('document-input-hint').textContent = 'Selected file will be used. Remove it to use pasted text.';
    window.DocodeResults.empty();
    announce(`${file.name} selected.`);
  }

  $('document-file').addEventListener('change', (event) => { if (event.target.files[0]) selectDocument(event.target.files[0]); });
  $('remove-file').addEventListener('click', () => {
    selectedFile = null;
    $('document-file').value = '';
    $('selected-file').hidden = true;
    $('document-text').disabled = false;
    $('document-input-hint').textContent = 'Your next insight starts here.';
    $('document-text').focus();
  });
  const dropZone = $('drop-zone');
  ['dragenter', 'dragover'].forEach((name) => dropZone.addEventListener(name, (event) => { event.preventDefault(); if (!activeController) dropZone.classList.add('dragging'); }));
  ['dragleave', 'drop'].forEach((name) => dropZone.addEventListener(name, (event) => { event.preventDefault(); dropZone.classList.remove('dragging'); }));
  dropZone.addEventListener('drop', (event) => {
    if (activeController) return;
    const files = event.dataTransfer.files;
    if (files.length !== 1) { window.DocodeResults.error('Please choose one document at a time.'); return; }
    selectDocument(files[0]);
  });

  $('code-file').addEventListener('change', async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    const message = fileError(file, ['py']);
    if (message) { event.target.value = ''; window.DocodeResults.error(message); return; }
    readingCode = true;
    $('code-fields').disabled = true;
    try {
      const code = await file.text();
      if (code.length > MAX_TEXT_LENGTH) throw new Error('This code file is too long. Use a file with at most 200,000 characters.');
      if (code.includes('\u0000') || code.includes('\uFFFD')) throw new Error('Use a UTF-8 Python source file. This file could not be read as plain text.');
      $('code-text').value = code;
      count('code-text', 'code-count');
      announce(`${file.name} loaded into the code editor.`);
    } catch (error) { if (mode === 'code') window.DocodeResults.error(error.message); }
    finally { readingCode = false; $('code-fields').disabled = Boolean(activeController); event.target.value = ''; }
  });

  $('document-text').addEventListener('input', () => count('document-text', 'document-count'));
  $('code-text').addEventListener('input', () => count('code-text', 'code-count'));

  function setBusy(busy) {
    $('document-fields').disabled = busy;
    $('code-fields').disabled = busy || readingCode;
  }

  async function submit(event) {
    event.preventDefault();
    if (activeController || readingCode) return;
    const text = $(mode === 'document' ? 'document-text' : 'code-text').value;
    if (!(mode === 'document' && selectedFile) && !text.trim()) {
      window.DocodeResults.error(mode === 'document' ? 'Add a document or paste some text to get started.' : 'Paste Python code or open a .py file to get started.');
      $(mode === 'document' ? 'document-text' : 'code-text').focus();
      return;
    }
    if (!(mode === 'document' && selectedFile) && text.length > MAX_TEXT_LENGTH) { window.DocodeResults.error('Use at most 200,000 characters per request.'); return; }
    const requestMode = mode;
    const controller = new AbortController();
    activeController = controller;
    setBusy(true);
    window.DocodeResults.loading();
    announce('Processing your content.');
    try {
      const result = requestMode === 'document'
        ? await window.DocodeAPI.summarize({ file: selectedFile, text, length: $('summary-length').value, style: $('summary-style').value }, controller.signal)
        : await window.DocodeAPI.analyze({ code: text, explanation_level: $('explanation-level').value, expected_behavior: $('code-context').value.trim() }, controller.signal);
      if (activeController !== controller) return;
      window.DocodeResults.show(result, requestMode);
      announce('Your result is ready.');
    } catch (error) {
      if (activeController !== controller) return;
      if (error.name === 'AbortError') { window.DocodeResults.empty(); announce('Request canceled.'); }
      else { window.DocodeResults.error(error.message); announce('The request could not be completed.'); }
    } finally {
      if (activeController === controller) { activeController = null; setBusy(false); }
    }
  }

  $('document-form').addEventListener('submit', submit);
  $('code-form').addEventListener('submit', submit);
  $('cancel-request').addEventListener('click', () => {
    activeController?.abort();
    announce('Canceling the browser request. The backend may still finish processing.');
  });
  $('copy-result').addEventListener('click', async () => {
    const button = $('copy-result');
    try { await window.DocodeResults.copy(); button.textContent = 'Copied!'; announce('Result copied.'); }
    catch { button.textContent = 'Use download instead'; announce('Clipboard unavailable. Download the result instead.'); }
    setTimeout(() => { button.textContent = 'Copy result'; }, 2500);
  });
  $('download-result').addEventListener('click', () => { window.DocodeResults.download(); announce('Result download requested.'); });
})();
