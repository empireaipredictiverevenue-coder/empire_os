"use strict";
const fs=require("node:fs"),http=require("node:http"),path=require("node:path");
const {once}=require("node:events");
const puppeteer=require("/home/ubuntu/.nvm/versions/node/v22.23.2/lib/node_modules/@wonderwhy-er/desktop-commander/node_modules/puppeteer");
const ROOT="/home/ubuntu/empire_staging/consumer_optin_roofing_20261020/out", PORT=18899;
let posts=0;
const server=http.createServer((req,res)=>{
  const relative=new URL(req.url,"http://localhost").pathname.slice(1);
  const fileName=relative.includes(".")?relative:relative+".html";
  if(req.method!=="GET"&&req.method!=="HEAD"){posts++;res.writeHead(405).end();return;}
  if(fileName.includes("..")){res.writeHead(404).end();return;}
  const file=path.join(ROOT,fileName);
  if(!file.startsWith(ROOT+"/")||!fs.existsSync(file)||!fs.statSync(file).isFile()){
    res.writeHead(404).end();return;
  }
  const mime={".html":"text/html",".js":"application/javascript",".css":"text/css",".svg":"image/svg+xml",".woff2":"font/woff2"};
  res.writeHead(200,{"Content-Type":mime[path.extname(file)]||"application/octet-stream"});
  fs.createReadStream(file).pipe(res);
});
(async()=>{
  server.listen(PORT,"127.0.0.1");await once(server,"listening");
  const browser=await puppeteer.launch({executablePath:"/home/ubuntu/.cache/puppeteer/chrome/linux-153.0.8010.36/chrome-linux64/chrome",headless:true,args:["--no-sandbox","--disable-dev-shm-usage"]});
  try{
    const page=await browser.newPage();
    const token="U".repeat(43);
    await page.goto("http://127.0.0.1:"+PORT+"/roofing/email-preferences#unsubscribe="+token,{waitUntil:"networkidle2",timeout:30000});
    await page.waitForFunction(()=>[...document.querySelectorAll("button")].some(b=>b.textContent.includes("Unsubscribe from updates")),{timeout:12000});
    const before=await page.evaluate(()=>({
      title:document.title,hash:location.hash,
      body:document.body.innerText.includes("Stop homeowner email updates"),
      button:[...document.querySelectorAll("button")].some(x=>x.textContent.includes("Unsubscribe from updates")),
      emailForms:document.querySelectorAll('input[type="email"]').length,
    }));
    if(before.hash!==""||!before.button||!before.body||posts!==0)throw Error("auto-processing or missing unsubscribe controls");
    await page.evaluate(()=>[...document.querySelectorAll("button")].find(b=>b.textContent.includes("Unsubscribe from updates")).click());
    await new Promise(resolve=>setTimeout(resolve,1800));
    const clickPosts=posts;
    await page.goto("http://127.0.0.1:"+PORT+"/roofing/email-preferences#confirm="+"C".repeat(43),{waitUntil:"networkidle2",timeout:30000});
    await page.waitForFunction(()=>[...document.querySelectorAll("button")].some(b=>b.textContent.includes("Confirm my subscription")),{timeout:11000});
    if((await page.evaluate(()=>location.hash))!==""||posts!==clickPosts)throw Error("confirmation was automatic or token leaked");
    console.log(JSON.stringify({
      status:"PREFERENCES_REAL_BROWSER_PREVIEW_PASS",
      preference_view:before,automatic_posts_before_click:0,
      attempted_post_only_after_user_click:clickPosts,
      confirm_view_requires_explicit_click:true,
      subscriber_records_created:false,
    },null,2));
    if(clickPosts!==1)throw Error("expected only one user-initiated blocked POST");
  }finally{await browser.close();server.close()}
})().catch(e=>{process.stderr.write("PREFERENCES_SMOKE_HELD "+e.message+"\n");server.close();process.exitCode=3});
