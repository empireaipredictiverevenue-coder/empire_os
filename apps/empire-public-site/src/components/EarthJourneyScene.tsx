"use client";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useTexture } from "@react-three/drei";
import { Suspense, useEffect, useLayoutEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import IntelligenceInfrastructure from "./IntelligenceInfrastructure";
import { createScrollWorldFrame, sampleScrollWorld } from "./scroll-world-director";

type Props = {selected:number; progress?:number; hero?:boolean; entry?:number; onLost:()=>void; onReady?:()=>void; onSlow?:()=>void};
const vertex = `varying vec2 vUv; varying vec3 vNormal; varying vec3 vView;
void main(){vUv=uv;vec4 p=modelViewMatrix*vec4(position,1.);vNormal=normalize(normalMatrix*normal);vView=normalize(-p.xyz);gl_Position=projectionMatrix*p;}`;
const earthFragment = `uniform sampler2D dayMap; uniform sampler2D nightMap; varying vec2 vUv; varying vec3 vNormal; varying vec3 vView;
void main(){vec3 n=normalize(vNormal);float sun=dot(n,normalize(vec3(-.6,.35,-.2)));
vec3 day=texture2D(dayMap,vUv).rgb;vec3 night=texture2D(nightMap,vUv).rgb;
// A soft front-side fill keeps continents readable without losing the night lights.
float lit=smoothstep(-.08,.48,sun);vec3 color=pow(day,vec3(2.2))*(.035+1.1*lit)+pow(night,vec3(2.2))*vec3(1.3,1.08,.72)*(1.-lit)*3.4;
float rim=pow(1.-max(0.,dot(n,normalize(vView))),3.);
color+=vec3(.015,.18,.65)*rim*.85;gl_FragColor=vec4(color,1.);
#include <colorspace_fragment>
}`;
const airFragment = `varying vec3 vNormal;varying vec3 vView;void main(){float f=pow(1.-abs(dot(normalize(vNormal),normalize(vView))),3.8);gl_FragColor=vec4(.07,.46,1.,f*.5);}`;
function geo(lat:number,lon:number,r=1.84){const a=THREE.MathUtils.degToRad(lat),b=THREE.MathUtils.degToRad(lon+180);return new THREE.Vector3(-r*Math.cos(a)*Math.cos(b),r*Math.sin(a),r*Math.cos(a)*Math.sin(b));}
function Globe({selected,onReady}:{selected:number;onReady?:()=>void}) {
 const [day,night,clouds]=useTexture(["/art/earth/day.jpg","/art/earth/night.jpg","/art/earth/clouds.webp"]);
 useEffect(()=>{onReady?.()},[onReady]);
 const shell=useRef<THREE.Group>(null), cloud=useRef<THREE.Mesh>(null);
 const pulses=useRef<Array<THREE.Mesh|null>>([]);
 const routes=useMemo(()=>{
  const hub=geo(51.5,-.12);
  return [[40.7,-74],[25.2,55.3],[1.3,103.8],[35.7,139.7],[-33.9,151.2],[37.8,-122.4],[-23.5,-46.6],[28.6,77.2]].map(([lat,lon])=>{
   const end=geo(lat,lon);const middle=hub.clone().add(end).normalize().multiplyScalar(2.25+hub.distanceTo(end)*.15);
   return new THREE.QuadraticBezierCurve3(hub,middle,end);
  });
 },[]);
 const tubes=useMemo(()=>routes.map(c=>new THREE.TubeGeometry(c,32,.006,4,false)),[routes]);
 useEffect(()=>()=>tubes.forEach(t=>t.dispose()),[tubes]);
 const uniforms=useMemo(()=>({dayMap:{value:day},nightMap:{value:night}}),[day,night]);
 useFrame((state,delta)=>{
  if(shell.current) shell.current.rotation.y=THREE.MathUtils.damp(shell.current.rotation.y,-1.5+selected*.12+Math.sin(state.clock.elapsedTime*.035)*.1,2,Math.min(delta,.05));
  if(cloud.current) cloud.current.rotation.y+=Math.min(delta,.05)*.009;
  pulses.current.forEach((p,i)=>{if(p)p.position.copy(routes[i].getPoint((state.clock.elapsedTime*.075+i*.13)%1));});
 });
 return <group ref={shell} rotation={[.12,-1.5,-.18]}>
  <mesh><sphereGeometry args={[1.8,64,40]}/><shaderMaterial vertexShader={vertex} fragmentShader={earthFragment} uniforms={uniforms}/></mesh>
  <mesh ref={cloud}><sphereGeometry args={[1.818,64,40]}/><meshStandardMaterial color="#dceaff" alphaMap={clouds} transparent opacity={.16} depthWrite={false}/></mesh>
  <mesh scale={1.018}><sphereGeometry args={[1.8,64,40]}/><shaderMaterial vertexShader={vertex} fragmentShader={airFragment} transparent depthWrite={false} blending={THREE.AdditiveBlending}/></mesh>
  {routes.map((curve,i)=><group key={i}>
   <mesh geometry={tubes[i]}><meshBasicMaterial color={i%5===selected?"#ffe1a1":"#239cff"} transparent opacity={i%5===selected?.95:.55} toneMapped={false}/></mesh>
   <mesh ref={node=>{pulses.current[i]=node}}><sphereGeometry args={[.025,8,8]}/><meshBasicMaterial color="#e1f6ff" toneMapped={false}/></mesh>
   <mesh position={curve.v2}><sphereGeometry args={[.024,8,8]}/><meshBasicMaterial color="#ffd28a" toneMapped={false}/></mesh>
  </group>)}
  <mesh position={geo(51.5,-.12)}><sphereGeometry args={[.055,12,12]}/><meshBasicMaterial color="#b9edff" toneMapped={false}/></mesh>
 </group>;
}
/** Original studio reflection rig, baked once; no remote HDR or per-frame capture. */
function ArchitecturalReflections(){
 const {gl,scene}=useThree();
 useLayoutEffect(()=>{
  const rig=new THREE.Scene();
  const geometry=new THREE.BoxGeometry(1,1,1);
  const materials:THREE.MeshBasicMaterial[]=[];
  const panel=(color:string,intensity:number,position:[number,number,number],scale:[number,number,number])=>{
   const material=new THREE.MeshBasicMaterial({color:new THREE.Color(color).multiplyScalar(intensity)});
   materials.push(material);const mesh=new THREE.Mesh(geometry,material);
   mesh.position.set(...position);mesh.scale.set(...scale);rig.add(mesh);
  };
  panel("#c9e9ff",2,[0,7,0],[5,.2,18]);
  panel("#298dff",3,[-7,1,0],[.2,4,18]);
  panel("#74bfff",2,[7,2,0],[.2,3,18]);
  panel("#ffd198",4,[0,2,-10],[5,5,.2]);
  panel("#d5edff",1,[0,1,10],[4,4,.2]);
  const baker=new THREE.PMREMGenerator(gl);
  const reflection=baker.fromScene(rig,.06,.1,40,{size:128});
  const previous=scene.environment;const previousIntensity=scene.environmentIntensity;
  scene.environment=reflection.texture;scene.environmentIntensity=.85;
  geometry.dispose();materials.forEach(m=>m.dispose());baker.dispose();
  return()=>{scene.environment=previous;scene.environmentIntensity=previousIntensity;reflection.dispose()};
 },[gl,scene]);
 return null;
}
/** Original bevelled console geometry. Camera crosses this same aperture. */
function ConsolePortal({progress}:{progress:number}){
 const aspect=useThree(state=>state.size.width/state.size.height);
 const aperture=useRef(aspect);
 if(progress===0)aperture.current=aspect;
 const width=Math.max(2.6,3.55*aperture.current),height=3.55;
 const frame=useMemo(()=>{
  // A continuous rounded bezel avoids four overlapping, mirror-bright box ends.
  const rounded=(w:number,h:number,r:number)=>{
   const p=new THREE.Shape(),x=-w/2,y=-h/2;
   p.moveTo(x+r,y);p.lineTo(x+w-r,y);p.quadraticCurveTo(x+w,y,x+w,y+r);
   p.lineTo(x+w,y+h-r);p.quadraticCurveTo(x+w,y+h,x+w-r,y+h);
   p.lineTo(x+r,y+h);p.quadraticCurveTo(x,y+h,x,y+h-r);
   p.lineTo(x,y+r);p.quadraticCurveTo(x,y,x+r,y);
   return p;
  };
  const shape=rounded(width+.12,height+.12,.19);
  shape.holes.push(rounded(width-.12,height-.12,.12));
  const geometry=new THREE.ExtrudeGeometry(shape,{depth:.16,steps:1,bevelEnabled:true,bevelSegments:3,bevelSize:.025,bevelThickness:.025,curveSegments:10});
  geometry.translate(0,0,-.08);
  return geometry;
 },[width,height]);
 useEffect(()=>()=>frame.dispose(),[frame]);
 return <group position={[0,.1,.9]} rotation={[-.035*(1-progress),-.16*(1-progress),.045*(1-progress)]}>
  <mesh geometry={frame}><meshPhysicalMaterial color="#092039" metalness={.68} roughness={.36} envMapIntensity={.45} clearcoat={.65} clearcoatRoughness={.25}/></mesh>
  {[[0,height/2,width-.28,.012],[0,-height/2,width-.28,.012],[-width/2,0,.012,height-.28],[width/2,0,.012,height-.28]].map(([x,y,w,h],i)=><mesh key={i} position={[x,y,.105]}><boxGeometry args={[w,h,.008]}/><meshBasicMaterial color={i===1?"#c99952":"#259ee8"} toneMapped={false}/></mesh>)}
  <mesh position={[0,0,-.02]}><planeGeometry args={[width-.14,height-.14]}/><meshPhysicalMaterial color="#70bfff" transparent opacity={.035*(1-progress)} metalness={.15} roughness={.18} clearcoat={.7} depthWrite={false}/></mesh>
 </group>;
}
function Journey({selected,progress=0,hero=false,entry=hero?0:1,onLost,onReady,onSlow}:Props){
 const {gl,setDpr,scene}=useThree();
 const infrastructureVisible=entry>.08;
 useEffect(()=>{
  // Architecture is static: bake its directional shadow once on entry, not every frame.
  gl.shadowMap.autoUpdate=false;gl.shadowMap.needsUpdate=true;
  return()=>{gl.shadowMap.autoUpdate=true};
 },[gl,infrastructureVisible]);
 useEffect(()=>{
  const previous=scene.fog;scene.fog=new THREE.Fog("#020817",18,48);
  return()=>{scene.fog=previous};
 },[scene]);
 // Match the HTML mobile composition, not the changing canvas aspect ratio.
 const wide=typeof window!=="undefined"&&window.innerWidth>600;
 const goal=useMemo(()=>new THREE.Vector3(),[]);
 const look=useMemo(()=>new THREE.Vector3(0,.1,0),[]);
 const lookGoal=useMemo(()=>new THREE.Vector3(),[]);
 const travelLight=useRef<THREE.PointLight>(null);
 const frameState=useRef(createScrollWorldFrame());
 const telemetry=useRef({next:0,chapter:-1});
 const cool=useMemo(()=>new THREE.Color("#43adff"),[]);
 const warm=useMemo(()=>new THREE.Color("#ffbd70"),[]);
 const frames=useRef({time:0,count:0,adapted:false,reported:false});

 useEffect(()=>{const lost=(e:Event)=>{e.preventDefault();onLost()};gl.domElement.addEventListener("webglcontextlost",lost);return()=>gl.domElement.removeEventListener("webglcontextlost",lost)},[gl,onLost,onReady]);
 useFrame((state,delta)=>{
  // One scroll-driven world and camera, independent of clicked chapter selection.
  // Scrubbing backwards returns to exactly the same authored spatial position.
  const frame=sampleScrollWorld(progress,entry,goal,lookGoal,frameState.current);
  state.camera.position.lerp(goal,1-Math.exp(-Math.min(delta,.08)*5));
  look.lerp(lookGoal,1-Math.exp(-Math.min(delta,.08)*5));state.camera.lookAt(look);
  if(travelLight.current){
   travelLight.current.position.z=2-8*frame.entry-12*frame.warmth;
   travelLight.current.color.lerpColors(cool,warm,frame.warmth);
   travelLight.current.intensity=12+6*frame.warmth;
  }
  // Diagnostics are for QA, not animation: avoid writing DOM attributes 60x/s.
  // Update at chapter changes and <=4Hz while the camera continues every frame.
  const diagnostic=telemetry.current;
  if(frame.chapter!==diagnostic.chapter||state.clock.elapsedTime>=diagnostic.next){
   diagnostic.chapter=frame.chapter;
   diagnostic.next=state.clock.elapsedTime+.25;
   gl.domElement.dataset.camera=[state.camera.position.x,state.camera.position.y,state.camera.position.z].map(n=>n.toFixed(3)).join(",");
   gl.domElement.dataset.scrollWorldProgress=frame.progress.toFixed(3);
   gl.domElement.dataset.scrollWorldChapter=String(frame.chapter);
  }
  const f=frames.current;f.time+=delta;f.count++;
  if(f.time>4&&!f.adapted){f.adapted=true;if(f.count/f.time<24)setDpr(onSlow ? .75 : 1);f.time=0;f.count=0;}
  else if(f.adapted&&f.time>6&&!f.reported){f.reported=true;if(f.count/f.time<12)onSlow?.();}
 });
 const stars=useMemo(()=>{const a=new Float32Array(360);for(let i=0;i<120;i++){a[i*3]=Math.sin(i*73.2)*12;a[i*3+1]=Math.cos(i*21.3)*8;a[i*3+2]=-6-Math.abs(Math.sin(i))*8}return a},[]);
 return <>
  <ArchitecturalReflections/><ambientLight intensity={.22}/><hemisphereLight args={["#aadfff","#111b27",.4]}/><directionalLight castShadow position={[-5,9,6]} intensity={1.8} color="#b0dfff" shadow-mapSize={[1024,1024]} shadow-camera-left={-20} shadow-camera-right={20} shadow-camera-top={16} shadow-camera-bottom={-24} shadow-camera-near={.5} shadow-camera-far={65} shadow-bias={-.00015} shadow-normalBias={.035}/><pointLight ref={travelLight} position={[4,2,2-8*entry]} intensity={12} color="#43adff"/>
  <points><bufferGeometry><bufferAttribute attach="attributes-position" args={[stars,3]}/></bufferGeometry><pointsMaterial size={.025} color="#a4caff" transparent opacity={.65}/></points>
  <ConsolePortal progress={entry}/>
  {entry<.3&&<mesh position={[0,0,-3]}><planeGeometry args={[40,30]}/><meshBasicMaterial color="#020817" transparent opacity={1-THREE.MathUtils.smoothstep(entry,.04,.3)} depthWrite={false}/></mesh>}
  <group visible={entry>.08} position={[0,0,-8]}><IntelligenceInfrastructure selected={selected} entry={entry}/></group>
  <group position={[0,0,-8*entry]}>
  <group position={[(wide?1.45:0)*(1-entry),entry*1.2,-entry*1.6]} scale={Math.max(.001,(wide?.96:.94)*(1-THREE.MathUtils.smoothstep(entry,.25,.92)))}><Suspense fallback={null}><Globe selected={selected} onReady={onReady}/></Suspense></group>
  </group>
 </>;
}
export default function EarthJourneyScene(props:Props){
 return <Canvas shadows="soft" frameloop="always" dpr={[1,1.5]} camera={{position:[0,.25,6.9],fov:43,near:.1,far:40}} gl={{alpha:true,antialias:true,powerPreference:"default"}}><Journey {...props}/></Canvas>;
}
