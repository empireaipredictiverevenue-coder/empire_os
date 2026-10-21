import Link from "next/link";
import {ArrowLeft,ArrowRight,ArrowUpRight,BookOpen,CloudLightning,FileText,FlaskConical,ShieldCheck,ExternalLink} from "lucide-react";
import {SOURCES,RESEARCH_PRIORITIES} from "../../lib/research-library.js";
export const metadata={title:"Storm Intelligence Research & Sources | National Storm Hub",description:"Transparent source provenance, forecast limitations and product research behind National Storm Hub.",alternates:{canonical:"/research"},robots:{index:false,follow:false}};
export default function Research(){
return <div className="nsh">
 <div className="top-alert">RESEARCH LIBRARY / PUBLIC PREVIEW <span className="top-alert-sep">/</span> NO CLAIMS OF GOVERNMENT ENDORSEMENT</div>
 <header className="site-header"><Link href="/" className="brand"><span className="site-mark"><CloudLightning size={22}/></span><span>NATIONAL<span className="brand-highlight">STORM</span>HUB<span className="brand-period">.</span></span></Link><Link href="/predictor" className="header-action">Storm Predictor <ArrowUpRight size={15}/></Link></header>
 <main>
  <section className="wrap deep-hero">
   <Link href="/" className="state-back"><ArrowLeft size={15}/> Back home</Link>
   <div className="eyebrow"><span className="eyebrow-line"/> RESEARCH / SOURCE TRANSPARENCY</div>
   <h1>Built on evidence. <em>Not on weather hype.</em></h1>
   <p>We are building a consumer resource from official public weather and preparedness sources, with an existing EmpireOS storm intelligence engine behind the research. Here's exactly what each data source can—and cannot—establish.</p>
   <div className="deep-stat-row"><div><strong>03</strong><span>Source families integrated into the candidate</span></div><div><strong>07</strong><span>Primary research references</span></div><div><strong>00</strong><span>Verified property-damage predictions claimed</span></div></div>
  </section>
  <section className="wrap deep-section"><div className="eyebrow"><span className="eyebrow-line"/> THE SOURCE REGISTER</div><h2>Where the data comes from.</h2><p className="deep-lead">Public sources and their limitations are displayed side by side. A linked data source does not make National Storm Hub an official warning service.</p>
   <div className="research-source-grid">{SOURCES.map(s=><article className="research-source" key={s.id}><div className="research-source-top"><FileText size={21}/><span>{s.state}</span></div><h3>{s.name}</h3><div className="fine-label">{s.type}</div><h4>What we use it for</h4><p>{s.use}</p><h4>What it cannot prove</h4><p>{s.limit}</p><a href={s.url} target="_blank" rel="noreferrer">Review original source <ExternalLink size={14}/></a></article>)}</div>
  </section>
  <section className="deep-band"><div className="wrap"><div className="eyebrow"><span className="eyebrow-line"/> PRODUCT RESEARCH PROGRAMME</div><h2>What we're testing next.</h2><div className="deep-priority-list">{RESEARCH_PRIORITIES.map((r,i)=><article key={r.title}><span>{String(i+1).padStart(2,"0")}</span><div><h3>{r.title}</h3><p>{r.detail}</p></div><small>{r.status}</small></article>)}</div></div></section>
  <section className="wrap deep-footer-promo"><FlaskConical size={32}/><h2>Trust the source. <em>Know the limits.</em></h2><p>Explore live NWS information alongside a transparent, bounded Storm Predictor interpretation.</p><Link href="/predictor">Explore Storm Predictor <ArrowRight size={17}/></Link></section>
 </main>
 <footer className="site-footer"><div className="wrap bottom-footer"><span>National Storm Hub · Independent public information platform</span><Link href="/">National home <ArrowRight size={14}/></Link></div></footer>
</div>;
}
