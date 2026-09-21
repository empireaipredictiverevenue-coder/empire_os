"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { Float, Line } from "@react-three/drei";
import * as THREE from "three";
import { useEffect, useMemo, useRef, useState } from "react";

type Vec3 = [number, number, number];

const CAMERA_KEYS: Array<{ at: number; position: Vec3; target: Vec3 }> = [
  { at: 0.0, position: [0.2, 0.15, 11.5], target: [0, 0, 0] },
  { at: 0.22, position: [3.6, 1.1, 5.6], target: [0, 0, -1.5] },
  { at: 0.44, position: [-3.1, 0.35, -0.8], target: [0, 0, -7.2] },
  { at: 0.66, position: [2.5, -0.6, -8.2], target: [0, 0, -13.2] },
  { at: 0.84, position: [-1.4, 0.65, -15.1], target: [0, 0, -19.0] },
  { at: 1.0, position: [0, 0.15, -20.4], target: [0, 0, -24.0] },
];

function sampleCamera(progress: number) {
  const p = THREE.MathUtils.clamp(progress, 0, 1);
  let left = CAMERA_KEYS[0];
  let right = CAMERA_KEYS[CAMERA_KEYS.length - 1];

  for (let index = 0; index < CAMERA_KEYS.length - 1; index += 1) {
    if (p >= CAMERA_KEYS[index].at && p <= CAMERA_KEYS[index + 1].at) {
      left = CAMERA_KEYS[index];
      right = CAMERA_KEYS[index + 1];
      break;
    }
  }

  const local = THREE.MathUtils.smoothstep(
    (p - left.at) / Math.max(0.0001, right.at - left.at),
    0,
    1,
  );

  return {
    position: new THREE.Vector3(...left.position).lerp(
      new THREE.Vector3(...right.position),
      local,
    ),
    target: new THREE.Vector3(...left.target).lerp(
      new THREE.Vector3(...right.target),
      local,
    ),
  };
}

function CameraRig({ reducedMotion }: { reducedMotion: boolean }) {
  const target = useRef(new THREE.Vector3());

  useFrame((state, delta) => {
    const maxScroll = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
    const rawProgress = reducedMotion ? 0 : window.scrollY / maxScroll;
    const sampled = sampleCamera(rawProgress);
    const damping = 1 - Math.exp(-delta * 3.4);

    state.camera.position.lerp(sampled.position, damping);
    target.current.lerp(sampled.target, damping);
    state.camera.lookAt(target.current);
  });

  return null;
}

function SignalField() {
  const ref = useRef<THREE.InstancedMesh>(null);
  const dummy = useMemo(() => new THREE.Object3D(), []);

  const particles = useMemo(
    () =>
      Array.from({ length: 115 }, (_, index) => {
        const lane = (index % 7) - 3;
        const ring = Math.floor(index / 7);
        const phase = index * 1.731;
        return {
          x: lane * 0.88 + Math.sin(phase) * 0.45,
          y: Math.cos(phase * 0.73) * 2.6,
          z: 8.5 - ring * 2.0,
          scale: 0.025 + (index % 5) * 0.008,
          speed: 0.17 + (index % 9) * 0.012,
        };
      }),
    [],
  );

  useFrame((state) => {
    if (!ref.current) return;
    const t = state.clock.elapsedTime;

    particles.forEach((particle, index) => {
      const z = particle.z - ((t * particle.speed + index * 0.07) % 4.5);
      dummy.position.set(
        particle.x + Math.sin(t * 0.24 + index) * 0.08,
        particle.y + Math.cos(t * 0.19 + index) * 0.06,
        z,
      );
      const pulse = 0.78 + Math.sin(t * 1.6 + index) * 0.22;
      dummy.scale.setScalar(particle.scale * pulse);
      dummy.updateMatrix();
      ref.current!.setMatrixAt(index, dummy.matrix);
    });
    ref.current.instanceMatrix.needsUpdate = true;
  });

  return (
    <instancedMesh ref={ref} args={[undefined, undefined, particles.length]}>
      <sphereGeometry args={[1, 8, 8]} />
      <meshBasicMaterial color="#a6ff6a" transparent opacity={0.55} />
    </instancedMesh>
  );
}

function DataRail({
  points,
  color,
  speed,
  offset = 0,
}: {
  points: Vec3[];
  color: string;
  speed: number;
  offset?: number;
}) {
  const pulse = useRef<THREE.Mesh>(null);
  const curve = useMemo(
    () => new THREE.CatmullRomCurve3(points.map((point) => new THREE.Vector3(...point))),
    [points],
  );
  const linePoints = useMemo(() => curve.getPoints(80), [curve]);

  useFrame((state) => {
    if (!pulse.current) return;
    const progress = (state.clock.elapsedTime * speed + offset) % 1;
    pulse.current.position.copy(curve.getPointAt(progress));
  });

  return (
    <group>
      <Line
        points={linePoints}
        color={color}
        transparent
        opacity={0.22}
        lineWidth={0.7}
      />
      <mesh ref={pulse}>
        <sphereGeometry args={[0.065, 14, 14]} />
        <meshBasicMaterial color={color} toneMapped={false} />
      </mesh>
    </group>
  );
}

