/* Real browser -> FastAPI -> Ollama integration. No API/model mocks.
 * Start the backend first; see Frontend/README.md for prerequisites.
 * Each run creates a synthetic account and retained conversation in that DB.
 */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const format = process.env.DOCODE_TEST_FORMAT || 'txt';
assert.ok(['txt', 'pdf', 'docx'].includes(format), 'Use txt, pdf, or docx for DOCODE_TEST_FORMAT.');
const filename = `orion.${format}`;

const base = new URL(process.env.DOCODE_TEST_URL || 'http://127.0.0.1:8000');
assert.ok(base.protocol === 'http:' && ['127.0.0.1', 'localhost', '[::1]'].includes(base.hostname),
  'Use a loopback HTTP backend with a disposable test database.');
assert.equal(base.pathname, '/');
const email = `live-${randomUUID()}@example.com`;
const password = randomUUID();
const source = 'Project Orion has a budget of 240 rupees.\nThe delivery deadline is 18 November 2026.\nMira owns the project.';

(async () => {
  const browser = await chromium.launch({ headless: true,
    ...(process.env.BROWSER_CHANNEL ? { channel: process.env.BROWSER_CHANNEL } : {}) });
  try {
    const context = await browser.newContext();
    const page = await context.newPage();
    page.setDefaultTimeout(15000);
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));
    const health = await context.request.get(new URL('/health', base).href);
    assert.equal(health.status(), 200, 'Start the FastAPI backend before running this test.');

    await page.goto(new URL('/login.html', base).href);
    await page.locator('#auth-switch').click();
    await page.locator('#name').fill('Live Integration Test');
    await page.locator('#email').fill(email);
    await page.locator('#password').fill(password);
    await page.locator('#auth-submit').click();
    await page.waitForURL('**/index.html');
    await page.locator('#account-name').filter({ hasText: 'Live Integration Test' }).waitFor();
    const cookie = (await context.cookies()).find((item) => item.name === 'docode_session');
    assert.ok(cookie?.httpOnly, 'Signup must establish an HttpOnly session.');
    assert.equal(await page.evaluate((secret) => JSON.stringify({ ...localStorage, ...sessionStorage }).includes(secret), password), false);

    const buffer = format === 'txt' ? Buffer.from(source)
      : fs.readFileSync(path.resolve(__dirname, '../../.test-tools/fixtures', filename));
    const mimeType = { txt: 'text/plain', pdf: 'application/pdf',
      docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' }[format];
    await page.locator('#file-input').setInputFiles({ name: filename, mimeType, buffer });
    await page.locator('#prompt').fill('Summarize the project budget, delivery deadline, and owner.');
    async function send() {
      const responsePromise = page.waitForResponse((response) => new URL(response.url()).pathname === '/api/chat'
        && response.request().method() === 'POST', { timeout: 180000 });
      const started = Date.now();
      await page.locator('#send-button').click();
      const response = await responsePromise;
      assert.equal(response.status(), 200, `Chat failed: ${await response.text()}`);
      const answer = await response.json();
      assert.equal(answer.status, 'answered');
      assert.ok(answer.source_ids.length > 0);
      assert.deepEqual(new Set(answer.source_ids), new Set(answer.sources.map((span) => span.id)));
      for (const span of answer.sources) {
        assert.equal(span.filename, filename);
        assert.match(span.location, format === 'pdf' ? /^page \d+, lines/ : format === 'docx' ? /paragraph \d+, lines/ : /^lines/);
        assert.ok(answer.reply.includes(`[source: ${span.id}, ${span.filename}, ${span.location}]`));
      }
      await page.waitForFunction((reply) => [...document.querySelectorAll('.message.assistant .message-text')]
        .some((node) => node.textContent === reply), answer.reply);
      await page.waitForFunction(() => !document.getElementById('prompt').disabled);
      console.log(`PASS: real model answer with resolvable citations (${Date.now() - started} ms).`);
      return { answer, request: response.request() };
    }
    const first = await send();
    assert.match(first.answer.reply, /240/);
    assert.match(first.answer.reply, /Mira/i);
    assert.equal(await page.locator('.attachment').count(), 0);
    assert.equal(await page.locator('#prompt').inputValue(), '');

    // Reload the UI, then ask about the retained file without reattaching it.
    await page.reload();
    await page.locator('.recent-chat').click();
    await page.locator('#prompt').fill('What is the project budget?');
    const second = await send();
    assert.match(second.answer.reply, /240/);
    assert.equal(second.answer.conversation_id, first.answer.conversation_id);
    assert.ok(second.answer.sources.every((span) => first.answer.sources.some((old) => old.file_id === span.file_id)));
    assert.equal(second.request.postDataBuffer().includes(Buffer.from('filename=')), false,
      'Follow-up must use server-held sources without another file upload.');
    assert.equal(await page.locator('.message.assistant').count(), 2);

    await page.locator('#account-button').click();
    await page.locator('#logout-button').click();
    await page.waitForFunction(() => !document.getElementById('top-login').hidden);
    assert.deepEqual(await (await context.request.get(new URL('/api/auth/session', base).href)).json(), { user: null });
    const denied = await page.evaluate(async () => {
      const form = new FormData();
      form.append('mode', 'document'); form.append('message', 'Follow-up');
      form.append('conversation_id', 'signed-out-probe');
      return (await fetch('/api/chat', { method: 'POST', body: form })).status;
    });
    assert.equal(denied, 401);
    assert.deepEqual(errors, []);
    console.log(`PASS: signup, ${format.toUpperCase()} upload, cited answer, reload, retained-source follow-up, logout, and signed-out rejection.`);
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
