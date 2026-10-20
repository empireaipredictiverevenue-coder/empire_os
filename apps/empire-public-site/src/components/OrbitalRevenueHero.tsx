import { ArrowDownRight, ArrowRight, Crosshair, Network, ShieldCheck } from "lucide-react";
import "./orbital-revenue-hero.css";

/**
 * Accessible, source-first version of the founder's approved blue/gold mockup.
 * No generated-picture metrics, invented customers, transactions or market counts.
 *
 * The existing global BrandLockup remains the sole visible identity.
 * The console reuses the existing Earth artwork and shared scene anchor.
 */
const proofPoints = [
  { icon: Crosshair, label: "Opportunity intelligence", text: "Investigate market and buyer signals with traceable sources." },
  { icon: Network, label: "Governed AI workflows", text: "Make the next step reviewable before action." },
  { icon: ShieldCheck, label: "Verified outcomes", text: "Distinguish a forecast from a signed, realised result." },
];

type ConsoleChapter = {label:string; module:string; detail:string; body:string; href:string};
type Props = {chapters:ConsoleChapter[]; selected:number; onSelect:(index:number)=>void};
export default function OrbitalRevenueHero({chapters,selected,onSelect}:Props) {
  const active=chapters[selected];
  return <section className="orbital-home-hero" aria-labelledby="orbital-home-title">
    <div className="orbital-home-atmosphere" aria-hidden="true"/>
    <div className="orbital-home-earth" aria-hidden="true"/>
    <div className="orbital-home-tint" aria-hidden="true"/>
    <div className="orbital-home-inner">
      <div className="orbital-home-copy">
        <p className="orbital-home-eyebrow">Predictive Revenue Infrastructure</p>
        <h1 id="orbital-home-title">Turn market intelligence into <span>better revenue decisions.</span></h1>
        <p className="orbital-home-lede">Connect company intelligence, opportunity research and governed AI workflows to make each commercial next step clearer. Evidence first. Real people. Measurable outcomes.</p>
        <div className="orbital-home-actions">
          <a className="orbital-home-cta" href="/commercial">Discuss your business <ArrowRight aria-hidden="true" size={18}/></a>
          <a className="orbital-home-cta-alt" href="#intelligence-world">See how it works <ArrowDownRight aria-hidden="true" size={18}/></a>
        </div>
        <p className="orbital-home-qualifier">Founder-reviewed, nonbinding enquiries. No guarantee of enquiries or revenue.</p>
      </div>
      <div className="orbital-home-art" aria-label="Interactive Empire AI intelligence console">
        <div className="arrival-console">
          <div className="arrival-console-heading"><span>EMPIREOS / INTELLIGENCE</span><span>Explore the system</span></div>
          <div className="arrival-console-screen">
            <div className="hero-scene-anchor" aria-hidden="true"/>
            <div className="arrival-console-orbit" aria-hidden="true"><span/><span/></div>
            <div className="arrival-console-modules" aria-label="Console capabilities">
              {chapters.map((c,i)=><button type="button" key={c.module} aria-pressed={selected===i} aria-controls="arrival-console-detail" onClick={()=>onSelect(i)}><span>0{i+1}</span><span>{c.module}<small>{c.detail}</small></span></button>)}
            </div>
            <div className="arrival-console-focus" aria-hidden="true"><span>0{selected+1} / {active.label}</span><strong>{active.detail}</strong></div>
          </div>
          <div className="arrival-console-detail" id="arrival-console-detail" aria-live="polite" aria-atomic="true"><span>{active.label}</span><p>{active.body}</p><a href={active.href}>Explore {active.module} <ArrowRight size={15} aria-hidden="true"/></a></div>
          <a className="arrival-console-enter" href="#intelligence-world">Enter the infrastructure <ArrowDownRight size={19} aria-hidden="true"/></a>
          <p className="arrival-console-caption">Illustrative system view · Scroll to explore</p>
        </div>
      </div>
    </div>
    <div className="orbital-home-proof" aria-label="Core platform principles">
      {proofPoints.map(({icon: Icon, label, text}) =>
        <div key={label} className="orbital-home-proof-item">
          <span className="orbital-home-proof-icon"><Icon aria-hidden="true" size={23}/></span>
          <div><strong>{label}</strong><p>{text}</p></div>
        </div>
      )}
      <a href="/insights/revenue-opportunity-assessment" className="orbital-home-proof-more">Explore illustrative ROI scenarios <ArrowRight aria-hidden="true" size={17}/></a>
    </div>
  </section>;
}
