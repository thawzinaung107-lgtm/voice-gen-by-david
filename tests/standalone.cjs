const { chromium } = require('playwright');
const { spawn } = require('node:child_process');
const assert = require('node:assert/strict');
const root = require('node:path').resolve(__dirname, '..');
const server = spawn(process.execPath, ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '5187', '--strictPort'], { cwd: root });
const ready = new Promise((resolve, reject) => { server.stdout.on('data', data => { if (data.toString().includes('Local:')) resolve(); }); server.on('exit', code => reject(Error(`Vite exited ${code}`))); });
let browser;
const routes = ['home', 'library', 'studio', 'projects', 'history', 'pricing', 'settings', 'admin'];
const labels = ['Overview', 'Voice Library', 'Voice Studio', 'My Projects', 'History', 'Pricing & Credits', 'Settings', 'Admin'];
(async () => {
  await ready;
  browser = await chromium.launch({ executablePath: process.env.CHROMIUM_EXECUTABLE_PATH || undefined, args: ['--no-sandbox', '--disable-dev-shm-usage'], headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [], remote = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', req => { if (/fetch|xhr/.test(req.resourceType()) && !req.url().startsWith('http://127.0.0.1:5187/')) remote.push(req.url()); });
  await page.goto('http://127.0.0.1:5187/#/studio');
  await page.getByRole('button', { name: 'EN', exact: true }).click();
  const script = 'Standalone draft survives navigation and refresh.';
  await page.locator('textarea').fill(script);
  await page.locator('.voice-picker button').filter({ hasText: 'Daniel' }).click();
  for (const mode of ['Guided', 'Advanced']) {
    await page.locator('.mode-switch button').filter({ hasText: mode }).click();
    for (const name of ['Text to Speech', 'Dialogue to Speech', 'SRT to Speech']) {
      await page.getByRole('tab', { name }).click();
      assert(await page.getByRole('button', { name: 'Generate speech', exact: true }).isDisabled());
      assert.equal(await page.locator('.studio-summary strong').innerText(), 'Available after provider setup');
    }
  }
  await page.getByRole('tab', { name: 'Text to Speech', exact: true }).click();
  for (let i = 0; i < routes.length; i++) {
    await page.locator('.sidebar__nav button').nth(i).click();
    await page.waitForURL(`**/#/${routes[i]}`);
    assert.equal((await page.locator('.topbar__breadcrumb').innerText()).trim(), `/ ${labels[i]}`);
    if (!['library', 'studio'].includes(routes[i])) await page.locator(`[data-page="${routes[i]}"]`).waitFor();
    await page.reload();
    assert.equal((await page.locator('.topbar__breadcrumb').innerText()).trim(), `/ ${labels[i]}`);
    assert.equal(await page.locator('.credit-pill,.history-item,.profile').count(), 0);
  }
  await page.locator('.sidebar__nav button').nth(2).click();
  assert.equal(await page.locator('textarea').inputValue(), script);
  assert.equal(await page.locator('.voice-picker .is-active').innerText(), 'Daniel');
  await page.locator('.sidebar__nav button').nth(1).click();
  await page.locator('#voice-search').fill('Daniel');
  await page.locator('.sidebar__nav button').nth(4).click();
  await page.goBack();
  await page.locator('#voice-search').waitFor();
  assert.equal(await page.locator('#voice-search').inputValue(), 'Daniel');
  await page.goForward();
  await page.locator('[data-page="history"]').waitFor();
  await page.locator('.sidebar__nav button').nth(6).click();
  await page.getByLabel('Appearance', { exact: true }).selectOption('light');
  await page.getByLabel('Interface language', { exact: true }).selectOption('mm');
  await page.reload();
  assert(await page.locator('.app--light[lang="my"]').count());
  // Every disconnected route has Myanmar content as well as a translated breadcrumb.
  for (const i of [0, 3, 4, 5, 6, 7]) {
    await page.locator('.sidebar__nav button').nth(i).click();
    await page.locator(`[data-page="${routes[i]}"]`).waitFor();
    assert.match(await page.locator('.standalone-page h1').innerText(), /[\u1000-\u109f]/);
  }
  await page.getByRole('button', { name: 'EN', exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  for (let i = 0; i < routes.length; i++) {
    await page.getByRole('button', { name: 'Open menu', exact: true }).click();
    await page.locator('#mobile-navigation > button').nth(i + 1).click();
    await page.waitForURL(`**/#/${routes[i]}`);
    assert.equal(await page.locator('#mobile-navigation').count(), 0);
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
  }
  for (const [i, route] of ['home', 'library', 'studio', 'history'].entries()) {
    await page.locator('.bottom-nav button').nth(i).click();
    await page.waitForURL(`**/#/${route}`);
  }
  await page.goto('http://127.0.0.1:5187/#/unknown');
  await page.locator('#voice-search').waitFor();
  // Blocked or corrupt browser storage must not prevent rendering/editing.
  const blocked = await browser.newPage();
  await blocked.addInitScript(() => { Object.defineProperty(window, 'localStorage', { get() { throw new Error('Storage blocked'); } }); });
  await blocked.goto('http://127.0.0.1:5187/#/studio');
  await blocked.locator('textarea').fill('Draft without storage');
  assert.equal(await blocked.locator('textarea').inputValue(), 'Draft without storage');
  await blocked.close();
  const corrupt = await browser.newPage();
  await corrupt.addInitScript(() => {
    localStorage.setItem('voicegen.v2.script', '{broken json');
    localStorage.setItem('voicegen.v2.voice', JSON.stringify('unknown'));
    localStorage.setItem('voicegen.v2.favorites', JSON.stringify([null]));
  });
  await corrupt.goto('http://127.0.0.1:5187/#/studio');
  assert.equal(await corrupt.locator('textarea').inputValue(), '');
  assert.equal(await corrupt.locator('.voice-picker .is-active').innerText(), 'Brian');
  await corrupt.close();
  const fallback = await browser.newPage();
  await fallback.route('**/gen/*.png', route => route.abort());
  await fallback.goto('http://127.0.0.1:5187/#/library');
  await fallback.locator('.avatar__face img').first().waitFor({ state: 'hidden' });
  assert(await fallback.locator('.avatar__fallback').first().isVisible());
  await fallback.close();
  // Test cancellation deterministically without depending on host audio voices.
  await page.goto('http://127.0.0.1:5187/#/library');
  await page.evaluate(() => {
    window.__cancels = 0;
    Object.defineProperty(window, 'speechSynthesis', { configurable: true, value: {
      getVoices: () => [], speak: () => {}, cancel: () => { window.__cancels++; },
    } });
    Object.defineProperty(window, 'SpeechSynthesisUtterance', { configurable: true, value: class {} });
  });
  await page.locator('.play-btn').first().click();
  assert(await page.locator('.play-btn--active').count());
  await page.evaluate(() => {
    Object.defineProperty(document, 'hidden', { configurable: true, value: true });
    document.dispatchEvent(new Event('visibilitychange'));
  });
  await page.waitForFunction(() => !document.querySelector('.play-btn--active'));
  assert((await page.evaluate(() => window.__cancels)) >= 2);
  assert.deepEqual(errors, []);
  assert.deepEqual(remote, []);
  console.log('PASS standalone: all 8 routes, desktop/drawer/bottom navigation, hash back/forward/refresh, draft/voice/preferences persistence, filter retention, 6 disabled generation combinations, unavailable estimates, no fake records/balance, blocked storage, mobile overflow, no runtime errors or external service requests.');
})().catch(error => { console.error(error); process.exitCode = 1; }).finally(async () => { if (browser) await browser.close(); server.kill(); });
