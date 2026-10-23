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
  try {
    await page.waitForSelector('[data-showroom-active="true"] canvas',{timeout:23000});
  } catch (error) {
    const diagnostic=await page.evaluate(()=>({
      active: document.querySelector('[data-showroom-active]')?.getAttribute('data-showroom-active'),
      scripts: [...document.scripts].map(s=>({type:s.type,src:s.src})).filter(s=>s.src),
      fallback: !!document.querySelector('[data-3d-fallback]'),
      modules:performance.getEntriesByType('resource').filter(r=>r.name.includes('yard-')).map(r=>r.name)
    }));
    throw new Error('ASYNC_SCENE_LOAD_DIAGNOSTIC '+JSON.stringify(diagnostic)+' PAGE_ERRORS '+JSON.stringify(pageErrors));
  }
  capture('real_three_js_webgl_canvas_rendered',await page.evaluate(()=>!!document.querySelector('canvas')));
  capture('native_wordpress_es_module_loaded',await page.evaluate(() =>
    !!document.querySelector('script[type="module"][src*="yard.js"]')));
  capture('real_view_and_paint_controls_rendered',await page.evaluate(() =>
    document.querySelectorAll('[data-camera-view]').length===3 &&
    document.querySelectorAll('[data-paint-finish]').length===3));
  await page.click('[data-camera-view="side"]');
  capture('side_view_interaction_state',await page.evaluate(() =>
    document.querySelector('[data-camera-view="side"]')?.getAttribute('aria-pressed')==='true' &&
    document.querySelector('[role="status"]')?.innerText.includes('Side profile')));
  await page.click('[data-paint-finish="champagne"]');
  capture('paint_palette_interaction_state',await page.evaluate(() =>
    document.querySelector('[data-paint-finish="champagne"]')?.getAttribute('aria-pressed')==='true' &&
    document.querySelector('[role="status"]')?.innerText.includes('Champagne gold')));
  capture('all_vehicle_controls_are_real_buttons',await page.evaluate(() =>
    [...document.querySelectorAll('[data-camera-view],[data-paint-finish]')].every(
      el=>el.tagName==='BUTTON'&&el.getAttribute('aria-pressed')!==null&&el.type==='button')));
  capture('webgl_is_active_in_visible_hero',await page.evaluate(() =>
    document.querySelector('[data-showroom-active]')?.dataset.showroomActive==='true'));
  await new Promise(resolve=>setTimeout(resolve,1200));
  const heroFile=screenDir+'/home-hero-desktop-v7.png';
  capture('v6_hero_real_3d_canvas_visible_when_captured',await page.evaluate(() =>
    !!document.querySelector('[data-showroom-active="true"] canvas')));
  await page.screenshot({path:heroFile,fullPage:false});
  screenshots['home-hero-desktop-v7.png']={sha256:sum(heroFile),bytes:fs.statSync(heroFile).size};
  capture('v7_studio_pbr_controls_registered',await page.evaluate(() =>
    document.querySelectorAll('[data-model-mode]').length===2 &&
    document.querySelector('[data-model-mode="studio"]')?.getAttribute('aria-pressed')==='false'));
  capture('v7_high_detail_glb_not_downloaded_before_opt_in',await page.evaluate(() =>
    !performance.getEntriesByType('resource').some(e=>e.name.endsWith('car-concept-editorial-webp.glb'))));
  await page.click('[data-model-mode="studio"]');
  try {
    await page.waitForFunction(() => document.querySelector('[data-studio-model-ready]')?.dataset.studioModelReady==='true',{timeout:45000});
  } catch(err) {
    throw new Error('PBR_STUDIO_GLTF_DIAGNOSTIC '+JSON.stringify(await page.evaluate(()=>({
      readiness:document.querySelector('[data-studio-model-ready]')?.dataset.studioModelReady,
      sceneIsActive:document.querySelector('[data-showroom-active]')?.dataset.showroomActive,
      loading:document.body.innerText.slice(0,200),
      modelNetwork:performance.getEntriesByType('resource').filter(r=>r.name.includes('.glb')).map(r=>({status:r.responseStatus,encoded:r.encodedBodySize,duration:r.duration})),
      assetScript:document.querySelector('#empire-yard-brand-settings')?.textContent?.slice(-350)
    })))+' ERRORS '+JSON.stringify(pageErrors));
  }
  capture('v7_studio_pbr_model_loaded_from_local_wordpress_glb',await page.evaluate(() =>
    performance.getEntriesByType('resource').some(e=>e.name.startsWith(location.origin+'/wp-content/themes/empire-yard-atelier/assets/models/') &&
      e.name.endsWith('car-concept-editorial-webp.glb') && e.encodedBodySize>8_000_000)));
  capture('v7_studio_pbr_status_and_attribution',await page.evaluate(() =>
    document.querySelector('[data-selected-model]')?.dataset.selectedModel==='studio' &&
    document.body.innerText.includes('Eric Chadwick') &&
    document.body.innerText.includes('CC BY 4.0')));
  capture('v7_studio_pbr_canvas_visible',await page.evaluate(() =>
    !!document.querySelector('[data-showroom-active="true"] canvas')));
  await page.click('[data-camera-view="front"]');
  capture('v7_studio_pbr_camera_view_switch',await page.evaluate(() =>
    document.querySelector('[data-camera-view="front"]')?.getAttribute('aria-pressed')==='true'));
  await page.click('[data-paint-finish="silver"]');
  capture('v7_studio_pbr_material_finish_switch',await page.evaluate(() =>
    document.querySelector('[data-paint-finish="silver"]')?.getAttribute('aria-pressed')==='true'));
  await new Promise(resolve=>setTimeout(resolve,1350));
  const studioFile=screenDir+'/home-pbr-model-desktop-v7.png';
  await page.screenshot({path:studioFile,fullPage:false});
  screenshots['home-pbr-model-desktop-v7.png']={sha256:sum(studioFile),bytes:fs.statSync(studioFile).size};
  await page.click('[data-model-mode="concept"]');
  capture('v7_studio_can_return_to_lightweight_concept',await page.evaluate(() =>
    document.querySelector('[data-selected-model]')?.dataset.selectedModel==='concept'));

  await page.evaluate(()=>window.scrollTo(0,document.body.scrollHeight));
  await page.waitForFunction(() =>
    document.querySelector('[data-showroom-active]')?.dataset.showroomActive==='false' &&
    !document.querySelector('canvas'), {timeout:12000});
  capture('offscreen_scene_unmounted_to_save_gpu',true);
  await page.evaluate(()=>window.scrollTo(0,0));
  await page.waitForSelector('canvas',{timeout:12000});
  capture('returning_to_hero_restores_scene',await page.evaluate(() =>
    document.querySelector('[data-showroom-active]')?.dataset.showroomActive==='true'));
  capture('3d_chunk_requested_separately',await page.evaluate(() =>
    performance.getEntriesByType('resource').some(r=>/yard-ShowroomScene-/.test(r.name))));
  await page.evaluate(() => document.querySelector('#collection')?.scrollIntoView());
  await page.waitForFunction(() => [...document.querySelectorAll('[data-editorial-photo] img')]
    .length===3 && [...document.querySelectorAll('[data-editorial-photo] img')]
    .every(img=>img.complete&&img.naturalWidth>=700), {timeout:15000});
  capture('v6_real_editorial_photos_loaded',await page.evaluate(()=>[...document.querySelectorAll(
    '[data-editorial-photo] img')].length===3));
  capture('v6_photos_locally_served_in_child_theme',await page.evaluate(()=>[...document.querySelectorAll(
    '[data-editorial-photo] img')].every(img=>
      img.src.startsWith(location.origin+'/wp-content/themes/empire-yard-atelier/assets/editorial/'))));
  capture('v6_photo_alt_text_and_lazy_decode',await page.evaluate(()=>[...document.querySelectorAll(
    '[data-editorial-photo] img')].every(img=>img.alt.includes('not') &&
      img.loading==='lazy' && img.decoding==='async')));
  capture('v6_photo_credits_visible_and_link_to_real_sources',await page.evaluate(()=>[...document.querySelectorAll(
    '[data-editorial-photo] figcaption a[href^="https://unsplash.com/photos/"]')].length===3));
  await page.evaluate(()=>window.scrollTo(0,0));
  await page.waitForSelector('[data-showroom-active="true"] canvas',{timeout:17000});
  capture('v6_desktop_scene_restored_before_screenshot',true);

  capture('desktop_hero_present',await page.evaluate(()=>document.body.innerText.includes('Fictional')||document.body.innerText.length>100));
  const wide=await page.evaluate(()=>({window:innerWidth,document:document.documentElement.scrollWidth,title:document.title}));
  capture('desktop_no_horizontal_overflow',wide.document<=wide.window+3);
  const desktopFile=screenDir+'/home-desktop-v7.png';
  await page.screenshot({path:desktopFile,fullPage:true});
  screenshots['home-desktop-v7.png']={sha256:sum(desktopFile),bytes:fs.statSync(desktopFile).size};
  await page.setViewport({width:390,height:844,deviceScaleFactor:1,isMobile:true,hasTouch:true});
  res=await go('/');
  capture('mobile_home_200',res.status()===200);
  await page.waitForSelector('[data-react-showroom="true"]',{timeout:16000});
  await page.waitForSelector('[data-launch-3d="true"]',{timeout:12000});
  capture('v5_mobile_hero_text_not_hidden_by_entrance_animation',await page.evaluate(()=>{
    const title=document.querySelector('#studio-title');
    return !!title && getComputedStyle(title).opacity==='1' &&
      title.getBoundingClientRect().height>30 &&
      title.innerText.includes('extraordinary.');
  }));
  capture('v7_mobile_pbr_model_not_requested_initially',await page.evaluate(() =>
    !performance.getEntriesByType('resource').some(r=>r.name.endsWith('car-concept-editorial-webp.glb'))));
  capture('v5_mobile_preview_and_opt_in_visible_before_screenshot',await page.evaluate(()=>{
    const node=document.querySelector('[data-showroom-active]');
    const button=document.querySelector('[data-launch-3d]');
    return !!node && !!button && getComputedStyle(node.parentElement).opacity==='1' &&
      button.getBoundingClientRect().height>=44 &&
      getComputedStyle(button).visibility==='visible' &&
      node.dataset.showroomActive==='false';
  }));
  const narrow=await page.evaluate(()=>({window:innerWidth,document:document.documentElement.scrollWidth,title:document.title}));
  capture('mobile_no_horizontal_overflow',narrow.document<=narrow.window+3);
  await page.evaluate(()=>document.querySelector('#collection')?.scrollIntoView());
  await page.waitForFunction(()=>[...document.querySelectorAll('[data-editorial-photo] img')]
    .length===3&&[...document.querySelectorAll('[data-editorial-photo] img')]
    .every(img=>img.complete&&img.naturalWidth>=700),{timeout:17000});
  capture('v6_mobile_editorial_photographs_rendered_before_screenshot',true);
  await page.evaluate(()=>window.scrollTo(0,0));
  await page.waitForSelector('[data-launch-3d="true"]',{timeout:12000});
  const mobileFile=screenDir+'/home-mobile-v7.png';
  await page.screenshot({path:mobileFile,fullPage:true});
  screenshots['home-mobile-v7.png']={sha256:sum(mobileFile),bytes:fs.statSync(mobileFile).size};
  res=await go('/demo-stock/');
  capture('mobile_inventory_200',res.status()===200);
  capture('synthetic_vehicle_visible',await page.evaluate(()=>document.body.innerText.includes('SYNTHETIC DEMO BLUE VAN')));
  await page.waitForFunction(()=>document.querySelector('.empire-yard-inventory')?.dataset.yardStyled==='true',{timeout:15000});
  capture('tailwind_inventory_enhancement_loaded',await page.evaluate(()=>document.querySelector('.empire-yard-inventory')?.classList.contains('max-w-6xl')));
  capture('inventory_card_tailwind_styled',await page.evaluate(()=>document.querySelector('.empire-yard-inventory article')?.classList.contains('rounded-xl')));
  capture('inventory_filter_labels_accessible',await page.evaluate(()=>[...document.querySelectorAll('.empire-yard-inventory form label')].every(el=>el.querySelector('input'))));
  await page.waitForFunction(() => Array.from(document.querySelectorAll('img')).some(i=>i.complete&&i.naturalWidth>0),{timeout:12000});
  capture('inventory_image_present',await page.evaluate(()=>Array.from(document.querySelectorAll('img')).some(i=>i.complete&&i.naturalWidth>0)));
  const stockFile=screenDir+'/stock-mobile-v7.png';
  await page.screenshot({path:stockFile,fullPage:true});
  screenshots['stock-mobile-v7.png']={sha256:sum(stockFile),bytes:fs.statSync(stockFile).size};
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
  const staffFile=screenDir+'/staff-desktop-v7.png';
  await page.screenshot({path:staffFile,fullPage:true});
  screenshots['staff-desktop-v7.png']={sha256:sum(staffFile),bytes:fs.statSync(staffFile).size};
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
  res=await go('/wp-admin/themes.php?page=empire-yard-branding');
  capture('branding_admin_page_200',res.status()===200);
  capture('branding_form_registered',await page.evaluate(() =>
    !!document.querySelector('input[name="empire_yard_brand_v1[name]"]') &&
    !!document.querySelector('input[name="empire_yard_brand_v1[contact_path]"]') &&
    !!document.querySelector('select[name="empire_yard_brand_v1[accent]"]')));
  capture('v6_wp_media_picker_controls_rendered',await page.evaluate(() =>
    document.querySelectorAll('.empire-yard-choose-media').length===3 &&
    document.querySelectorAll('.empire-yard-remove-media').length===3 &&
    document.querySelectorAll('input[name^="empire_yard_brand_v1[editorial_media_"]').length===3));
  capture('v6_media_picker_script_enqueued_in_wp_admin',await page.evaluate(()=>
    [...document.scripts].some(el=>el.src.includes('brand-media-picker.js')) &&
    !!window.wp?.media));
  await page.click('.empire-yard-choose-media[data-media-index="2"]');
  await page.waitForSelector('.media-modal',{timeout:14000});
  capture('v6_native_wordpress_media_modal_opens',await page.evaluate(()=>
    !!document.querySelector('.media-modal .media-frame')));
  await page.click('.media-modal-close');
  await page.$eval('input[name="empire_yard_brand_v1[editorial_media_2]"]',el=>{
    el.value='11';
    el.dispatchEvent(new Event('input',{bubbles:true}));
  });
  // Save through the real WordPress options.php authenticated nonce/capability flow.
  await page.$eval('input[name="empire_yard_brand_v1[name]"]',el=>{el.value='Northstar Concept';el.dispatchEvent(new Event('input',{bubbles:true}));});
  await page.$eval('input[name="empire_yard_brand_v1[strapline]"]',el=>{el.value='A Different Journey';el.dispatchEvent(new Event('input',{bubbles:true}));});
  await page.$eval('input[name="empire_yard_brand_v1[headline]"]',el=>{el.value='Discover the next';el.dispatchEvent(new Event('input',{bubbles:true}));});
  await page.$eval('input[name="empire_yard_brand_v1[highlight]"]',el=>{el.value='chapter.';el.dispatchEvent(new Event('input',{bubbles:true}));});
  await page.$eval('textarea[name="empire_yard_brand_v1[description]"]',el=>{el.value='Fictional premium studio experience with configurable presentation.';el.dispatchEvent(new Event('input',{bubbles:true}));});
  await page.$eval('input[name="empire_yard_brand_v1[contact_label]"]',el=>{el.value='Ask our studio';el.dispatchEvent(new Event('input',{bubbles:true}));});
  // Deliberately hostile external destination: sanitizer must refuse it.
  await page.$eval('input[name="empire_yard_brand_v1[contact_path]"]',el=>{el.value='https://malicious.invalid/collect';el.dispatchEvent(new Event('input',{bubbles:true}));});
  await page.select('select[name="empire_yard_brand_v1[accent]"]','ice');
  await Promise.all([page.waitForNavigation({waitUntil:'domcontentloaded',timeout:15000}),
    page.$eval('input[type="submit"][value="Save showroom branding"]',el=>el.form.requestSubmit())]);
  capture('wordpress_admin_branding_saved',page.url().includes('page=empire-yard-branding'));
  capture('external_contact_path_rejected_on_save',await page.evaluate(()=>
    document.querySelector('input[name="empire_yard_brand_v1[contact_path]"]')?.value==='/contact/'));
  res=await go('/');
  capture('configured_frontend_home_200',res.status()===200);
  capture('v6_wp_selected_media_replaced_second_photo',await page.evaluate(()=>
    document.querySelector('[data-editorial-photo="02"] img')?.src.includes('/wp-content/uploads/')));
  capture('v6_remaining_fallback_photo_sources_still_local',await page.evaluate(()=>
    [document.querySelector('[data-editorial-photo="01"] img'),
     document.querySelector('[data-editorial-photo="03"] img')].every(
       img=>img?.src.startsWith(location.origin+'/wp-content/themes/empire-yard-atelier/assets/editorial/'))));
  capture('v6_replaced_media_has_no_false_unsplash_credit',await page.evaluate(()=>
    !document.querySelector('[data-editorial-photo="02"] a[href*="unsplash.com"]') &&
    document.querySelector('[data-editorial-photo="02"]')?.textContent.includes('Media Library selection')));
  await page.waitForSelector('[data-react-showroom="true"]',{timeout:14000});
  capture('configured_brand_name_rendered',await page.evaluate(()=>
    document.querySelector('nav a[aria-label="Northstar Concept concept home"]')!==null));
  capture('configured_hero_headline_rendered',await page.evaluate(()=>
    document.querySelector('#studio-title')?.innerText.includes('Discover the next') &&
    document.querySelector('#studio-title')?.innerText.includes('chapter.')));
  capture('configured_brand_strapline_rendered',await page.evaluate(()=>
    document.body.innerText.includes('A DIFFERENT JOURNEY')));
  capture('configured_contact_remains_internal',await page.evaluate(()=>
    [...document.querySelectorAll('a')].filter(a=>a.textContent.includes('Ask our studio'))
      .every(a=>a.getAttribute('href')==='/contact/')));
  capture('configured_accent_tailwind_applied',await page.evaluate(()=>
    document.querySelector('[data-brand-accent]')?.dataset.brandAccent==='ice' &&
    getComputedStyle(document.querySelector('#studio-title em')).color==='rgb(182, 221, 235)'));
  capture('brand_script_json_non_executable',await page.evaluate(()=>
    document.querySelector('#empire-yard-brand-settings')?.type==='application/json'));
  capture('configured_3d_controls_still_present',await page.evaluate(()=>
    document.querySelectorAll('[data-camera-view]').length===3 &&
    document.querySelectorAll('[data-paint-finish]').length===3));
  res=await go('/demo-stock/');
  capture('configured_stock_page_200',res.status()===200);
  capture('configured_stock_header_uses_saved_brand',await page.evaluate(()=>
    document.querySelector('[data-yard-site-header]')?.innerText.includes('Northstar Concept')));
  capture('configured_stock_footer_uses_saved_brand',await page.evaluate(()=>
    document.querySelector('[data-yard-site-footer]')?.innerText.toLowerCase().includes('northstar concept')));
  capture('configured_stock_contact_link_stays_internal',await page.evaluate(()=>
    [...document.querySelectorAll('[data-yard-site-header] a')].some(a=>
      a.textContent.includes('Ask our studio')&&a.getAttribute('href')==='/contact/')));
  capture('configured_stock_accent_from_tailwind',await page.evaluate(()=>
    [...document.querySelectorAll('[data-yard-site-header] span')].some(span=>
      getComputedStyle(span).color==='rgb(182, 221, 235)')));
  capture('inventory_still_available_after_brand_change',await page.evaluate(()=>
    document.body.innerText.includes('SYNTHETIC DEMO BLUE VAN')));
  // Browser accessibility: targeted programmatic checks, not a full WCAG audit.
  const auditPage=await browser.newPage();
  await auditPage.setViewport({width:390,height:844,deviceScaleFactor:2,
    isMobile:true,hasTouch:true});
  await auditPage.setRequestInterception(true);
  auditPage.on('request', req => {
    if (req.url().startsWith(address+'/') || req.url().startsWith('data:') ||
        req.url().startsWith('blob:')) req.continue();
    else req.abort('blockedbyclient');
  });
  const mobileCDP=await auditPage.createCDPSession();
  await mobileCDP.send('Network.enable');
  await mobileCDP.send('Network.setCacheDisabled',{cacheDisabled:true});
  await mobileCDP.send('Network.emulateNetworkConditions',{
    offline:false,latency:150,downloadThroughput:1600000/8,
    uploadThroughput:750000/8,connectionType:'cellular4g'
  });
  await mobileCDP.send('Emulation.setCPUThrottlingRate',{rate:4});
  await auditPage.evaluateOnNewDocument(()=>{
    window.__empireLcp=0;
    try {new PerformanceObserver(list=>{
      for(const item of list.getEntries())window.__empireLcp=item.startTime;
    }).observe({type:'largest-contentful-paint',buffered:true});} catch{}
  });
  await auditPage.goto(address+'/',{waitUntil:'domcontentloaded',timeout:30000});
  await auditPage.waitForSelector('[data-react-showroom="true"]',{timeout:35000});
  await auditPage.waitForSelector('[data-launch-3d="true"]',{timeout:40000});
  // Allow a stable post-hydration paint/LCP candidate before reading timings.
  await auditPage.evaluate(()=>new Promise(resolve=>
    requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  await new Promise(resolve=>setTimeout(resolve,1100));
  const mobilePerformance=await auditPage.evaluate(()=>{
    const nav=performance.getEntriesByType('navigation')[0];
    const fcp=performance.getEntriesByName('first-contentful-paint')[0];
    const js=performance.getEntriesByType('resource')
      .filter(x=>x.name.includes('/dist/yard') && x.name.endsWith('.js'))
      .map(x=>({name:x.name.split('/').pop(),duration_ms:Math.round(x.duration),
        encoded_bytes:x.encodedBodySize,transfer_bytes:x.transferSize}));
    return {
      ttfb_ms:Math.round(nav.responseStart-nav.requestStart),
      dom_content_loaded_ms:Math.round(nav.domContentLoadedEventEnd-nav.startTime),
      fcp_ms:fcp?Math.round(fcp.startTime):null,
      lcp_candidate_ms:window.__empireLcp?Math.round(window.__empireLcp):null,
      js_resources:js,
      dom_nodes:document.querySelectorAll('*').length,
      canvas_visible:!!document.querySelector('[data-showroom-active="true"] canvas'),
      opt_in_button_visible:!!document.querySelector('[data-launch-3d="true"]'),
      scene_requested_before_opt_in:performance.getEntriesByType('resource')
        .some(x=>x.name.includes('yard-ShowroomScene-')),
      horizontal_overflow:document.documentElement.scrollWidth>innerWidth+3
    };
  });
  await auditPage.click('[data-launch-3d="true"]');
  await auditPage.waitForSelector('[data-showroom-active="true"] canvas',{timeout:50000});
  const postOptIn3D=await auditPage.evaluate(()=>({
    canvas_visible:!!document.querySelector('[data-showroom-active="true"] canvas'),
    scene_chunks:performance.getEntriesByType('resource').filter(x=>
      x.name.includes('yard-ShowroomScene-')).map(x=>({
      name:x.name.split('/').pop(),duration_ms:Math.round(x.duration),
      encoded_bytes:x.encodedBodySize
    }))
  }));
  const ax=await mobileCDP.send('Accessibility.getFullAXTree');
  const invalidNames=ax.nodes.filter(node=>
    !node.ignored && ['button','link'].includes(node.role?.value) &&
    !String(node.name?.value||'').trim());
  const accessAudit=await auditPage.evaluate(()=>{
    const links=[...document.querySelectorAll('a[href]')];
    const controls=[...document.querySelectorAll('button')];
    const source=document.querySelector('[data-react-showroom]');
    const labelled=controls.every(el=>el.getAttribute('aria-label')?.trim() ||
      el.textContent?.trim());
    const headings=[...document.querySelectorAll('h1')];
    const luma=color=>{
      const vals=color.match(/\d+(?:\.\d+)?/g)?.slice(0,3).map(Number);
      if(!vals)return 0;
      const [r,g,b]=vals.map(x=>{x/=255;return x<=.04045?x/12.92:((x+.055)/1.055)**2.4;});
      return .2126*r+.7152*g+.0722*b;
    };
    const contrast=(a,b)=>{
      const x=luma(a),y=luma(b);
      return Math.round((Math.max(x,y)+.05)/(Math.min(x,y)+.05)*100)/100;
    };
    const hero=document.querySelector('#studio-title');
    const highlight=hero?.querySelector('em');
    const background=getComputedStyle(document.querySelector('#studio')).backgroundColor;
    return {
      main_landmarks:document.querySelectorAll('main').length,
      h1_count:headings.length,
      named_buttons:labelled,
      named_links:links.every(a=>a.textContent.trim()||a.getAttribute('aria-label')?.trim()),
      live_region_count:document.querySelectorAll('[role="status"]').length,
      skip_link:!!document.querySelector('a[href="#main"]'),
      paint_button_pressed_states:[...document.querySelectorAll('[data-paint-finish]')].every(
        el=>['true','false'].includes(el.getAttribute('aria-pressed'))),
      hero_text_contrast:contrast(getComputedStyle(hero).color,background),
      hero_highlight_contrast:contrast(getComputedStyle(highlight).color,background),
      measured_brand:source?.dataset.brandAccent||null
    };
  });
  accessAudit.unnamed_ax_interactive_nodes=invalidNames.length;
  capture('v5_mobile_emulation_fcp_recorded',Number.isFinite(mobilePerformance.fcp_ms) &&
    mobilePerformance.fcp_ms>0);
  capture('v5_mobile_opt_in_avoids_automatic_3d_download',
    mobilePerformance.opt_in_button_visible===true &&
    mobilePerformance.canvas_visible===false &&
    mobilePerformance.scene_requested_before_opt_in===false);
  capture('v5_mobile_3d_chunk_load_recorded_after_opt_in',
    postOptIn3D.canvas_visible===true && postOptIn3D.scene_chunks.length===1 &&
    postOptIn3D.scene_chunks[0].encoded_bytes>0);
  capture('v5_mobile_no_overflow',mobilePerformance.horizontal_overflow===false);
  capture('v5_accessibility_one_h1_and_main',accessAudit.h1_count===1&&accessAudit.main_landmarks===1);
  capture('v5_accessibility_buttons_have_names',accessAudit.named_buttons===true);
  capture('v5_accessibility_links_have_names',accessAudit.named_links===true);
  capture('v5_accessibility_ax_tree_no_unnamed_links_buttons',
    accessAudit.unnamed_ax_interactive_nodes===0);
  capture('v5_accessibility_hero_contrast_aa',accessAudit.hero_text_contrast>=4.5 &&
    accessAudit.hero_highlight_contrast>=4.5);
  capture('v5_accessibility_controls_pressed_states',accessAudit.paint_button_pressed_states);
  // Reduced motion should use the native static fallback WITHOUT importing 3D.
  const reducePage=await browser.newPage();
  await reducePage.setViewport({width:390,height:844,isMobile:true,hasTouch:true});
  await reducePage.emulateMediaFeatures([{name:'prefers-reduced-motion',value:'reduce'}]);
  await reducePage.goto(address+'/',{waitUntil:'domcontentloaded',timeout:18000});
  await reducePage.waitForSelector('[data-react-showroom="true"]',{timeout:18000});
  const reducedMotion=await reducePage.evaluate(()=>({
    fallback:!!document.querySelector('[data-3d-fallback="true"]'),
    live_canvas:!!document.querySelector('canvas'),
    scene_chunk_requests:performance.getEntriesByType('resource')
      .filter(r=>r.name.includes('yard-ShowroomScene-')).length
  }));
  capture('v5_reduced_motion_no_webgl_canvas',reducedMotion.fallback &&
    !reducedMotion.live_canvas&&reducedMotion.scene_chunk_requests===0);
  await reducePage.close();
  await auditPage.close();
  capture('admin_no_server_5xx',responses.length===0);
  capture('all_external_browser_requests_blocked',outside===outsideBlocked);
  console.log(JSON.stringify({
    status:'WORDPRESS_REACT_3D_BROWSER_ACCEPTANCE_PASS',
    mobilePerformance,postOptIn3D,accessAudit,reducedMotion,
    checks,number_of_checks:Object.keys(checks).length,
    screenshots,wide,narrow,
    external_requests_blocked:outsideBlocked,external_requests_attempted:outside,server_errors:responses,
    browser:await browser.version(),
    origin:'127.0.0.1'
  }));
})().catch(err=>{console.error(String(err.stack||err));process.exitCode=1}).finally(async()=>{if(browser)await browser.close()});
