/* Run with Node and Playwright installed, optionally setting PLAYWRIGHT_MODULE
 * to an absolute module path and BROWSER_CHANNEL to an installed browser.
 * These tests mock the API; they do not certify a real backend or AI service.
 */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.BROWSER_CHANNEL ? { channel: process.env.BROWSER_CHANNEL } : {}) });
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 960 }, colorScheme: 'light' });
    const page = await context.newPage();
    page.setDefaultTimeout(8000);
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));
    const root = path.resolve(__dirname, '..');
    let user = null, chatBody = '', chatStatus = 200, authStatus = 200, logoutStatus = 204, slow = false;
    await context.route('http://docode.test/**', async (route) => {
      const request = route.request(), url = new URL(request.url());
      if (url.pathname.startsWith('/api/')) {
        let status = 200, data = {};
        if (url.pathname === '/api/auth/session') data = { user };
        else if (['/api/auth/login', '/api/auth/signup'].includes(url.pathname)) {
          status = authStatus;
          if (status === 200) {
            const input = request.postDataJSON();
            user = { id: 'test-user', name: input.name || 'Alex Morgan', email: input.email };
            data = { user };
          }
        } else if (url.pathname === '/api/auth/logout') {
          status = logoutStatus;
          if (status === 204) user = null;
        } else if (url.pathname === '/api/chat') {
          chatBody = request.postData(); status = chatStatus;
          data = { reply: 'A clear summary. <img src=x onerror=alert(1)>' };
          if (slow) await new Promise((resolve) => setTimeout(resolve, 350));
        }
        return route.fulfill({ status, contentType: 'application/json', body: status === 204 ? '' : JSON.stringify(data) }).catch(() => {});
      }
      const file = path.resolve(root, '.' + decodeURIComponent(url.pathname));
      if (!file.startsWith(root + path.sep) || !fs.existsSync(file)) return route.fulfill({ status: 404, body: 'Not found' });
      const types = { '.html': 'text/html', '.css': 'text/css', '.js': 'application/javascript', '.svg': 'image/svg+xml' };
      return route.fulfill({ body: fs.readFileSync(file), contentType: types[path.extname(file)] || 'application/octet-stream' });
    });

    await page.goto('http://docode.test/index.html');
    assert.equal(await page.locator('#send-button').isDisabled(), true);
    await page.locator('#close-sidebar').click();
    assert.equal(await page.locator('#sidebar').evaluate((node) => node.inert), true);
    await page.locator('#open-sidebar').click();
    await page.locator('#explore-button').click();
    await page.locator('#explore-dialog [data-template=review]').click();
    assert.equal(await page.locator('#workspace-title').textContent(), 'Code workspace');
    assert.match(await page.locator('#prompt').inputValue(), /Review/);
    await page.locator('#document-mode').click();
    await page.locator('#file-input').setInputFiles({ name: 'report.txt', mimeType: 'text/plain', buffer: Buffer.from('Report content') });
    await page.locator('#prompt').fill('Summarize this report in three points.');
    await page.locator('#send-button').click();
    await page.locator('.message.assistant').waitFor();
    assert.match(chatBody, /Summarize this report in three points/);
    assert.match(chatBody, /filename="report.txt"/);
    assert.match(chatBody, /Report content/);
    assert.equal(await page.locator('.message-text img').count(), 0);
    assert.equal(await page.locator('#prompt').inputValue(), '');
    const downloading = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Download', exact: true }).click();
    assert.equal((await downloading).suggestedFilename(), 'docode-response.txt');
    await page.locator('#prompt').fill('Explain the conclusion.');
    await page.locator('#send-button').click();
    await page.locator('.message.assistant').nth(1).waitFor();
    assert.match(chatBody, /attachments/);
    await page.reload();
    await page.locator('.recent-chat').click();
    assert.equal(await page.locator('.message.assistant').count(), 2);
    console.log('PASS: navigation, templates, attachments + instructions, safe output, download, follow-up history and reload.');

    await page.locator('#new-chat').click();
    await page.locator('#file-input').setInputFiles({ name: 'bad.exe', mimeType: 'application/octet-stream', buffer: Buffer.from('invalid') });
    assert.match(await page.locator('#composer-error').textContent(), /unsupported/);
    await page.locator('#file-input').setInputFiles({ name: 'photo.png', mimeType: 'image/png', buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aI1sAAAAASUVORK5CYII=', 'base64') });
    assert.equal(await page.locator('.attachment img').count(), 1);
    await page.getByRole('button', { name: 'Remove photo.png' }).click();
    chatStatus = 500;
    await page.locator('#prompt').fill('Retry me');
    await page.locator('#send-button').click();
    await page.locator('.message.error').waitFor();
    assert.equal(await page.locator('#prompt').inputValue(), 'Retry me');
    chatStatus = 200; slow = true;
    await page.locator('#send-button').click();
    await page.locator('#stop-button').click();
    assert.match(await page.locator('.message.error').last().textContent(), /canceled/);
    slow = false;
    await page.locator('#new-chat').click();
    await page.locator('#account-button').click();
    await page.locator('#appearance-button').click();
    assert.equal(await page.locator('html').getAttribute('data-theme'), 'dark');
    await page.locator('#settings-button').click();
    await page.locator('#theme-select').selectOption('light');
    await page.locator('#clear-history').click();
    await page.locator('#confirm-clear').click();
    assert.equal(await page.locator('.recent-chat').count(), 0);
    console.log('PASS: invalid upload, photo preview/removal, backend failure, draft preservation, cancellation, themes, clear history.');

    await page.goto('http://docode.test/login.html');
    await page.locator('#auth-switch').click();
    await page.locator('#name').fill('Alex Morgan');
    await page.locator('#email').fill('alex@example.com');
    await page.locator('#password').fill('example-test-pass');
    await page.locator('#show-password').click();
    assert.equal(await page.locator('#password').getAttribute('type'), 'text');
    await page.locator('#auth-submit').click();
    await page.waitForURL('**/index.html');
    await page.locator('#account-name').filter({ hasText: 'Alex Morgan' }).waitFor();
    assert.equal(await page.evaluate(() => JSON.stringify({ ...localStorage, ...sessionStorage }).includes('example-test-pass')), false);
    await page.locator('#account-button').click();
    logoutStatus = 500;
    await page.locator('#logout-button').click();
    await page.locator('#toast').filter({ hasText: 'Could not log out' }).waitFor();
    assert.equal(await page.locator('#account-name').textContent(), 'Alex Morgan');
    logoutStatus = 204;
    await page.locator('#switch-account').click();
    await page.waitForURL('**/login.html');
    assert.equal(user, null);
    authStatus = 401;
    await page.locator('#email').fill('alex@example.com');
    await page.locator('#password').fill('wrong-test-pass');
    await page.locator('#auth-submit').click();
    await page.locator('#auth-error').filter({ hasText: 'not accepted' }).waitFor();
    assert.equal(await page.locator('#password').inputValue(), '');
    console.log('PASS: signup, password visibility, credential non-storage, account identity, logout failure, switch account, login error.');

    await page.setViewportSize({ width: 390, height: 844 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await page.goto('http://docode.test/index.html');
    assert.equal(await page.locator('#sidebar').evaluate((node) => node.inert), true);
    await page.locator('#open-sidebar').click();
    assert.equal(await page.locator('#main').evaluate((node) => node.inert), true);
    await page.locator('#code-mode').click();
    assert.equal(await page.locator('#sidebar').evaluate((node) => node.inert), true);
    assert.equal(await page.locator('#main').evaluate((node) => node.inert), false);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    assert.deepEqual(errors, []);
    console.log('PASS: mobile login/workspace widths, drawer focus isolation, and no browser JavaScript errors.');
  } finally { await browser.close(); }
})().catch((error) => { console.error(error); process.exitCode = 1; });
