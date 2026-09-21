"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { Scroll, ScrollControls, useScroll } from "@react-three/drei";
import * as THREE from "three";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

type LayerSpec = {
  angle: number;
  radius: number;
  width: number;
  depth: number;
  y: number;
};

function ScrollBridge({
  onProgress,
}: {
  onProgress?: (progress: number) => void;
}) {
  const scroll = useScroll();
  const last = useRef(-1);

  useEffect(() => {
    const handleJump = (event: Event) => {
      const custom = event as CustomEvent<{ target?: number }>;
      const target = THREE.MathUtils.clamp(
        Number(custom.detail?.target ?? 0),
        0,
        1,
      );
      const max = scroll.el.scrollHeight - scroll.el.clientHeight;
      scroll.el.scrollTop = target * max;
    };
    window.addEventListener("empire-jump", handleJump as EventListener);
    return () => {
      window.removeEventListener("empire-jump", handleJump as EventListener);
    };
  }, [scroll]);

  useFrame(() => {
    if (!onProgress) return;
    if (Math.abs(scroll.offset - last.current) < 0.006) return;
    last.current = scroll.offset;
    onProgress(scroll.offset);
  });

  return null;
}

function CameraRig() {
  const scroll = useScroll();
  const look = useRef(new THREE.Vector3(0, 0, 0));

  useFrame((state, delta) => {
    const p = scroll.offset;
    const angle = -0.38 + p * 1.15;
    const radius = 10.3 - Math.sin(p * Math.PI) * 1.2;
    const height = 0.7 + Math.sin(p * Math.PI * 1.4) * 1.15;

    const goal = new THREE.Vector3(
      Math.sin(angle) * radius + state.pointer.x * 0.5,
      height + state.pointer.y * 0.28,
      Math.cos(angle) * radius,
    );

    const damping = 1 - Math.exp(-delta * 4.8);
    state.camera.position.lerp(goal, damping);
    look.current.lerp(
      new THREE.Vector3(
        0,
        p > 0.7 ? -0.2 : 0.15,
        0,
      ),
      damping,
    );
    state.camera.lookAt(look.current);
  });

  return null;
}

function EngineLayers() {
  const scroll = useScroll();
  const group = useRef<THREE.Group>(null);

  const specs = useMemo<LayerSpec[]>(
    () =>
      Array.from({ length: 18 }, (_, index) => ({
        angle: (index / 18) * Math.PI * 2,
        radius: 2.3 + (index % 3) * 0.34,
        width: 1.0 + (index % 4) * 0.18,
        depth: 0.14 + (index % 3) * 0.05,
        y: ((index % 6) - 2.5) * 0.28,
      })),
    [],
  );

  useFrame((state, delta) => {
    if (!group.current) return;
    const p = scroll.offset;
    const t = state.clock.elapsedTime;
    const explode = THREE.MathUtils.smoothstep(p, 0.12, 0.42);
    const collapse = THREE.MathUtils.smoothstep(p, 0.76, 1);
    const travel = explode * (1 - collapse);

    group.current.rotation.y += delta * (0.11 + p * 0.08);
    group.current.rotation.x =
      Math.sin(t * 0.21) * 0.07 + (p - 0.5) * 0.08;

    group.current.children.forEach((child, index) => {
      const spec = specs[index];
      if (!spec) return;
      const radial = spec.radius + travel * (1.45 + (index % 5) * 0.16);
      const goalX = Math.cos(spec.angle) * radial;
      const goalZ = Math.sin(spec.angle) * radial;
      const goalY =
        spec.y +
        Math.sin(t * 0.55 + index) * 0.06 +
        travel * ((index % 2 ? 1 : -1) * 0.42);

      const k = 1 - Math.exp(-delta * 5.6);
      child.position.x = THREE.MathUtils.lerp(child.position.x, goalX, k);
      child.position.y = THREE.MathUtils.lerp(child.position.y, goalY, k);
      child.position.z = THREE.MathUtils.lerp(child.position.z, goalZ, k);
      child.rotation.z = spec.angle + Math.PI / 2;
      child.rotation.y =
        Math.sin(t * 0.35 + index) * 0.08 + p * 0.4;
    });
  });

  return (
    <group ref={group}>
      {specs.map((spec, index) => (
        <mesh
          key={index}
          position={[
            Math.cos(spec.angle) * spec.radius,
            spec.y,
            Math.sin(spec.angle) * spec.radius,
          ]}
        >
          <boxGeometry args={[spec.width, spec.depth, 0.52]} />
          <meshPhysicalMaterial
            color={index % 3 === 0 ? "#0b2150" : "#07162f"}
            metalness={0.94}
            roughness={0.14}
            clearcoat={1}
            clearcoatRoughness={0.05}
            emissive={index % 4 === 0 ? "#2563eb" : "#0b3f72"}
            emissiveIntensity={0.3}
          />
        </mesh>
      ))}
    </group>
  );
}

