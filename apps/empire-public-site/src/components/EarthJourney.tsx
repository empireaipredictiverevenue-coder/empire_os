"use client";
import InfrastructureStill from "./InfrastructureStill";
import dynamic from "next/dynamic";
import { Component, useCallback, useEffect, useRef, useState, type ReactNode } from "react";
const Scene = dynamic(() => import("./EarthJourneyScene"), {ssr:false});
class SceneBoundary extends Component<{children:ReactNode;onFailed:()=>void},{failed:boolean}> {
 state={failed:false};
 static getDerivedStateFromError(){return {failed:true}}
 componentDidCatch(){this.props.onFailed()}
 render(){return this.state.failed?null:this.props.children}
}
export default function EarthJourney({selected,paused,progress=0,hero=false,entry=hero?0:1,quality="auto"}:{selected:number;paused:boolean;progress?:number;hero?:boolean;entry?:number;quality?:"auto"|"enhanced"|"simple"}){
 const host=useRef<HTMLDivElement>(null);
 const [visible,setVisible]=useState(false),[allowed,setAllowed]=useState(false),[lost,setLost]=useState(false),[ready,setReady]=useState(false);
 const fail=useCallback(()=>{setLost(true);setReady(false)},[]);
 const loaded=useCallback(()=>setReady(true),[]);
 useEffect(()=>{
  const media=matchMedia("(prefers-reduced-motion: reduce)");
  const update=()=>{
   const nav=navigator as Navigator&{deviceMemory?:number;connection?:{saveData?:boolean}};
   if(media.matches||nav.connection?.saveData||(nav.deviceMemory!==undefined&&nav.deviceMemory<3)){setAllowed(false);return}
   const probe=document.createElement("canvas");const context=probe.getContext("webgl2");
   setAllowed(Boolean(context));context?.getExtension("WEBGL_lose_context")?.loseContext();
  };
  update();media.addEventListener("change",update);return()=>media.removeEventListener("change",update);
 },[]);
 useEffect(()=>{const observer=new IntersectionObserver(([e])=>setVisible(e.isIntersecting),{rootMargin:"80px"});if(host.current)observer.observe(host.current);return()=>observer.disconnect()},[]);
 useEffect(()=>{setLost(false)},[quality]);
 const active=allowed&&visible&&!paused&&!lost&&quality!=="simple";
 return <div ref={host} className={hero?"earth-webgl hero-webgl":"earth-webgl"} aria-hidden="true" data-scene-state={lost?"fallback":paused?"paused":active?"active":"static"} data-ready={active&&ready}>
  <div className="globe-static"/>{entry>.5&&<InfrastructureStill selected={selected}/>}
  {active&&<SceneBoundary onFailed={fail}><Scene selected={selected} progress={progress} hero={hero} entry={entry} onLost={fail} onReady={loaded} onSlow={quality==="auto"?fail:undefined}/></SceneBoundary>}
 </div>;
}
