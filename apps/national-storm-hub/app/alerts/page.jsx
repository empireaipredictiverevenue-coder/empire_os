"use client";
import Link from "next/link";
import {useCallback,useEffect,useRef,useState} from "react";
import {AlertTriangle,ArrowLeft,ArrowRight,ArrowUpRight,Bell,BellOff,Bookmark,Check,ChevronDown,Clock3,CloudLightning,ExternalLink,MapPin,Radio,RefreshCw,ShieldCheck,ShieldAlert,Info} from "lucide-react";
import {STATE_NAMES,normalizeZip,normalizeState} from "../../lib/storm-data.js";

const REGION_KEY="nsh.alerts.region.v1";
const READ_KEY="nsh.alerts.acknowledged.v1";
const CHECK_EVERY_MS=300000;
const stateOptions=Object.entries(STATE_NAMES).sort((a,b)=>a[1].localeCompare(b[1]));
function stamp(str){
 if(!str)return "Not provided by source";
 const date=new Date(str);
 return Number.isFinite(date.getTime())?new Intl.DateTimeFormat("en-US",{dateStyle:"medium",timeStyle:"short",timeZoneName:"short"}).format(date):"Source time unavailable";
}
export default function AlertsCentre(){
 const [region,setRegion]=useState({state:"TX"});
 const [zip,setZip]=useState("");
 const [feed,setFeed]=useState({state:"loading"});
 const [notice,setNotice]=useState("");
 const [permission,setPermission]=useState("unsupported");
 const [ack,setAck]=useState([]);
 const [expanded,setExpanded]=useState("");
 const baseline=useRef(null);
 const notifyActive=useRef(false);
 const regionRef=useRef(region);
 const pollRef=useRef(null);

 useEffect(()=>{
  try{
   const saved=JSON.parse(localStorage.getItem(REGION_KEY)||"null");
   if(saved?.zip&&normalizeZip(saved.zip)){setRegion({zip:saved.zip});setZip(saved.zip);}
   else if(saved?.state&&normalizeState(saved.state))setRegion({state:saved.state});
   const prev=JSON.parse(localStorage.getItem(READ_KEY)||"[]");
   if(Array.isArray(prev))setAck(prev.filter(x=>typeof x==="string").slice(-150));
  }catch{}
  setPermission("Notification" in window?Notification.permission:"unsupported");
 },[]);

 const update=useCallback(async(selected,signal)=>{
  setFeed(x=>x.state==="ready"?{...x,refreshing:true}:{state:"loading"});
  try{
   const query=new URLSearchParams(selected.zip?{zip:selected.zip}:{state:selected.state||"TX"});
   const response=await fetch("/api/alerts?"+query,{cache:"no-store",signal});
   const body=await response.json();
   if(!response.ok)throw new Error(body.error||"Official feed unavailable.");
   if(signal?.aborted)return;
   setFeed({state:"ready",data:body,refreshing:false});
   const ids=new Set(body.alerts.map(a=>a.id));
   // On the first check establish a baseline without alarming the visitor about pre-existing alerts.
   if(baseline.current!==null && notifyActive.current && document.visibilityState==="visible"){
    const fresh=body.alerts.filter(a=>!baseline.current.has(a.id)&&["Extreme","Severe"].includes(a.severity)).slice(0,3);
    for(const a of fresh){
     if("Notification" in window&&Notification.permission==="granted"){
      new Notification("National Storm Hub · New official warning",{body:a.event+" — "+(a.area||"See official source"),tag:a.id});
     }
    }
   }
   baseline.current=ids;
  }catch(error){
   if(signal?.aborted)return;
   setFeed({state:"error",message:error?.message||"Feed unavailable."});
  }
 },[]);

 useEffect(()=>{
  regionRef.current=region;
  baseline.current=null;
  const controller=new AbortController();
  update(region,controller.signal);
  const timer=window.setInterval(()=>{
   if(document.visibilityState==="visible")update(regionRef.current,controller.signal);
  },CHECK_EVERY_MS);
  return()=>{controller.abort();clearInterval(timer);};
 },[region,update]);

 function chooseState(code){
  const safe=normalizeState(code);
  if(!safe)return;
  setRegion({state:safe});setZip("");setExpanded("");setNotice("");
  try{localStorage.setItem(REGION_KEY,JSON.stringify({state:safe}));}catch{}
 }
 function chooseZip(e){
  e.preventDefault();const safe=normalizeZip(zip);
  if(!safe){setNotice("Enter a valid five-digit US ZIP code.");return;}
  setRegion({zip:safe});setExpanded("");setNotice("");
  try{localStorage.setItem(REGION_KEY,JSON.stringify({zip:safe}));}catch{}
 }
 function passportArea(){
  try{
   const p=JSON.parse(localStorage.getItem("national-storm-hub-passport-preview-v1")||"null");
   if(p?.savedZip&&normalizeZip(p.savedZip)){
    setRegion({zip:p.savedZip});setZip(p.savedZip);setNotice("Using your saved Storm Passport ZIP.");
   }else if(p?.savedState&&normalizeState(p.savedState)){
    setRegion({state:p.savedState});setZip("");setNotice("Using your saved Storm Passport state.");
   }else setNotice("No saved area found in this browser. Save an area in Storm Atlas first.");
  }catch{setNotice("Saved Passport could not be read in this browser.");}
 }
 async function allowNotifications(){
  if(!("Notification" in window)){setNotice("Desktop notifications are not supported by this browser.");return;}
  try{
   const answer=await Notification.requestPermission();
   setPermission(answer);
   notifyActive.current=answer==="granted";
   if(answer==="granted")setNotice("Browser alerts enabled while this page is open. Existing alerts will not trigger a pop-up.");
   else setNotice("Notifications were not enabled. The on-page alert feed remains available.");
  }catch{setNotice("Browser notifications could not be enabled.");}
 }
 function markRead(id){
  const result=ack.includes(id)?ack.filter(x=>x!==id):[...ack,id].slice(-150);
  setAck(result);
  try{localStorage.setItem(READ_KEY,JSON.stringify(result));}catch{}
 }
 const list=feed.state==="ready"?feed.data.alerts:[];
 const displayedArea=feed.state==="ready"?feed.data.zip?"ZIP "+feed.data.zip+" · "+feed.data.area:feed.data.area:
   region.zip?"ZIP "+region.zip:STATE_NAMES[region.state]||"United States";
 const critical=list.filter(a=>["Severe","Extreme"].includes(a.severity)).length;
 return <div className="nsh alerts-centre">
  <div className="top-alert" role="note"><span className="top-alert-dot"/> PUBLIC ALERTS CENTRE / INDEPENDENT SITE <span className="top-alert-sep">/</span> For immediate danger follow local authorities and <a href="https://www.weather.gov/" target="_blank" rel="noreferrer">NWS</a></div>
  <header className="site-header"><Link href="/" className="brand"><span className="site-mark"><CloudLightning size={22}/></span><span>NATIONAL<span className="brand-highlight">STORM</span>HUB<span className="brand-period">.</span></span></Link><Link className="header-action" href="/predictor">Storm Predictor <ArrowUpRight size={15}/></Link></header>
  <main>
   <section className="wrap deep-hero alerts-hero"><Link href="/" className="state-back"><ArrowLeft size={16}/> National Storm Hub</Link><div className="eyebrow"><span className="eyebrow-line"/> OFFICIAL WEATHER WARNINGS / REAL SOURCES</div>
    <h1>Storm Alerts<span className="punctuation">.</span><br/><em>Stay informed, stay in control.</em></h1>
    <p>Check current National Weather Service alerts by state or ZIP code. Keep an eye on an area from your Storm Passport, and choose optional browser notifications when new severe warnings appear.</p>
    <div className="alerts-warning-banner"><ShieldAlert size={21}/><span>This website is <strong>not an emergency warning system</strong>. Browser notifications work only while this page remains open and are not guaranteed. For life-safety decisions use Wireless Emergency Alerts, NOAA Weather Radio, weather.gov and local officials.</span></div>
   </section>

   <section className="wrap alerts-console">
    <div className="alerts-controls">
     <div><label htmlFor="alerts-state">Browse US state</label><div className="alerts-select"><select id="alerts-state" value={region.state||""} onChange={e=>chooseState(e.target.value)}><option value="" disabled>{region.zip?"Using ZIP code":"Choose state"}</option>{stateOptions.map(([code,name])=><option key={code} value={code}>{name}</option>)}</select><ChevronDown size={16}/></div></div>
     <form onSubmit={chooseZip}><label htmlFor="alerts-zip">Or search a ZIP code</label><div className="alerts-zip-input"><MapPin size={17}/><input id="alerts-zip" inputMode="numeric" autoComplete="postal-code" maxLength={5} placeholder="5-digit ZIP" value={zip} onChange={e=>setZip(e.target.value.replace(/[^0-9]/g,"").slice(0,5))}/><button type="submit">Search <ArrowRight size={15}/></button></div></form>
     <div><label>My saved area</label><button type="button" className="alerts-saved" onClick={passportArea}><Bookmark size={16}/> Use Storm Passport</button></div>
    </div>
    {notice&&<p role="status" className="alerts-notice">{notice}</p>}
    <div className="alerts-statusbar">
      <div><span className="fine-label">SELECTED AREA</span><h2>{displayedArea}</h2>{feed.state==="ready"&&<p><Clock3 size={14}/> Last checked {stamp(feed.data.checked_at)}</p>}</div>
      <div className="alerts-status-right">
       {feed.state==="ready"&&<span className="alert-count">{list.length} <small>current records</small></span>}
       {feed.state==="error"&&<span className="source-mark unavailable">SOURCE UNAVAILABLE</span>}
       <button type="button" disabled={feed.state==="loading"||feed.refreshing} onClick={()=>update(region)}><RefreshCw size={16} className={feed.refreshing?"spinning":""}/> Refresh</button>
      </div>
    </div>
    <div className="alerts-content">
     {feed.state==="loading"&&<div className="message-state"><RefreshCw size={25} className="spinning"/><strong>Checking the official weather feed</strong><span>Requesting the latest available NWS records…</span></div>}
     {feed.state==="error"&&<div className="message-state"><ShieldAlert size={27}/><strong>Weather alert source unavailable</strong><span>{feed.message} This is not an all-clear. Check weather.gov directly.</span><a href="https://www.weather.gov/" target="_blank" rel="noreferrer" className="alert-official-link">Visit NWS <ExternalLink size={14}/></a></div>}
     {feed.state==="ready"&&<>
      <div className="alerts-source-info"><span className="source-mark"><Radio size={12}/> OFFICIAL NWS RECORDS</span><span>Alerts shown are issued messages, not evidence of individual property damage.</span></div>
      {critical>0&&<p className="alerts-severe-summary"><AlertTriangle size={17}/> {critical} record{critical===1?"":"s"} marked Severe or Extreme in the returned NWS feed. Review location and expiry times.</p>}
      {list.length===0?<div className="message-state"><ShieldCheck size={27}/><strong>No active warnings returned in this check</strong><span>This is not an all-clear. Stay subscribed to local official warning channels.</span></div>:<div className="alerts-results">
        {list.map(a=><article key={a.id} className={"alerts-record "+(ack.includes(a.id)?"is-acknowledged":"")}><div className="alert-record-top"><span className={"alert-severity severity-"+a.severity.toLowerCase()}><AlertTriangle size={15}/> {a.severity}</span><span className="fine-label">{a.issuer||"National Weather Service"}</span></div>
         <h3>{a.event}</h3><p className="alerts-record-area"><MapPin size={14}/>{a.area||"Location not specified"}</p>
         <div className="alerts-times"><span>Sent: {stamp(a.sent)}</span><span>Expires: {stamp(a.expires)}</span></div>
         <p>{a.headline}</p>
         {expanded===a.id&&<div className="alerts-detail"><p>{a.description||"Refer to the official NWS source for further details."}</p>{a.instruction&&<p><strong>NWS instructions:</strong> {a.instruction}</p>}</div>}
         <div className="alerts-record-actions"><button type="button" onClick={()=>setExpanded(expanded===a.id?"":a.id)}>{expanded===a.id?"Hide details":"Read details"} <ChevronDown size={14}/></button><button type="button" onClick={()=>markRead(a.id)}>{ack.includes(a.id)?<Check size={15}/>:<Bookmark size={15}/>} {ack.includes(a.id)?"Acknowledged":"Mark reviewed"}</button><a href={a.source} target="_blank" rel="noreferrer">Original NWS alert <ExternalLink size={14}/></a></div>
        </article>)}
       </div>}
     </>}
    </div>
    <div className="alerts-notify-section"><div><Bell size={22}/><div><strong>Optional browser notifications</strong><p>While this page is open, check every five minutes and notify you about newly appearing Severe or Extreme warnings. Not a substitute for official emergency alerts.</p></div></div><button type="button" disabled={permission==="denied"||permission==="unsupported"} onClick={allowNotifications}>{permission==="granted"&&notifyActive.current?"Notifications enabled":permission==="denied"?"Blocked in browser":"Enable browser alerts"} <Bell size={16}/></button></div>
   </section>
   <section className="wrap alerts-next"><div><span className="eyebrow"><span className="eyebrow-line"/> MORE INFORMATION</span><h2>More than an alert.</h2><p>Alerts are one part of understanding changing conditions. Explore official forecasts and preparedness guidance alongside your selected area.</p></div><div><Link href="/predictor">Explore the Storm Predictor <ArrowRight size={16}/></Link><Link href="/recovery">Prepare and recover safely <ArrowRight size={16}/></Link></div></section>
  </main>
  <footer className="site-footer"><div className="wrap bottom-footer"><span>National Storm Hub · Independent weather information</span><Link href="/">Home <ArrowRight size={14}/></Link></div></footer>
 </div>;
}
