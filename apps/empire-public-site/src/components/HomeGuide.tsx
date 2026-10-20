"use client";
import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";
import { ArrowUpRight, ArrowRight, Play, ScanLine, Workflow, Fingerprint } from "lucide-react";
const Experience = dynamic(() => import("@/components/CinematicExperience"), { ssr: false });
const solutions = [
  {n:"01", title:"Predictive Revenue", tag:"YOUR COMMERCIAL PICTURE", copy:"Understand your pipeline, assess emerging opportunities and make the next decision with the evidence in view.", href:"/predictive-revenue", action:"Explore Predictive Revenue"},
  {n:"02", title:"Intelligence products", tag:"A CLEARER VIEW OF YOUR MARKET", copy:"Explore specialist intelligence for market research, territory planning and opportunity qualification. Review the available scope before committing.", href:"/buy", action:"View intelligence products"},
  {n:"03", title:"AI Workforce & advisory", tag:"EXPERTISE INTO EXECUTION", copy:"Discuss a scoped Digital Avatar deployment or a founder-led consultancy engagement built around your business needs.", href:"/commercial", action:"Discuss a tailored proposal"},
];
export default function HomeGuide() {
  const [cinema,setCinema]=useState(false);
  const launch=useRef<HTMLButtonElement>(null);
  const close=useRef<HTMLButtonElement>(null);
  useEffect(()=>{
    if(!cinema)return;
    const previous=document.body.style.overflow;
    document.body.style.overflow="hidden"; close.current?.focus();
    const key=(e:KeyboardEvent)=>{if(e.key==="Escape")setCinema(false); if(e.key==="Tab") {const nodes=Array.from(document.querySelectorAll<HTMLElement>('.cinema-dialog a, .cinema-dialog button')).filter(el=>el.getClientRects().length); const first=nodes[0],last=nodes[nodes.length-1]; if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus()}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus()}}};
    window.addEventListener("keydown",key);
    return()=>{document.body.style.overflow=previous;window.removeEventListener("keydown",key);launch.current?.focus()};
  },[cinema]);
  return <>
    <main inert={cinema} className="flagship">
      <section className="flagship-hero">
        <div className="hero-orbit" aria-hidden="true"><div className="empire-fallback-engine"><div className="empire-fallback-ring empire-fallback-ring-a"/><div className="empire-fallback-ring empire-fallback-ring-b"/><div className="empire-fallback-ring empire-fallback-ring-c"/><div className="empire-fallback-core"/></div><span className="orbit-caption">SIGNAL → DECISION → OUTCOME</span></div>
        <div className="hero-copy"><p className="eyebrow">EMPIRE AI / PREDICTIVE REVENUE</p><h1>See the signal.<br />Shape the next<br /><span>commercial move.</span></h1><p className="hero-intro">Connect market intelligence, commercial priorities and governed AI execution. Build a clearer route from opportunity to a measurable outcome.</p><div className="hero-actions"><a className="primary-action" href="/commercial">Discuss your business <ArrowUpRight size={18}/></a><a className="secondary-action" href="#solutions">Find your starting point <ArrowRight size={17}/></a></div><button ref={launch} className="experience-launch" onClick={()=>setCinema(true)}><Play size={14}/> Explore the 3D system <span>Optional interactive experience</span></button></div>
        <div className="hero-baseline"><span>Evidence before action.</span><span>Authority stays with you.</span><span>Forecasts are not revenue.</span></div>
      </section>
      <section id="solutions" className="flagship-section"><div className="section-heading"><p className="eyebrow">01 / WAYS TO WORK WITH EMPIRE</p><h2>Start with the decision<br />you need to make.</h2><p>Explore a focused product or discuss a wider deployment. We establish fit, scope and delivery before you commit.</p></div><div className="solution-grid">{solutions.map(s=><a className="solution-card" href={s.href} key={s.n}><div className="card-top"><span>{s.n}</span><ArrowUpRight size={22}/></div><p className="eyebrow">{s.tag}</p><h3>{s.title}</h3><p>{s.copy}</p><span className="card-action">{s.action}<ArrowRight size={17}/></span></a>)}</div></section>
      <section className="method-section flagship-section"><div className="section-heading"><p className="eyebrow">02 / THE EMPIRE METHOD</p><h2>A signal is a beginning.<br /><span>Proof closes the loop.</span></h2><p>Our approach connects research with commercial judgement. Every proposed deployment starts with the evidence and capabilities available for your use case.</p></div><div className="method-grid"><article><ScanLine/><h3>Understand the opportunity</h3><p>Bring market, business and demand signals into context. Separate a useful observation from an assumption.</p></article><article><Workflow/><h3>Choose the next action</h3><p>Assess fit, priorities and commercial scope. Agree who can act and where a human decision is required.</p></article><article><Fingerprint/><h3>Measure the actual outcome</h3><p>Keep forecasts, enquiries, agreements and realised revenue distinct. Learn from what can be verified.</p></article></div></section>
      <section className="flagship-section market-section"><div><p className="eyebrow">03 / SPECIALIST CONTEXT</p><h2>Different markets.<br />Different signals.</h2><p>Property, private capital, home services and legal markets each need their own context. Explore the industry research behind a more focused conversation.</p><a className="secondary-action" href="/industries">Explore industry intelligence <ArrowUpRight size={18}/></a></div><div className="market-index">{[["Property & construction","Permit and project context"],["Home services","Territory and demand context"],["Private capital","Company and market context"],["Legal markets","Opportunity qualification"]].map(([name,copy],i)=><a href="/industries" key={name}><span>0{i+1}</span><div><h3>{name}</h3><p>{copy}</p></div><ArrowUpRight size={18}/></a>)}</div></section>
      <section className="flagship-section closing-section"><p className="eyebrow">YOUR NEXT COMMERCIAL MOVE</p><h2>Bring the ambition.<br /><span>Let’s define the work.</span></h2><p>Tell us where your business is today and what you want to improve. Start an email-first conversation with the founder.</p><a className="primary-action" href="/commercial">Request a founder proposal <ArrowUpRight size={18}/></a><a className="trust-link" href="/trust">Read our evidence principles</a></section>
    </main>
    {cinema&&<div className="cinema-dialog" role="dialog" aria-modal="true" aria-label="Empire AI interactive system"><Experience/><button ref={close} className="close-experience" onClick={()=>setCinema(false)}>Close experience ×</button></div>}
  </>;
}
