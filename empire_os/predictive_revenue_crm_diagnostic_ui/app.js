'use strict';
(() => {
 const $=id=>document.getElementById(id);
 let bearer=null,expiresAt=0,generation=0,timer=null;
 const summary=$('summary');
 function clear(message,error=false){
  generation++;bearer=null;expiresAt=0;
  if(timer!==null){clearTimeout(timer);timer=null}
  $('password').value='';$('logout').disabled=true;$('signin').disabled=false;
  $('history-preview-button').disabled=true;$('history-file').value='';
  summary.hidden=true;$('metrics').replaceChildren();$('priorities').replaceChildren();$('flags').replaceChildren();
  $('history-result').hidden=true;$('history-result').replaceChildren();
  $('history-status').textContent='Sign in before uploading a file. Nothing is uploaded before you submit.';
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
   $('history-preview-button').disabled=false;
   $('auth-status').textContent='Signed in. Token held in memory only.';
   timer=setTimeout(()=>{if(active===generation)clear('CRM token expired. Sign in again.')},result.expires_in*1000);
   await refresh(active);
  }catch(_){clear('Existing CRM sign-in or diagnostic unavailable.',true)}
  finally{$('signin').disabled=false}
 });
 $('history-upload').addEventListener('submit',async event=>{
  event.preventDefault();
  const file=$('history-file').files?.[0];
  if(!bearer||Date.now()>=expiresAt){clear('CRM session expired. Sign in again.');return}
  if(!file||file.size<1||file.size>32768){$('history-status').textContent='Choose a CSV file no larger than 32 KB.';return}
  const token=bearer,active=generation;
  $('history-preview-button').disabled=true;$('history-result').hidden=true;
  $('history-status').textContent='Validating the private 30-day history preview…';
  try{
   const csv=await file.text();
   if(active!==generation||token!==bearer)throw Error('CRM session changed');
   const horizon=$('horizon').value;
   const response=await fetch('/v1/revenue-crm/predictive-diagnostic/customer-history/forecast-preview?horizon_days='+encodeURIComponent(horizon),{
    method:'POST',cache:'no-store',credentials:'omit',redirect:'error',
    headers:{'Accept':'application/json','Content-Type':'text/csv','Authorization':'Bearer '+token},body:csv
   });
   if(active!==generation||token!==bearer||Date.now()>=expiresAt){clear('CRM session expired or changed. Sign in again.');return}
   if(response.status===401){clear('CRM authentication ended. Sign in again.');return}
   if(!response.ok){
    const issue=await response.json().catch(()=>({}));
    const safe=new Set(['history_csv_schema_or_row_count_invalid','history_csv_row_invalid_or_incomplete','history_currency_mixed_or_missing','history_upload_size_invalid','history_csv_invalid','forecast_horizon_invalid']);
    $('history-status').textContent=safe.has(issue.detail)?'CSV rejected: '+issue.detail.replaceAll('_',' '):'History preview unavailable. Check the CSV format and CRM session.';
    return;
   }
   const result=await response.json();
   if(result?.schema_version!=='empire.predictive_revenue.customer_history_preview.v1'||
      result?.status!=='CUSTOMER_PROVIDED_HISTORY_PREVIEW_UNVERIFIED'||
      result?.history_days_required!==30||result?.history_days_observed!==30||
      result?.tenant_bound_request_authenticated!==true||result?.original_source_system_authenticated!==false||
      result?.upload_persisted!==false||result?.forecast_registered!==false||
      result?.calibration_authorized!==false)throw Error('History preview contract unavailable');
   $('history-status').textContent='Preview only · customer-provided source not independently verified · file not saved or registered.';
   const value=document.createElement('div');value.className='metric';
   const amount=document.createElement('b');amount.textContent=result.forecast_available&&Number.isSafeInteger(result.predicted_revenue_minor_units)?String(result.predicted_revenue_minor_units):'Unavailable';
   const label=document.createElement('span');label.textContent='Forecast revenue ('+String(result.currency_code)+' minor units) at '+String(result.forecast_horizon_days)+' days';
   value.append(amount,label);
   const details=document.createElement('div');details.className='metric';
   const sample=document.createElement('b');sample.textContent=String(result.model_sample_count);
   const sampleLabel=document.createElement('span');sampleLabel.textContent='Daily observations, '+String(result.observed_from_utc)+' to '+String(result.observed_through_utc);
   details.append(sample,sampleLabel);
   $('history-result').replaceChildren(value,details);$('history-result').hidden=false;
  }catch(_){
   if(active===generation)$('history-status').textContent='History preview unavailable. No file was saved.';
  }finally{
   $('history-file').value='';
   if(active===generation&&bearer)$('history-preview-button').disabled=false;
  }
 });
 $('logout').addEventListener('click',()=>clear('Signed out. No CRM diagnostic loaded.'));
 document.addEventListener('visibilitychange',()=>{
  if(document.visibilityState==='hidden'&&bearer&&Date.now()>=expiresAt)clear('CRM session expired. Sign in again.');
 });
})();
