"use client";
import InfrastructureStill from "./InfrastructureStill";
import { useEffect, useRef, useState } from "react";
import { ArrowRight, ArrowDown, Radar, Activity, Network, ShieldCheck, Users, Layers } from "lucide-react";
import OrbitalRevenueHero from "./OrbitalRevenueHero";
import PlatformCapabilities from "./PlatformCapabilities";
import SharedJourney from "./SharedJourney";
import "./immersive.css";
import "./homepage-editorial.css";
const chapters = [
 {label:"Signal Intelligence",icon:Activity,title:"Find the signal. Understand the context.",body:"Research company changes, search demand and market signals with their source and observation date. An interesting signal is a reason to investigate, not proof of buying intent.",module:"Revenue Pulse",detail:"Demand & market evidence",href:"/buy"},
 {label:"Predictive Priority",icon:Radar,title:"See what deserves your next move.",body:"Assess opportunity, timing and potential economics with the evidence available. Predictions support a decision; they are not a promise of revenue.",module:"Opportunity Radar",detail:"Opportunity prioritisation",href:"/predictive-revenue"},
 {label:"Opportunity Resolution",icon:Users,title:"Connect opportunity with commercial fit.",body:"Connect company identity, buyer requirements and commercial fit. Empire GTM Intelligence is being developed to support research and qualification before any approved outreach.",module:"Buyer Match",detail:"Requirements & commercial fit",href:"/industries"},
 {label:"Governed Execution",icon:Network,title:"Build intelligence into the way you work.",body:"Bring AI Workforce, Digital Avatars, search and content into a scoped workflow. Define what the system may do, where your team reviews it and how delivery will be assessed.",module:"Cortex",detail:"Governed AI workflows",href:"/commercial"},
 {label:"Economic Truth",icon:ShieldCheck,title:"Measure the outcome. Keep the evidence.",body:"Distinguish forecasts, conversations, agreements and realised revenue. Every stage has its own evidence; none stands in for the next.",module:"Commercial Exchange",detail:"Scope, delivery & outcomes",href:"/trust"},
];
export default function CinematicExperience() {
 const [selected,setSelected]=useState(0);
 const [paused,setPaused]=useState(false);
 const [quality,setQuality]=useState<"auto"|"enhanced"|"simple">("auto");
 const root=useRef<HTMLElement>(null);
 const world=useRef<HTMLElement>(null);

 const [progress,setProgress]=useState(0);
 const [reduced,setReduced]=useState(false);
 const drag=useRef<{x:number;left:number;moved:boolean}|null>(null);
 const dragged=useRef(false);
 const offers=useRef<HTMLDivElement>(null);
 const [offerIndex,setOfferIndex]=useState(0);
 const [goal,setGoal]=useState<number|null>(null);
 const goals=[{label:"Prioritise revenue opportunities",detail:"Start with Predictive Revenue to discuss your commercial data, priorities and decision process."},{label:"Research a market or territory",detail:"Explore intelligence products and pricing, then establish the evidence and coverage you need."},{label:"Improve a workflow with AI",detail:"Discuss AI Workforce, Digital Avatars or advisory around a clearly defined workflow and human approvals."}];
 function chooseGoal(index:number){setGoal(index);showOffer(index)}

 function showOffer(index:number){
  const rail=offers.current;if(!rail)return;
  const card=rail.children[index] as HTMLElement|undefined;if(!card)return;
  rail.scrollTo({left:card.offsetLeft-(rail.children[0] as HTMLElement).offsetLeft,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches||paused?'instant':'smooth'});
 }

 useEffect(()=>{
  const preference=matchMedia('(prefers-reduced-motion: reduce)');let frame=0;
  const update=()=>{
   frame=0;setReduced(preference.matches);
   if(!root.current)return;
   const p=preference.matches||paused?0:Math.min(scrollY/innerHeight,1.5);
   root.current.style.setProperty('--travel',String(p));
   if(world.current&&!preference.matches&&!paused&&getComputedStyle(world.current.firstElementChild as Element).position==='sticky'){
    const r=world.current.getBoundingClientRect();
    const journey=Math.max(0,Math.min(1,-r.top/Math.max(1,r.height-innerHeight)));
    setProgress(journey);
    if(r.top<=20&&r.bottom>=innerHeight-20)setSelected(Math.round(journey*4));
   }
  };
  const scroll=()=>{if(!frame)frame=requestAnimationFrame(update)};
  window.addEventListener('scroll',scroll,{passive:true});
  window.addEventListener('resize',scroll);
  preference.addEventListener('change',scroll);update();
  return()=>{window.removeEventListener('scroll',scroll);window.removeEventListener('resize',scroll);preference.removeEventListener('change',scroll);cancelAnimationFrame(frame)};
 },[paused]);
 const active=chapters[selected];
 function move(n:number){
  const next=Math.max(0,Math.min(4,n));setSelected(next);setProgress(next/4);
  if(world.current&&!paused&&!reduced&&getComputedStyle(world.current.firstElementChild as Element).position==='sticky'){
   const r=world.current.getBoundingClientRect();
   if(r.top<100&&r.bottom>innerHeight/2)window.scrollTo({top:scrollY+r.top+next/4*(r.height-innerHeight),behavior:'instant'});
  }
 }
 return <main ref={root} className="earth-experience" data-motion={paused||reduced?"paused":"enabled"} data-scene-detail={quality} aria-label="Empire AI commercial intelligence">
  <SharedJourney selected={selected} progress={progress} paused={paused} quality={quality}/>
  <OrbitalRevenueHero chapters={chapters} selected={selected} onSelect={move}/>
  <section ref={world} id="intelligence-world" className="intelligence-world" aria-labelledby="world-title"><div className="world-sticky"><div className="world-heading"><div><p className="eyebrow">ENTER THE SYSTEM</p><h2 id="world-title">The EmpireOS<br/><span>Intelligence Infrastructure.</span></h2></div><p>From source evidence to measured outcomes.<br/>Enter the architecture behind each decision.</p></div><div className="world-landscape"><img src="/art/earth-detail-v2.webp" alt="" width="1672" height="941" loading="lazy"/><div className="world-scene-anchor"><div className="scene-anchor-static"><InfrastructureStill selected={selected}/></div></div><div className="world-stations" aria-label="Intelligence stages">{chapters.map((c,i)=><button type="button" key={c.label} className={selected===i?'is-selected':''} aria-pressed={selected===i} onClick={()=>move(i)}><span className="station-number">0{i+1}</span><span className="station-beacon"><c.icon size={25}/></span><span>{c.label}</span></button>)}</div></div><div className="world-detail"><div aria-live="polite" aria-atomic="true"><div key={selected} className="stage-copy"><p className="eyebrow">0{selected+1} / {active.label.toUpperCase()}</p><h3>{active.title}</h3><p>{active.body}</p><a href={active.href} className="secondary-action">Explore {active.module} <ArrowRight size={16}/></a></div></div><div className="world-controls"><div className="world-control-row"><button type="button" aria-label="Previous scene" disabled={selected===0} onClick={()=>move(selected-1)}>←</button><label htmlFor="journey-position">Explore the system <span>{selected+1} / 5</span></label><button type="button" aria-label="Next scene" disabled={selected===4} onClick={()=>move(selected+1)}>→</button></div><input id="journey-position" type="range" min="0" max="4" value={selected} aria-label="Intelligence stage" aria-valuetext={active.label} onChange={e=>move(Number(e.target.value))}/><div className="scene-preferences"><select aria-label="Scene detail" value={quality} onChange={e=>setQuality(e.target.value as typeof quality)}><option value="auto">Auto detail</option><option value="enhanced">Detailed 3D</option><option value="simple">Simple view</option></select><button className="motion-control" type="button" aria-pressed={paused} onClick={()=>setPaused(!paused)}>{paused?'Enable depth motion':'Pause depth motion'}</button></div></div></div><p className="scene-caption">Illustrative architecture · not live system activity. <a href="/art/earth/credits.html">Earth imagery credits</a></p></div></section>
  <section className="earth-offers" aria-labelledby="offers-title"><p className="eyebrow">MAKE YOUR NEXT MOVE</p><h2 id="offers-title">Find your starting point.</h2><fieldset className="goal-picker"><legend>What would you like to improve?</legend><div>{goals.map((g,i)=><button type="button" key={g.label} aria-pressed={goal===i} aria-controls="product-slides" onClick={()=>chooseGoal(i)}>{g.label}<ArrowRight size={16}/></button>)}</div></fieldset><p className="goal-guidance" role="status">{goal===null?"Choose a goal to highlight a relevant starting point, or explore all three below.":goals[goal].detail}</p><div ref={offers} id="product-slides" className="solution-grid" aria-label="Ways to work with Empire AI" role="region" aria-roledescription="carousel" tabIndex={0}
  onKeyDown={e=>{if(e.key==='ArrowRight'||e.key==='ArrowLeft'||e.key==='Home'||e.key==='End'){e.preventDefault();showOffer(e.key==='Home'?0:e.key==='End'?2:Math.max(0,Math.min(2,offerIndex+(e.key==='ArrowRight'?1:-1))))}}}
  onPointerDown={e=>{if(e.pointerType!=="mouse"||e.button!==0)return;dragged.current=false;drag.current={x:e.clientX,left:e.currentTarget.scrollLeft,moved:false}}}
  onPointerMove={e=>{const d=drag.current;if(!d)return;const dx=e.clientX-d.x;if(Math.abs(dx)>6){d.moved=true;dragged.current=true;e.currentTarget.setPointerCapture(e.pointerId);e.currentTarget.style.scrollSnapType='none';e.currentTarget.scrollLeft=d.left-dx}}}
  onPointerUp={e=>{if(!drag.current)return;const moved=drag.current.moved;drag.current=null;if(e.currentTarget.hasPointerCapture(e.pointerId))e.currentTarget.releasePointerCapture(e.pointerId);e.currentTarget.style.scrollSnapType='';if(moved){const rail=e.currentTarget;const cards=Array.from(rail.children) as HTMLElement[];const first=cards[0].offsetLeft;const nearest=cards.reduce((best,c,i)=>Math.abs(c.offsetLeft-first-rail.scrollLeft)<Math.abs(cards[best].offsetLeft-first-rail.scrollLeft)?i:best,0);showOffer(nearest)}}}
  onPointerCancel={e=>{drag.current=null;e.currentTarget.style.scrollSnapType=''}}
  onClickCapture={e=>{if(dragged.current){e.preventDefault();dragged.current=false}}}
  onDragStart={e=>e.preventDefault()} onScroll={()=>{const rail=offers.current;if(!rail)return;const cards=Array.from(rail.children) as HTMLElement[];const origin=cards[0].offsetLeft;setOfferIndex(cards.reduce((best,card,i)=>Math.abs(card.offsetLeft-origin-rail.scrollLeft)<Math.abs(cards[best].offsetLeft-origin-rail.scrollLeft)?i:best,0))}}>{[{title:'Predictive Revenue',copy:'Bring your commercial picture into focus. Explore the products and discuss the evidence your business needs.',href:'/predictive-revenue',cta:'Explore the platform'},{title:'Intelligence products',copy:'Specialist market and opportunity intelligence for your next research, territory or qualification decision.',href:'/buy',cta:'View products & pricing'},{title:'AI Workforce & advisory',copy:'Discuss Digital Avatars, governed AI workflows and founder-led consulting around a clearly agreed scope.',href:'/commercial',cta:'Discuss your business'}].map((s,i)=><a className={"solution-card"+(goal===i?" is-recommended":"")+(offerIndex===i?" is-current":"")} aria-label={`${i+1} of 3: ${s.title}`} onFocus={()=>showOffer(i)} key={s.title} href={s.href}><div className={`product-art product-art-${i}`} aria-hidden="true">{i===0?<img src="/art/earth-detail-v2.webp" width="1536" height="1024" loading="lazy" alt=""/>:i===1?<><span><small>01 / EVIDENCE</small><b>Trace the source.</b><i/></span><span><small>02 / CONTEXT</small><b>Understand the market.</b><i/></span><span><small>03 / DECISION</small><b>Choose the next step.</b><i/></span></>:<><span><small>DEFINE</small><b>Your business challenge</b></span><span><small>DESIGN</small><b>A clearly agreed scope</b></span><span><small>REVIEW</small><b>Human-led next steps</b></span></>}</div><div className="card-top"><span>{goal===i?"YOUR STARTING POINT":`0${i+1}`}</span><ArrowRight size={22}/></div><h3>{s.title}</h3><p>{s.copy}</p><span className="card-action">{s.cta}<ArrowRight size={16}/></span></a>)}</div><div className="product-slider-controls" aria-label="Product slider controls"><button type="button" aria-label="Previous product" aria-controls="product-slides" disabled={offerIndex===0} onClick={()=>showOffer(offerIndex-1)}>←</button><span aria-live="polite">0{offerIndex+1} <span>/ 03</span></span><button type="button" aria-label="Next product" aria-controls="product-slides" disabled={offerIndex===2} onClick={()=>showOffer(offerIndex+1)}>→</button></div></section>
  <PlatformCapabilities />
  <section className="earth-close"><p className="eyebrow">YOUR BUSINESS. YOUR NEXT CHAPTER.</p><h2>Put intelligence<br/>to work.</h2><p>Tell us which decision, workflow or growth challenge you want to improve. We’ll establish the evidence needed, current capability fit and a practical scope.</p><a className="primary-action" href="/commercial">Discuss your business <ArrowRight size={18}/></a><a className="trust-link" href="/trust">How we handle evidence and authority</a></section>
 </main>;
}
