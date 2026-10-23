import React, { useRef } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { RoundedBox, ContactShadows, Float } from '@react-three/drei'
import * as THREE from 'three'

// Original geometry, not a branded car model or customer vehicle.
function Tire({ x, z }) {
  return (
    <group position={[x, .46, z]}>
      <mesh rotation={[Math.PI / 2, 0, 0]} castShadow>
        <cylinderGeometry args={[.47, .47, .22, 28]} />
        <meshStandardMaterial color="#111b23" metalness={.18} roughness={.75} />
      </mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, 0, z > 0 ? .121 : -.121]}>
        <cylinderGeometry args={[.28, .28, .03, 28]} />
        <meshStandardMaterial color="#b5c4ca" metalness={.85} roughness={.2} />
      </mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, 0, z > 0 ? .145 : -.145]}>
        <cylinderGeometry args={[.075, .075, .04, 14]} />
        <meshStandardMaterial color="#182e38" metalness={.4} roughness={.4} />
      </mesh>
    </group>
  )
}

function Vehicle({ motionAllowed, view, paint }) {
  const car = useRef()
  useFrame(({ clock, pointer }, delta) => {
    if (!car.current || !motionAllowed) return
    const angle = view === 'front' ? -.85 : view === 'side' ? 1.15 : -.32
    const desired = angle + pointer.x * .045
    car.current.rotation.y = THREE.MathUtils.damp(car.current.rotation.y, desired, 1.4, delta)
    car.current.position.y = Math.sin(clock.elapsedTime * .65) * .022
  })
  return (
    <group ref={car} rotation={[0, -.32, 0]} scale={.83} position={[0, -.18, 0]}>
      <RoundedBox args={[4.7, .88, 2.05]} radius={.28} smoothness={5} position={[0, .97, 0]} castShadow receiveShadow>
        <meshPhysicalMaterial color={paint.body} metalness={.82} roughness={.18} clearcoat={1} clearcoatRoughness={.11} />
      </RoundedBox>
      <RoundedBox args={[2.55, .85, 1.83]} radius={.27} smoothness={5} position={[-.16, 1.67, 0]} castShadow>
        <meshPhysicalMaterial color={paint.roof} metalness={.78} roughness={.19} clearcoat={1} />
      </RoundedBox>
      {[-1, 1].map(side => (
        <React.Fragment key={side}>
          <mesh position={[-.12, 1.73, side * .924]} castShadow>
            <boxGeometry args={[2.12, .53, .018]} />
            <meshPhysicalMaterial color="#122a36" metalness={.5} roughness={.12} transparent opacity={.96} />
          </mesh>
          <mesh position={[0.18, 1.68, side * .945]}>
            <boxGeometry args={[.05, .53, .018]} />
            <meshStandardMaterial color="#c4d5d6" metalness={.85} roughness={.3} />
          </mesh>
          <mesh position={[0, 1.06, side * 1.038]}>
            <boxGeometry args={[2.7, .015, .016]} />
            <meshStandardMaterial color="#d7ba86" metalness={.85} roughness={.2} />
          </mesh>
          <Tire x={-1.55} z={side * .995} />
          <Tire x={1.52} z={side * .995} />
        </React.Fragment>
      ))}
      <RoundedBox args={[.095, .29, 1.58]} radius={.04} position={[2.36, 1.12, 0]}>
        <meshStandardMaterial color="#0b1720" metalness={.9} roughness={.25} />
      </RoundedBox>
      {[-.72,.72].map(z => (
        <group key={z} position={[2.39, 1.21, z]}>
          <RoundedBox args={[.055, .16, .4]} radius={.035}>
            <meshStandardMaterial color="#e9f8ff" emissive="#9ed9e9" emissiveIntensity={.9} />
          </RoundedBox>
          <pointLight color="#b7e5f4" intensity={.5} distance={3.5} />
        </group>
      ))}
      {[-.76,.76].map(z => (
        <mesh key={z} position={[-2.38, 1.18, z]}>
          <boxGeometry args={[.055,.13,.32]} />
          <meshStandardMaterial color="#a93630" emissive="#de544c" emissiveIntensity={.6} />
        </mesh>
      ))}
      <mesh position={[2.4, .79, 0]}>
        <boxGeometry args={[.035, .2, 1.1]} />
        <meshStandardMaterial color="#091822" metalness={.3} />
      </mesh>
      <mesh position={[0, .45, 0]}>
        <boxGeometry args={[4.18,.08,1.55]} />
        <meshStandardMaterial color="#0a1a22" metalness={.7} roughness={.3} />
      </mesh>
    </group>
  )
}

export default function ShowroomScene({ motionAllowed = true, view = 'three-quarter',
  paint = { body: '#1a3d46', roof: '#203c48' } }) {
  return (
    <Canvas
      data-testid="showroom-webgl"
      dpr={[1, 1.6]}
      camera={{ position: [6.4, 3.2, 7.8], fov: 32, near: .1, far: 80 }}
      gl={{ alpha: true, antialias: true, powerPreference: 'low-power' }}
      shadows
    >
      <color attach="background" args={['#0c202a']} />
      <fog attach="fog" args={['#0c202a', 13, 28]} />
      <ambientLight intensity={1.25} color="#d2e3e9" />
      <hemisphereLight args={['#bcd6ec', '#08212b', 2.1]} />
      <spotLight position={[2, 9, 4]} angle={.53} penumbra={.6} intensity={75} color="#f0dfbd" castShadow />
      <spotLight position={[-5, 6, -4]} angle={.8} penumbra={.7} intensity={55} color="#72b9cc" />
      <directionalLight position={[0, 7, -4]} intensity={1.9} color="#e1f4ff" />
      <Float speed={motionAllowed ? .55 : 0} rotationIntensity={0} floatIntensity={motionAllowed ? .2 : 0}>
        <Vehicle motionAllowed={motionAllowed} view={view} paint={paint} />
      </Float>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -.68, 0]} receiveShadow>
        <planeGeometry args={[80, 80]} />
        <meshStandardMaterial color="#101f29" roughness={.36} metalness={.2} />
      </mesh>
      <ContactShadows position={[0, -.655, 0]} opacity={.65} scale={12} blur={2.7} far={4.2} />
      <gridHelper args={[20, 28, '#3a5055', '#203941']} position={[0, -.645, 0]} />
    </Canvas>
  )
}