function Core() {
  const scroll = useScroll();
  const core = useRef<THREE.Group>(null);
  const rings = useRef<THREE.Group>(null);
  const [boost, setBoost] = useState(false);

  useFrame((state, delta) => {
    const p = scroll.offset;
    const t = state.clock.elapsedTime;

    if (core.current) {
      const pulse =
        1 +
        Math.sin(t * (boost ? 3.6 : 1.8)) * (boost ? 0.08 : 0.035) +
        p * 0.05;
      core.current.scale.setScalar(pulse);
      core.current.rotation.y += delta * (boost ? 0.7 : 0.22);
      core.current.rotation.x = Math.sin(t * 0.35) * 0.12;
    }

    if (rings.current) {
      rings.current.rotation.x += delta * (0.16 + p * 0.25);
      rings.current.rotation.y -= delta * (0.22 + p * 0.34);
      rings.current.rotation.z =
        Math.sin(t * 0.28) * 0.16 + p * 0.5;
    }
  });

  return (
    <group>
      <pointLight
        color="#60a5fa"
        intensity={boost ? 42 : 28}
        distance={14}
      />
      <pointLight
        color="#22d3ee"
        intensity={18}
        distance={12}
        position={[2.5, -1.2, 2.1]}
      />

      <group ref={rings}>
        {[3.65, 3.08, 2.52].map((radius, index) => (
          <mesh
            key={radius}
            rotation={[
              index * 0.78,
              index * 0.52,
              index * 0.33,
            ]}
          >
            <torusGeometry
              args={[
                radius,
                index === 0 ? 0.055 : 0.032,
                10,
                128,
              ]}
            />
            <meshBasicMaterial
              color={index === 1 ? "#22d3ee" : "#4f8cff"}
              transparent
              opacity={0.52 - index * 0.1}
              toneMapped={false}
            />
          </mesh>
        ))}
      </group>

      <group
        ref={core}
        onClick={(event) => {
          event.stopPropagation();
          setBoost((value) => !value);
        }}
      >
        <mesh>
          <icosahedronGeometry args={[1.55, 3]} />
          <meshPhysicalMaterial
            color="#07152e"
            metalness={0.94}
            roughness={0.1}
            clearcoat={1}
            clearcoatRoughness={0.03}
            emissive={boost ? "#2563eb" : "#133a86"}
            emissiveIntensity={boost ? 1.6 : 0.72}
          />
        </mesh>
        <mesh scale={1.025}>
          <icosahedronGeometry args={[1.55, 2]} />
          <meshBasicMaterial
            color="#93c5fd"
            wireframe
            transparent
            opacity={boost ? 0.42 : 0.22}
            toneMapped={false}
          />
        </mesh>
      </group>
    </group>
  );
}

function SignalStreams() {
  const scroll = useScroll();
  const refs = useRef<Array<THREE.Mesh | null>>([]);

  const curves = useMemo(
    () =>
      Array.from({ length: 8 }, (_, index) => {
        const side = index % 2 ? 1 : -1;
        const y = ((index % 4) - 1.5) * 0.8;
        return new THREE.CatmullRomCurve3([
          new THREE.Vector3(side * 7.4, y + 1.4, -2.8),
          new THREE.Vector3(side * 5.3, y, -1.1),
          new THREE.Vector3(side * 3.7, y * 0.6, 0),
          new THREE.Vector3(side * 1.8, y * 0.2, 0),
        ]);
      }),
    [],
  );

  useFrame((state) => {
    const p = scroll.offset;
    const t = state.clock.elapsedTime;
    refs.current.forEach((mesh, index) => {
      if (!mesh) return;
      const curve = curves[index];
      const speed = 0.06 + index * 0.007 + p * 0.035;
      const u = (t * speed + index * 0.12) % 1;
      mesh.position.copy(curve.getPointAt(u));
      const next = curve.getPointAt(Math.min(1, u + 0.01));
      mesh.lookAt(next);
    });
  });

  return (
    <group>
      {curves.map((_, index) => (
        <mesh
          key={index}
          ref={(node) => {
            refs.current[index] = node;
          }}
        >
          <octahedronGeometry args={[0.1 + (index % 3) * 0.025, 0]} />
          <meshBasicMaterial
            color={index % 2 ? "#22d3ee" : "#60a5fa"}
            toneMapped={false}
          />
        </mesh>
      ))}
    </group>
  );
}

