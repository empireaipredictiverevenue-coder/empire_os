"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { Float, Line, OrbitControls, Stars } from "@react-three/drei";
import * as THREE from "three";
import { useMemo, useRef } from "react";

const NODES = [
  [-1.8, 0.95, 0.65],
  [-0.8, 1.45, -0.85],
  [0.55, 1.25, 0.95],
  [1.65, 0.45, -0.7],
  [1.35, -0.85, 0.75],
  [0.15, -1.5, -0.65],
  [-1.35, -0.85, 0.9],
] as const;

function Network() {
  const group = useRef<THREE.Group>(null);
  const paths = useMemo(
    () =>
      NODES.map((node, index) => {
        const next = NODES[(index + 2) % NODES.length];
        return [
          new THREE.Vector3(...node),
          new THREE.Vector3(0, 0, 0),
          new THREE.Vector3(...next),
        ];
      }),
    [],
  );

  useFrame((state) => {
    if (!group.current) return;
    const maxScroll = Math.max(
      1,
      document.body.scrollHeight - window.innerHeight,
    );
    const scroll = window.scrollY / maxScroll;
    group.current.rotation.y =
      state.clock.elapsedTime * 0.08 + scroll * 2.35;
    group.current.rotation.x =
      Math.sin(state.clock.elapsedTime * 0.18) * 0.08;
  });

  return (
    <group ref={group}>
      <mesh>
        <sphereGeometry args={[1.82, 64, 64]} />
        <meshPhysicalMaterial
          color="#050807"
          roughness={0.38}
          metalness={0.72}
          transmission={0.05}
          transparent
          opacity={0.82}
        />
      </mesh>

      <mesh>
        <sphereGeometry args={[1.87, 36, 36]} />
        <meshBasicMaterial
          color="#7CFF00"
          wireframe
          transparent
          opacity={0.09}
        />
      </mesh>

      {NODES.map((position, index) => (
        <Float
          speed={1.2 + index * 0.08}
          rotationIntensity={0}
          floatIntensity={0.15}
          key={index}
        >
          <mesh position={position}>
            <sphereGeometry
              args={[index === 2 ? 0.075 : 0.052, 20, 20]}
            />
            <meshStandardMaterial
              color={index % 2 === 0 ? "#7CFF00" : "#00E5FF"}
              emissive={index % 2 === 0 ? "#5BDD00" : "#00B8D9"}
              emissiveIntensity={2.4}
            />
          </mesh>
        </Float>
      ))}

      {paths.map((points, index) => (
        <Line
          key={index}
          points={points}
          color={index % 2 === 0 ? "#7CFF00" : "#00E5FF"}
          transparent
          opacity={0.32}
          lineWidth={0.9}
        />
      ))}
    </group>
  );
}

export default function EmpireWorld() {
  return (
    <div className="h-full w-full [mask-image:radial-gradient(circle,black_52%,transparent_76%)]" aria-hidden="true">
      <Canvas camera={{ position: [0, 0, 5.8], fov: 45 }} dpr={[1, 1.8]}>
        <ambientLight intensity={0.6} />
        <pointLight
          position={[4, 4, 4]}
          intensity={28}
          color="#7CFF00"
        />
        <pointLight
          position={[-4, -2, 3]}
          intensity={24}
          color="#00E5FF"
        />
        <Network />
        <Stars
          radius={55}
          depth={32}
          count={900}
          factor={1.3}
          saturation={0}
          fade
          speed={0.3}
        />
        <OrbitControls
          enableZoom={false}
          enablePan={false}
          autoRotate
          autoRotateSpeed={0.16}
        />
      </Canvas>
    </div>
  );
}