function RevenueReactor() {
  const outer = useRef<THREE.Group>(null);
  const inner = useRef<THREE.Group>(null);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    if (outer.current) {
      outer.current.rotation.x = t * 0.16;
      outer.current.rotation.y = t * -0.21;
    }
    if (inner.current) {
      inner.current.rotation.y = t * 0.42;
      inner.current.rotation.z = Math.sin(t * 0.3) * 0.2;
    }
  });

  return (
    <group position={[0, 0, 0]}>
      <pointLight color="#8dff32" intensity={18} distance={11} />
      <pointLight color="#00d9ff" intensity={13} distance={9} position={[1.5, -1.5, 1]} />

      <group ref={outer}>
        <mesh>
          <torusGeometry args={[2.45, 0.032, 12, 160]} />
          <meshBasicMaterial color="#8dff32" transparent opacity={0.55} toneMapped={false} />
        </mesh>
        <mesh rotation={[Math.PI / 2.4, 0.4, 0]}>
          <torusGeometry args={[2.05, 0.02, 10, 140]} />
          <meshBasicMaterial color="#00d9ff" transparent opacity={0.42} toneMapped={false} />
        </mesh>
        <mesh rotation={[0.35, Math.PI / 2, 0.7]}>
          <torusGeometry args={[1.62, 0.016, 10, 120]} />
          <meshBasicMaterial color="#ffffff" transparent opacity={0.17} />
        </mesh>
      </group>

      <group ref={inner}>
        <Float speed={1.8} rotationIntensity={0.15} floatIntensity={0.18}>
          <mesh>
            <icosahedronGeometry args={[1.08, 2]} />
            <meshPhysicalMaterial
              color="#07130d"
              roughness={0.16}
              metalness={0.82}
              clearcoat={1}
              clearcoatRoughness={0.08}
              emissive="#194e17"
              emissiveIntensity={0.55}
            />
          </mesh>
          <mesh scale={1.025}>
            <icosahedronGeometry args={[1.08, 2]} />
            <meshBasicMaterial
              color="#9dff4a"
              wireframe
              transparent
              opacity={0.21}
              toneMapped={false}
            />
          </mesh>
        </Float>
      </group>

      {[0, 1, 2, 3, 4, 5].map((index) => {
        const angle = (index / 6) * Math.PI * 2;
        return (
          <mesh
            key={index}
            position={[Math.cos(angle) * 3.35, Math.sin(angle) * 1.55, Math.sin(angle) * 0.55]}
            rotation={[angle * 0.23, angle, angle * 0.5]}
          >
            <boxGeometry args={[0.62, 0.06, 0.24]} />
            <meshStandardMaterial
              color={index % 2 ? "#0a2d2c" : "#142b0b"}
              emissive={index % 2 ? "#00d9ff" : "#8dff32"}
              emissiveIntensity={0.32}
              metalness={0.88}
              roughness={0.22}
            />
          </mesh>
        );
      })}
    </group>
  );
}

function OpportunityTunnel() {
  const group = useRef<THREE.Group>(null);

  useFrame((state) => {
    if (!group.current) return;
    group.current.rotation.z = Math.sin(state.clock.elapsedTime * 0.12) * 0.08;
  });

  return (
    <group ref={group}>
      {Array.from({ length: 8 }, (_, index) => {
        const z = -5 - index * 1.05;
        const scale = 1.0 + index * 0.075;
        return (
          <group key={index} position={[0, 0, z]} scale={scale}>
            <mesh rotation={[0, 0, index * 0.18]}>
              <torusGeometry args={[2.45, index % 2 ? 0.018 : 0.035, 10, 120]} />
              <meshBasicMaterial
                color={index % 3 === 0 ? "#8dff32" : "#00d9ff"}
                transparent
                opacity={0.11 + index * 0.012}
                toneMapped={false}
              />
            </mesh>
            {[0, Math.PI / 2, Math.PI, (Math.PI * 3) / 2].map((angle) => (
              <mesh
                key={angle}
                position={[Math.cos(angle) * 2.45, Math.sin(angle) * 2.45, 0]}
                rotation={[0, 0, angle]}
              >
                <boxGeometry args={[0.34, 0.04, 0.12]} />
                <meshBasicMaterial color="#d9ffd0" transparent opacity={0.42} />
              </mesh>
            ))}
          </group>
        );
      })}
    </group>
  );
}

