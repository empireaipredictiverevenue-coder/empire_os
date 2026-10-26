/** Direct visual/browser acceptance of PRIVATE localhost static export.
 * Never submits real or synthetic buyer POST and never visits a public page.
 */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const puppeteer=require('/home/ubuntu/.nvm/versions/node/v22.23.2/lib/node_modules/@wonderwhy-er/desktop-commander/node_modules/puppeteer');
const chrome='/home/ubuntu/.cache/puppeteer/chrome-headless-shell/linux-153.0.8010.36/chrome-headless-shell-linux64/chrome-headless-shell';
const base='http://127.0.0.1:28842';
const output=process.env.EMPIRE_REVIEW_OUTPUT || '/home/ubuntu/empire_releases/website_solar_commercial_premium_20261026_candidate/browser_qa';
fs.mkdirSync(output,{recursive:true,mode:0o700});
const report={schema_version:'empire.website.solar_commercial_private_browser_qa.v1',
 status:'NOT_RUN',
 origin:base,
 real_customer_post_count:0,
 public_website_modified:false,
 screens:[],
 no_external_requests:true,
 errors:[],
};
(async()=>{
 let browser;
 try{
  browser=await puppeteer.launch({executablePath:chrome,headless:true,
   args:['--no-sandbox','--disable-gpu','--disable-dev-shm-usage','--disable-background-networking','--window-size=1440,900']});
  for(const viewport of [{name:'desktop',width:1440,height:900},{name:'mobile',width:390,height:844}]){
   for(const route of ['/commercial','/industries/solar']){
    const page=await browser.newPage();
    await page.setCacheEnabled(false);
    await page.setViewport({width:viewport.width,height:viewport.height,deviceScaleFactor:1});
    const requests=[],bad=[],exceptions=[],posts=[];
    await page.setRequestInterception(true);
    page.on('request',req=>{
     const u=req.url();
     if(req.method()==='POST'){posts.push(u);return req.abort('blockedbyclient');}
     if(!u.startsWith(base)){requests.push({url:u.slice(0,160),type:'external'});return req.abort('blockedbyclient');}
     req.continue();
    });
    page.on('response',res=>{if(res.status()>=400)bad.push({status:res.status(),url:res.url().slice(0,175)});});
    page.on('pageerror',err=>exceptions.push(String(err).slice(0,220)));
    const res=await page.goto(base+route,{waitUntil:'networkidle2',timeout:45000});
    assert.equal(res.status(),200,route+' HTML');
    await new Promise(r=>setTimeout(r,600));
    const stats=await page.evaluate(()=>{
     const all=[...document.querySelectorAll('h1')].map(x=>x.innerText.trim());
     const form=document.querySelector('#commercial-enquiry form');
     const select=form?.querySelector('select');
     const consent=form?.querySelector('input[type=checkbox][required]');
     const submit=form?.querySelector('button[type=submit]');
     const styles=getComputedStyle(document.querySelector('main'));
     return {url:location.pathname,
       title:document.title,
       headings:all,
       viewport:window.innerWidth,
       documentWidth:document.documentElement.scrollWidth,
       bodyWidth:document.body.scrollWidth,
       imageLoads:[...document.images].filter(im=>!im.complete||!im.naturalWidth).map(im=>im.src),
       mainBackground:styles.backgroundColor,
       duplicateMainNavigation:!!document.querySelector('main nav, main header'),
       formCount:document.querySelectorAll('form').length,
       formPresent:!!form,
       catalogOffers:select?.options?.length??0,
       consentUnchecked:consent?!consent.checked:null,
       disabledBeforeConsent:submit?.disabled??null,
       sourceLink:[...document.querySelectorAll('a[href]')].map(a=>a.getAttribute('href')).find(u=>u?.startsWith('/commercial?entry='))||null,
       sourceTarget:document.querySelector('a[href="#commercial-enquiry"]')?.getAttribute('href')||null
     };
    });
    if(route==='/commercial'){
     assert.ok(stats.formCount>=1 && stats.formCount<=2,'approved Commercial and optional original brokerage forms only');
     assert.ok(stats.catalogOffers>1,'original approved offers loaded');
     assert.equal(stats.disabledBeforeConsent,true);
     assert.equal(stats.consentUnchecked,true);
    } else {
     assert.equal(stats.formCount,0);
     assert.ok(stats.sourceLink?.startsWith('/commercial?entry=%2Findustries%2Fsolar'), 'approved source-aware CTA');
    }
    assert.equal(stats.headings.length,1,'one H1');
    assert.equal(stats.duplicateMainNavigation,false,'flagship SiteChrome already owns the header');
    assert.ok(stats.documentWidth<=stats.viewport+3,'no horizontal overflow '+route+' '+viewport.name+' '+JSON.stringify(stats));
    assert.equal(stats.imageLoads.length,0,'missing images');
    assert.deepEqual(posts,[],'POST must never run');
    assert.deepEqual(bad,[],'GET 4xx/5xx');
    assert.deepEqual(exceptions,[],'JS errors');
    assert.deepEqual(requests,[],'no external requests');
    const filename=(route==='/commercial'?'commercial':'solar')+'-'+viewport.name+'.png';
    await page.screenshot({path:path.join(output,filename),fullPage:true,animations:'disabled'});
    report.screens.push({route,viewport:viewport.name,width:viewport.width,height:viewport.height,
      screenshot:filename,...stats,errors:exceptions,failed_requests:bad,external:requests,posts:posts.length});
    await page.close();
   }
  }
  // Follow the actual Solar source-aware link into the preserved consent form.
  const page=await browser.newPage();
  await page.setCacheEnabled(false);
  await page.setViewport({width:390,height:844});
  await page.setRequestInterception(true);
  const posts=[];
  page.on('request',req=>{
   if(req.method()==='POST'){posts.push(req.url());return req.abort();}
   if(!req.url().startsWith(base))return req.abort();
   req.continue();
  });
  await page.goto(base+'/industries/solar',{waitUntil:'networkidle2',timeout:45000});
  const link=await page.$('a[href^="/commercial?entry="]');
  assert.ok(link,'Solar source-aware link');
  await Promise.all([
   page.waitForNavigation({waitUntil:'networkidle2',timeout:45000}),
   link.click()
  ]);
  assert.equal(new URL(page.url()).pathname,'/commercial');
  assert.equal(new URL(page.url()).searchParams.get('entry'),'/industries/solar');
  const checks=await page.evaluate(()=>({
    form:!!document.querySelector('#commercial-enquiry form'),
    consentUnchecked:!document.querySelector('#commercial-enquiry input[type=checkbox][required]')?.checked,
    disabled:document.querySelector('#commercial-enquiry button[type=submit]')?.disabled
  }));
  assert.deepEqual(checks,{form:true,consentUnchecked:true,disabled:true});
  assert.deepEqual(posts,[]);
  report.solar_source_navigation={status:'PASS',query:'entry=/industries/solar',...checks};
  await page.close();
  report.status='ORIGINAL_TWO_PAGE_PRIVATE_DESKTOP_MOBILE_BROWSER_PASS';
  fs.writeFileSync(path.join(output,'qa_receipt.json'),JSON.stringify(report,null,2)+'\n',{flag:'wx',mode:0o600});
  console.log(JSON.stringify({status:report.status,screens:report.screens.map(x=>({
   route:x.route,viewport:x.viewport,h1:x.headings[0],overflow:x.documentWidth-x.viewport,
   form:x.formPresent,offers:x.catalogOffers,posts:x.posts})),
   source_navigation:report.solar_source_navigation,
   post_requests:0,production_modified:false},null,2));
 }catch(err){
  console.error('BROWSER_QA_FAILED',err.stack||String(err));
  process.exitCode=1;
 }finally{await browser?.close();}
})();
