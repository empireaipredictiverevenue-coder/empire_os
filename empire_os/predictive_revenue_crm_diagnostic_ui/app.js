'use strict';
(() => {
 const $=id=>document.getElementById(id);
 let bearer=null,expiresAt=0,generation=0,timer=null;
 const summary=$('summary');
 function clear(message,error=false){
  generation++;bearer=null;expiresAt=0;
  if(timer!==null){clearTimeout(timer);timer=null}
  $('password').value='';$('logout').disabled=true;$('signin').disabled=false;
  summary.hidden=true;$('metrics').replaceChildren();$('priorities').replaceChildren();$('flags').replaceChildren();
  $('status').textContent=message;$('status').classList.toggle('error',error);
  $('auth-status').textContent='Credentials and the short-lived token stay in memory for this page only.';
 }
 function metric(name,value){
  if(!Number.isSafeInteger(value)||value<0)throw Error('Invalid source metric');
  const node=document.createElement('div');node.className='metric';
  const count=document.createElement('b');count.textContent=String(value);
  const label=document.createElement('span');label.textContent=name;
  node.append(count,label);$('metrics').append(node);
 }
 function flag(text){const n=document.createElement('span');n.className='flag';n.textContent=text;$('flags').append(n)}
 function render(packet){
  const review=packet?.existing_crm_observation_review;
  const counts=review?.bounded_observations;
  if(review?.schema_version!=='empire.predictive_revenue.crm_case_observation.v1'||
     review?.tenant_bound_existing_repository_read!==true||
     review?.source_row_details_exported!==false||
     review?.original_tenant_identifier_exported!==false||
     review?.snapshot_is_full_tenant_census!==false||
     review?.observed_quote_value_is_recognized_revenue!==false||
     review?.authorized_client_report_release!==false||
     !counts||typeof counts!=='object')throw Error('Diagnostic source contract unavailable');
  $('metrics').replaceChildren();$('priorities').replaceChildren();$('flags').replaceChildren();
  flag(String(review.status||'Source status unknown'));
  flag('Bounded snapshot · maximum 500 records');
  flag('Not a full tenant census');
  metric('Records observed',counts.observed_records);
  metric('Missing conversation links',counts.conversation_reference_missing);
  metric('Missing closer links',counts.closer_reference_missing);
  metric('Missing buyer links',counts.buyer_reference_missing);
  metric('Missing fulfilment links',counts.fulfilment_order_reference_missing);
  metric('Positive quoted prices',counts.quoted_price_positive_records);
  metric('Missing deal probabilities',counts.deal_probability_missing_records);
  if(!Array.isArray(review.investigation_priorities))throw Error('Diagnostic priorities unavailable');
  review.investigation_priorities.forEach(item=>{
   const row=document.createElement('section');row.className='priority';
   const title=document.createElement('b');title.textContent=String(item.code||'Review source coverage');
   const detail=document.createElement('p');detail.textContent=
    'Observed gap: '+String(item.observed_missing_count)+' · '+String(item.action||'Review source records');
   row.append(title,detail);$('priorities').append(row);
  });
  summary.hidden=false;
  $('status').textContent=review.status==='CRM_SOURCE_SNAPSHOT_OBSERVED'
   ?'Authenticated CRM snapshot reviewed. Confirm the coverage limits before drawing conclusions.'
   :'Authenticated source hold: '+String(review.status||'unknown coverage');
  $('status').classList.remove('error');
 }
 async function refresh(expectedGeneration){
  if(!bearer||Date.now()>=expiresAt){clear('CRM session expired. Sign in again.');return}
  const token=bearer;
  const response=await fetch('/v1/revenue-crm/predictive-diagnostic?limit=500',{
   cache:'no-store',credentials:'omit',redirect:'error',
   headers:{'Accept':'application/json','Authorization':'Bearer '+token}
  });
  if(expectedGeneration!==generation||token!==bearer||Date.now()>=expiresAt){clear('CRM session changed. Sign in again.');return}
  if(response.status===401){clear('CRM authentication ended. Sign in again.');return}
  if(response.status===409){clear('The enterprise report is held by its source evidence gate.',true);return}
  if(!response.ok)throw Error('Authenticated CRM diagnostic unavailable.');
  const packet=await response.json();
  if(expectedGeneration!==generation||token!==bearer){clear('CRM session changed. Sign in again.');return}
  render(packet);
 }
 $('login').addEventListener('submit',async event=>{
  event.preventDefault();const email=$('email').value.trim(),password=$('password').value,tenant=$('tenant').value;
  $('password').value='';clear('Checking the existing CRM member login…');
  const current=generation;$('signin').disabled=true;
  try{
   const response=await fetch('/v1/revenue-crm/auth/login',{
    method:'POST',cache:'no-store',credentials:'omit',redirect:'error',
    headers:{'Content-Type':'application/json'},body:JSON.stringify({email,password,tenant_id:tenant})
   });
   if(current!==generation)throw Error('Sign-in superseded');
   if(!response.ok)throw Error('CRM sign-in denied');
   const result=await response.json();
   if(result.token_type!=='Bearer'||result.scope!=='crm:read'||typeof result.access_token!=='string'||
      result.access_token.length<100||result.access_token.length>6000||
      !Number.isInteger(result.expires_in)||result.expires_in<1||result.expires_in>900)throw Error('Invalid CRM sign-in response');
   bearer=result.access_token;expiresAt=Date.now()+result.expires_in*1000;
   const active=generation;$('logout').disabled=false;
   $('auth-status').textContent='Signed in. Token held in memory only.';
   timer=setTimeout(()=>{if(active===generation)clear('CRM token expired. Sign in again.')},result.expires_in*1000);
   await refresh(active);
  }catch(_){clear('Existing CRM sign-in or diagnostic unavailable.',true)}
  finally{$('signin').disabled=false}
 });
 $('logout').addEventListener('click',()=>clear('Signed out. No CRM diagnostic loaded.'));
 document.addEventListener('visibilitychange',()=>{
  if(document.visibilityState==='hidden'&&bearer&&Date.now()>=expiresAt)clear('CRM session expired. Sign in again.');
 });
})();
