const {chromium}=require('playwright');
const {spawn}=require('child_process');
const server=spawn(process.execPath,['node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5179'],{cwd:'/root/projects/voicegen'});
(async()=>{
  await new Promise(r=>server.stdout.on('data',d=>{if(d.toString().includes('Local:'))r()}));
  const b=await chromium.launch({args:['--no-sandbox'],headless:true});
  // studio 390 MM (viewport), light mode 1440 (fullPage), compare desktop 1440
  let p=await b.newPage({viewport:{width:390,height:844}});
  await p.goto('http://127.0.0.1:5179');await p.waitForTimeout(1200);
  await p.locator('.bottom-nav button').nth(2).click();await p.waitForTimeout(800);
  await p.screenshot({path:'/tmp/vp-390-studio.png'});
  await p.close();
  p=await b.newPage({viewport:{width:1440,height:900}});
  await p.goto('http://127.0.0.1:5179');await p.getByRole('button',{name:'EN',exact:true}).click();await p.waitForTimeout(800);
  await p.locator('.theme-btn').click();await p.waitForTimeout(600);
  await p.screenshot({path:'/tmp/vp-1440-light.png',fullPage:true});
  await p.locator('.theme-btn').click();await p.waitForTimeout(400);
  await p.locator('.compare-open').click();await p.waitForTimeout(600);
  await p.screenshot({path:'/tmp/vp-1440-compare.png'});
  await p.locator('.chosen-panel>button').scrollIntoViewIfNeeded().catch(()=>{});
  await b.close();server.kill();
})().catch(e=>{console.error(e);server.kill();process.exit(1)});
