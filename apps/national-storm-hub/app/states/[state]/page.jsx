import {notFound} from "next/navigation";
import Link from "next/link";
import {ArrowLeft,ArrowRight,ArrowUpRight,CloudLightning,Radio,ShieldCheck} from "lucide-react";
import {STATE_HUBS,getStateHub} from "../../../lib/state-hubs.js";

export function generateStaticParams(){return Object.keys(STATE_HUBS).map(state=>({state}));}
export async function generateMetadata({params}){
  const {state}=await params, data=getStateHub(state);
  return {title:data?`${data.name} | National Storm Hub`:"State Hub | National Storm Hub",
          description:data?.intro||"Official weather resources and preparedness information.",
          alternates:{canonical:data?`/states/${state}`:"/"},
          robots:{index:false,follow:false}};
}
export default async function StateHubPage({params}){
  const {state}=await params;
  const data=getStateHub(state);
  if(!data)notFound();
  return <div className="nsh state-page">
    <div className="top-alert">INDEPENDENT WEATHER INFORMATION <span className="top-alert-sep">/</span> Always follow local emergency authorities</div>
    <header className="site-header">
      <Link href="/" className="brand"><span className="site-mark"><CloudLightning size={24}/></span><span>NATIONAL<span className="brand-highlight">STORM</span>HUB<span className="brand-period">.</span></span></Link>
      <Link className="header-action" href={`/?state=${data.code}#atlas`}>View {data.code} official alerts <ArrowUpRight size={16}/></Link>
    </header>
    <main>
      <section className="wrap state-hero">
        <Link href="/" className="state-back"><ArrowLeft size={16}/> Back to National Storm Hub</Link>
        <div className="eyebrow"><span className="eyebrow-line"/>{data.eyebrow}</div>
        <h1>{data.name}<span className="punctuation">.</span><br/><em>{data.headline}</em></h1>
        <p>{data.intro}</p>
        <div className="state-actions"><Link href={`/?state=${data.code}#atlas`}>Browse official alerts <ArrowRight size={17}/></Link><Link href="/#passport">Storm Passport <ShieldCheck size={16}/></Link></div>
        <p className="state-caveat"><Radio size={15}/> State hub preview — no local contractor referrals, live impact estimates or insurance services.</p>
      </section>
      <section className="wrap state-body">
        <div className="eyebrow"><span className="eyebrow-line"/> LOCAL READINESS PRIORITIES</div>
        <h2>What matters in {state==="texas"?"Texas":"Florida"}.</h2>
        <div className="recovery-cards">{data.themes.map((theme,i)=><div className="shell-card recovery-card" key={theme.title}><span className="card-index">AREA GUIDE / {String(i+1).padStart(2,"0")}</span><div className="recovery-icon">{i===0?<CloudLightning/>:i===1?<Radio/>:<ShieldCheck/>}</div><h3>{theme.title}</h3><p>{theme.body}</p></div>)}</div>
      </section>
      <section className="state-check-band">
        <div className="wrap state-columns">
          <div><div className="eyebrow"><span className="eyebrow-line"/> SAFE ACTIONS</div><h2>Your local readiness checklist.</h2><ol>{data.steps.map(x=><li key={x}>{x}</li>)}</ol></div>
          <div><div className="eyebrow"><span className="eyebrow-line"/> AUTHORITATIVE RESOURCES</div><h2>Check the source.</h2><p>{data.explanation}</p><div className="state-source-list">{data.sources.map(src=><a key={src.name} href={src.href} target="_blank" rel="noreferrer">{src.name}<ArrowUpRight size={16}/></a>)}</div></div>
        </div>
      </section>
      <section className="wrap state-bottom"><h2>Build your preparedness history, <em>one season at a time.</em></h2><p>Save a region and track your personal checklist in our browser-only Storm Passport preview.</p><Link href="/#passport">Open Storm Passport <ArrowRight size={18}/></Link></section>
    </main>
    <footer className="site-footer"><div className="wrap bottom-footer"><span>© National Storm Hub — independent concept by Empire AI.</span><Link href="/">National home <ArrowUpRight size={14}/></Link></div></footer>
  </div>;
}
