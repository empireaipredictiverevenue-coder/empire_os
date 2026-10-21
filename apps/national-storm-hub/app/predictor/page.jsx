"use client";
import {useEffect,useState} from "react";
import Link from "next/link";
import {CloudLightning,ArrowLeft,ArrowRight,ExternalLink,ShieldCheck,CloudSun,AlertTriangle,MapPin,Clock3,Wind,Info,Radio,RefreshCw,Layers} from "lucide-react";
import {formatWeatherTime} from "../../lib/weather-time.js";
function pretty(value){
 return formatWeatherTime(value,"Unknown time");
}
function Flag({state}) {return <span className={state==="AVAILABLE"?"source-mark":"source-mark unavailable"}>{state==="AVAILABLE"?"SOURCE RECEIVED":state?.replaceAll("_"," ")||"UNAVAILABLE"}</span>;}
export default function Predictor(){
 const [zip,setZip]=useState("");
 const [view,setView]=useState(null);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 async function go(target){
  if(!/^[0-9]{5}$/.test(target)){setError("Enter a five-digit US ZIP code.");return;}
  setError("");setBusy(true);setView(null);
  try{
    const r=await fetch("/api/predictor?zip="+encodeURIComponent(target),{cache:"no-store"});
    const data=await r.json();
    if(!r.ok&&r.status!==503)throw new Error(data.error||"Unable to look up location.");
    if(!data.area)throw new Error(data.error||"Forecast sources are unavailable.");
    setView(data);
  }catch(e){setError(e.message||"Information could not be loaded.");}
  finally{setBusy(false);}
 }
 useEffect(()=>{
   const z=new URLSearchParams(window.location.search).get("zip");
   if(z&&/^[0-9]{5}$/.test(z)){setZip(z);go(z);}
 },[]);
 return <div className="nsh">
  <div className="top-alert"><span className="top-alert-dot"/> SOURCE-BASED PREDICTOR <span className="top-alert-sep">/</span> NOT AN EMERGENCY ALERT SERVICE</div>
  <header className="site-header"><Link href="/" className="brand"><span className="site-mark"><CloudLightning size={23}/></span><span>NATIONAL<span className="brand-highlight">STORM</span>HUB<span className="brand-period">.</span></span></Link><Link href="/" className="header-action"><ArrowLeft size={15}/> Back home</Link></header>
  <main>
   <section className="wrap predictor-hero"><Link className="state-back" href="/"><ArrowLeft size={15}/> National Storm Hub</Link>
    <div className="eyebrow"><span className="eyebrow-line"/> STORM INTELLIGENCE / PUBLIC BETA</div>
    <h1>Storm Predictor<span className="punctuation">.</span><br/><em>Evidence before assumptions.</em></h1>
    <p>Explore the official short-range outlook, local National Weather Service forecast and active weather warnings for a ZIP code. The source review puts official warnings and forecasts in context. It does not predict damage to individual homes.</p>
    <form onSubmit={e=>{e.preventDefault();go(zip);}} className="zip-search" aria-label="Storm Predictor ZIP lookup"><MapPin size={20} className="zip-pin"/><label className="sr-only" htmlFor="predictor-zip">ZIP code</label><input id="predictor-zip" value={zip} onChange={e=>setZip(e.target.value.replace(/[^0-9]/g,"").slice(0,5))} inputMode="numeric" maxLength={5} placeholder="Enter your ZIP code, e.g. 75201"/><button type="submit" disabled={busy}>{busy?"Checking...":"View local forecast"} <ArrowRight size={16}/></button></form>
    {error&&<p className="form-error" role="alert">{error}</p>}
    <div className="hero-trust"><span><ShieldCheck size={17}/> NWS official feeds</span><span><Layers size={17}/> SPC outlook</span><span><Info size={17}/> No damage claims</span></div>
   </section>
   <section className="wrap predictor-outcome" aria-live="polite">
    {!view&&!busy&&<div className="predictor-placeholder"><CloudSun size={35}/><h2>Explore your local weather picture</h2><p>Start with a ZIP code. You can see forecast periods, weather alerts and—where available—the Day 1 SPC severe-thunderstorm outlook category.</p></div>}
    {busy&&<div className="predictor-placeholder"><RefreshCw className="spinning" size={35}/><h2>Checking official sources</h2><p>Sources may load independently; missing information will be shown as unavailable, never as an all-clear.</p></div>}
    {view&&<div className="predictor-results">
      <div className="predictor-summary"><div><span className="fine-label">LOCAL FORECAST INTELLIGENCE / {view.area.state}</span><h2>{view.area.name} <em>· {view.area.zip}</em></h2><p>Checked {pretty(view.checked_at)} · ZIP centroid approximation</p></div><div className="predictor-overall"><span className="source-mark">{view.status.replaceAll("_"," ")}</span><small>Source checks, not a risk score</small></div></div>
      <div className="predictor-columns">
        <div className="predictor-box"><div className="predictor-head"><Radio size={20}/><h3>Active NWS alerts</h3><Flag state={view.alerts.status}/></div>
          {view.alerts.status!=="AVAILABLE"?<p className="data-missing">Alert feed unavailable. Check <a href="https://www.weather.gov/" target="_blank" rel="noreferrer">weather.gov</a> for official warnings.</p>:
           view.alerts.items.length? <div className="predictor-alert-list">{view.alerts.items.slice(0,8).map(a=><div className="predictor-alert" key={a.id}><span className="forecast-warning"><AlertTriangle size={16}/>{a.event}</span><p>{a.area||view.area.name} · {a.severity}</p><p>Expires: {pretty(a.expires)}</p><a href={a.source} target="_blank" rel="noreferrer">NWS source <ExternalLink size={13}/></a></div>)}</div>:
           <p className="data-missing">No active NWS alerts returned at the last check for the approximate ZIP centre. This is <strong>not</strong> an all-clear.</p>}
        </div>
        <div className="predictor-box"><div className="predictor-head"><Layers size={20}/><h3>SPC Day 1 outlook</h3><Flag state={view.spc.status}/></div>
           {view.spc.status!=="AVAILABLE"?<p className="data-missing">SPC categorical outlook could not be checked for this location. It may be outside the contiguous-US layer or temporarily unavailable.</p>:
            view.spc.category?<><div className="outlook-big">{view.spc.category.label}</div><p className="data-missing">The location intersects an official SPC categorical outlook area. This is a <strong>regional severe-thunderstorm outlook</strong>, not a home-damage likelihood or property-specific probability.</p></>:
            <><div className="outlook-big neutral">No outlook polygon found</div><p className="data-missing">No categorical polygon intersected this approximate ZIP centre in the checked layer. That does not mean there is no weather hazard.</p></>}
           <a href="https://www.spc.noaa.gov/products/outlook/" target="_blank" rel="noreferrer" className="predictor-source-link">Read the official SPC outlook <ExternalLink size={13}/></a>
        </div>
      </div>
      <div className="predictor-box"><div className="predictor-head"><CloudSun size={20}/><h3>Local NWS forecast periods</h3><Flag state={view.forecast.status}/></div>
        {view.forecast.status==="AVAILABLE"?<div className="period-grid">{view.forecast.periods.map((p,i)=><div className="period-card" key={p.start+String(i)}><span>{p.name}</span><strong>{p.temperature===null?"—":p.temperature+"°"+p.unit}</strong><p>{p.forecast}</p><small><Wind size={14}/> {p.wind} {p.windDirection}</small><small>{pretty(p.start)}</small></div>)}</div>:
          <p className="data-missing">The forecast source is unavailable. Do not substitute missing data with estimated conditions.</p>}
        <a href="https://www.weather.gov/" target="_blank" rel="noreferrer" className="predictor-source-link">Read the official National Weather Service forecast <ExternalLink size={13}/></a>
      </div>
      <div className="predictor-interpretation"><div className="eyebrow"><span className="eyebrow-line"/> STORM INTELLIGENCE / EVIDENCE REVIEW</div>
        <h3>{view.alerts.status!=="AVAILABLE"?"Warning classification unavailable.":view.predictor.signal_count?"Tracked severe-weather warning types were returned.":"No tracked warning types were returned at this check."}</h3><p>We check returned tornado, severe-thunderstorm, high-wind and flash-flood warnings for further review. These issued alerts do not establish damage to a home or predict demand for repair services.</p><p><strong>Evidence state:</strong> {view.alerts.status==="AVAILABLE"?"Warning classifications checked.":"Warning source unavailable."} <strong>Next action:</strong> consult official guidance and prepare safely.</p>
        {view.intelligence&&<div className="nsh-intelligence-review">
          <div className="fine-label">EMPIREOS SOURCE REVIEW · {view.intelligence.source_state.replaceAll("_"," ")}</div>
          <div className="nsh-intelligence-checks">{view.intelligence.source_context.map(item=><article key={item.type}>
            <span className={item.available?"source-mark":"source-mark unavailable"}>{item.type.replaceAll("_"," ")} · {item.available?"CHECKED":"UNAVAILABLE"}</span>
            <p>{item.message}</p>
          </article>)}</div>
          <p className="nsh-intelligence-boundary"><strong>Verification boundary:</strong> this tool cannot verify property damage, homeowner intent, contractor capacity or revenue. Missing sources remain unknown.</p>
        </div>}
      </div>
    </div>}
   </section>
   <section className="wrap predictor-education"><div><h2>Understand the difference.</h2><p>Forecasts, alerts and historical storm reports answer different questions. National Storm Hub keeps them separate, so visitors don't mistake a forecast for an observed event—or a warning for verified damage.</p></div><div className="predictor-steps"><div><span>01 / FORECAST</span><h3>What might happen?</h3><p>Local NWS forecast periods and SPC severe-weather outlooks.</p></div><div><span>02 / ACTIVE ALERT</span><h3>What is being warned?</h3><p>Official watches, warnings and advisories as issued.</p></div><div><span>03 / HISTORICAL</span><h3>What was recorded?</h3><p>NOAA's retrospective Storm Events Database; records arrive after review.</p></div></div><div className="more-links"><Link href="/research">Research & sources <ArrowRight size={16}/></Link><Link href="/recovery">Preparedness & recovery <ArrowRight size={16}/></Link></div></section>
  </main>
  <footer className="site-footer"><div className="wrap bottom-footer"><span>National Storm Hub · Independent public information platform</span><Link href="/">Back to homepage <ArrowRight size={14}/></Link></div></footer>
 </div>;
}
