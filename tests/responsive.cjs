const {chromium}=require(process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES ? process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES+'/playwright' : 'playwright');
const {spawn}=require('child_process');const fs=require('fs');
const root=require('path').resolve(__dirname,'..');
const server=spawn(process.execPath,['node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5173'],{cwd:root});
const audit=()=>{
 const failures=[];const rect=e=>e.getBoundingClientRect();const visible=e=>e.getClientRects().length&&getComputedStyle(e).visibility!=='hidden';
 if(document.documentElement.scrollWidth>innerWidth+1)failures.push('page overflow');
 for(const sel of ['.voice-card','.compare-choice','.compare-play','.chosen-panel button','.tool-tabs button','.studio-card','.editor-card','.mode-switch','.topbar__right'])for(const e of document.querySelectorAll(sel)){
  if(!visible(e))continue;const r=rect(e);if(r.left< -1||r.right>innerWidth+1)failures.push(sel+' outside viewport');if(e.scrollWidth>e.clientWidth+2)failures.push(sel+' internal width overflow');
 }
 for(const e of document.querySelectorAll('.wave')){if(!visible(e))continue;const a=rect(e),b=rect(e.parentElement);if(a.left<b.left-1||a.right>b.right+1)failures.push('wave outside parent');}
 for(const sel of ['.voice-card__top','.voice-card__actions','.compare-panel__controls','.studio-hero','.topbar']){for(const e of document.querySelectorAll(sel)){const kids=[...e.children].filter(visible);for(let i=0;i<kids.length;i++)for(let j=i+1;j<kids.length;j++){let a=rect(kids[i]),b=rect(kids[j]);if(Math.min(a.right,b.right)-Math.max(a.left,b.left)>2&&Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>2)failures.push(sel+' sibling overlap');}}}
 for(const e of document.querySelectorAll('button, h1, h2, h3, p, .voice-card__tagline, small')){if(!e.textContent.trim()||!visible(e)||e.closest('.sidebar')&&!visible(e.closest('.sidebar')))continue;if(e.scrollHeight>e.clientHeight+2&&['hidden','clip'].includes(getComputedStyle(e).overflowY))failures.push(e.className+' clipped text');}
 return [...new Set(failures)];
};
(async()=>{await new Promise((res,rej)=>{server.stdout.on('data',d=>{if(d.toString().includes('Local:'))res()});server.on('exit',rej)});
 const b=await chromium.launch({executablePath:process.env.CHROMIUM_EXECUTABLE_PATH || undefined,args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu'],headless:true});
 const results=[];fs.mkdirSync(root+'/qa-screenshots/current',{recursive:true});
 for(const width of [390,768,1024,1440])for(const locale of ['EN','MM']){
 const p=await b.newPage({viewport:{width,height:900},reducedMotion:'reduce'});await p.goto('http://127.0.0.1:5173');await p.getByRole('button',{name:locale,exact:true}).click();await p.evaluate(()=>document.fonts.ready);
 results.push({width,locale,page:'library',failures:await p.evaluate(audit)});
 if(process.env.QA_SCREENSHOTS) await p.screenshot({path:`${root}/qa-screenshots/current/${width}-${locale}-library.png`,fullPage:true});
 await p.locator('#voice-search').fill('Daniel');if(await p.locator('.voice-card').count()!==1)throw Error('search regression');await p.locator('#voice-search').fill('');
 const fav=p.locator('.fav-toggle').first();const checked=await fav.getAttribute('aria-checked');await fav.click();if(await fav.getAttribute('aria-checked')===checked)throw Error('favorite regression');await fav.click();
 await p.locator('.voice-card--daniel .select-btn').click();if(await p.locator('.voice-card--daniel .select-btn').getAttribute('aria-pressed')!=='true')throw Error('selection regression');
 await p.locator('.voice-card__tagline').first().evaluate(e=>e.textContent=e.textContent.repeat(6));results.push({width,locale,page:'long-description',failures:await p.evaluate(audit)});
 await p.locator('.voice-card__avatar').first().click();results.push({width,locale,page:'dialog',failures:await p.evaluate(audit)});await p.locator('.dialog-close').click();
 if(width<=1100){await p.getByRole('button',{name:'Open menu',exact:true}).click();results.push({width,locale,page:'menu',failures:await p.evaluate(audit)});await p.locator('.close-menu').click();}
 await p.locator('.chosen-panel>button').click();await p.evaluate(()=>document.fonts.ready);results.push({width,locale,page:'studio',failures:await p.evaluate(audit)});if(process.env.QA_SCREENSHOTS) await p.screenshot({path:`${root}/qa-screenshots/current/${width}-${locale}-studio.png`,fullPage:true});await p.close();
 }
 console.log(JSON.stringify(results,null,2));fs.writeFileSync(root+'/responsive-results.json',JSON.stringify(results,null,2));await b.close();server.kill();if(results.some(r=>r.failures.length))process.exitCode=1;
})().catch(e=>{console.error(e);server.kill();process.exit(1)});