function DataHalo() {
  const scroll = useScroll();
  const halo = useRef<THREE.Group>(null);

  useFrame((state) => {
    if (!halo.current) return;
    const p = scroll.offset;
    const t = state.clock.elapsedTime;
    halo.current.rotation.y = t * 0.06 + p * Math.PI * 1.2;
    halo.current.rotation.x = Math.sin(t * 0.17) * 0.08;
  });

  return (
    <group ref={halo}>
      {Array.from({ length: 40 }, (_, index) => {
        const a = (index / 40) * Math.PI * 2;
        const radius = 4.7 + (index % 5) * 0.12;
        return (
          <mesh
            key={index}
            position={[
              Math.cos(a) * radius,
              ((index % 8) - 3.5) * 0.11,
              Math.sin(a) * radius,
            ]}
            rotation={[0, -a, 0]}
          >
            <boxGeometry args={[0.08, 0.52, 0.08]} />
            <meshBasicMaterial
              color={index % 4 === 0 ? "#22d3ee" : "#4f8cff"}
              transparent
              opacity={0.38}
              toneMapped={false}
            />
          </mesh>
        );
      })}
    </group>
  );
}

function Engine({
  onProgress,
}: {
  onProgress?: (progress: number) => void;
}) {
  return (
    <>
      <ScrollBridge onProgress={onProgress} />
      <CameraRig />

      <fog attach="fog" args={["#020817", 10, 26]} />
      <ambientLight intensity={0.36} />
      <directionalLight
        position={[4, 8, 8]}
        color="#dbeafe"
        intensity={2.4}
      />
      <pointLight
        position={[-5, 3, 5]}
        color="#2563eb"
        intensity={10}
        distance={18}
      />

      <group position={[1.7, 0.2, 0]} scale={1.08}>
        <EngineLayers />
        <DataHalo />
        <Core />
        <SignalStreams />
      </group>

      <mesh
        rotation={[-Math.PI / 2, 0, 0]}
        position={[0, -4.7, 0]}
      >
        <planeGeometry args={[32, 32]} />
        <meshStandardMaterial
          color="#020817"
          metalness={0.7}
          roughness={0.35}
        />
      </mesh>
    </>
  );
}

function ScrollTrack() {
  return (
    <Scroll html>
      <div className="pointer-events-none w-screen" aria-hidden="true">
        {Array.from({ length: 7 }, (_, index) => (
          <section key={index} className="h-screen" />
        ))}
      </div>
    </Scroll>
  );
}

export default function EmpireWorld({
  onReady,
  onProgress,
}: {
  onReady?: () => void;
  onProgress?: (progress: number) => void;
}) {
  const [pixelRatio, setPixelRatio] = useState(1);

  useEffect(() => {
    const updateQuality = () => {
      const rawDpr = Math.max(1, window.devicePixelRatio || 1);
      const mobile = window.innerWidth < 900;
      const physicalWidth = window.innerWidth * rawDpr;
      const physicalHeight = window.innerHeight * rawDpr;
      const highResolution =
        Math.max(physicalWidth, physicalHeight) >= 3840;
      const cap = mobile ? 1.5 : highResolution ? 2 : 1.6;
      setPixelRatio(Math.min(rawDpr, cap));
    };

    updateQuality();
    window.addEventListener("resize", updateQuality);
    return () => window.removeEventListener("resize", updateQuality);
  }, []);

  return (
    <div className="h-screen w-screen bg-[#020817]">
      <Canvas
        onCreated={() => onReady?.()}
        camera={{
          position: [-3.8, 0.8, 10.3],
          fov: 42,
          near: 0.08,
          far: 70,
        }}
        dpr={pixelRatio}
        gl={{
          antialias: true,
          alpha: false,
          stencil: false,
          powerPreference: "high-performance",
        }}
      >
        <color attach="background" args={["#020817"]} />
        <ScrollControls
          pages={7}
          damping={0.14}
          distance={1}
          maxSpeed={0.9}
        >
          <Engine onProgress={onProgress} />
          <ScrollTrack />
        </ScrollControls>
      </Canvas>
    </div>
  );
}
