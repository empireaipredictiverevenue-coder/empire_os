"use client";
import {useEffect,useRef,useState} from "react";
import {ArrowLeft,ArrowRight,ArrowUpRight,BookOpen,House,Radio,ShieldCheck} from "lucide-react";
import {STORM_JOURNEYS,journeyIndex} from "../lib/storm-journey.js";
const icons=[House,Radio,ShieldCheck];
export default function StormJourneySlider(){
  const [index,setIndex]=useState(0);
  const [motion,setMotion]=useState(false);
  const [active,setActive]=useState(false);
  const [paused,setPaused]=useState(false);
  const [interacted,setInteracted]=useState(false);
  const section=useRef(null);
  const touch=useRef(null);
  const story=STORM_JOURNEYS[index];
  const VisualIcon=icons[index];

  useEffect(()=>{
    const media=window.matchMedia?.("(prefers-reduced-motion: reduce)");
    const sync=()=>setMotion(Boolean(media&&!media.matches));
    sync();media?.addEventListener?.("change",sync);
    return ()=>media?.removeEventListener?.("change",sync);
  },[]);
  useEffect(()=>{
    if(!("IntersectionObserver" in window)){setActive(true);return;}
    const observer=new IntersectionObserver(([entry])=>setActive(Boolean(entry?.isIntersecting)),{threshold:.28});
    if(section.current)observer.observe(section.current);
    return ()=>observer.disconnect();
  },[]);
  useEffect(()=>{
    if(!active||!motion||paused||interacted)return;
    const timer=window.setTimeout(()=>{
      if(document.visibilityState==="visible")setIndex(n=>journeyIndex(n,1));
    },10000);
    return ()=>window.clearTimeout(timer);
  },[index,active,motion,paused,interacted]);

  function select(next){
    setInteracted(true);
    setIndex(journeyIndex(next,0));
  }
  function move(delta){select(journeyIndex(index,delta));}
  function onTouchStart(e){
    if(e.touches.length!==1)return;
    touch.current={x:e.touches[0].clientX,y:e.touches[0].clientY};
  }
  function onTouchEnd(e){
    const start=touch.current;touch.current=null;
    const end=e.changedTouches[0];
    if(!start||!end)return;
    const dx=end.clientX-start.x;
    const dy=end.clientY-start.y;
    if(Math.abs(dx)>65&&Math.abs(dx)>Math.abs(dy)*1.5)move(dx<0?1:-1);
  }
  function onKeys(e){
    if(!e.target.closest("button[data-journey-control]"))return;
    if(e.key==="ArrowLeft"||e.key==="ArrowRight"){
      e.preventDefault();move(e.key==="ArrowLeft"?-1:1);
    }
  }

  return <section ref={section} id="prepare" className="storm-journey section wrap"
    aria-labelledby="recovery-title"
    onMouseEnter={()=>setPaused(true)} onMouseLeave={()=>setPaused(false)}
    onFocusCapture={()=>setPaused(true)}
    onBlurCapture={e=>{if(!e.currentTarget.contains(e.relatedTarget))setPaused(false);}}
    onTouchStart={onTouchStart} onTouchEnd={onTouchEnd}
    onKeyDown={onKeys}>
    <div className="journey-header">
      <div>
        <div className="journey-kicker">HOMEOWNER FIELD GUIDE <span> / THREE MOMENTS THAT MATTER</span></div>
        <h2 id="recovery-title">A clearer path <em>through the storm.</em></h2>
        <p>Useful guidance for the moments before, during and after severe weather.</p>
      </div>
      <div className="journey-head-controls" aria-label="Journey slide controls">
        <span aria-hidden="true">{story.step} <span>/ 03</span></span>
        <button type="button" data-journey-control onClick={()=>move(-1)} aria-label="Previous stage"><ArrowLeft size={19}/></button>
        <button type="button" data-journey-control onClick={()=>move(1)} aria-label="Next stage"><ArrowRight size={19}/></button>
      </div>
    </div>
    <div className={"journey-stage journey-stage-"+story.tone} role="group"
      aria-label={"Storm preparation guide, step "+(index+1)+" of "+STORM_JOURNEYS.length}>
      <div className="journey-atmosphere" aria-hidden="true">
        <div className="journey-light journey-light-first"/>
        <div className="journey-light journey-light-second"/>
        <div className="journey-visual-glyph"><VisualIcon size={84} strokeWidth={1.05}/></div>
        <span className="journey-scene-word">{story.label}</span>
        <span className="journey-scene-caption">STORM HUB / HOMEOWNER GUIDE</span>
      </div>
      <div className="journey-body" key={story.id}>
        <div className="journey-stage-label"><span className="journey-marker"/>{story.eyebrow}</div>
        <h3>{story.title} <em>{story.emphasis}</em></h3>
        <p className="journey-description">{story.description}</p>
        <div className="journey-actions-list">{story.actions.map(a=><div key={a}><ShieldCheck size={15}/><span>{a}</span></div>)}</div>
        <div className="journey-links">
          <a className="journey-main-action" href={story.primary.href}>{story.primary.label}<ArrowRight size={17}/></a>
          <a className="journey-source-link" href={story.secondary.href} target="_blank" rel="noopener noreferrer">{story.secondary.label}<ArrowUpRight size={15}/></a>
        </div>
        <div className="journey-provenance"><BookOpen size={14}/> Guidance: {story.source} · Not a live risk or damage assessment</div>
      </div>
    </div>
    <div className="journey-steps" role="group" aria-label="Choose a storm stage">
      {STORM_JOURNEYS.map((step,i)=><button type="button" key={step.id} data-journey-control
        className={"journey-step"+(index===i?" chosen":"")} aria-pressed={index===i}
        aria-label={"Show "+step.label.toLowerCase()+" guidance, stage "+step.step+" of 03"}
        onClick={()=>select(i)}>
        <span className="journey-step-index">{step.step}</span>
        <span className="journey-step-title">{step.label}</span>
        <span className="journey-step-meter" aria-hidden="true"/>
      </button>)}
    </div>
  </section>;
}