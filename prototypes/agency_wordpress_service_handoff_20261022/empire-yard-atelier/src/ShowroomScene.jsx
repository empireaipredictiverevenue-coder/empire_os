import React, { Suspense, useEffect, useMemo, useRef } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { RoundedBox, ContactShadows, Float } from '@react-three/drei'
import * as THREE from 'three'
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js'

/** One-time local studio softbox reflections. No HDRI CDN or remote requests. */
function LocalStudioReflections() {
  const { gl, scene, invalidate } = useThree()
  useEffect(() => {
    const environment = new RoomEnvironment()
    const generator = new THREE.PMREMGenerator(gl)
    const renderTarget = generator.fromScene(environment, .04)
    scene.environment = renderTarget.texture
    scene.environmentIntensity = 2.0
    invalidate()
    return () => {
      scene.environment = null
      scene.environmentIntensity = 1
      renderTarget.dispose()
      generator.dispose()
      environment.dispose()
      invalidate()
    }
  }, [gl, scene, invalidate])
  return null
}

const StudioPBRVehicle = React.lazy(() => import('./StudioPBRVehicle.jsx'))

// Fictional original GT silhouette. No imported manufacturer model, plate or emblem.
function Tire({ x, z }) {
  const outer = z > 0 ? 1 : -1
  return <group position={[x, .46, z]}>
    <mesh rotation={[Math.PI / 2, 0, 0]} castShadow>
      <cylinderGeometry args={[.47, .47, .235, 40]} />
      <meshStandardMaterial color="#12171c" metalness={.13} roughness={.89} />
    </mesh>
    <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, 0, outer * .128]}>
      <cylinderGeometry args={[.323, .323, .035, 40]} />
      <meshStandardMaterial color="#202e37" metalness={.9} roughness={.25} />
    </mesh>
    <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, 0, outer * .15]}>
      <torusGeometry args={[.305, .019, 10, 40]} />
      <meshStandardMaterial color="#bccad0" metalness={.94} roughness={.24} />
    </mesh>
    {Array.from({ length: 7 }, (_, i) => {
      const angle = (i / 7) * Math.PI * 2
      return <mesh key={i} position={[Math.cos(angle) * .18, Math.sin(angle) * .18, outer * .164]}
        rotation={[0, 0, angle + Math.PI / 2]}>
        <boxGeometry args={[.245, .039, .021]} />
        <meshStandardMaterial color="#a3b5bd" metalness={.94} roughness={.23} />
      </mesh>
    })}
    <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, 0, outer * .18]}>
      <cylinderGeometry args={[.07, .07, .03, 24]} />
      <meshStandardMaterial color="#d2b67d" metalness={.85} roughness={.3} />
    </mesh>
  </group>
}

function SideGlass({ side }) {
  const panels = useMemo(() => {
    const rear = new THREE.Shape()
    rear.moveTo(-1.07, 1.46)
    rear.lineTo(-.99, 1.97)
    rear.lineTo(-.27, 2.05)
    rear.lineTo(-.20, 1.46)
    rear.closePath()
    const front = new THREE.Shape()
    front.moveTo(-.13, 1.46)
    front.lineTo(-.20, 2.05)
    front.lineTo(.60, 2.00)
    front.lineTo(1.08, 1.47)
    front.closePath()
    return [rear, front]
  }, [])
  return <group position={[0, 0, side * .932]}>
    {panels.map((shape, i) => <mesh key={i} castShadow={false}>
      <shapeGeometry args={[shape]} />
      <meshPhysicalMaterial color="#183745" metalness={.4} roughness={.06}
        transmission={.18} transparent opacity={.92} side={THREE.DoubleSide}
        clearcoat={1} clearcoatRoughness={.06} />
    </mesh>)}
    <mesh position={[-.17, 1.75, side * .012]}>
      <boxGeometry args={[.042, .61, .036]} />
      <meshStandardMaterial color="#d0d9d5" metalness={.84} roughness={.25} />
    </mesh>
    <mesh position={[-.15, 1.44, side * .018]}>
      <boxGeometry args={[2.37, .025, .036]} />
      <meshStandardMaterial color="#c4d8df" metalness={.9} roughness={.2} />
    </mesh>
  </group>
}

