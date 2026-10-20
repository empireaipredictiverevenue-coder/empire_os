"use client";
import {useEffect,useLayoutEffect,useMemo,useRef} from "react";
import {useFrame} from "@react-three/fiber";
import * as THREE from "three";

type Block=[number,number,number,number,number,number];
function Batch({blocks,color,light=false,glass=false,floor=false}:{blocks:Block[];color:string;light?:boolean;glass?:boolean;floor?:boolean}){
 const mesh=useRef<THREE.InstancedMesh>(null);
 useLayoutEffect(()=>{
  const o=new THREE.Object3D();
  blocks.forEach(([x,y,z,w,h,d],i)=>{o.position.set(x,y,z);o.scale.set(w,h,d);o.updateMatrix();mesh.current?.setMatrixAt(i,o.matrix)});
  if(mesh.current){mesh.current.instanceMatrix.needsUpdate=true;mesh.current.computeBoundingSphere()}
 },[blocks]);
 return <instancedMesh castShadow={!light&&!glass} receiveShadow={!light&&!glass} ref={mesh} args={[undefined,undefined,blocks.length]} frustumCulled={false}>
 <boxGeometry args={[1,1,1]}/>
 {light?<meshBasicMaterial color={color}/>:glass?<meshPhysicalMaterial color={color} transparent opacity={.16} depthWrite={false} roughness={.12} metalness={.2} clearcoat={1}/>:<meshStandardMaterial color={color} roughness={floor?.86:.38} metalness={floor?.08:.65} envMapIntensity={floor?.12:.7}/>}
 </instancedMesh>;
}
/** Original instanced atrium. All activity is illustrative; no live system data. */
function StructuralPortal({z}:{z:number}){
 const geometry=useMemo(()=>{
  // Chamfered load-bearing frame, not a second renderer or imported model.
  const outline=(w:number,h:number,c:number)=>[
   [-w+c,-h],[w-c,-h],[w,-h+c],[w,h-c],[w-c,h],[-w+c,h],[-w,h-c],[-w,-h+c]
  ].map(([x,y])=>new THREE.Vector2(x,y));
  const shape=new THREE.Shape(outline(3.57,3.62,.52));
  shape.holes.push(new THREE.Path(outline(3.35,3.4,.5).reverse()));
  const g=new THREE.ExtrudeGeometry(shape,{depth:.32,bevelEnabled:true,bevelSize:.035,bevelThickness:.035,bevelSegments:2,steps:1});
  return g;
 },[]);
 useEffect(()=>()=>geometry.dispose(),[geometry]);
 return <group position={[0,1.55,z]}>
  <mesh geometry={geometry} castShadow receiveShadow><meshStandardMaterial color="#263d51" metalness={.72} roughness={.3}/></mesh>
  {[-1,1].map(side=><group key={side}>
   <mesh position={[side*3.39,0,.35]}><boxGeometry args={[.028,5.9,.025]}/><meshBasicMaterial color="#72c9f4"/></mesh>
   <mesh position={[side*3.44,-2.7,.32]}><boxGeometry args={[.16,.55,.15]}/><meshStandardMaterial color="#9d7944" metalness={.72} roughness={.35}/></mesh>
  </group>)}
 </group>;
}
export default function IntelligenceInfrastructure({selected}:{selected:number;entry:number}){
 const packets=useRef<THREE.InstancedMesh>(null);
 const lamp=useRef<THREE.PointLight>(null);
 const object=useMemo(()=>new THREE.Object3D(),[]);
 const architecture=useMemo(()=>{
  const steel:Block[]=[],dark:Block[]=[],blue:Block[]=[],gold:Block[]=[],glass:Block[]=[],panels:Block[]=[],trim:Block[]=[],floor:Block[]=[];
  // A long, connected architectural interior, viewed from inside its entrance.
  dark.push([0,-2.05,-7,13,.3,30],[0,6,-7,13,.2,30],[0,1.8,-21.8,13,7.4,.25]);
  for(const side of [-1,1]){
   dark.push([side*6.2,1.8,-7,.2,7.5,30]);
   steel.push([side*4.75,2.8,-7,2.7,.18,29]);
   glass.push([side*3.43,3.3,-7,.035,.88,28]);
   blue.push([side*3.42,2.82,-7,.03,.025,28],[side*2.6,-1.87,-7,.035,.025,28]);
   gold.push([side*3.42,3.77,-7,.035,.025,28]);
   for(let z=6;z>=-21;z-=3){
    steel.push([side*3.5,1.7,z,.17,7.3,.22],[side*5.9,1.7,z,.2,7.3,.22]);
    blue.push([side*3.39,1.7,z,.025,7.1,.04]);
    for(const y of [-.55,4.1]){
     dark.push([side*5.1,y,z-1,.95,2.65,1.6]);
     steel.push([side*4.59,y,z-1,.055,2.7,1.65]);
     // Recessed server cassettes, mounting rails and door handles give scale.
     trim.push([side*4.54,y,z-1.77,.07,2.6,.045],[side*4.54,y,z-.23,.07,2.6,.045]);
     trim.push([side*4.48,y+.15,z-.34,.06,.32,.055]);
     for(let u=0;u<10;u++){
      panels.push([side*4.53,y-1.1+u*.25,z-1,.035,.18,1.36]);
      for(let vent=0;vent<5;vent++)dark.push([side*4.50,y-1.1+u*.25,z-1.5+vent*.19,.025,.035,.11]);
     }
     for(let n=0;n<10;n++){
      blue.push([side*4.49,y-1.12+n*.25,z-.49,.02,.018,.16]);
      gold.push([side*4.49,y-1.1+n*.25,z-.36,.025,.025,.04]);
     }
    }
    glass.push([side*2.4,-1.87,z-1,1.7,.04,2.65]);
    steel.push([side*3.4,-1.35,z,.04,1,.04],[side*3.4,-.84,z-1.5,.04,.045,3]);
   }
  }
  // Ceiling service trays and segmented raised-floor panels remain instanced.
  for(const side of [-1,1]){
   steel.push([side*2.8,4.7,-7,.5,.12,28]);
   gold.push([side*2.8,4.62,-7,.12,.02,28]);
  }
  for(let z=6;z>=-21;z-=1.5){
   for(const x of [-1.5,0,1.5])floor.push([x,-1.91,z-1,1.46,.035,1.46]);
  }
  // Fine ribs, bridge soffits, upper galleries and continuous data channels.
  for(let z=6;z>=-21;z-=3){
   steel.push([0,5.35,z,7.2,.2,.22],[0,-1.96,z,7.2,.06,.12]);
   gold.push([0,5.21,z,7,.025,.035]);
  }
  for(const z of [-2,-11]){
   steel.push([0,2.8,z,7,.12,.65],[0,3.77,z-.3,7,.035,.035]);
   glass.push([0,3.3,z-.3,7,.88,.025]);
  }
  for(let x=-1.5;x<=1.5;x+=.75){
   blue.push([x,-1.89,-7,.015,.025,28]);
  }
  // Clear glass above the central channel leaves the luminous paths visible.
  glass.push([0,-1.85,-7,3.3,.05,28]);
  // Recessed wall panels and mechanical ceiling baffles establish human scale.
  for(let z=5;z>=-20;z-=3){
   for(const side of [-1,1]){
    panels.push([side*6.04,1.7,z-1,.08,6.8,2.65]);
    trim.push([side*5.98,1.7,z-2.37,.06,6.8,.025]);
    dark.push([side*2.85,5.65,z-1,.65,.32,2.5]);
    for(let rib=0;rib<8;rib++)steel.push([side*2.85,5.44,z-2.1+rib*.28,.68,.07,.045]);
   }
  }
  return {steel,dark,blue,gold,glass,panels,trim,floor};
 },[]);
 useFrame((state,delta)=>{
  if(lamp.current)lamp.current.position.z=THREE.MathUtils.damp(lamp.current.position.z,4-selected*5,4,Math.min(delta,.08));
  if(packets.current){
   for(let i=0;i<28;i++){
    object.position.set(((i%7)-3)*.5,-1.80,7-((state.clock.elapsedTime*1.5+i*1.07)%28));
    object.scale.set(.045,.035,.28);object.updateMatrix();packets.current.setMatrixAt(i,object.matrix);
   }
   packets.current.instanceMatrix.needsUpdate=true;
  }
 });
 const glow=useMemo(()=>{
  const size=64,data=new Uint8Array(size*size*4);
  for(let y=0;y<size;y++)for(let x=0;x<size;x++){
   const d=Math.hypot((x+.5)/size*2-1,(y+.5)/size*2-1);
   const i=(y*size+x)*4;data[i]=data[i+1]=data[i+2]=255;
   data[i+3]=Math.round(Math.pow(Math.max(0,1-d),3)*150);
  }
  const t=new THREE.DataTexture(data,size,size);t.needsUpdate=true;return t;
 },[]);
 useEffect(()=>()=>glow.dispose(),[glow]);
 const goldMaterial=useMemo(()=>new THREE.MeshStandardMaterial({color:"#bd8b48",metalness:.7,roughness:.24,emissive:"#704719",emissiveIntensity:.3}),[]);
 useEffect(()=>()=>goldMaterial.dispose(),[goldMaterial]);
 return <group>
 {[5,-5,-15].map(z=><StructuralPortal key={z} z={z}/>)}
 <Batch blocks={architecture.dark} color="#081321"/>
 <Batch blocks={architecture.steel} color="#223346"/>
 <Batch blocks={architecture.panels} color="#122334"/>
 <Batch blocks={architecture.floor} color="#081522" floor/>
 <Batch blocks={architecture.trim} color="#6e8394"/>
 <Batch blocks={architecture.blue} color="#309fff" light/>
 <Batch blocks={architecture.gold} color="#e4b472" light/>
 <Batch blocks={architecture.glass} color="#62bfff" glass/>
 <instancedMesh ref={packets} args={[undefined,undefined,28]} frustumCulled={false}><boxGeometry/><meshBasicMaterial color="#c6f4ff"/></instancedMesh>
 {/* Each chapter has a distinct illuminated threshold, synchronised with HTML. */}
 {[0,1,2,3,4].map(i=><group key={i} position={[0,0,4-i*5]}>
  <mesh position={[0,-1.82,0]}><boxGeometry args={[6.6,.025,.045]}/><meshBasicMaterial color={selected===i?"#ffe0a3":"#195b8b"}/></mesh>
  {[-1,1].map(side=><group key={side} position={[side*3.46,-.15,0]}>
   <mesh><boxGeometry args={[.06,.75,.7]}/><meshStandardMaterial color="#183b59" emissive={selected===i?"#c58c3e":"#09539d"} emissiveIntensity={selected===i?.8:.2}/></mesh>
   <mesh position={[-side*.04,0,0]}><boxGeometry args={[.02,.025,.52]}/><meshBasicMaterial color={selected===i?"#ffda98":"#59caff"}/></mesh>
  </group>)}
 </group>)}
 {/* Soft architectural light spill; original procedural falloff, never live metrics. */}
 <sprite position={[0,1.7,-20.6]} scale={[9,10,1]}><spriteMaterial map={glow} color="#ffbd69" transparent opacity={.7} blending={THREE.AdditiveBlending} depthWrite={false}/></sprite>
 {[-1,1].map(side=><sprite key={side} position={[side*3.25,3.9,-8]} scale={[3.5,7,1]}><spriteMaterial map={glow} color="#248bff" transparent opacity={.32} blending={THREE.AdditiveBlending} depthWrite={false}/></sprite>)}
 {/* Warm evidence vault: the destination, not a revenue counter. */}
 <group position={[0,0,-20]}>
  <mesh position={[0,-1.55,0]} castShadow receiveShadow><cylinderGeometry args={[2.35,2.55,.55,48]}/><meshStandardMaterial color="#112337" metalness={.7} roughness={.35}/></mesh>
  <mesh position={[0,4.1,0]} castShadow receiveShadow><cylinderGeometry args={[2.3,2.3,.22,48]}/><meshStandardMaterial color="#21384a" metalness={.75} roughness={.3}/></mesh>
  {[-1.27,3.95].map(y=><mesh key={y} position={[0,y,0]} rotation={[Math.PI/2,0,0]}><torusGeometry args={[2.14,.025,8,64]}/><meshBasicMaterial color="#f2cc86"/></mesh>)}
  {[-1.2,-.6,0,.6,1.2].map((x,i)=><group key={i} position={[x,1.35,0]}>
   <mesh material={goldMaterial} castShadow receiveShadow><boxGeometry args={[.08,4.8,.9]}/></mesh>
   <mesh position={[.12,0,0]}><boxGeometry args={[.16,4.65,.78]}/><meshPhysicalMaterial color="#83c7e2" metalness={.2} roughness={.18} transparent opacity={.3} depthWrite={false}/></mesh>
   {[-1.5,-.75,0,.75,1.5].map(y=><mesh key={y} position={[.12,y,.4]}><boxGeometry args={[.17,.015,.015]}/><meshBasicMaterial color="#c8e9f4"/></mesh>)}
  </group>)}
  <mesh position={[0,1.35,0]}><cylinderGeometry args={[2.12,2.12,5.2,48,1,true]}/><meshPhysicalMaterial color="#80bad2" transparent opacity={.07} depthWrite={false} roughness={.2} side={THREE.DoubleSide}/></mesh>
 </group>
 <pointLight ref={lamp} position={[0,1,4]} color="#6ac8ff" intensity={16} distance={12}/>
 <pointLight position={[0,2,-19]} color="#ffd08c" intensity={18} distance={18}/>
 <pointLight position={[-3,3,-5]} color="#2c8fff" intensity={18} distance={16}/>
 <pointLight position={[3,3,-12]} color="#71bfff" intensity={18} distance={16}/>
 </group>;
}
