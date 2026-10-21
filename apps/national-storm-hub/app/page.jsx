"use client";

import {useEffect,useState} from "react";
import {
  ArrowRight,ArrowUpRight,Bell,BookOpen,Bookmark,BookmarkCheck,Check,CheckCircle2,
  ChevronDown,CloudLightning,Compass,ExternalLink,FileCheck2,Home,Layers,
  LockKeyhole,MapPin,Menu,Radio,RefreshCw,Search,ShieldCheck,ShieldAlert,
  Sparkles,Wind,X,Building2,ChartNoAxesCombined,Clock3,CloudSun,Radar,
  Download,RotateCcw,Info,Globe2,ArrowDownRight
} from "lucide-react";
import {STATE_NAMES,normalizeZip,normalizeState} from "../lib/storm-data.js";
import {summarizeHomeSource} from "../lib/home-source-view.js";
import {formatWeatherTime} from "../lib/weather-time.js";

const STORAGE_KEY="national-storm-hub-passport-preview-v1";
const CHECKLIST=[
  ["communication","Create a household emergency contact plan"],
  ["supplies","Review emergency water, food and essential supplies"],
  ["exterior","Check roof, gutters and drainage safely from the ground"],
  ["documents","Identify where important documents are stored"],
  ["alerts","Know your local official warning and evacuation sources"],
  ["coverage","Review home cover and document maintenance information"],
];
const INITIAL_PASSPORT={savedZip:"",savedState:"",tasks:{},bookmarks:[]};
const STATES=Object.entries(STATE_NAMES).sort((a,b)=>a[1].localeCompare(b[1]));
function formatted(value) {
  return formatWeatherTime(value,"Time unavailable");
}
function IconLabel({icon:Icon,children,className=""}) {
  return <span className={"icon-label "+className}><Icon size={15} strokeWidth={1.8}/>{children}</span>;
}
function ShellCard({children,className=""}) {
  return <div className={"shell-card "+className}>{children}</div>;
}
function SiteMark() {
  return <span className="site-mark" aria-hidden="true"><CloudLightning size={24} strokeWidth={1.8}/></span>;
}
function GlobeVisual() {
  return <div className="globe-scene" aria-label="Decorative spherical weather illustration. Not a live geographic warning map." role="img">
    <div className="globe-orbit orbit-one"/><div className="globe-orbit orbit-two"/>
    <div className="globe-sphere"><div className="sphere-graticule"/><div className="sphere-highlights"/></div>
    <div className="globe-pulse pulse-a"/><div className="globe-pulse pulse-b"/>
    <span className="globe-pin pin-one"/><span className="globe-pin pin-two"/><span className="globe-pin pin-three"/>
    <div className="globe-readout readout-top"><span className="status-line"/> OBSERVATION NETWORK <span>01 / 03</span></div>
    <div className="globe-readout readout-bottom">SOURCE-FIRST INTELLIGENCE <span>USA</span></div>
  </div>;
}
function Status({state}) {
  if(state.kind==="loading")return <span className="status-chip muted"><span className="pulse-dot"/> CHECKING NWS</span>;
  if(state.kind==="error")return <span className="status-chip warning"><ShieldAlert size={13}/> SOURCE UNAVAILABLE</span>;
  return <span className="status-chip"><span className="pulse-dot"/> NWS SOURCE CHECKED</span>;
}

