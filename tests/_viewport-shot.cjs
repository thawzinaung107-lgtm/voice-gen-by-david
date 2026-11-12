const {chromium}=require('playwright');
const {spawn}=require('child_process');
const server=spawn(process.execPath,['node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5179'],{cwd:'/root/projects/voicegen'});
(async()=>{
  await new Promise(r=>server.stdout.on('data',d=>{if(d.toString().includes('Local:'))r()}));
  const b=await chromium.launch({args:['--no-sandbox'],headless:true});
  const p=await b.newPage({viewport:{width:390,height:844}});
  await p.goto('http://127.0.0.1:5179');await p.waitForTimeout(1200);
  await p.screenshot({path:'/tmp/vp-390-top.png'}); // viewport only, not fullPage
  await p.locator('.compare-open').click();await p.waitForTimeout(600);
  await p.screenshot({path:'/tmp/vp-390-compare.png'});
  await b.close();server.kill();
})().catch(e=>{console.error(e);server.kill();process.exit(1)});
