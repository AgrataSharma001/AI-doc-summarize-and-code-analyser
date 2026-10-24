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
  const items = (value, limit = 100) => Array.isArray(value) ? value.filter((item) => item && typeof item === 'object').slice(0, limit) : [];
  const string = (value) => typeof value === 'string' ? value : '';
  function review(data) {
    if (!data || !Array.isArray(data.findings) || !data.analysis) return null;
    return { findings: items(data.findings, 108), corrections: items(data.corrections, 4),
      analysis: { correction_validation: items(data.analysis.correction_validation, 4),
        checks: items(data.analysis.checks, 5), syntax_checks: items(data.analysis.syntax_checks, 5) },
      warnings: Array.isArray(data.warnings) ? data.warnings.filter((value) => typeof value === 'string').slice(0, 30) : [] };
  }
  function node(tag, className, text) {
    const element = document.createElement(tag); element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }
  const statusLabels = { checks_passed: 'Static checks passed', syntax_error: 'Syntax error remains',
    issues_remaining: 'Issues remain', incomplete: 'Checks incomplete', invalid_edit: 'Invalid replacement', not_checked: 'Not checked' };
  function badge(status) {
    const known = Object.hasOwn(statusLabels, status) ? status : 'not_checked';
    return node('span', `review-badge review-status-${known}`, statusLabels[known]);
  }
  function location(item, correction = false) {
    const start = correction ? item.start_line : item.line;
    const end = item.end_line;
    const lines = Number.isInteger(start) ? `line ${start}${Number.isInteger(end) && end !== start ? `–${end}` : ''}` : 'line unavailable';
    return `${string(item.filename) || 'Python source'} · ${lines}${Number.isInteger(item.column) ? `, column ${item.column}` : ''}`;
  }
  function originalCode(parent, excerpt) {
    parent.append(node('p', 'review-label', 'Original code'));
    if (!excerpt || !Array.isArray(excerpt.lines)) { parent.append(node('p', 'review-note', 'Original code is unavailable for this line mapping.')); return; }
    const pre = node('pre', 'review-code');
    pre.append(node('code', '', items(excerpt.lines, 8).map((row) => `${Number.isInteger(row.line) ? row.line : '?'} | ${string(row.code)}`).join('\n')));
    parent.append(pre);
    if (excerpt.truncated) parent.append(node('p', 'review-note', 'Excerpt shortened. See the original file for the full range.'));
  }
  function correctionBlock(correction) {
    const block = node('section', 'review-correction');
    const heading = node('div', 'review-row');
    heading.append(node('h5', '', 'Suggested correction'), badge(correction.validation_status));
    block.append(heading, node('p', 'review-location', `Replace ${location(correction, true)}`));
    const pre = node('pre', 'review-code'); pre.append(node('code', '', string(correction.replacement_code)));
    block.append(pre, node('p', 'review-label', 'Why this helps'), node('p', 'review-reason', string(correction.explanation)));
    return block;
  }
  function renderReview(data) {
    const report = node('section', 'code-review'); report.setAttribute('aria-label', 'Python code review');
    const findings = [...data.findings].sort((a, b) => (a.tool === 'python' ? 0 : 1) - (b.tool === 'python' ? 0 : 1));
    const title = findings.length ? `${findings.length} ${findings.length === 1 ? 'issue' : 'issues'} to review` : 'No issues reported';
    report.append(node('h3', 'review-title', title), node('p', 'review-note', 'Review the issues first, then the suggested changes. Static checks do not verify runtime behavior.'));
    const incomplete = data.analysis.checks.some((check) => check.status !== 'ok' || check.truncated)
      || data.analysis.syntax_checks.some((check) => ['limited', 'unavailable'].includes(check.status));
    if (incomplete) report.append(node('p', 'review-note', 'Some original-file checks did not complete. Review checker coverage below.'));
    const used = new Set();
    findings.forEach((finding) => {
      const card = node('section', 'review-issue');
      const heading = node('div', 'review-row');
      const severity = ['low', 'medium', 'high'].includes(finding.severity) ? ` · ${finding.severity}` : '';
      heading.append(node('span', `review-badge ${finding.tool === 'python' ? 'review-syntax' : ''}`, (finding.tool === 'python' ? 'Syntax error' : 'Potential issue') + severity),
        node('span', 'review-origin', finding.tool === 'model' ? 'Model review' : finding.tool === 'python' ? 'Python parser' : `Ruff ${string(finding.rule)}`));
      card.append(heading, node('h4', '', string(finding.message)), node('p', 'review-location', location(finding)),
        node('p', 'review-label', 'Reason'), node('p', 'review-reason', string(finding.reasoning)));
      originalCode(card, finding.code_excerpt);
      data.corrections.forEach((correction, index) => {
        if (!used.has(index) && correction.file_id === finding.file_id && correction.start_line <= (finding.end_line || finding.line) && correction.end_line >= finding.line) {
          card.append(correctionBlock(correction)); used.add(index);
        }
      });
      report.append(card);
    });
    data.corrections.forEach((correction, index) => {
      if (used.has(index)) return;
      const card = node('section', 'review-issue');
      card.append(node('h4', '', 'Suggested change'), node('p', 'review-location', location(correction, true)));
      originalCode(card, correction.code_excerpt); card.append(correctionBlock(correction)); report.append(card);
    });
    if (data.analysis.correction_validation.length) {
      report.append(node('h4', 'review-section-title', 'Validation results'));
      data.analysis.correction_validation.forEach((result) => {
        const block = node('section', 'review-validation'); const heading = node('div', 'review-row');
        heading.append(node('strong', '', string(result.filename)), badge(result.status)); block.append(heading,
          node('p', 'review-note', 'Results apply to all suggested edits together for this file. Line numbers below refer to the proposed file.'));
        block.append(node('p', 'review-reason', `Python syntax: ${string(result.syntax?.status) || 'not checked'} · Ruff: ${string(result.ruff?.status) || 'not checked'}`));
        if (result.message) block.append(node('p', 'review-reason', string(result.message)));
        items(result.syntax?.diagnostics).forEach((item) => block.append(node('p', 'review-reason', `Line ${item.line ?? '?'}: ${string(item.message)}`)));
        items(result.ruff?.findings).forEach((item) => block.append(node('p', 'review-reason', `Line ${item.line ?? '?'} · ${string(item.rule)}: ${string(item.message)}`)));
        if (result.ruff?.truncated) block.append(node('p', 'review-note', 'Additional findings were omitted.'));
        report.append(block);
      });
    }
    if (data.analysis.checks.length || data.warnings.length) {
      const coverage = node('details', 'review-details'); coverage.append(node('summary', '', 'Checker coverage and notes'));
      coverage.open = incomplete;
      data.analysis.checks.forEach((check) => coverage.append(node('p', 'review-note', `${string(check.filename)} · Original-file Ruff: ${string(check.status)}${check.truncated ? ' (findings shortened)' : ''}`)));
      data.analysis.syntax_checks.forEach((check) => coverage.append(node('p', 'review-note', `${string(check.filename)} · Original-file syntax: ${string(check.status)}`)));
      data.warnings.forEach((warning) => coverage.append(node('p', 'review-note', warning))); report.append(coverage);
    }
    return report;
  }
  function render(message, notify) {
    const article = document.createElement('article'); article.className = `message ${message.role}`;
    article.setAttribute('aria-label', message.role === 'user' ? 'Your message' : message.role === 'error' ? 'Request error' : 'Docode response');
    if (message.role === 'assistant') {
      const label = document.createElement('div'); label.className = 'assistant-label';
      const logo = document.createElement('img'); logo.src = 'assets/logo.svg'; logo.alt = ''; label.append(logo, 'Docode'); article.append(label);
    }
    (message.files || []).forEach((file) => { const label = document.createElement('span'); label.className = 'message-attachment'; label.textContent = `Attachment: ${file.name}`; article.append(label); });
    const content = document.createElement('div'); content.className = 'message-text'; content.textContent = message.content;
    const report = message.role === 'assistant' ? review(message.review) : null;
    if (report) {
      article.append(renderReview(report));
      const full = node('details', 'review-details'); full.append(node('summary', '', 'Full report and source references'), content); article.append(full);
    } else article.append(content);
    if (message.role === 'assistant') {
      const actions = document.createElement('div'); actions.className = 'message-actions';
      const copy = document.createElement('button'); copy.textContent = 'Copy'; copy.addEventListener('click', async () => { try { await navigator.clipboard.writeText(message.content); notify('Copied to clipboard.'); } catch { notify('Clipboard unavailable. Use Download instead.'); } });
      const save = document.createElement('button'); save.textContent = 'Download'; save.addEventListener('click', () => download(message.content)); actions.append(copy, save); article.append(actions);
    }
    return article;
  }
  return { normalize, review, render };
})();