export default function HomePage(){
  const [menuOpen,setMenuOpen]=useState(false);
  const [region,setRegion]=useState("TX");
  const [zipInput,setZipInput]=useState("");
  const [request,setRequest]=useState({state:"TX"});
  const [errorInput,setErrorInput]=useState("");
  const [weather,setWeather]=useState({kind:"loading"});
  const [passport,setPassport]=useState(INITIAL_PASSPORT);
  const [hydrated,setHydrated]=useState(false);
  const [expandAlert,setExpandAlert]=useState(null);
  const [passportMessage,setPassportMessage]=useState("");

  useEffect(()=>{
    try {
      const saved=JSON.parse(window.localStorage.getItem(STORAGE_KEY)||"null");
      if(saved && typeof saved==="object") {
        setPassport({
          savedZip:normalizeZip(saved.savedZip)||"",
          savedState:Object.hasOwn(STATE_NAMES,saved.savedState)?saved.savedState:"",
          tasks:typeof saved.tasks==="object" && saved.tasks?Object.fromEntries(CHECKLIST.map(([id])=>[id,saved.tasks[id]===true])):{},
          bookmarks:Array.isArray(saved.bookmarks)?saved.bookmarks.filter(x=>x&&typeof x.id==="string"&&x.id.startsWith("https://api.weather.gov/alerts/")).slice(0,10):[]
        });
      }
    } catch {/* unreadable client storage should never block public information */}
    setHydrated(true);
  },[]);
  useEffect(()=>{
    if(!hydrated)return;
    try {window.localStorage.setItem(STORAGE_KEY,JSON.stringify(passport));}
    catch {setPassportMessage("Browser storage is unavailable. Your changes may not persist.");}
  },[passport,hydrated]);

  useEffect(()=>{
    const urlState=new URLSearchParams(window.location.search).get("state");
    const safe=normalizeState(urlState);
    if(safe){setRegion(safe);setRequest({state:safe});}
  },[]);

  useEffect(()=>{
    const controller=new AbortController();
    async function load(){
      setWeather({kind:"loading"});
      try {
        const params=new URLSearchParams(request.zip?{zip:request.zip}:{state:request.state});
        const response=await fetch("/api/alerts?"+params.toString(),{signal:controller.signal,cache:"no-store"});
        const data=await response.json();
        if(!response.ok)throw new Error(data.error||"Weather source unavailable.");
        if(!controller.signal.aborted){
          setWeather({kind:"ready",data});
          if(data.state)setRegion(data.state);
        }
      } catch(error){
        if(!controller.signal.aborted)setWeather({kind:"error",message:error.message});
      }
    }
    load();
    return ()=>controller.abort();
  },[request]);

  function browseState(e){
    const state=e.target.value;
    setRegion(state);setZipInput("");setErrorInput("");setRequest({state});
    setExpandAlert(null);
  }
  function browseZip(e){
    e.preventDefault();
    const zip=normalizeZip(zipInput);
    if(!zip){setErrorInput("Please enter a valid five-digit US ZIP code.");return;}
    setErrorInput("");setRequest({zip});setExpandAlert(null);
    document.querySelector("#atlas")?.scrollIntoView({behavior:"smooth",block:"start"});
  }
  function saveArea(){
    if(weather.kind!=="ready")return;
    const data=weather.data;
    setPassport(prev=>({...prev,savedZip:data.zip||"",savedState:data.state}));
    setPassportMessage("Your area is saved in this browser.");
  }
  function toggleTask(id){
    setPassport(prev=>({...prev,tasks:{...prev.tasks,[id]:!prev.tasks[id]}}));
  }
  function toggleBookmark(alert){
    setPassport(prev=>{
      const exists=prev.bookmarks.some(x=>x.id===alert.id);
      return {...prev,bookmarks:exists?prev.bookmarks.filter(x=>x.id!==alert.id):
        [{id:alert.id,title:alert.event,area:alert.area,source:alert.source},...prev.bookmarks].slice(0,10)};
    });
  }
  function exportPassport(){
    const data={schema:"national_storm_hub.passport_browser_preview.v1",exported_at:new Date().toISOString(),passport};
    const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:"application/json"}));
    const link=document.createElement("a");
    link.href=url;link.download="storm-passport-local-export.json";
    document.body.appendChild(link);link.click();link.remove();URL.revokeObjectURL(url);
    setPassportMessage("A copy of your local Passport has been exported.");
  }
  function clearPassport(){
    if(!window.confirm("Clear saved areas, bookmarks and checklist progress from this browser?"))return;
    setPassport({...INITIAL_PASSPORT,tasks:{},bookmarks:[]});
    setPassportMessage("Local Passport information cleared.");
  }

  const alerts=weather.kind==="ready"?weather.data.alerts:[];
  const sourceView=summarizeHomeSource(weather);
  const done=CHECKLIST.filter(([id])=>passport.tasks[id]).length;
  const passportState=passport.savedState?STATE_NAMES[passport.savedState]:null;
  return <div className="nsh">
    <div className="top-alert" role="note"><span className="top-alert-dot"/> INDEPENDENT WEATHER INFORMATION PLATFORM <span className="top-alert-sep">/</span> For emergency warnings, follow <a href="https://www.weather.gov/" target="_blank" rel="noreferrer">weather.gov <ArrowUpRight size={12}/></a></div>
    <header className="site-header">
      <a className="brand" href="#home" aria-label="National Storm Hub home"><SiteMark/><span>NATIONAL<span className="brand-highlight">STORM</span>HUB<span className="brand-period">.</span></span></a>
      <nav id="site-main-navigation" className={menuOpen?"nav-links open":"nav-links"} aria-label="Main navigation">
        <a href="#atlas" onClick={()=>setMenuOpen(false)}>Storm Atlas</a>
        <a href="/predictor" onClick={()=>setMenuOpen(false)}>Storm Predictor</a>
        <a href="/alerts" onClick={()=>setMenuOpen(false)}>Live Alerts</a>
        <a href="#passport" onClick={()=>setMenuOpen(false)}>Storm Passport</a>
        <a href="/recovery" onClick={()=>setMenuOpen(false)}>Prepare & Recover</a>
        <a href="#pro" onClick={()=>setMenuOpen(false)}>For Contractors</a>
      </nav>
      <a className="header-action" href="#passport">My Storm Passport <ArrowUpRight size={16}/></a>
      <button type="button" className="mobile-menu" aria-controls="site-main-navigation" aria-label={menuOpen?"Close menu":"Open menu"} aria-expanded={menuOpen} onClick={()=>setMenuOpen(!menuOpen)}>{menuOpen?<X/>:<Menu/>}</button>
    </header>

    <main id="home">
      <section className="hero wrap" aria-labelledby="hero-title">
        <div className="hero-copy">
          <div className="eyebrow"><span className="eyebrow-line"/> WEATHER INTELLIGENCE, REIMAGINED <span className="eyebrow-index">/ 01</span></div>
          <h1 id="hero-title">When the weather changes, <em>know what matters.</em></h1>
          <p className="hero-lead">One place to explore official storm information, prepare your home and keep the history that matters to you. Built for the moments before, during and after a storm.</p>
          <form className="zip-search" onSubmit={browseZip} aria-label="Explore storm information by ZIP code">
            <MapPin size={20} className="zip-pin" aria-hidden="true"/>
            <label htmlFor="zip-entry" className="sr-only">Five-digit US ZIP code</label>
            <input id="zip-entry" autoComplete="postal-code" inputMode="numeric" maxLength={5} placeholder="Enter your US ZIP code" value={zipInput} onChange={e=>setZipInput(e.target.value.replace(/[^0-9]/g,"").slice(0,5))} aria-invalid={Boolean(errorInput)} aria-describedby={errorInput?"zip-error":"zip-help"}/>
            <button type="submit">Explore my area <ArrowRight size={17}/></button>
          </form>
          {errorInput?<p className="form-error" id="zip-error" role="alert">{errorInput}</p>:<p className="microcopy" id="zip-help"><LockKeyhole size={13}/> No account needed. ZIP lookup uses an external public location service.</p>}
          <div className="hero-trust"><span><ShieldCheck size={16}/> Official sources</span><span><Clock3 size={16}/> Dated evidence</span><span><LockKeyhole size={16}/> Privacy by design</span></div>
          <a href="/alerts" className="hero-alerts-cta"><Bell size={17}/> Check current storm alerts <ArrowRight size={16}/></a>
          <a href="/predictor" className="hero-predictor-cta"><Sparkles size={17}/> Explore Storm Predictor <ArrowRight size={16}/></a>
        </div>
        <div className="hero-art"><GlobeVisual/><div className="floating-weather"><div className="float-icon"><Radar size={21}/></div><div><span>STORM ATLAS</span><strong>Explore the evidence</strong><small>Forecasts ≠ confirmed damage</small></div><ArrowUpRight size={18}/></div><div className="art-note">CONCEPTUAL EARTH VISUAL • NOT AN ALERT BOUNDARY MAP</div></div>
      </section>

      <section className="source-snapshot wrap" aria-labelledby="source-snapshot-title">
        <div className="snapshot-context">
          <span className="snapshot-overline"><span className={"snapshot-indicator "+sourceView.phase}/> LIVE DATA / NWS SOURCE STATUS</span>
          <h2 id="source-snapshot-title">{sourceView.title}</h2>
          <p>{sourceView.detail}</p>
        </div>
        <div className="snapshot-details">
          <div><span>SELECTED AREA</span><strong>{sourceView.area}</strong></div>
          <div><span>LAST SOURCE CHECK</span><strong>{sourceView.checked_at?<time dateTime={sourceView.checked_at}>{formatted(sourceView.checked_at)}</time>:"Not verified"}</strong></div>
        </div>
        <a className="snapshot-action" href="/alerts">View official alerts <ArrowUpRight size={17}/></a>
      </section>

      <section className="trust-ribbon" aria-label="Platform information"><div className="wrap trust-inner"><div>01 <span>SOURCE-GROUNDED WEATHER</span></div><div>02 <span>HOMEOWNER CONTROL</span></div><div>03 <span>REGIONAL KNOWLEDGE</span></div><div>04 <span>NO FALSE DAMAGE CLAIMS</span></div></div></section>

      <section className="state-hubs wrap" aria-label="Explore our founding state hubs"><div><span className="state-hub-eyebrow">FOUNDING REGIONAL EXPERIENCES</span><h2>One network. <em>Locally useful.</em></h2></div><div className="state-hub-cards"><a href="/states/texas"><span>TEXAS / HAIL &amp; WIND</span><strong>Texas Storm Hub</strong><span>Local preparedness &amp; official sources <ArrowUpRight size={15}/></span></a><a href="/states/florida"><span>FLORIDA / HURRICANES</span><strong>Florida Storm Hub</strong><span>Local preparedness &amp; official sources <ArrowUpRight size={15}/></span></a></div></section>

      <section className="predictor-feature wrap" aria-label="Introducing Storm Predictor"><div><span className="eyebrow"><span className="eyebrow-line"/> NEW / STORM INTELLIGENCE</span><h2>Meet the Storm <em>Predictor.</em></h2><p>From our existing EmpireOS storm intelligence work: a public, read-only weather research tool combining official NWS forecasts, active alerts and SPC severe-weather outlooks. No invented storm tracks. No unsupported property-damage claims.</p><a href="/predictor">Explore a ZIP forecast <ArrowRight size={17}/></a></div><div className="predictor-feature-right"><div><Radar size={26}/><span>National Weather Service</span><strong>Local forecasts &amp; alerts</strong></div><div><Layers size={26}/><span>Storm Prediction Center</span><strong>Day 1 categorical outlook</strong></div><div><ShieldCheck size={26}/><span>EmpireOS source review</span><strong>Evidence-only interpretation</strong></div></div></section>

      <section id="atlas" className="section atlas-section wrap" aria-labelledby="atlas-title">
        <div className="section-intro"><div><div className="eyebrow"><span className="eyebrow-line"/> EXPLORE THE CONDITIONS <span className="eyebrow-index">/ 02</span></div><h2 id="atlas-title">Storm Atlas<span className="punctuation">.</span></h2><p>Real NWS alerts, without the guesswork. Search a US ZIP code or browse by state.</p></div><a className="text-link" href="https://www.weather.gov/" target="_blank" rel="noreferrer">Official NWS website <ExternalLink size={15}/></a></div>
        <div className="atlas-grid">
          <div className="atlas-visual">
            <div className="atlas-upper"><IconLabel icon={Radio}>SOURCE MONITOR</IconLabel><span>UNITED STATES / PUBLIC PREVIEW</span></div>
            <div className="atlas-map"><div className="atlas-grid-lines"/><div className="atlas-radar-ring ring-a"/><div className="atlas-radar-ring ring-b"/><div className="atlas-radar-ring ring-c"/><div className="atlas-radar-core"/><div className="atlas-grid-cross"/> <span className="map-label map-label-one">STORM EVIDENCE</span><span className="map-label map-label-two">REGION FILTER: {region}</span><span className="map-coordinate">US / NWS</span></div>
            <div className="atlas-foot"><span><Info size={15}/> Map graphic is illustrative, not official alert geometry.</span><span>DATA: WEATHER.GOV</span></div>
          </div>
          <div className="atlas-panel">
            <div className="panel-heading"><span>OFFICIAL ALERTS</span><Status state={weather}/></div>
            <div className="state-select">
              <label htmlFor="state-picker">Browse state</label>
              <span><select id="state-picker" value={region} onChange={browseState}>{STATES.map(([code,name])=><option key={code} value={code}>{name}</option>)}</select><ChevronDown size={16}/></span>
              {weather.kind==="ready"&&<p>{weather.data.mode==="ZIP_CENTROID"?`Approximate ZIP area: ${weather.data.zip}, ${weather.data.area}`:`Statewide alerts: ${weather.data.area}`}</p>}
            </div>
            <div className="alert-result" aria-live="polite">
              {weather.kind==="loading"&&<div className="message-state"><RefreshCw className="spinning" size={24}/><strong>Checking the NWS feed</strong><span>Fetching current source records…</span></div>}
              {weather.kind==="error"&&<div className="message-state"><ShieldAlert size={28}/><strong>Source unavailable</strong><span>{weather.message}</span><button className="ghost-action" onClick={()=>setRequest({...request})} type="button"><RefreshCw size={15}/> Retry</button></div>}
              {weather.kind==="ready"&&<>
                <p className="checked-at"><Clock3 size={13}/> Checked {formatted(weather.data.checked_at)} · {weather.data.alert_count} current record{weather.data.alert_count===1?"":"s"}</p>
                {alerts.length===0?<div className="message-state"><CloudSun size={28}/><strong>No active alerts returned</strong><span>None were returned for this selected area at the last check. This is not an all-clear; continue using official warning channels.</span></div>:
                  <div className="alerts-list">
                    {alerts.slice(0,8).map((a,i)=><div key={a.id} className="alert-row">
                      <div className="alert-item"><span className={"severity-dot sev-"+a.severity.toLowerCase()}/><div><strong>{a.event}</strong><span>{a.area||"Area not provided"}</span></div><button aria-label={expandAlert===a.id?"Collapse alert":"Expand alert"} aria-expanded={expandAlert===a.id} onClick={()=>setExpandAlert(expandAlert===a.id?null:a.id)} type="button"><ChevronDown size={17}/></button></div>
                      {expandAlert===a.id&&<div className="alert-expanded"><p>{a.headline}</p><p>Severity: {a.severity} · Issued: {formatted(a.sent)} · Expires: {formatted(a.expires)}</p><div><a href={a.source} target="_blank" rel="noreferrer">NWS record <ExternalLink size={13}/></a><button type="button" onClick={()=>toggleBookmark(a)}>{passport.bookmarks.some(x=>x.id===a.id)?<BookmarkCheck size={14}/>:<Bookmark size={14}/>} {passport.bookmarks.some(x=>x.id===a.id)?"Saved":"Save event"}</button></div></div>}
                    </div>)}
                    {alerts.length>8&&<p className="many-alerts">Showing 8 of {alerts.length} records; review the official NWS source for the full list.</p>}
                  </div>}
              </>}
            </div>
            <div className="atlas-panel-foot"><span>Alerts do not confirm property damage.</span><button type="button" onClick={saveArea} disabled={weather.kind!=="ready"}><Bookmark size={14}/> Save area</button></div>
          </div>
        </div>
      </section>

      <section id="passport" className="section passport-section" aria-labelledby="passport-title">
        <div className="wrap passport-grid"><div className="passport-info"><div className="eyebrow"><span className="eyebrow-line"/> YOUR HOME, YOUR RECORD <span className="eyebrow-index">/ 03</span></div><h2 id="passport-title">Meet your <em>Storm Passport.</em></h2><p>Your own home-preparedness space. Start with an area, follow official weather information, save useful records and build better habits between storms.</p><div className="passport-benefits"><div><ShieldCheck size={20}/><span>Choose which areas you follow</span></div><div><FileCheck2 size={20}/><span>Track your preparedness checklist</span></div><div><Bookmark size={20}/><span>Bookmark source-linked weather events</span></div><div><LockKeyhole size={20}/><span>Control what stays in your browser</span></div></div><p className="privacy-note"><Info size={16}/> This first release is a browser-only Passport preview, not a registered account or encrypted cloud document vault. Do not store sensitive information here.</p></div>
          <div className="passport-card">
            <div className="passport-card-top"><span><SiteMark/> STORM PASSPORT</span><span className="preview-tag">LOCAL PREVIEW</span></div>
            <div className="passport-area"><span className="fine-label">MY SAVED AREA</span><h3>{passportState||"No saved area"}</h3><p>{passport.savedZip?"ZIP "+passport.savedZip:"Use Storm Atlas to save an area"} {passportState&&<MapPin size={14}/>}</p></div>
            <div className="passport-progress"><div><span>MY READINESS</span><strong>{done} <small>/ {CHECKLIST.length}</small></strong></div><div className="progress-rail"><span style={{width:(done/CHECKLIST.length*100)+"%"}}/></div></div>
            <fieldset className="task-list"><legend>Preparedness checklist</legend>{CHECKLIST.map(([id,label])=><label key={id} className="task-item"><input type="checkbox" checked={Boolean(passport.tasks[id])} onChange={()=>toggleTask(id)}/><span className="task-check"><Check size={14}/></span><span>{label}</span></label>)}</fieldset>
            <div className="passport-saved"><div><Bookmark size={16}/><strong>{passport.bookmarks.length} saved event{passport.bookmarks.length!==1?"s":""}</strong></div>{passport.bookmarks.length>0&&<div className="saved-links">{passport.bookmarks.map(b=><a key={b.id} href={b.source} target="_blank" rel="noreferrer">{b.title} <ExternalLink size={12}/></a>)}</div>}</div>
            {passportMessage&&<p className="passport-message" role="status">{passportMessage}</p>}
            <div className="passport-actions"><button type="button" onClick={exportPassport}><Download size={14}/> Export</button><button type="button" onClick={clearPassport}><RotateCcw size={14}/> Clear Passport</button><span><LockKeyhole size={13}/> Browser-only</span></div>
          </div>
        </div>
      </section>

      <section className="research-invite wrap"><div><span className="eyebrow"><span className="eyebrow-line"/> FROM DATA TO UNDERSTANDING</span><h2>Research behind <em>every layer.</em></h2><p>Explore our original-source register, data limitations, official severe-weather sources, historical-storm gaps and product research programme.</p></div><a href="/research">Read the research library <ArrowRight size={16}/></a></section>

      <section id="prepare" className="section recovery-section wrap" aria-labelledby="recovery-title">
        <div className="section-intro"><div><div className="eyebrow"><span className="eyebrow-line"/> BEFORE · DURING · AFTER <span className="eyebrow-index">/ 04</span></div><h2 id="recovery-title">A clearer path <em>through the storm.</em></h2><p>Information that helps you decide what to do next, without pressure or invented urgency.</p></div></div>
        <div className="recovery-cards">
          <ShellCard className="recovery-card"><span className="card-index">01 / PREPARE</span><div className="recovery-icon"><Home size={26}/></div><h3>Before it arrives.</h3><p>Review household plans, safe property maintenance, important documents and official warning channels.</p><a href="https://www.ready.gov/" target="_blank" rel="noreferrer">Preparedness guidance <ArrowUpRight size={16}/></a></ShellCard>
          <ShellCard className="recovery-card"><span className="card-index">02 / UNDERSTAND</span><div className="recovery-icon"><Radio size={26}/></div><h3>When conditions change.</h3><p>Follow National Weather Service warnings, source timestamps and local authorities. Always prioritise safety.</p><a href="https://www.weather.gov/" target="_blank" rel="noreferrer">Official weather alerts <ArrowUpRight size={16}/></a></ShellCard>
          <ShellCard className="recovery-card"><span className="card-index">03 / RECOVER</span><div className="recovery-icon"><ShieldCheck size={26}/></div><h3>After the weather clears.</h3><p>Document observations safely, organise next steps and explore trustworthy repair resources when needed.</p><a href="https://www.ready.gov/recovering-disaster" target="_blank" rel="noreferrer">Recovery guidance <ArrowUpRight size={16}/></a></ShellCard>
        </div>
      </section>

      <section id="pro" className="pro-section"><div className="wrap pro-grid"><div><div className="eyebrow"><span className="eyebrow-line"/> INTELLIGENCE FOR LOCAL OPERATORS <span className="eyebrow-index">/ 05</span></div><h2>Built for homeowners. <em>Useful for professionals.</em></h2><p>Storm Hub Pro is our planned contractor intelligence workspace: documented weather signals, territory research, verified coverage and governed customer enquiries.</p><div className="pro-flag"><Info size={17}/> Pro subscriptions and contractor enrolment are not open in this preview.</div></div><div className="pro-module"><div className="module-header"><Building2 size={19}/> STORM HUB PRO <span>CONCEPT</span></div><div className="module-line"><Radar size={18}/><span>Regional weather & market intelligence</span><CheckCircle2 size={16}/></div><div className="module-line"><Compass size={18}/><span>Service territory and capacity controls</span><CheckCircle2 size={16}/></div><div className="module-line"><ShieldCheck size={18}/><span>Credential and compliance review</span><CheckCircle2 size={16}/></div><div className="module-line"><ChartNoAxesCombined size={18}/><span>Verified outcome reporting</span><CheckCircle2 size={16}/></div><p className="module-disclaimer">Planned modules. No active marketplace or paid referrals.</p></div></div></section>

      <section className="final-cta wrap"><span className="eyebrow">STAY PREPARED. STAY INFORMED.</span><h2>Weather will change. <em>How you prepare can too.</em></h2><a href="#atlas">Explore Storm Atlas <ArrowRight size={17}/></a></section>
    </main>
    <footer className="site-footer"><div className="wrap footer-inner"><div><a className="brand footer-brand" href="#home"><SiteMark/><span>NATIONAL<span className="brand-highlight">STORM</span>HUB<span className="brand-period">.</span></span></a><p>Independent weather information and property preparedness. Not an official emergency alert service.</p></div><div className="footer-links"><a href="https://www.weather.gov/" target="_blank" rel="noreferrer">National Weather Service <ExternalLink size={13}/></a><a href="https://www.ready.gov/" target="_blank" rel="noreferrer">Ready.gov <ExternalLink size={13}/></a><a href="#passport">Storm Passport</a><a href="/predictor">Storm Predictor</a><a href="/alerts">Live Storm Alerts</a><a href="/founder/revenue-pulse">Founder Revenue Pulse</a><a href="/research">Research &amp; Sources</a><a href="/recovery">Recovery Guide</a><a href="#pro">Storm Hub Pro</a></div></div><div className="wrap bottom-footer"><span>© {new Date().getFullYear()} National Storm Hub · A planned Empire AI-operated brand.</span><span>Preview release · Source transparency first</span></div></footer>
  </div>;
}
