"use client";
import {useEffect,useMemo,useRef} from "react";
import * as THREE from "three";
const vertex=`varying vec2 vUv; varying vec3 vColor; varying vec3 vNormal;
void main(){vUv=uv;
#ifdef USE_INSTANCING_COLOR
vColor=instanceColor;
#else
vColor=vec3(.1,.6,1.);
#endif
vNormal=normalize(normalMatrix*mat3(instanceMatrix)*normal);gl_Position=projectionMatrix*modelViewMatrix*instanceMatrix*vec4(position,1.);}`;
const fragment=`varying vec2 vUv;varying vec3 vColor;varying vec3 vNormal;
void main(){vec2 cell=fract(vUv*vec2(3.,8.));float windows=step(.22,cell.x)*step(cell.x,.62)*step(.3,cell.y)*step(cell.y,.62);float floorId=floor(vUv.y*8.);float lit=step(.28,fract(sin(floorId*13.7+floor(vUv.x*3.)*47.2)*43758.5));float edge=step(vUv.x,.025)+step(.975,vUv.x);float face=.3+.7*max(0.,dot(normalize(vNormal),normalize(vec3(-.6,.8,1.))));float roof=step(.7,abs(vNormal.y));vec3 c=mix(vec3(.028,.055,.08),vec3(.09,.15,.19),roof)*face+vColor*(windows*lit*.45*(1.-roof)+edge*.14);gl_FragColor=vec4(c,1.);
#include <colorspace_fragment>
}`;
/** Original procedural architecture; no purchased models, metrics or live activity. */
export default function IntelligenceCity({selected,entry}:{selected:number;entry:number}){
 const mesh=useRef<THREE.InstancedMesh>(null);
 const buildings=useMemo(()=>Array.from({length:150},(_,i)=>{const district=Math.floor(i/30),n=i%30;const x=(district-2)*2.05+(n%5-2)*.32;const z=Math.floor(n/5)*.57-2.2;const h=.3+Math.abs(Math.sin(i*7.31))*(.65+1.3*Math.exp(-Math.pow((n%5-2)/1.3,2)))+(n===12?.6:0);return {district,x,z,h,w:.23+Math.abs(Math.cos(i*3))*.07}}),[]);
 useEffect(()=>{if(!mesh.current)return;const o=new THREE.Object3D(),c=new THREE.Color();buildings.forEach((b,i)=>{for(let tier=0;tier<3;tier++){const h=tier===0?b.h:tier===1?b.h*.22:.055;const base=tier===0?0:tier===1?b.h:b.h*1.22;const w=b.w*(tier===0?1:tier===1?.72:.5);o.position.set(b.x,-2.23+base+h/2,b.z);o.scale.set(w,h,tier===0?b.w*1.18:w);o.updateMatrix();const index=i*3+tier;mesh.current!.setMatrixAt(index,o.matrix);c.set(b.district===selected?"#e8b979":i%4===0?"#b3d9e5":"#4289b0");mesh.current!.setColorAt(index,c)}});mesh.current.instanceMatrix.needsUpdate=true;if(mesh.current.instanceColor)mesh.current.instanceColor.needsUpdate=true},[buildings,selected]);
 return <group scale={1+entry*.15}>
 <mesh position={[0,-2.28,0]}><boxGeometry args={[11.2,.1,6.8]}/><meshPhysicalMaterial color="#12344e" emissive="#061526" emissiveIntensity={.6} metalness={.25} roughness={.32} clearcoat={1}/></mesh>
 <instancedMesh ref={mesh} args={[undefined,undefined,buildings.length*3]} frustumCulled={false}><boxGeometry args={[1,1,1]}/><shaderMaterial vertexShader={vertex} fragmentShader={fragment}/></instancedMesh>
 {Array.from({length:7},(_,i)=><mesh key={"street"+i} position={[0,-2.215,-2.5+i*.83]}><boxGeometry args={[10.8,.014,.11]}/><meshBasicMaterial color={i%3===0?"#5d503d":"#12334b"} transparent opacity={.5+entry*.3}/></mesh>)}
 {[0,1,2,3,4].map(i=><group key={i} position={[(i-2)*2.05,0,0]}>
 <mesh position={[0,-2.20,0]}><boxGeometry args={[.018,.012,6.4]}/><meshBasicMaterial color={i===selected?"#ffe0a2":"#37bfff"}/></mesh>
 <mesh position={[0,-.72,-1.05]}><boxGeometry args={[.38,2.9,.38]}/><meshPhysicalMaterial color="#225775" emissive="#061b2a" metalness={.3} roughness={.22} clearcoat={1}/></mesh>
 <mesh position={[0,-.72,-.852]}><boxGeometry args={[.032,2.9,.012]}/><meshBasicMaterial color={i===selected?"#ffdf9a":"#62daff"}/></mesh>
 <mesh position={[0,.9,-1.05]}><coneGeometry args={[.12,.34,4]}/><meshBasicMaterial color={i===selected?"#ffdf9a":"#62daff"}/></mesh>
 <mesh rotation={[Math.PI/2,0,0]} position={[0,-2.16,1.8]}><torusGeometry args={[.38,.018,6,48]}/><meshBasicMaterial color={i===selected?"#ffcf87":"#168cff"}/></mesh>
 </group>)}
 </group>;
}
