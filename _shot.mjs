import { BrowserUse } from 'browser-use-sdk';
import { chromium } from 'playwright-core';

const client = new BrowserUse();
const session = await client.browsers.create({ viewportWidth: 1440, viewportHeight: 1100 });
const sid = session.id;
const cdp = session.cdpUrl.replace(/^https:/,'wss:').replace(/^http:/,'ws:');
try {
  const browser = await chromium.connectOverCDP(cdp);
  const ctx = browser.contexts()[0] || await browser.newContext({ viewport:{width:1440,height:1100} });
  const page = ctx.pages()[0] || await ctx.newPage();
  const url = 'https://however-jennifer-sixth-rugs.trycloudflare.com/';
  await page.goto(url, { waitUntil:'networkidle', timeout:60000 }).catch(e=>console.log('nav:',e.message));
  await page.waitForTimeout(2500);
  await page.screenshot({ path:'shots/lib-1440.png', fullPage:true });
  // mobile
  await page.setViewportSize({ width:390, height:900 });
  await page.waitForTimeout(1200);
  await page.screenshot({ path:'shots/lib-390.png', fullPage:true });
  // studio page desktop
  await page.setViewportSize({ width:1440, height:1100 });
  const studio = page.getByText('Voice Studio').first();
  if (await studio.count()) { await studio.click(); await page.waitForTimeout(1500); await page.screenshot({ path:'shots/studio-1440.png', fullPage:true }); }
  console.log('DONE shots');
} finally {
  await client.browsers.stop(sid).catch(()=>{});
  console.log('stopped '+sid);
}
