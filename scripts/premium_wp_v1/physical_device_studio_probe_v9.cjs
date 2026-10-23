'use strict';
/**
 * Connected REAL Chrome hardware acceptance. NO browser emulation and NO server writes.
 * Usage requires a physically authorised Chrome DevTools target (e.g. USB ADB forward),
 * a synthetic non-production staging site, exact operator allowlist and an output path.
 * Does NOT independently certify actual manufacturer rights or physical device ownership.
 */
const fs=require('node:fs');
const crypto=require('node:crypto');

function assertScope(env) {
  const allowed=env.EMPIRE_DEVICE_QA_ALLOWED_SITE;
  const target=env.EMPIRE_DEVICE_QA_SITE;
  const cdp=env.EMPIRE_DEVICE_QA_CDP;
  if(env.EMPIRE_DEVICE_QA_ACK!=='AUTHORISE_SYNTHETIC_STAGING_READ_ONLY')
    throw new Error('EXPLICIT_OPERATOR_DEVICE_QA_ACK_REQUIRED');
  if(!target || target!==allowed || !/^https:\/\/[a-z0-9.-]+(?:\:\d+)?\/$/.test(target))
    throw new Error('EXACT_HTTPS_NONPRODUCTION_STAGING_URL_REQUIRED');
  const url=new URL(target);
  if(url.hostname==='localhost'||url.hostname==='127.0.0.1'||!url.hostname.includes('.'))
    throw new Error('REMOTE_PHYSICAL_STAGING_ORIGIN_REQUIRED');
  if(!cdp || !/^http:\/\/127\.0\.0\.1:\d{2,5}$/.test(cdp))
    throw new Error('LOOPBACK_CDP_BROWSER_CONNECTION_REQUIRED');
  if(!env.EMPIRE_DEVICE_QA_RECEIPT ||
     !env.EMPIRE_DEVICE_QA_RECEIPT.endsWith('.json'))
    throw new Error('CREATE_ONLY_LOCAL_REPORT_PATH_REQUIRED');
  if(fs.existsSync(env.EMPIRE_DEVICE_QA_RECEIPT))
    throw new Error('REFUSE_TO_OVERWRITE_DEVICE_QA_EVIDENCE');
  return {site:target,cdp,receipt:env.EMPIRE_DEVICE_QA_RECEIPT};
}
function classifyGpu(vendor,renderer,headless,webdriver) {
  const combined=(vendor+' '+renderer).toLowerCase();
  if(headless||webdriver) return {hardware_backend_observed:false,reason:'HEADLESS_OR_WEBDRIVER'};
  if(!vendor||!renderer) return {hardware_backend_observed:false,reason:'UNDISCLOSED_GL_RENDERER'};
  if(/swiftshader|llvmpipe|softpipe|lavapipe|software|microsoft basic render|mesa offscreen|virtualbox|vmware/.test(combined))
    return {hardware_backend_observed:false,reason:'SOFTWARE_OR_VIRTUAL_RENDERER'};
  return {hardware_backend_observed:true,reason:'NATIVE_GPU_RENDERER_REPORTED_NOT_INDEPENDENTLY_ATTESTED'};
}
const sha=x=>crypto.createHash('sha256').update(x).digest('hex');
async function probe(env) {
  const scope=assertScope(env);
  // Puppeteer-core is deliberately a *test-only* local requirement, never
  // installed into or bundled with the WordPress child theme.
  const puppeteer=require(env.EMPIRE_DEVICE_QA_PUPPETEER_MODULE||'puppeteer-core');
  const browser=await puppeteer.connect({browserURL:scope.cdp,defaultViewport:null});
  let page;
  try {
    page=await browser.newPage();
    const origin=new URL(scope.site).origin;
    let externalRequests=0;
    await page.setRequestInterception(true);
    page.on('request',req=>{
      try {
        const url=new URL(req.url());
        if(url.origin===origin || ['blob:','data:'].includes(url.protocol))
          req.continue();
        else {externalRequests++;req.abort('blockedbyclient');}
      } catch {externalRequests++;req.abort('blockedbyclient');}
    });
    const errors=[];
    page.on('pageerror',e=>errors.push(String(e).slice(0,180)));
    const cdp=await page.createCDPSession();
    await cdp.send('Performance.enable');
    const started=new Date().toISOString();
    await page.goto(scope.site,{waitUntil:'domcontentloaded',timeout:45000});
    await page.waitForSelector('[data-react-showroom="true"]',{timeout:30000});
    const disclosure=await page.evaluate(()=>({
      banner:document.body.innerText.includes('FICTIONAL DESIGN PREVIEW') ||
        document.body.innerText.includes('Fictional dealership demonstration'),
      user_agent:navigator.userAgent.slice(0,200),
      webdriver:navigator.webdriver===true,
      device_memory_gb:navigator.deviceMemory??null,
      save_data:navigator.connection?.saveData??null,
      viewport:{width:innerWidth,height:innerHeight,devicePixelRatio},
      timezone:Intl.DateTimeFormat().resolvedOptions().timeZone,
      model_before_click:performance.getEntriesByType('resource').some(r=>
        r.name.endsWith('car-concept-studio-meshopt.glb'))
    }));
    if(!disclosure.banner) throw new Error('SYNTHETIC_STAGE_DISCLOSURE_MISSING');
    if(disclosure.model_before_click) throw new Error('GLB_WAS_PRELOADED_WITHOUT_OPT_IN');
    if(disclosure.webdriver||/HeadlessChrome/i.test(disclosure.user_agent))
      throw new Error('HEADLESS_OR_EMULATED_BROWSER_NOT_ACCEPTED');
    await page.waitForSelector('[data-launch-3d="true"],[data-showroom-active="true"] canvas',
      {timeout:22000});
    if(await page.$('[data-launch-3d="true"]'))
      await page.click('[data-launch-3d="true"]');
    await page.waitForSelector('[data-showroom-active="true"] canvas',{timeout:45000});
    const gpu=await page.evaluate(()=>{
      const canvas=document.querySelector('[data-showroom-active="true"] canvas');
      const gl=canvas.getContext('webgl2')||canvas.getContext('webgl');
      if(!gl)return {vendor:'',renderer:'',webgl_version:null};
      const debug=gl.getExtension('WEBGL_debug_renderer_info');
      return {
        vendor:debug?String(gl.getParameter(debug.UNMASKED_VENDOR_WEBGL)):'',
        renderer:debug?String(gl.getParameter(debug.UNMASKED_RENDERER_WEBGL)):'',
        webgl_version:String(gl.getParameter(gl.VERSION)),
        gpu_timer_available:!!gl.getExtension('EXT_disjoint_timer_query_webgl2')
      };
    });
    const decision=classifyGpu(gpu.vendor,gpu.renderer,false,disclosure.webdriver);
    if(!decision.hardware_backend_observed)
      throw new Error('NO_REAL_HARDWARE_RENDERER_EVIDENCE: '+decision.reason);
    const before=(await cdp.send('Performance.getMetrics')).metrics;
    await page.click('[data-model-mode="studio"]');
    if(await page.$('[data-device-caution="true"]')){
      await page.click('[data-model-mode="studio"]');
    }
    const began=Date.now();
    await page.waitForFunction(()=>document.querySelector('[data-studio-model-ready]')?.dataset.studioModelReady==='true',
      {timeout:90000});
    const readyAfterMs=Date.now()-began;
    for(const value of ['front','side','three-quarter']){
      await page.click('[data-camera-view="'+value+'"]');
      await page.waitForFunction(v=>
        document.querySelector('[data-camera-view="'+v+'"]')?.getAttribute('aria-pressed')==='true',
        {},value);
    }
    for(const color of ['silver','ocean','champagne']){
      await page.click('[data-paint-finish="'+color+'"]');
      await page.waitForFunction(v=>
        document.querySelector('[data-paint-finish="'+v+'"]')?.getAttribute('aria-pressed')==='true',
        {},color);
    }
    await new Promise(resolve=>setTimeout(resolve,400));
    const after=(await cdp.send('Performance.getMetrics')).metrics;
    const network=await page.evaluate(()=>{
      const glb=performance.getEntriesByType('resource').find(r=>
        r.name.endsWith('car-concept-studio-meshopt.glb'));
      return glb?{
        encoded_bytes:glb.encodedBodySize,
        transfer_bytes:glb.transferSize,
        duration_ms:Math.round(glb.duration),
        same_origin:glb.name.startsWith(location.origin+'/')
      }:null;
    });
    if(!network?.same_origin||network.encoded_bytes<2_500_000||network.encoded_bytes>3_500_000)
      throw new Error('STUDIO_MESHOPT_NETWORK_PROOF_FAILED');
    const timing=(arr,key)=>arr.find(item=>item.name===key)?.value??null;
    const report={
      schema:'empire.agency.physical_chrome_browser_probe.v9',
      observed_at:started,
      stage:scope.site,
      cdp_transport:'loopback_forward_only',
      release_status:'HOLD_OWNER_IP_AND_MULTI_DEVICE_QA',
      operator_reported_device_class:env.EMPIRE_DEVICE_QA_DEVICE_CLASS||'unspecified',
      physically_verified_device:false,
      hardware_backend_observed:decision.hardware_backend_observed,
      hardware_evidence_reason:decision.reason,
      gpu,
      browser:disclosure,
      model_load_ready_ms:readyAfterMs,
      model_network:network,
      browser_main_thread_metrics:{
        task_duration_delta_sec:timing(after,'TaskDuration')-timing(before,'TaskDuration'),
        js_heap_after_bytes:timing(after,'JSHeapUsedSize'),
        layout_count_delta:timing(after,'LayoutCount')-timing(before,'LayoutCount'),
      },
      gpu_frame_time_ms:null,
      gpu_fps:null,
      gpu_performance_claim:'UNMEASURED_PHYSICAL_GPU_COMPLETION_TIMES',
      browser_callback_fps:null,
      tests:{six_camera_and_paint_controls:true,model_loaded_only_after_click:true,
        external_requests_blocked:externalRequests===0,script_errors:errors.length===0},
      external_request_count:externalRequests,
      page_errors:errors,
      customer_data:false,server_writes:false,production_changes:false,
      owner_review_required:true,
    };
    if(externalRequests || errors.length)throw new Error('EXTERNAL_RESOURCE_OR_BROWSER_ERROR');
    const json=JSON.stringify(report,null,2)+'\n';
    fs.writeFileSync(scope.receipt,json,{flag:'wx',mode:0o600});
    return {status:'REAL_BROWSER_EVIDENCE_REVIEW_PENDING',sha256:sha(json),receipt:scope.receipt};
  } finally {
    if(page)await page.close().catch(()=>{});
    await browser.disconnect();
  }
}
module.exports={assertScope,classifyGpu,probe};
if(require.main===module){
  probe(process.env).then(x=>{process.stdout.write(JSON.stringify(x)+'\n')})
    .catch(err=>{process.stderr.write('PHYSICAL_BROWSER_QA_HELD: '+err.message+'\n');process.exitCode=2});
}