function Vehicle({ motionAllowed, view, paint }) {
  const car = useRef()
  useFrame(({ clock, pointer }, delta) => {
    if (!car.current || !motionAllowed) return
    const angle = view === 'front' ? -.85 : view === 'side' ? 1.15 : -.32
    const desired = angle + pointer.x * .045
    car.current.rotation.y = THREE.MathUtils.damp(car.current.rotation.y, desired, 1.4, delta)
    car.current.position.y = Math.sin(clock.elapsedTime * .65) * .012
  })
  return <group ref={car} rotation={[0, -.32, 0]} scale={.82} position={[0, -.18, 0]}>
    {/* Body and hood remain paint-reactive; contrasting sculpted lower sills. */}
    <RoundedBox args={[4.70, .86, 2.07]} radius={.23} smoothness={5} position={[0, .96, 0]}
      castShadow receiveShadow>
      <meshPhysicalMaterial color={paint.body} metalness={.78} roughness={.21}
        clearcoat={1} clearcoatRoughness={.09} />
    </RoundedBox>
    <RoundedBox args={[2.50, .78, 1.82]} radius={.23} smoothness={5}
      position={[-.18, 1.67, 0]} castShadow>
      <meshPhysicalMaterial color={paint.roof} metalness={.77} roughness={.18}
        clearcoat={1} clearcoatRoughness={.09} />
    </RoundedBox>
    {/* Tapered windshield and sloping rear glass, reflected by gallery lighting. */}
    {[-1, 1].map(face => <mesh key={face}
      position={[face > 0 ? 1.04 : -1.37, 1.73, 0]}
      rotation={[0, 0, face > 0 ? -.42 : .35]}>
      <boxGeometry args={[.036, .54, 1.58]} />
      <meshPhysicalMaterial color="#173746" metalness={.38} roughness={.065}
        transparent opacity={.93} clearcoat={1} />
    </mesh>)}
    <RoundedBox args={[1.72, .055, 1.47]} radius={.04}
      position={[-.25, 2.065, 0]}>
      <meshStandardMaterial color="#121f29" metalness={.5} roughness={.2} />
    </RoundedBox>
    {/* Sculpted bonnet lines; slim side mirrors, handles and shoulder trims. */}
    {[-1, 1].map(side => <React.Fragment key={side}>
      <SideGlass side={side} />
      <RoundedBox args={[1.35, .018, .025]} radius={.008}
        position={[1.52, 1.401, side * .61]} rotation={[0, 0, -.055]}>
        <meshStandardMaterial color="#93b3bd" metalness={.85} roughness={.2} />
      </RoundedBox>
      <mesh position={[-.25, 1.01, side * 1.04]}>
        <boxGeometry args={[2.95, .018, .015]} />
        <meshStandardMaterial color="#bb976c" metalness={.88} roughness={.23} />
      </mesh>
      <mesh position={[.09, .98, side * 1.05]}>
        <boxGeometry args={[.02, .67, .013]} />
        <meshStandardMaterial color="#42616c" metalness={.7} roughness={.38} />
      </mesh>
      <RoundedBox args={[.34, .12, .11]} radius={.045}
        position={[1.05, 1.40, side * 1.04]} castShadow>
        <meshPhysicalMaterial color={paint.body} metalness={.85} roughness={.17} />
      </RoundedBox>
      <RoundedBox args={[.25, .032, .025]} radius={.013}
        position={[-.47, 1.20, side * 1.054]}>
        <meshStandardMaterial color="#d9dfe0" metalness={.9} roughness={.15} />
      </RoundedBox>
      <RoundedBox args={[.25, .032, .025]} radius={.013}
        position={[.76, 1.20, side * 1.054]}>
        <meshStandardMaterial color="#d9dfe0" metalness={.9} roughness={.15} />
      </RoundedBox>
      <RoundedBox args={[2.9, .105, .115]} radius={.03}
        position={[0, .55, side * 1.008]}>
        <meshStandardMaterial color="#111e26" metalness={.48} roughness={.35} />
      </RoundedBox>
      <Tire x={-1.55} z={side * 1.005} />
      <Tire x={1.52} z={side * 1.005} />
    </React.Fragment>)}
    {/* Gallery signature grille with repeated satin-metal blades and LED outlines. */}
    <RoundedBox args={[.08, .44, 1.42]} radius={.035}
      position={[2.385, .96, 0]}>
      <meshStandardMaterial color="#0b151e" metalness={.42} roughness={.34} />
    </RoundedBox>
    {Array.from({length: 8},(_,i) => <mesh key={i} position={[2.441, .96, -.57+i*.162]}>
      <boxGeometry args={[.017, .28, .017]} />
      <meshStandardMaterial color="#91a9ae" metalness={.93} roughness={.22} />
    </mesh>)}
    {[-.78,.78].map(z => <group key={z} position={[2.395, 1.17, z]}>
      <RoundedBox args={[.038, .20, .38]} radius={.018}>
        <meshStandardMaterial color="#f3f9ff" emissive="#9dd9ef" emissiveIntensity={.8} />
      </RoundedBox>
      <mesh position={[.027, -.10, 0]}>
        <boxGeometry args={[.01, .025, .41]} />
        <meshBasicMaterial color="#a4e7ff" />
      </mesh>
    </group>)}
    {/* Rear light bars and diffuser remain original, not any manufacturer's design. */}
    {[-.77,.77].map(z=><RoundedBox key={z} args={[.055,.16,.40]} radius={.032}
      position={[-2.387,1.18,z]}>
      <meshStandardMaterial color="#b83431" emissive="#e04545" emissiveIntensity={.43} />
    </RoundedBox>)}
    <RoundedBox args={[.045,.07,1.05]} radius={.014} position={[-2.397,1.15,0]}>
      <meshBasicMaterial color="#ce3944" />
    </RoundedBox>
    <mesh position={[2.41, .72, 0]}>
      <boxGeometry args={[.05, .22, 1.12]} />
      <meshStandardMaterial color="#111b24" metalness={.4} roughness={.35} />
    </mesh>
    <mesh position={[-2.40, .71, 0]}>
      <boxGeometry args={[.055, .23, 1.14]} />
      <meshStandardMaterial color="#101a24" metalness={.35} roughness={.45} />
    </mesh>
    <mesh position={[0,.425,0]}>
      <boxGeometry args={[4.23,.08,1.58]} />
      <meshStandardMaterial color="#111c25" metalness={.4} roughness={.44} />
    </mesh>
  </group>
}

