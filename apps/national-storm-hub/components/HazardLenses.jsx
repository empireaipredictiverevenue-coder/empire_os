"use client";
import {useRef,useState} from "react";
import {ArrowLeft,ArrowRight,ArrowUpRight,CloudLightning,ShieldAlert,ShieldCheck,Waves,Wind} from "lucide-react";
import {HAZARD_LENSES} from "../lib/hazard-lenses.js";
import {nextHeroIndex} from "../lib/hero-stories.js";
const symbols=[CloudLightning,Waves,Wind,ShieldAlert];
export default function HazardLenses(){
  const [index,setIndex]=useState(0);
  const touch=useRef(null);
  const item=HAZARD_LENSES[index];
  const Symbol=symbols[index];
  const navigate=delta=>setIndex(i=>nextHeroIndex(i,delta,HAZARD_LENSES.length));
  return <section className="hazard-lenses wrap" aria-labelledby="hazard-lenses-title">
    <div className="hazard-lenses-heading">
      <div><span className="eyebrow"><span className="eyebrow-line"/> THE STORM INTELLIGENCE LIBRARY / 04 LENSES</span>
        <h2 id="hazard-lenses-title">Different hazards. <em>Different decisions.</em></h2>
        <p>Four ways to understand severe weather, with practical source-backed guidance. These cards are editorial—not live threat predictions.</p>
      </div>
      <div className="hazard-controls">
        <button type="button" onClick={()=>navigate(-1)} aria-label="Previous hazard"><ArrowLeft size={18}/></button>
        <button type="button" onClick={()=>navigate(1)} aria-label="Next hazard"><ArrowRight size={18}/></button>
      </div>
    </div>
    <div className={"hazard-lens-card hazard-lens-"+item.theme}
      onTouchStart={e=>{touch.current={x:e.touches[0]?.clientX,y:e.touches[0]?.clientY};}}
      onTouchEnd={e=>{const s=touch.current;touch.current=null;if(!s||!e.changedTouches[0])return;
        const dx=e.changedTouches[0].clientX-s.x,dy=e.changedTouches[0].clientY-s.y;
        if(Math.abs(dx)>55&&Math.abs(dx)>Math.abs(dy)*1.4)navigate(dx<0?1:-1);}}>
      <div className="hazard-lens-art" aria-hidden="true">
        <div className="hazard-ring hazard-ring-a"/><div className="hazard-ring hazard-ring-b"/>
        <div className="hazard-ring hazard-ring-c"/><Symbol size={70} strokeWidth={1}/>
        <span>HAZARD / {item.index}</span>
      </div>
      <div className="hazard-lens-description" key={item.id}>
        <span>{item.type}</span>
        <h3>{item.title}</h3>
        <p>{item.summary}</p>
        <div className="hazard-note"><ShieldCheck size={18}/>{item.note}</div>
        <div className="hazard-links">
          <a href={item.href} target="_blank" rel="noreferrer">{item.label} <ArrowUpRight size={16}/></a>
          <a href="/alerts">Official alerts <ArrowRight size={16}/></a>
        </div>
      </div>
    </div>
    <div className="hazard-lens-pagination" role="group" aria-label="Select a hazard guide">
      {HAZARD_LENSES.map((x,i)=><button key={x.id} type="button"
        aria-pressed={i===index} className={i===index?"selected":""}
        onClick={()=>setIndex(i)}><span>{x.index}</span> {x.type.split(" / ")[0]}</button>)}
    </div>
  </section>;
}
