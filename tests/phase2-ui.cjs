// Explicit local API fixture only: no supplier calls or credentials.
const { chromium } = require('playwright');
const { spawn } = require('node:child_process');
const assert = require('node:assert/strict');
const origin = 'http://127.0.0.1:4188';
const server = spawn(process.execPath, ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '4188', '--strictPort'], { stdio: 'pipe' });
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
(async () => {
  let browser;
  try {
    for (let i=0;i<60;i++) { try { if ((await fetch(origin)).ok) break; } catch {} await wait(100); }
    browser = await chromium.launch({headless:true, args:['--no-sandbox']});
    const context = await browser.newContext();
    const page = await context.newPage();
    const errors=[]; page.on('pageerror', error => errors.push(error.message));
    let authenticated=false, failGeneration=false, failHistory=false, missingVoice=false, supported=true;
    let submitted=[], polls=0, calls=[];
    const voice={id:'nPczCjzI2devNBz1zQrb',name:'Brian',provider:'elevenlabs'};
    const catalog=[voice,{id:'onwK4e9ZLuTAKqWW03F9',name:'Daniel',provider:'elevenlabs'},{id:'pFZP5JQG7iQjIQuC4Bku',name:'Lily',provider:'elevenlabs'},{id:'pNInz6obpgDQGcFmaJgB',name:'Adam',provider:'elevenlabs'}];
    const record={id:'local-fixture-1',taskId:'supplier-fixture-task',kind:'tts',state:'processing',createdAt:Date.now(),voiceIds:[voice.id]};
    await page.addInitScript(() => localStorage.setItem('voicegen.v2.locale',JSON.stringify('en')));
    await page.route('**/api/**',async route => {
      const req=route.request(), path=new URL(req.url()).pathname;
      calls.push({path, hash:new URL(page.url()).hash, referer:req.headers().referer});
      const send=(body,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
      if(path==='/api/session') { assert.equal(req.postDataJSON().token,'fixture-owner-token'); authenticated=true; return send({ok:true}); }
      if(path==='/api/health') return send({configured:true,capabilities:{tts:supported,dialogue:false,srt:false}});
      if(!authenticated) return send({error:'Sign-in required'},401);
      if(path==='/api/me') return send({user:{id:'fixture-owner'},wallet:{balance:125}});
      if(path==='/api/voices') return send({voices:missingVoice?[]:catalog});
      if(path==='/api/history') return failHistory?send({error:'Fixture history unavailable'},502):send({items:submitted.length&&!failGeneration?[record]:[]});
      if(path==='/api/generate') { submitted.push(req.postDataJSON()); await wait(150); return failGeneration?send({error:'Fixture supplier timeout; retry with same request'},504):send({generation:record}); }
      if(path==='/api/history/local-fixture-1') { polls++; return send({generation:{...record,state:'completed',audioUrl:'/api/audio/local-fixture-1'}}); }
      if(path==='/api/audio/local-fixture-1') return route.fulfill({status:200,contentType:'audio/wav',body:Buffer.alloc(44)});
      throw new Error('Unexpected local API path '+path);
    });
    await page.goto(origin+'/#/studio');
    await page.getByRole('textbox',{name:'Script editor'}).fill('Hello fixture narration.');
    assert.equal(await page.getByRole('button',{name:'Generate speech',exact:true}).isDisabled(),true);
    await page.goto(origin+'/#/settings');
    await page.getByLabel('Access token',{exact:true}).fill('fixture-owner-token');
    await page.getByRole('button',{name:'Sign in',exact:true}).click();
    await page.getByRole('heading',{name:'Signed in',exact:true}).waitFor();
    assert.equal(await page.evaluate(() => JSON.stringify(localStorage).includes('fixture-owner-token')),false);
    await page.goto(origin+'/#/studio');
    for (const item of catalog.slice(1)) {
      await page.locator('.voice-picker button').filter({hasText:item.name}).click();
      await page.getByRole('textbox',{name:'Script editor'}).fill(`Mapping check ${item.name}`);
      failGeneration=true;
      await page.getByRole('button',{name:'Generate speech',exact:true}).click();
      await page.getByRole('alert').filter({hasText:'Fixture supplier timeout'}).waitFor();
      assert.equal(submitted.at(-1).voice_id,item.id,`${item.name} exact catalog mapping`);
    }
    submitted=[];
    await page.locator('.voice-picker button').filter({hasText:'Brian'}).click();
    await page.getByRole('textbox',{name:'Script editor'}).fill('Hello fixture narration.');
    await page.getByLabel('Speech language',{exact:true}).selectOption('my');
    await page.getByRole('button',{name:'MM',exact:true}).click();
    await page.getByRole('button',{name:'EN',exact:true}).click();
    assert.equal(await page.getByRole('tab',{name:'Dialogue to Speech'}).isDisabled(),true);
    failGeneration=true;
    await page.locator('.studio-summary button').evaluate(button => { button.click(); button.click(); });
    await page.getByRole('alert').filter({hasText:'Fixture supplier timeout'}).waitFor();
    assert.equal(submitted.length,1,'duplicate click must not double submit');
    assert.equal(submitted[0].voice_id,voice.id);
    assert.equal(submitted[0].language_code,'my','speech language independent from EN UI');
    assert.match(submitted[0].request_id,/^[0-9a-f-]{36}$/);
    await page.getByRole('button',{name:'Generate speech',exact:true}).click();
    await page.getByRole('alert').filter({hasText:'Fixture supplier timeout'}).waitFor();
    assert.equal(submitted[1].request_id,submitted[0].request_id,'uncertain retry must reuse request id');
    await page.getByRole('textbox',{name:'Script editor'}).fill('Changed fixture narration.');
    failGeneration=false;
    await page.getByRole('button',{name:'Generate speech',exact:true}).click();
    await page.locator('audio').waitFor();
    assert.notEqual(submitted[2].request_id,submitted[1].request_id);
    assert.ok(polls>=1);
    assert.equal(await page.locator('audio').getAttribute('src'),'/api/audio/local-fixture-1');
    assert.equal(await page.getByRole('link',{name:'Download'}).getAttribute('href'),'/api/audio/local-fixture-1');
    await page.getByRole('button',{name:'Check status',exact:true}).click();
    assert.equal(submitted.length,3,'polling must not generate');
    failHistory=true;
    await page.getByRole('button',{name:'Refresh history'}).click();
    await page.getByRole('alert').filter({hasText:'Fixture history unavailable'}).waitFor();
    assert.equal(await page.locator('.history-item').count(),1,'history errors preserve existing tasks');
    failHistory=false;
    await page.goto(origin+'/#/projects');
    await page.goBack();
    await page.goto(origin+'/#/studio');
    assert.equal(await page.getByRole('textbox',{name:'Script editor'}).inputValue(),'Changed fixture narration.');
    await page.reload();
    assert.equal(await page.getByRole('textbox',{name:'Script editor'}).inputValue(),'Changed fixture narration.');
    missingVoice=true;
    await page.reload();
    await page.getByText('This voice is unavailable in the supplier catalog.').waitFor();
    assert.equal(await page.getByRole('button',{name:'Generate speech',exact:true}).isDisabled(),true);
    missingVoice=false; supported=false;
    await page.reload();
    await page.getByText('Speech generation is unavailable.',{exact:true}).waitFor();
    assert.equal(await page.getByRole('button',{name:'Generate speech',exact:true}).isDisabled(),true);
    authenticated=false; supported=true;
    await page.goto(origin+'/#access=fixture-owner-token');
    await page.reload();
    await page.getByRole('heading',{name:'Signed in',exact:true}).waitFor();
    assert.equal(await page.evaluate(() => location.hash),'#/settings');
    assert.ok(calls.every(call=>!call.hash.includes('fixture-owner-token')),'access hash erased before requests');
    assert.ok(calls.every(call=>!call.referer?.includes('fixture-owner-token')));
    assert.equal(await page.evaluate(() => JSON.stringify(localStorage).includes('fixture-owner-token')),false);
    assert.deepEqual(errors,[]);
    console.log('PASS Phase2 mock E2E: auth gate/login/access erasure, supplier credits, mapped voice + separate speech language, duplicate guard, stable retry IDs, payload reset, polling/audio/download, visible history errors, unsupported gates, draft routes/refresh.');
  } finally { if(browser) await browser.close(); server.kill('SIGTERM'); }
})().catch(error => { console.error(error); process.exitCode=1; });
