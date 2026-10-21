"use client";
import Link from "next/link";
import {useEffect,useRef,useState} from "react";
import {Activity,AlertTriangle,ArrowLeft,Bell,Clock3,CloudLightning,Eye,EyeOff,LockKeyhole,RefreshCw,ShieldCheck,ShieldAlert} from "lucide-react";
const refreshMs=60000;
function count(x){return Number.isFinite(x)?x.toLocaleString("en-GB"):"Not verified";}
function money(cents){return Number.isFinite(cents)?"$ / £ / USDT not interchangeable — accounting minor units: "+cents.toLocaleString("en-GB"):"Not verified";}
export default function FounderPulse(){
 const [access,setAccess]=useState("");
 const [locked,setLocked]=useState(true);
 const [show,setShow]=useState(false);
 const [data,setData]=useState(null);
 const [storm,setStorm]=useState(null);
 const [stormError,setStormError]=useState("");
 const [state,setState]=useState("LOCKED");
 const [error,setError]=useState("");
 const [desktopAlerts,setDesktopAlerts]=useState(false);
 const seenAlerts=useRef(null);
 const desktopAlertsRef=useRef(false);
 const bearer=useRef(null);
 async function load(secret){
  if(!secret){setState("LOCKED");return;}
  setState("CHECKING");setError("");
  try{
   const r=await fetch("/api/founder/revenue-pulse",{headers:{Authorization:"Bearer "+secret},cache:"no-store"});
   const j=await r.json();
   if(!r.ok){
    if(r.status===401){bearer.current=null;setLocked(true);setData(null);setAccess("");}
    throw new Error(r.status===401?"Invalid founder access key.":j.status||"Private revenue feed unavailable.");
   }
   const keys=new Set((j.alerts||[]).map(a=>a.stage+"|"+a.message));
   if(seenAlerts.current!==null && desktopAlertsRef.current && "Notification" in window && Notification.permission==="granted"){
     for(const a of (j.alerts||[]).filter(a=>!seenAlerts.current.has(a.stage+"|"+a.message)).slice(0,2)){
       try{new Notification("National Storm Hub · Revenue Pulse",{body:"New internal conversion alert: "+a.stage.replaceAll("_"," ")});}catch{}
     }
   }
   seenAlerts.current=keys;
   bearer.current=secret;setAccess("");setLocked(false);setData(j);setState(j.status);
   try{
     const stormResponse=await fetch("/api/founder/storm-intelligence",{
       headers:{Authorization:"Bearer "+secret},cache:"no-store"
     });
     const stormBody=await stormResponse.json();
     if(!stormResponse.ok)throw new Error(stormBody.reason||stormBody.status||"Source not available");
     setStorm(stormBody);setStormError("");
   }catch(e){setStorm(null);setStormError(e.message||"Storm intelligence unavailable");}
  }catch(e){setState("ERROR");setError(e.message||"Unable to read protected pulse.");}
 }
 useEffect(()=>{
  const timer=setInterval(()=>{if(bearer.current&&document.visibilityState==="visible")load(bearer.current);},refreshMs);
  return()=>clearInterval(timer);
 },[]);
 async function toggleAlerts(){
  if(desktopAlerts){desktopAlertsRef.current=false;setDesktopAlerts(false);return;}
  if(!("Notification" in window)){setError("This browser does not support desktop notifications.");return;}
  try{
   const permission=await Notification.requestPermission();
   if(permission!=="granted"){setError("Browser notification permission was not granted.");return;}
   desktopAlertsRef.current=true;setDesktopAlerts(true);setError("");
  }catch{setError("Browser notification permission could not be enabled.");}
 }
 function lock(){bearer.current=null;seenAlerts.current=null;desktopAlertsRef.current=false;setDesktopAlerts(false);setAccess("");setData(null);setStorm(null);setStormError("");setLocked(true);setState("LOCKED");}
 return <div className="nsh">
   <div className="top-alert"><LockKeyhole size={13}/> FOUNDER ACCESS / PROTECTED REVENUE INTELLIGENCE / NO PUBLIC ACCOUNT DATA</div>
   <header className="site-header"><Link href="/" className="brand"><span className="site-mark"><CloudLightning size={23}/></span><span>NATIONAL<span className="brand-highlight">STORM</span>HUB<span className="brand-period">.</span></span></Link><Link href="/alerts" className="header-action">Public Alerts Centre</Link></header>
   <main><section className="wrap deep-hero founder-pulse-hero"><Link href="/" className="state-back"><ArrowLeft size={14}/> National Storm Hub</Link><div className="eyebrow"><span className="eyebrow-line"/> PRIVATE / REVENUE PULSE</div><h1>Revenue Pulse<span className="punctuation">.</span><br/><em>Proof over projections.</em></h1><p>Internal business alert intelligence based on the existing EmpireOS canonical read model. The wider company's results are kept distinct from National Storm Hub's unconnected tenant ledger.</p></section>
   <section className="wrap founder-pulse-content">
    {locked?<div className="founder-login"><LockKeyhole size={30}/><h2>Founder access required</h2><p>Enter the server-provisioned access key. Your key is used only for this session, held in memory and never stored in browser local storage or URL parameters.</p><form onSubmit={e=>{e.preventDefault();if(access.length>=48)load(access);else setError("Enter the full founder access key.");}}><label htmlFor="pulse-secret">Founder access key</label><div className="founder-secret-input"><input id="pulse-secret" type={show?"text":"password"} autoComplete="off" spellCheck={false} value={access} onChange={e=>setAccess(e.target.value)} placeholder="Your private access key"/><button type="button" aria-label={show?"Hide key":"Show key"} onClick={()=>setShow(!show)}>{show?<EyeOff size={18}/>:<Eye size={18}/>}</button></div><button type="submit" disabled={state==="CHECKING"} className="founder-submit">{state==="CHECKING"?"Checking...":"Unlock Revenue Pulse"} <LockKeyhole size={15}/></button></form>{error&&<p className="form-error" role="alert">{error}</p>}</div>:
      <div className="founder-unlocked">
       <div className="founder-session"><span className="source-mark"><ShieldCheck size={13}/> PRIVATE VERIFIED ACCESS</span><div><button onClick={toggleAlerts}><Bell size={15}/> {desktopAlerts?"Pause pop-ups":"Enable alert pop-ups"}</button><button onClick={()=>load(bearer.current)} disabled={state==="CHECKING"}><RefreshCw size={15}/> Refresh</button><button onClick={lock}><LockKeyhole size={15}/> Lock</button></div></div>
       <p className="founder-alert-notice">New conversion-gap pop-ups require your permission and this page to remain open; the source feed refreshes once per minute. They do not send customer messages or replace company monitoring.</p>
       {error&&<p className="form-error">{error}</p>}
       {data?.status==="CURRENT"||data?.status==="STALE"?<>
        <div className="founder-pulse-status"><div><span className="fine-label">EMPIREOS REVENUE PULSE V3 / WHOLE COMPANY</span><h2>{data.status==="CURRENT"?"Current source snapshot":"Snapshot needs refresh"}</h2><p>Generated {new Date(data.generated_at).toLocaleString("en-GB")} · checked against canonical EmpireDB observations</p></div><span className={data.status==="CURRENT"?"source-mark":"source-mark unavailable"}>{data.status}</span></div>
        <div className="founder-pulse-metrics">{Object.entries(data.stages||{}).map(([k,v])=><div key={k}><span>{k.replaceAll("_"," ")}</span><strong>{count(v)}</strong></div>)}</div>
        <div className="founder-pulse-finance"><Activity size={25}/><div><span className="fine-label">RECOGNIZED REVENUE — EMPIRE AI GLOBAL</span><strong>{data.recognized_revenue_cents===null?"Not verified":data.recognized_revenue_cents.toLocaleString("en-GB")+" canonical minor units"}</strong><p>Company-wide accounting observation. Not National Storm Hub revenue. Do not mix currencies or modeled forecasts into sales.</p></div></div>
        <div className="founder-alert-list"><div className="founder-alert-head"><Bell size={19}/><h3>Business conversion alerts</h3><span className="source-mark">{data.alerts.length} observed gaps</span></div>{data.alerts.length?data.alerts.map((a,i)=><div className="founder-alert" key={a.stage+i}><AlertTriangle size={19}/><div><strong>{a.stage.replaceAll("_"," ")}</strong><p>{a.message}</p></div></div>):<p className="founder-empty">No conversion-gap alerts in this source snapshot. This does not guarantee the sales pipeline is healthy.</p>}</div>
       </>:<div className="founder-data-unavailable"><ShieldAlert size={25}/><h3>Revenue source unavailable</h3><p>{data?.reason||"This canonical feed could not be validated."}</p></div>}
       <section className="founder-storm-intelligence" aria-label="EmpireOS Storm Intelligence bridge">
         <div className="founder-alert-head"><ShieldCheck size={19}/><h3>Storm Intelligence · EmpireOS</h3>
           <span className={storm?.status==="CURRENT"?"source-mark":"source-mark unavailable"}>{storm?.status||"UNAVAILABLE"}</span>
         </div>
         <div className="founder-storm-body">
          <p>Read-only connection to the existing Storm Intelligence runtime. Its internal evidence is separate from National Storm Hub customers and income.</p>
          {storm?.status==="STALE"?<p className="founder-storm-warning">Last source snapshot: {new Date(storm.generated_at).toLocaleString("en-GB")}. This evidence is stale; it cannot represent current storm opportunities.</p>:null}
          {storm?.status==="CURRENT"?<p>Internal events reviewed: <strong>{storm.events_reviewed??"Unverified"}</strong> · Evidence blockers: <strong>{storm.missing_evidence??"Unknown"}</strong> · Source: <strong>{storm.source_health}</strong></p>:null}
          {stormError?<p role="status">Storm source unavailable: {stormError}</p>:null}
          <p><strong>Commercial activation: off.</strong> No verified homeowner damage, buying intent, authorised outreach or payable National Storm Hub leads can be concluded from this source.</p>
         </div>
       </section>
       <div className="founder-pulse-tenant"><LockKeyhole size={23}/><div><strong>National Storm Hub tenant revenue</strong><p>Not yet connected to a verified tenant-scoped ledger. Enquiries, payments and recognised revenue remain <strong>unknown</strong>—not zero and not the EmpireOS company-wide figures above.</p></div></div>
      </div>}
   </section></main><footer className="site-footer"><div className="wrap bottom-footer"><span>National Storm Hub · Founder-only evidence dashboard</span><Link href="/alerts">Public weather alerts</Link></div></footer>
 </div>;
}