function ExecutionChamber() {
  const group = useRef<THREE.Group>(null);

  useFrame((state) => {
    if (!group.current) return;
    const t = state.clock.elapsedTime;
    group.current.children.forEach((child, index) => {
      child.position.y += Math.sin(t * 0.55 + index) * 0.0009;
      child.rotation.y += 0.0008 * (index % 2 ? -1 : 1);
    });
  });

  return (
    <group ref={group} position={[0, 0, -13.9]}>
      {Array.from({ length: 10 }, (_, index) => {
        const side = index % 2 ? 1 : -1;
        const row = Math.floor(index / 2);
        return (
          <mesh
            key={index}
            position={[side * (2.6 + row * 0.22), (row - 2) * 0.85, -row * 0.38]}
            rotation={[0.08 * row, side * -0.42, side * 0.05]}
          >
            <boxGeometry args={[1.4, 0.52, 0.08]} />
            <meshPhysicalMaterial
              color="#07100d"
              metalness={0.88}
              roughness={0.18}
              clearcoat={0.8}
              emissive={index % 3 === 0 ? "#15480b" : "#032f37"}
              emissiveIntensity={0.35}
            />
          </mesh>
        );
      })}

      <mesh>
        <octahedronGeometry args={[1.32, 1]} />
        <meshPhysicalMaterial
          color="#07120c"
          metalness={0.92}
          roughness={0.15}
          emissive="#163b10"
          emissiveIntensity={0.55}
        />
      </mesh>
      <mesh scale={1.04}>
        <octahedronGeometry args={[1.32, 1]} />
        <meshBasicMaterial
          color="#8dff32"
          wireframe
          transparent
          opacity={0.19}
          toneMapped={false}
        />
      </mesh>
    </group>
  );
}

function RevenueMonolith() {
  const shell = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    if (!shell.current) return;
    shell.current.rotation.y = Math.sin(state.clock.elapsedTime * 0.16) * 0.12;
  });

  return (
    <group position={[0, 0, -23.2]}>
      <pointLight position={[0, 0, 2]} intensity={26} color="#8dff32" distance={8} />
      <mesh ref={shell}>
        <boxGeometry args={[3.0, 5.6, 0.72]} />
        <meshPhysicalMaterial
          color="#030605"
          roughness={0.11}
          metalness={0.96}
          clearcoat={1}
          clearcoatRoughness={0.06}
        />
      </mesh>
      <mesh position={[0, 0, 0.39]}>
        <planeGeometry args={[2.18, 4.72]} />
        <meshBasicMaterial color="#07110a" />
      </mesh>
      {Array.from({ length: 11 }, (_, index) => (
        <mesh key={index} position={[0, 2.02 - index * 0.4, 0.405]}>
          <planeGeometry args={[1.72 - (index % 3) * 0.18, 0.025]} />
          <meshBasicMaterial
            color={index < 8 ? "#8dff32" : "#00d9ff"}
            transparent
            opacity={0.25 + (10 - index) * 0.035}
            toneMapped={false}
          />
        </mesh>
      ))}
      <mesh position={[0, -1.9, 0.42]}>
        <planeGeometry args={[1.1, 0.11]} />
        <meshBasicMaterial color="#d7ffc3" transparent opacity={0.85} toneMapped={false} />
      </mesh>
    </group>
  );
}

function Scene({ reducedMotion }: { reducedMotion: boolean }) {
  return (
    <>
      <fog attach="fog" args={["#020403", 10, 42]} />
      <ambientLight intensity={0.24} />
      <directionalLight position={[5, 8, 8]} color="#dfffd2" intensity={1.8} />
      <pointLight position={[-6, 3, 1]} color="#00d9ff" intensity={8} distance={18} />

      <CameraRig reducedMotion={reducedMotion} />
      <SignalField />

      <DataRail
        color="#8dff32"
        speed={0.08}
        points={[
          [-4.5, 2.2, 6],
          [-2.4, 1.5, 2.6],
          [-1.3, 0.6, 0.7],
          [0, 0, 0],
        ]}
      />
      <DataRail
        color="#00d9ff"
        speed={0.065}
        offset={0.42}
        points={[
          [4.2, -2.1, 5.2],
          [2.1, -1.2, 2.2],
          [1.4, -0.55, 0.4],
          [0, 0, 0],
        ]}
      />
      <DataRail
        color="#d9ffd0"
        speed={0.05}
        offset={0.73}
        points={[
          [0, 3.4, 4.8],
          [0.8, 2.3, 2.4],
          [0.5, 1.2, 0.6],
          [0, 0, 0],
        ]}
      />

      <RevenueReactor />
      <OpportunityTunnel />
      <ExecutionChamber />
      <RevenueMonolith />
    </>
  );
}

export default function EmpireWorld() {
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const apply = () => setReducedMotion(media.matches);
    apply();
    media.addEventListener?.("change", apply);
    return () => media.removeEventListener?.("change", apply);
  }, []);

  return (
    <div className="h-full w-full" aria-hidden="true">
      <Canvas
        camera={{ position: [0.2, 0.15, 11.5], fov: 44, near: 0.1, far: 80 }}
        dpr={[1, 1.45]}
        gl={{ antialias: true, powerPreference: "high-performance" }}
      >
        <color attach="background" args={["#020403"]} />
        <Scene reducedMotion={reducedMotion} />
      </Canvas>
    </div>
  );
}
