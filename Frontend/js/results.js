window.DocodeResults = (() => {
  function normalize(data) {
    if (typeof data.reply === 'string' && data.reply.trim()) return data.reply;
    const sections = [];
    for (const [key, label] of Object.entries({ summary: 'Summary', purpose: 'Purpose', explanation: 'Explanation', key_points: 'Key points', findings: 'Findings', suggestions: 'Suggestions', tests: 'Suggested tests', warnings: 'Warnings', source_ids: 'Source references', revised_code: 'Proposed code' })) {
      const value = data[key];
      if (typeof value === 'string' && value.trim()) sections.push(`${label}\n${value}`);
      if (Array.isArray(value)) {
        const lines = value.map((item) => typeof item === 'string' ? item : item && typeof item === 'object' ? [item.source, item.severity, Number.isInteger(item.line) ? `Line ${item.line}` : '', item.title, item.message, item.suggestion].filter((part) => typeof part === 'string' && part).join(' — ') : '').filter(Boolean);
        if (lines.length) sections.push(`${label}\n${lines.map((line) => `• ${line}`).join('\n')}`);
      }
    }
    if (!sections.length) throw new Error('The backend returned no usable answer. Check its response format.');
    return sections.join('\n\n');
  }
  function download(text) {
    const url = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' }));
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'docode-response.txt'; document.body.append(anchor); anchor.click(); anchor.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function render(message, notify) {
    const article = document.createElement('article'); article.className = `message ${message.role}`;
    article.setAttribute('aria-label', message.role === 'user' ? 'Your message' : message.role === 'error' ? 'Request error' : 'Docode response');
    if (message.role === 'assistant') {
      const label = document.createElement('div'); label.className = 'assistant-label';
      const logo = document.createElement('img'); logo.src = 'assets/logo.svg'; logo.alt = ''; label.append(logo, 'Docode'); article.append(label);
    }
    (message.files || []).forEach((file) => { const label = document.createElement('span'); label.className = 'message-attachment'; label.textContent = `Attachment: ${file.name}`; article.append(label); });
    const content = document.createElement('div'); content.className = 'message-text'; content.textContent = message.content; article.append(content);
    if (message.role === 'assistant') {
      const actions = document.createElement('div'); actions.className = 'message-actions';
      const copy = document.createElement('button'); copy.textContent = 'Copy'; copy.addEventListener('click', async () => { try { await navigator.clipboard.writeText(message.content); notify('Copied to clipboard.'); } catch { notify('Clipboard unavailable. Use Download instead.'); } });
      const save = document.createElement('button'); save.textContent = 'Download'; save.addEventListener('click', () => download(message.content)); actions.append(copy, save); article.append(actions);
    }
    return article;
  }
  return { normalize, render };
})();
