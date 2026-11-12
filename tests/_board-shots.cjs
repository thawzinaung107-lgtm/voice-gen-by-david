const {chromium}=require('playwright');
const {spawn}=require('child_process');
const server=spawn(process.execPath,['node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5179'],{cwd:'/root/projects/voicegen'});
(async()=>{
  await new Promise(r=>server.stdout.on('data',d=>{if(d.toString().includes('Local:'))r()}));
  const b=await chromium.launch({args:['--no-sandbox'],headless:true});
  const p=await b.newPage({viewport:{width:1280,height:900}});
  const errors=[];p.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
  for(const d of ['A','B','C']){
    await p.goto('http://127.0.0.1:5179/design.html');await p.waitForTimeout(900);
    await p.locator(`.dir button[data-d="${d}"]`).click();await p.waitForTimeout(400);
    await p.screenshot({path:`/tmp/board-${d}-1440.png`,fullPage:true});
    await p.setViewportSize({width:390,height:844});await p.waitForTimeout(300);
    await p.screenshot({path:`/tmp/board-${d}-390.png`,fullPage:true});
    await p.setViewportSize({width:1280,height:900});
    // MM variant
    await p.locator('.loc button[data-l="mm"]').click();await p.waitForTimeout(300);
    await p.screenshot({path:`/tmp/board-${d}-mm.png`,fullPage:true});
    await p.locator('.loc button[data-l="en"]').click();
  }
  console.log('console errors:',errors.length?errors:'none');
  await b.close();server.kill();
})().catch(e=>{console.error(e);server.kill();process.exit(1)});
