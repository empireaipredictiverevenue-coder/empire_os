"use client";
import {useEffect,useRef,useState} from "react";
import {Layers3,MoveUpRight,ScanLine} from "lucide-react";

/**
 * Immersive conceptual Stormfront Intelligence Array.
 * This is genuine native Three.js geometry — terrain, layered isobars,
 * sweeping storm bands and signal beacons — NOT a data/radar visualization.
 * No network data is used to position the illustration.
 */
export default function StormfrontScene({sceneMode="front"}){
 const holder=useRef(null);
 const modeRef=useRef(sceneMode);
 const [kind,setKind]=useState("fallback");
 useEffect(()=>{modeRef.current=sceneMode;},[sceneMode]);
 useEffect(()=>{
  const el=holder.current;
  if(!el)return;
  const reduced=window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  // Mobile and low-motion still get an intentional static atmospheric artwork.
  if(reduced||window.innerWidth<660) return;
  let cancelled=false,cleanup=()=>{};
  const begin=async()=>{
   let THREE;
   try{THREE=await import("three");}catch{return;}
   if(cancelled)return;
   let renderer;
   try{
     renderer=new THREE.WebGLRenderer({antialias:true,alpha:true,powerPreference:"low-power"});
     renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,1.5));
   }catch{return;}
   if(cancelled){renderer.dispose();return;}
   renderer.setClearColor(0x000000,0);
   renderer.outputColorSpace=THREE.SRGBColorSpace;
   const world=new THREE.Scene();
   const camera=new THREE.PerspectiveCamera(38,1,.1,100);
   camera.position.set(0,5.3,12.5);
   camera.lookAt(0,-.05,0);
   const group=new THREE.Group();
   world.add(group);
   const pieces=[];
   const remember=(thing)=>{pieces.push(thing);return thing;};
   const height=(x,z)=>{
     const wave=.42*Math.sin(x*.78+z*.35)+.28*Math.cos(z*.95-x*.24);
     const front=.6*Math.exp(-((x-z*.45-1.6)**2)/7);
     return -.8+wave+front;
   };
   const groundGeometry=remember(new THREE.PlaneGeometry(14,12,75,64));
   groundGeometry.rotateX(-Math.PI/2);
   const pos=groundGeometry.getAttribute("position");
   for(let i=0;i<pos.count;i++){
     pos.setY(i,height(pos.getX(i),pos.getZ(i)));
   }
   pos.needsUpdate=true;
   groundGeometry.computeVertexNormals();
   const groundMaterial=remember(new THREE.MeshBasicMaterial({
     color:0x421522,transparent:true,opacity:.63,side:THREE.DoubleSide,depthWrite:false
   }));
   const ground=new THREE.Mesh(groundGeometry,groundMaterial);
   group.add(ground);
   const strandMaterial=remember(new THREE.LineBasicMaterial({color:0x9e3548,transparent:true,opacity:.36,depthWrite:false}));
   for(let z=-6;z<=6.001;z+=.47){
     const points=[];
     for(let x=-7;x<=7.001;x+=.18)points.push(new THREE.Vector3(x,height(x,z)+.035,z));
     group.add(new THREE.Line(remember(new THREE.BufferGeometry().setFromPoints(points)),strandMaterial));
   }
   for(let x=-7;x<=7.001;x+=.46){
     const points=[];
     for(let z=-6;z<=6.001;z+=.18)points.push(new THREE.Vector3(x,height(x,z)+.04,z));
     group.add(new THREE.Line(remember(new THREE.BufferGeometry().setFromPoints(points)),strandMaterial));
   }
   const ribbons=new THREE.Group();
   const glowColors=[0xdd304e,0xf75a57,0xff9866,0x94203a];
   for(let band=0;band<4;band++){
     const pts=[];
     for(let step=0;step<=55;step++){
       const t=step/55,z=-6+12*t;
       const x=-4+band*1.65+Math.sin(t*6.1+band*.8)*.65+z*.25;
       pts.push(new THREE.Vector3(x,height(x,z)+.34+band*.045,z));
     }
     const curve=new THREE.CatmullRomCurve3(pts);
     const geometry=remember(new THREE.TubeGeometry(curve,120,.075+band*.015,5,false));
     const mat=remember(new THREE.MeshBasicMaterial({color:glowColors[band],transparent:true,opacity:.7,depthWrite:false}));
     ribbons.add(new THREE.Mesh(geometry,mat));
   }
   group.add(ribbons);
   const markerMaterial=remember(new THREE.MeshBasicMaterial({color:0xffdf65}));
   const haloMaterial=remember(new THREE.MeshBasicMaterial({color:0xffb56d,transparent:true,opacity:.27,depthWrite:false}));
   for(const [x,z] of [[-2.55,-.4],[1.25,1.8],[3,-2.1]]){
     const level=height(x,z);
     const marker=new THREE.Mesh(remember(new THREE.SphereGeometry(.085,12,9)),markerMaterial);
     marker.position.set(x,level+.36,z);group.add(marker);
     const stem=new THREE.Mesh(remember(new THREE.CylinderGeometry(.013,.013,.64,8)),markerMaterial);
     stem.position.set(x,level+.05,z);group.add(stem);
     const halo=new THREE.Mesh(remember(new THREE.RingGeometry(.18,.21,40)),haloMaterial);
     halo.rotation.x=-Math.PI/2;
     halo.position.set(x,level+.085,z);group.add(halo);
   }
   const starMaterial=remember(new THREE.PointsMaterial({color:0xffbbb5,size:.035,transparent:true,opacity:.46,sizeAttenuation:true}));
   const starPositions=[];
   for(let i=0;i<140;i++){
     const x=(Math.sin(i*13.312)*43758.5%1)*12;
     const z=(Math.cos(i*7.117)*12345.3%1)*10;
     starPositions.push(x,1.45+Math.abs(Math.sin(i*5.173))*3.1,z);
   }
   group.add(new THREE.Points(remember(new THREE.BufferGeometry().setAttribute("position",new THREE.Float32BufferAttribute(starPositions,3))),starMaterial));
   const canvas=renderer.domElement;
   canvas.className="stormfront-webgl-canvas";
   canvas.setAttribute("aria-hidden","true");
   el.appendChild(canvas);
   const pointer={x:0,y:0};
   const onMove=e=>{const r=el.getBoundingClientRect();pointer.x=(e.clientX-r.left)/r.width*2-1;pointer.y=(e.clientY-r.top)/r.height*2-1;};
   const onLeave=()=>{pointer.x=0;pointer.y=0;};
   let scrollFraction=0;
   const onScroll=()=>{scrollFraction=Math.max(0,Math.min(1,window.scrollY/900));};
   const resize=()=>{const width=el.clientWidth,height=el.clientHeight;
      if(width<1||height<1)return;
      renderer.setSize(width,height,false);
      camera.aspect=width/height;
      camera.updateProjectionMatrix();
   };
   const ro="ResizeObserver" in window?new ResizeObserver(resize):null;
   ro?.observe(el);
   window.addEventListener("resize",resize,{passive:true});
   resize();
   let inViewport=true;
   const observer="IntersectionObserver" in window?new IntersectionObserver(entries=>{
     inViewport=entries[0]?.isIntersecting??true;
   },{threshold:.01}):null;
   observer?.observe(el);
   el.addEventListener("pointermove",onMove,{passive:true});
   el.addEventListener("pointerleave",onLeave);
   window.addEventListener("scroll",onScroll,{passive:true});
   const clock=new THREE.Clock();
   let frame=0;
   function animate(){
     frame=requestAnimationFrame(animate);
     if(document.hidden||!inViewport)return;
     const t=clock.getElapsedTime();
     const mood=modeRef.current;
     const targetY=mood==="bands"?.18:mood==="terrain"?-.14:0;
     group.rotation.y+=(targetY+pointer.x*.07-group.rotation.y)*.022;
     group.rotation.x+=(-.085+pointer.y*.042+scrollFraction*.085-group.rotation.x)*.022;
     ribbons.position.x=Math.sin(t*.21)*.16;
     ribbons.position.z=Math.cos(t*.13)*.13;
     ribbonLight();
     renderer.render(world,camera);
   }
   function ribbonLight(){
     const mood=modeRef.current;
     strandMaterial.opacity=mood==="terrain"?.58:mood==="bands"?.27:.4;
     ribbons.scale.y=mood==="bands"?1.38:1;
   }
   setKind("webgl");
   animate();
   cleanup=()=>{
     cancelAnimationFrame(frame);
     ro?.disconnect();
     observer?.disconnect();
     window.removeEventListener("resize",resize);
     el.removeEventListener("pointermove",onMove);
     el.removeEventListener("pointerleave",onLeave);
     window.removeEventListener("scroll",onScroll);
     pieces.forEach(x=>x.dispose?.());
     renderer.dispose();
     canvas.remove();
   };
  };
  begin();
  return ()=>{cancelled=true;cleanup();};
 },[]);
 return <div className="stormfront-frame" ref={holder}
     role="img" aria-label="Conceptual 3D stormfront intelligence array: a layered weather-pattern landscape with red wave bands and yellow markers. This is not a live radar, forecast track, or warning map.">
   <div className={"stormfront-fallback "+(kind==="webgl"?"dimmed":"")} aria-hidden="true">
     <div className="stormfront-static-grid"/>
     <div className="stormfront-static-ribbon ribbon-a"/>
     <div className="stormfront-static-ribbon ribbon-b"/>
     <div className="stormfront-static-ribbon ribbon-c"/>
     <div className="stormfront-static-marker mark-a"/>
     <div className="stormfront-static-marker mark-b"/>
     <div className="stormfront-static-marker mark-c"/>
   </div>
   <div className="stormfront-tag"><ScanLine size={15}/> STORMFRONT / <span>CONCEPTUAL MODEL</span></div>
   <div className="stormfront-side-tag"><Layers3 size={15}/> MULTI-LAYER INTELLIGENCE <MoveUpRight size={13}/></div>
 </div>;
}
