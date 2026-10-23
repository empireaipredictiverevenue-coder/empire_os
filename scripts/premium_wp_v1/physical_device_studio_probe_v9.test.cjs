'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {assertScope,classifyGpu}=require('./physical_device_studio_probe_v9.cjs');

function stage(){
  return {
    EMPIRE_DEVICE_QA_ACK:'AUTHORISE_SYNTHETIC_STAGING_READ_ONLY',
    EMPIRE_DEVICE_QA_SITE:'https://private-preview.example.test/',
    EMPIRE_DEVICE_QA_ALLOWED_SITE:'https://private-preview.example.test/',
    EMPIRE_DEVICE_QA_CDP:'http://127.0.0.1:9222',
    EMPIRE_DEVICE_QA_RECEIPT:'/tmp/empire-agency-v9-physical-pending-qa.json'
  }
}
test('device QA is explicitly scoped to authorised synthetic staging',()=>{
  const out=assertScope(stage());
  assert.equal(out.site,stage().EMPIRE_DEVICE_QA_SITE);
  assert.equal(out.cdp,'http://127.0.0.1:9222');
});
test('missing operator acknowledgement, mismatched host, insecure target are refused',()=>{
  for(const delta of [
    {EMPIRE_DEVICE_QA_ACK:''},
    {EMPIRE_DEVICE_QA_ALLOWED_SITE:'https://other.invalid/'},
    {EMPIRE_DEVICE_QA_SITE:'http://private-preview.example.test/',
     EMPIRE_DEVICE_QA_ALLOWED_SITE:'http://private-preview.example.test/'},
    {EMPIRE_DEVICE_QA_CDP:'http://remote.example.test:9222'},
    {EMPIRE_DEVICE_QA_CDP:'https://127.0.0.1:9222'},
    {EMPIRE_DEVICE_QA_RECEIPT:'/tmp/no-extension'},
    {EMPIRE_DEVICE_QA_SITE:'https://127.0.0.1/',
     EMPIRE_DEVICE_QA_ALLOWED_SITE:'https://127.0.0.1/'},
  ]) {
    assert.throws(()=>assertScope({...stage(),...delta}));
  }
});
test('SwiftShader, software or headless renders are not real physical GPU evidence',()=>{
  for(const renderer of [
    'Google SwiftShader',
    'llvmpipe (LLVM 18)',
    'Microsoft Basic Render Driver',
    'Mesa software rasterizer',
    'VMware SVGA3D',
  ]){
    assert.equal(classifyGpu('vendor',renderer,false,false).hardware_backend_observed,false);
  }
  assert.equal(classifyGpu('ARM','Mali-G78',true,false).hardware_backend_observed,false);
  assert.equal(classifyGpu('ARM','Mali-G78',false,true).hardware_backend_observed,false);
  assert.equal(classifyGpu('','',false,false).hardware_backend_observed,false);
});
test('hardware renderer name is provisional only, not independent device certification',()=>{
  const out=classifyGpu('Qualcomm','Adreno (TM) 740',false,false);
  assert.equal(out.hardware_backend_observed,true);
  assert.match(out.reason,/NOT_INDEPENDENTLY_ATTESTED/);
});
