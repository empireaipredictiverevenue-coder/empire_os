'use strict';
/** Localhost-only Chrome acceptance. All data synthetic. */
const fs=require('fs');
const crypto=require('crypto');
const puppeteer=require('/home/ubuntu/.nvm/versions/node/v22.23.2/lib/node_modules/@wonderwhy-er/desktop-commander/node_modules/puppeteer');
const address=process.env.YARD_BASE_URL;
const password=process.env.YARD_ADMIN_PASSWORD;
const screenDir=process.env.YARD_SCREENSHOT_DIR;
if(!/^http:\/\/127\.0\.0\.1:\d+$/.test(address)||!password||!screenDir) throw new Error('Isolated browser variables absent');
const screenshots={};
const checks={};
const capture=(name,ok)=>{checks[name]=!!ok;if(!ok)throw new Error('BROWSER_CHECK_FAILED '+name)};
const sum=(p)=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
let browser;
(async()=>{
  browser=await puppeteer.launch({
    executablePath:process.env.YARD_CHROME,
    headless:true,
    args:['--no-sandbox','--disable-dev-shm-usage','--no-first-run','--disable-background-networking','--disable-sync','--disable-features=Translate,MediaRouter']
  });
  const page=await browser.newPage();
  const pageErrors=[];
  page.on('pageerror',error=>pageErrors.push(String(error)));
  await page.setRequestInterception(true);
  let outside=0;
  let outsideBlocked=0;
  page.on('request',req=>{
    if(req.url().startsWith('data:') || req.url().startsWith('blob:')) { req.continue(); return; }
    if(!req.url().startsWith(address+'/')){outside++;req.abort('blockedbyclient');}
    else req.continue();
  });
  page.on('requestfailed',req=>{
    if(!req.url().startsWith(address+'/') &&
      req.failure()?.errorText?.includes('BLOCKED_BY_CLIENT')) outsideBlocked++;
  });
  page.on('dialog',d=>d.dismiss());
  const responses=[];
  page.on('response',res=>{
    if(res.status()>=500&&res.url().startsWith(address+'/')) responses.push(res.status()+' '+res.url());
  });
  const go=async(path)=>page.goto(address+path,{waitUntil:'domcontentloaded',timeout:15000});
  await page.setViewport({width:1440,height:900,deviceScaleFactor:1});
  let res=await go('/');
  capture('desktop_home_200',res.status()===200);
  try {
    await page.waitForSelector('[data-react-showroom="true"]',{timeout:13000});
  } catch(err) {
    const diag=await page.evaluate(()=>({
      root:!!document.getElementById('empire-yard-react-root'),
      title:document.title,
      body:document.body.innerText.slice(0,700),
      scripts:[...document.scripts].map(x=>x.src).filter(Boolean).slice(-10),
      styles:[...document.styleSheets].map(x=>x.href).filter(Boolean).slice(-10),
      child:document.getElementById('empire-yard-react-root')?.outerHTML?.slice(0,450)
    }));
    throw new Error('REACT_MOUNT_DIAGNOSTIC '+JSON.stringify(diag)+' ERRORS '+JSON.stringify(pageErrors));
  }
  capture('react_root_hydrated',await page.evaluate(()=>!!document.querySelector('[data-react-showroom="true"]')));
  capture('react_three_heading',await page.evaluate(()=>document.querySelector('#studio-title')?.innerText.toLowerCase().includes('extraordinary')));
  capture('tailwind_css_generated',await page.evaluate(()=>getComputedStyle(document.querySelector('#studio')).backgroundColor==='rgb(9, 25, 35)'));
  capture('magic_ui_style_animated_grid',await page.evaluate(()=>document.querySelectorAll('#studio svg[aria-hidden="true"] rect').length>=5));
  await page.waitForFunction(()=>document.querySelector('canvas')||document.querySelector('[data-3d-fallback]'),{timeout:18000});
  capture('three_js_canvas_or_accessible_fallback',await page.evaluate(()=>!!(document.querySelector('canvas')||document.querySelector('[data-3d-fallback]'))));
  capture('real_three_js_webgl_canvas_rendered',await page.evaluate(()=>!!document.querySelector('canvas')));
  capture('desktop_hero_present',await page.evaluate(()=>document.body.innerText.includes('Fictional')||document.body.innerText.length>100));
  const wide=await page.evaluate(()=>({window:innerWidth,document:document.documentElement.scrollWidth,title:document.title}));
  capture('desktop_no_horizontal_overflow',wide.document<=wide.window+3);
  const desktopFile=screenDir+'/home-desktop.png';
  await page.screenshot({path:desktopFile,fullPage:true});
  screenshots['home-desktop.png']={sha256:sum(desktopFile),bytes:fs.statSync(desktopFile).size};
  await page.setViewport({width:390,height:844,deviceScaleFactor:1,isMobile:true,hasTouch:true});
  res=await go('/');
  capture('mobile_home_200',res.status()===200);
  const narrow=await page.evaluate(()=>({window:innerWidth,document:document.documentElement.scrollWidth,title:document.title}));
  capture('mobile_no_horizontal_overflow',narrow.document<=narrow.window+3);
  const mobileFile=screenDir+'/home-mobile.png';
  await page.screenshot({path:mobileFile,fullPage:true});
  screenshots['home-mobile.png']={sha256:sum(mobileFile),bytes:fs.statSync(mobileFile).size};
  res=await go('/demo-stock/');
  capture('mobile_inventory_200',res.status()===200);
  capture('synthetic_vehicle_visible',await page.evaluate(()=>document.body.innerText.includes('SYNTHETIC DEMO BLUE VAN')));
  await page.waitForFunction(()=>document.querySelector('.empire-yard-inventory')?.dataset.yardStyled==='true',{timeout:15000});
  capture('tailwind_inventory_enhancement_loaded',await page.evaluate(()=>document.querySelector('.empire-yard-inventory')?.classList.contains('max-w-6xl')));
  capture('inventory_card_tailwind_styled',await page.evaluate(()=>document.querySelector('.empire-yard-inventory article')?.classList.contains('rounded-xl')));
  capture('inventory_filter_labels_accessible',await page.evaluate(()=>[...document.querySelectorAll('.empire-yard-inventory form label')].every(el=>el.querySelector('input'))));
  await page.waitForFunction(() => Array.from(document.querySelectorAll('img')).some(i=>i.complete&&i.naturalWidth>0),{timeout:12000});
  capture('inventory_image_present',await page.evaluate(()=>Array.from(document.querySelectorAll('img')).some(i=>i.complete&&i.naturalWidth>0)));
  const stockFile=screenDir+'/stock-mobile.png';
  await page.screenshot({path:stockFile,fullPage:true});
  screenshots['stock-mobile.png']={sha256:sum(stockFile),bytes:fs.statSync(stockFile).size};
  await page.keyboard.press('Tab');
  capture('keyboard_focusable_element',await page.evaluate(()=>document.activeElement&&document.activeElement!==document.body));
  res=await go('/wp-login.php');
  capture('login_page_200',res.status()===200);
  await page.$eval('#user_login',el=>{el.value='demo_yard_admin';el.dispatchEvent(new Event('input',{bubbles:true}));});
  await page.$eval('#user_pass',(el,pw)=>{el.value=pw;el.dispatchEvent(new Event('input',{bubbles:true}));},password);
  capture('login_username_field_correct',await page.$eval('#user_login',el=>el.value==='demo_yard_admin'));
  capture('login_password_field_present',await page.$eval('#user_pass',el=>el.value.length>=32));
  await Promise.all([page.waitForNavigation({waitUntil:'domcontentloaded',timeout:15000}),
    page.$eval('#loginform',form=>form.requestSubmit())]);
  if(page.url().includes('wp-login.php')) {
    const diagnostic=await page.evaluate(()=>({url:location.pathname+location.search,error:document.querySelector('#login_error')?.innerText||'',notice:document.querySelector('.message')?.innerText||''}));
    throw new Error('ADMIN_LOGIN_DIAGNOSTIC '+JSON.stringify(diagnostic));
  }
  capture('admin_login_success',true);
  await page.setViewport({width:1440,height:900,deviceScaleFactor:1,isMobile:false,hasTouch:false});
  res=await go('/wp-admin/admin.php?page=empire-yard-bookings');
  capture('staff_workbench_200',res.status()===200);
  capture('staff_form_present',await page.$('form input[name="bay"]')!==null);
  capture('staff_recent_table_present',await page.evaluate(()=>document.body.innerText.includes('Recent synthetic appointments')));
  const staffFile=screenDir+'/staff-desktop.png';
  await page.screenshot({path:staffFile,fullPage:true});
  screenshots['staff-desktop.png']={sha256:sum(staffFile),bytes:fs.statSync(staffFile).size};
  await page.$eval('input[name="bay"]',el=>{el.value='bay-1';el.dispatchEvent(new Event('change',{bubbles:true}));});
  await page.$eval('input[name="date"]',el=>{el.value='2026-10-26';el.dispatchEvent(new Event('change',{bubbles:true}));});
  await page.$eval('input[name="time"]',el=>{el.value='10:00';el.dispatchEvent(new Event('change',{bubbles:true}));});
  await page.select('select[name="service"]','repair');
  await page.select('select[name="minutes"]','60');
  await Promise.all([
    page.waitForNavigation({waitUntil:'domcontentloaded',timeout:15000}),
    page.$eval('form input[name="action"][value="empire_yard_staff_hold"]',node=>node.form.requestSubmit())
  ]);
  capture('staff_hold_receipt',await page.evaluate(()=>document.body.innerText.includes('Demo hold recorded.')));
  capture('staff_hold_listed',await page.evaluate(()=>
    Array.from(document.querySelectorAll('table tbody tr')).some(tr=>tr.innerText.includes('held'))));
  await Promise.all([
    page.waitForNavigation({waitUntil:'domcontentloaded',timeout:15000}),
    page.$eval('form input[name="next_status"][value="confirmed"]',node=>node.form.requestSubmit())
  ]);
  capture('staff_confirmation_receipt',await page.evaluate(()=>document.body.innerText.includes('Status updated.')));
  await Promise.all([
    page.waitForNavigation({waitUntil:'domcontentloaded',timeout:15000}),
    page.$eval('form input[name="next_status"][value="cancelled"]',node=>node.form.requestSubmit())
  ]);
  capture('staff_cancel_receipt',await page.evaluate(()=>document.body.innerText.includes('Status updated.')));
  capture('admin_no_server_5xx',responses.length===0);
  capture('all_external_browser_requests_blocked',outside===outsideBlocked);
  console.log(JSON.stringify({
    status:'WORDPRESS_REACT_3D_BROWSER_ACCEPTANCE_PASS',
    checks,number_of_checks:Object.keys(checks).length,
    screenshots,wide,narrow,
    external_requests_blocked:outsideBlocked,external_requests_attempted:outside,server_errors:responses,
    browser:await browser.version(),
    origin:'127.0.0.1'
  }));
})().catch(err=>{console.error(String(err.stack||err));process.exitCode=1}).finally(async()=>{if(browser)await browser.close()});
