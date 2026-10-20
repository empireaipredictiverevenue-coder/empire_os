"use client";
import { useEffect, useRef, useState } from "react";
import EarthJourney from "./EarthJourney";

type Props={selected:number;progress:number;paused:boolean;quality:"auto"|"enhanced"|"simple"};
/** One renderer and globe survive the document-space console → world handoff. */
export default function SharedJourney(props:Props){
 const layer=useRef<HTMLDivElement>(null);
 const [entry,setEntry]=useState(0),[visible,setVisible]=useState(false);
 useEffect(()=>{
  const host=layer.current,root=host?.closest(".earth-experience") as HTMLElement|null;
  if(!host||!root)return;
  const hero=root.querySelector(".hero-scene-anchor") as HTMLElement;
  const world=root.querySelector(".world-scene-anchor") as HTMLElement;
  const section=root.querySelector("#intelligence-world") as HTMLElement;
  const heroSection=root.querySelector(".orbital-home-hero, .earth-hero") as HTMLElement|null;
  // Guard the renderer if a future hero template omits one of its scene anchors.
  if (!hero || !world || !section || !heroSection) return;
  const media=matchMedia("(prefers-reduced-motion: reduce)");
  let frame=0;
  const update=()=>{
   frame=0;
   const h=hero.getBoundingClientRect(),w=world.getBoundingClientRect(),s=section.getBoundingClientRect();
   const end=scrollY+s.top,start=Math.max(0,end-innerHeight);
   const linear=Math.max(0,Math.min(1,(scrollY-start)/Math.max(1,end-start)));
   // Quintic easing limits visible velocity changes at the transition anchors.
   const p=linear*linear*linear*(linear*(linear*6-15)+10);
   const blend=(a:number,b:number)=>a+(b-a)*p;
   const left=Math.max(0,blend(h.left,w.left));
   const width=Math.max(1,Math.min(innerWidth-left,blend(h.width,w.width)));
   host.style.left=left+"px";host.style.top=blend(h.top,w.top)+"px";
   host.style.maskImage=`linear-gradient(to bottom,transparent,#000 ${p*16}%,#000 ${100-p*12}%,transparent)`;
   // Keep the same real Earth and dimensional console visible from arrival.
   host.style.opacity="1";
   host.style.borderRadius="12px";
   host.style.width=width+"px";host.style.height=Math.max(1,blend(h.height,w.height))+"px";
   const active=!media.matches&&(heroSection.getBoundingClientRect().bottom>0||s.bottom>0)&&s.top<innerHeight*2;
   host.style.visibility=active?"visible":"hidden";
   root.dataset.sharedScene=String(!media.matches);
   setEntry(p);setVisible(active);
  };
  const schedule=()=>{if(!frame)frame=requestAnimationFrame(update)};
  window.addEventListener("scroll",schedule,{passive:true});
  window.addEventListener("resize",schedule);
  media.addEventListener("change",schedule);
  const resize=new ResizeObserver(schedule);resize.observe(hero);resize.observe(world);resize.observe(section);
  const readiness=new MutationObserver(schedule);readiness.observe(host,{subtree:true,attributes:true,attributeFilter:["data-ready"]});
  update();
  return()=>{cancelAnimationFrame(frame);readiness.disconnect();resize.disconnect();window.removeEventListener("scroll",schedule);window.removeEventListener("resize",schedule);media.removeEventListener("change",schedule);delete root.dataset.sharedScene};
 },[props.paused]);
 return <div ref={layer} className="shared-journey" aria-hidden="true" data-entry={entry.toFixed(3)}>
  <EarthJourney {...props} hero={entry<.5} entry={entry} paused={props.paused||!visible}/>
 </div>;
}
