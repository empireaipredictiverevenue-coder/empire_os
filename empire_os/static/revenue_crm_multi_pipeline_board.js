'use strict';
/* EmpireOS Smart CRM: authenticated, read-only multi-motion pipeline board. */
(() => {
 const root='/v1/revenue-crm/pipelines/board';
 const $=id=>document.getElementById(id);
 const state={data:null,pipeline:'',search:'',industry:'',sort:'stalled',busy:false};
 const el=(tag,cls,txt)=>{
  const node=document.createElement(tag);
  if(cls)node.className=cls;
  if(txt!==undefined && txt!==null)node.textContent=String(txt);
  return node;
 };
 const status=(message,error=false)=>{
  $('status').textContent=message;
  $('status').classList.toggle('error',!!error);
 };
 function option(value,label){
  const node=el('option','',label);
  node.value=value;
  return node;
 }
 function setMetrics(board){
  $('metric-lanes').textContent=String(board.pipelines.filter(x=>x.id!=='unclassified').length);
  $('metric-records').textContent=String(board.total_cards);
  $('metric-unassigned').textContent=String(board.unassigned_prospects);
  $('metric-buyers').textContent=String(board.buyer_account_cards);
 }
 function selectedDefinition(){
  return state.data?.pipelines.find(x=>x.id===state.pipeline);
 }
 function filteredCards(){
  if(!state.data)return[];
  const needle=state.search.trim().toLowerCase();
  const cards=state.data.cards.filter(x=>
   x.pipeline_id===state.pipeline &&
   (!needle||x.title.toLowerCase().includes(needle)) &&
   (!state.industry||x.industry===state.industry));
  cards.sort((a,b)=>{
   if(state.sort==='stalled'&&a.stalled_review!==b.stalled_review){
    return a.stalled_review?-1:1;
   }
   return a.title.localeCompare(b.title);
  });
  return cards;
 }
 function renderDetail(card){
  const modal=$('detail');const d=$('detail-data');d.replaceChildren();
  $('detail-title').textContent=card.title;
  const fields=[
   ['Pipeline',selectedDefinition()?.name||card.pipeline_id],
   ['Stage',String(card.stage).replaceAll('_',' ')],
   ['Canonical record type',card.source_kind],
   ['Industry',card.industry||'Not verified'],
   ['Metro',card.metro||'Not supplied'],
   ['Country',card.market||'Not verified'],
   ['Lead / call outcome',card.outcome_format||'Not verified'],
   ['Source status',card.source_status||'Not supplied'],
   ['Evidence stage',card.evidence_stage],
   ['Next activity',card.next_activity],
   ['Due date',card.next_activity_due_at||'No verified scheduled activity'],
   ['Last verified status date',card.last_observed_at||'Unknown'],
   ['Pipeline source binding',card.pipeline_binding_verified?'Recorded / trusted':'Not recorded'],
   ['Won deal',card.won_verified?'Verified':'Not verified'],
   ['Revenue recognised',card.recognized_revenue_cents===null?'Not available from source':'See canonical source'],
   ['Outreach permission',card.outbound_authorized?'Requires owner check':'Not authorised'],
  ];
  fields.forEach(([label,value])=>{
   const dt=el('dt','',label);const dd=el('dd','',value);
   d.append(dt,dd);
  });
  modal.hidden=false;$('close').focus();
 }
 function addCard(card,where){
  const node=el('button','deal');
  node.type='button';node.setAttribute('aria-label','View evidence for '+card.title);
  node.append(el('span','deal-head',card.title));
  node.append(el('span','deal-meta',
    [card.industry||'Industry unverified',card.metro].filter(Boolean).join(' · ')));
  const label=card.stalled_review?'Review inactivity':'Evidence only';
  node.append(el('span','mini-chip'+(card.stalled_review?' alert':''),label));
  node.append(el('span','deal-next',card.next_activity));
  node.addEventListener('click',()=>renderDetail(card));
  where.append(node);
 }
 function render(){
  const data=state.data;
  const definition=selectedDefinition();
  if(!data||!definition)return;
  const cards=filteredCards();
  const b=$('board');b.replaceChildren();
  const overview=$('overview');overview.replaceChildren();
  const tag=el('div','pill');
  tag.append(el('b','',definition.name));
  overview.append(tag,el('div','pill',definition.motion.replaceAll('_',' ')));
  overview.append(el('div','pill',cards.length+' visible records'));
  if(definition.product_examples?.length){
   overview.append(el('div','pill','Examples: '+definition.product_examples.slice(0,4).join(', ')));
  }
  definition.stages.forEach(stage=>{
   const col=el('section','column');
   col.setAttribute('aria-label',stage.label);
   const head=el('div','column-head');
   head.append(el('span','',stage.label));
   const members=cards.filter(x=>x.stage===stage.id);
   head.append(el('span','count',members.length));
   col.append(head);
   const body=el('div','cards');
   if(!members.length){
    body.append(el('div','empty','No verified records at this stage.'));
   }else members.forEach(x=>addCard(x,body));
   col.append(body);b.append(col);
  });
  status('Read-only canonical view · '+cards.length+' records in '+definition.name+
   ' · No stage changes or emails sent.');
 }
 function configureFilters(data){
  const pipeline=$('pipeline');pipeline.replaceChildren();
  data.pipelines.forEach(p=>pipeline.append(option(p.id,p.name+' ('+p.record_count+')')));
  if(!data.pipelines.some(p=>p.id===state.pipeline)){
   const first=data.pipelines.find(p=>p.record_count>0);
   state.pipeline=first?.id||'service_customers';
  }
  pipeline.value=state.pipeline;
  const values=[...new Set(data.cards.map(c=>c.industry).filter(Boolean))].sort();
  const industry=$('industry');industry.replaceChildren();industry.append(option('','All industries'));
  values.forEach(s=>industry.append(option(s,s)));
  if(!values.includes(state.industry))state.industry='';
  industry.value=state.industry;
  for(const id of ['pipeline','search','industry','sort','refresh'])$(id).disabled=false;
 }
 async function load(){
  if(state.busy)return;
  state.busy=true;$('refresh').disabled=true;
  status('Refreshing authenticated CRM evidence…');
  try{
   const r=await fetch(root+'?limit=500',{cache:'no-store',credentials:'same-origin',
     headers:{'Accept':'application/json'}});
   if(!r.ok)throw Error(r.status===401?'Authenticated CRM sign-in required':
     'CRM source unavailable (HTTP '+r.status+')');
   const board=await r.json();
   if(board.schema_version!=='empire.revenue_crm.multi_pipeline_board.v1'||
      board.read_only!==true||board.execution_authority!=='none'||
      !Array.isArray(board.cards)||!Array.isArray(board.pipelines)||
      board.authenticated_tenant_scope!==true)throw Error('Invalid CRM evidence contract');
   state.data=board;
   setMetrics(board);configureFilters(board);render();
  }catch(e){
   state.data=null;$('board').replaceChildren();$('overview').replaceChildren();
   status('Held: '+String(e.message||'Unable to verify authenticated CRM'),true);
  }finally{state.busy=false;$('refresh').disabled=false}
 }
 $('pipeline').addEventListener('change',e=>{state.pipeline=e.target.value;render()});
 $('search').addEventListener('input',e=>{state.search=e.target.value;render()});
 $('industry').addEventListener('change',e=>{state.industry=e.target.value;render()});
 $('sort').addEventListener('change',e=>{state.sort=e.target.value;render()});
 $('refresh').addEventListener('click',load);
 $('close').addEventListener('click',()=>{$('detail').hidden=true;$('pipeline').focus()});
 $('detail').addEventListener('click',e=>{if(e.target===$('detail'))$('detail').hidden=true});
 document.addEventListener('keydown',e=>{if(e.key==='Escape')$('detail').hidden=true});
 load();
})();