const {chromium}=require('playwright');
const {spawn}=require('child_process');
const server=spawn(process.execPath,['node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5179'],{cwd:'/root/projects/voicegen'});
(async()=>{
  await new Promise(r=>server.stdout.on('data',d=>{if(d.toString().includes('Local:'))r()}));
  const b=await chromium.launch({args:['--no-sandbox'],headless:true});
  const p=await b.newPage({viewport:{width:390,height:900}});
  await p.goto('http://127.0.0.1:5179');await p.waitForTimeout(1200);
  const res=await p.evaluate(()=>{
    const out=[];
    document.querySelectorAll('.voice-card').forEach((e,i)=>{
      const r=e.getBoundingClientRect();
      // find the offending child
      const kids=[...e.querySelectorAll('*')].filter(k=>k.getBoundingClientRect().right>e.getBoundingClientRect().right+2);
      out.push({i,sw:e.scrollWidth,cw:e.clientWidth,right:r.right,kids:kids.map(k=>({tag:k.tagName,cls:k.className.baseVal||k.className,right:Math.round(k.getBoundingClientRect().right)}))});
    });
    return {vw:innerWidth,docSW:document.documentElement.scrollWidth,cards:out};
  });
  console.log(JSON.stringify(res,null,1));
  await b.close();server.kill();
})().catch(e=>{console.error(e);server.kill();process.exit(1)});