export default function ShowroomScene({ motionAllowed = true, view = 'three-quarter',
  paint = { body: '#1a3d46', roof: '#203c48' }, modelMode = 'concept',
  modelUrl, onStudioReady }) {
  return <Canvas
      data-testid="showroom-webgl"
      dpr={modelMode === 'studio' ? [1, 1] : [1, 1.5]}
      frameloop={modelMode === 'studio' ? 'demand' : 'always'}
      camera={{ position: [6.4, 3.2, 7.8], fov: 32, near: .1, far: 80 }}
      gl={{ alpha: true, antialias: modelMode !== 'studio', powerPreference: 'low-power' }}
      shadows={modelMode !== 'studio'}
    >
      <color attach="background" args={['#0c202a']} />
      {modelMode !== 'studio' && <fog attach="fog" args={['#0c202a', 13, 28]} />}
      <ambientLight intensity={1.18} color="#d2e3e9" />
      {modelMode === 'studio' && <LocalStudioReflections />}
      <hemisphereLight args={['#bcd6ec', '#08212b', 1.65]} />
      <spotLight position={[2, 9, 4]} angle={.53} penumbra={.6} intensity={modelMode === 'studio' ? 28 : 72} color="#f0dfbd" castShadow={modelMode !== 'studio'} shadow-mapSize={[512, 512]} />
      <spotLight position={[-5, 6, -4]} angle={.8} penumbra={.7} intensity={modelMode === 'studio' ? 20 : 48} color="#72b9cc" />
      <directionalLight position={[0, 7, -4]} intensity={1.6} color="#e1f4ff" />
      <Suspense fallback={<Vehicle motionAllowed={motionAllowed} view={view} paint={paint} />}>
        {modelMode === 'studio' && modelUrl
          ? <StudioPBRVehicle modelUrl={modelUrl} motionAllowed={motionAllowed}
              view={view} paint={paint} onReady={onStudioReady} />
          : <Float speed={motionAllowed ? .48 : 0} rotationIntensity={0}
              floatIntensity={motionAllowed ? .13 : 0}>
              <Vehicle motionAllowed={motionAllowed} view={view} paint={paint} />
            </Float>}
      </Suspense>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -.68, 0]} receiveShadow>
        <planeGeometry args={[60, 60]} />
        {modelMode === 'studio'
          ? <meshBasicMaterial color="#0b1f29" toneMapped={false} />
          : <meshStandardMaterial color="#101f29" roughness={.38} metalness={.2} />}
      </mesh>
      {modelMode !== 'studio' && <ContactShadows position={[0, -.655, 0]} opacity={.55} scale={12} blur={2.5} far={4.2} />}
      <gridHelper args={[20, 28, '#3a5055', '#203941']} position={[0, -.645, 0]} />
    </Canvas>
}
