const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROMIUM_EXECUTABLE_PATH, args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu'] });
  const results = [];
  const audit = () => {
    const failures = [];
    const visible = e => e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden';
    if (document.documentElement.scrollWidth > innerWidth + 1) failures.push('page overflow');
    for (const sel of ['.voice-card','.compare-choice','.compare-play','.chosen-panel button','.tool-tabs button','.studio-card','.editor-card','.mode-switch','.topbar__right','.iconbtn.heritage-btn'])
      for (const e of document.querySelectorAll(sel)) {
        if (!visible(e)) continue;
        const r = e.getBoundingClientRect();
        if (r.left < -1 || r.right > innerWidth + 1) failures.push(sel + ' outside viewport');
        if (e.scrollWidth > e.clientWidth + 2) failures.push(sel + ' internal overflow');
      }
    // contrast probe: heritage button + active accent visibility
    const hb = document.querySelector('.iconbtn.heritage-btn');
    if (!hb) failures.push('heritage button missing');
    return [...new Set(failures)];
  };
  for (const [w, h, locale, name] of [[1440,1100,'EN','d1440-en'],[390,900,'EN','d390-en'],[1440,1100,'MM','d1440-mm'],[390,900,'MM','d390-mm']]) {
    const p = await b.newPage({ viewport:{width:w,height:h}, reducedMotion:'reduce' });
    await p.goto('http://127.0.0.1:5173', { waitUntil:'networkidle' });
    await p.getByRole('button', { name: locale, exact: true }).click();
    await p.locator('.iconbtn.heritage-btn').click();
    await p.waitForTimeout(600);
    results.push({ name, theme: await p.getAttribute('.app', 'data-theme'), failures: await p.evaluate(audit) });
    await p.screenshot({ path:`shots/heritage-${name}.png`, fullPage:true });
    if (w === 1440) { // studio in heritage too
      await p.locator('.chosen-panel > button, .navitem').nth(2).click().catch(()=>{});
      await p.locator('.sidebar__footer button').click().catch(()=>{});
      await p.waitForTimeout(800);
      await p.screenshot({ path:`shots/heritage-${name}-studio.png`, fullPage:true });
      results.push({ name: name+'-studio', failures: await p.evaluate(audit) });
    }
    await p.close();
  }
  console.log(JSON.stringify(results, null, 1));
  await b.close();
})().catch(e => { console.error(e.message); process.exit(1); });
