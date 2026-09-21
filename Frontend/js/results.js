/* Document response: summary (string), key_points (string[]),
 * limitations, source_ids, warnings (optional string[]).
 * Code response: explanation and/or purpose (string), findings (strings or
 * objects with title, message, line, severity, source, suggestion), suggestions
 * and tests (string[]), revised_code (optional string), warnings (string[]).
 * Model content is always inserted as text, never HTML.
 */
window.DocodeResults = (() => {
  const element = (id) => document.getElementById(id);
  let exportText = '';
  let exportMode = 'document';

  function reset() {
    ['empty-state', 'loading-state', 'error-state', 'result-content', 'result-actions', 'result-note', 'result-badge'].forEach((id) => { element(id).hidden = true; });
    element('result-panel').setAttribute('aria-busy', 'false');
    element('result-content').replaceChildren();
    exportText = '';
  }

  function empty() { reset(); element('empty-state').hidden = false; element('result-title').textContent = 'Room for understanding'; }
  function loading() { reset(); element('loading-state').hidden = false; element('result-panel').setAttribute('aria-busy', 'true'); element('result-title').textContent = 'Finding the useful parts'; }
  function error(message) { reset(); element('error-state').textContent = message; element('error-state').hidden = false; element('result-title').textContent = 'Let’s try that again'; }

  function show(data, mode) {
    const sections = [];
    const add = (title, value, kind = 'text') => {
      if (typeof value === 'string' && value.trim()) sections.push({ title, value, kind });
      else if (Array.isArray(value)) {
        const entries = value.filter((item) => typeof item === 'string' && item.trim());
        if (entries.length) sections.push({ title, value: entries, kind: 'list' });
      }
    };
    if (mode === 'document') {
      if (typeof data.summary !== 'string' || !data.summary.trim()) throw new Error('The backend response is missing a document summary.');
      add('Summary', data.summary);
      add('Key points', data.key_points);
      add('Limitations', data.limitations);
      add('Source references', data.source_ids);
    } else {
      if (![data.explanation, data.purpose].some((value) => typeof value === 'string' && value.trim())) throw new Error('The backend response is missing a code explanation.');
      add('Purpose', data.purpose);
      add('How it works', data.explanation);
      if (Array.isArray(data.findings)) {
        add('Findings', data.findings.map((finding) => {
          if (typeof finding === 'string') return finding;
          if (!finding || typeof finding !== 'object') return '';
          const location = Number.isInteger(finding.line) ? `Line ${finding.line}` : '';
          return [finding.source, finding.severity, location, finding.title, finding.message, finding.suggestion].filter((item) => typeof item === 'string' && item.trim()).join(' — ');
        }));
      }
      add('Suggestions', data.suggestions);
      add('Suggested tests', data.tests);
      add('Proposed revision', data.revised_code, 'code');
    }
    add('Warnings', data.warnings);
    reset();
    exportMode = mode;
    const content = element('result-content');
    sections.forEach(({ title, value, kind }) => {
      const heading = document.createElement('h3');
      heading.textContent = title;
      content.append(heading);
      const block = document.createElement(kind === 'list' ? 'ul' : kind === 'code' ? 'pre' : 'p');
      if (kind === 'list') value.forEach((item) => { const li = document.createElement('li'); li.textContent = item; block.append(li); });
      else block.textContent = value;
      content.append(block);
    });
    exportText = sections.map(({ title, value }) => `${title}\n${Array.isArray(value) ? value.map((item) => `- ${item}`).join('\n') : value}`).join('\n\n');
    ['result-content', 'result-actions', 'result-note', 'result-badge'].forEach((id) => { element(id).hidden = false; });
    element('result-title').textContent = mode === 'document' ? 'Your document, distilled' : 'Your code, explained';
  }

  async function copy() {
    if (!exportText) return;
    if (!navigator.clipboard?.writeText) throw new Error('Clipboard access is unavailable. Use Download .txt instead.');
    await navigator.clipboard.writeText(exportText);
  }

  function download() {
    if (!exportText) return;
    const url = URL.createObjectURL(new Blob([exportText], { type: 'text/plain;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = `docode-${exportMode}-result.txt`;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return { empty, loading, error, show, copy, download };
})();
