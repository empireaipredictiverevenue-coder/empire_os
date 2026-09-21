"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import {
  Html,
  Line,
  Scroll,
  ScrollControls,
  useCursor,
  useScroll,
} from "@react-three/drei";
import * as THREE from "three";
import {
  useMemo,
  useRef,
  useState,
} from "react";

type V3 = [number, number, number];

const CHAPTERS = [
  {
    id: "signal",
    at: 0.08,
    index: "01",
    eyebrow: "SIGNAL FIELD",
    title: "Enter the market before the market moves.",
    body:
      "Live demand, search, storm, company and buyer signals become one navigable commercial field.",
  },
  {
    id: "reactor",
    at: 0.28,
    index: "02",
    eyebrow: "REVENUE REACTOR",
    title: "Evidence is compressed into priority.",
    body:
      "Omega and Cortex turn noisy observations into the few opportunities worth acting on now.",
  },
  {
    id: "opportunity",
    at: 0.49,
    index: "03",
    eyebrow: "OPPORTUNITY VAULT",
    title: "Identity. Intent. Economics. Why now.",
    body:
      "The route into revenue is resolved before the system is allowed to move.",
  },
  {
    id: "execution",
    at: 0.70,
    index: "04",
    eyebrow: "EXECUTION CHAMBER",
    title: "Agents operate inside governed authority.",
    body:
      "Research, outreach, conversation and fulfilment coordinate through one control fabric.",
  },
  {
    id: "truth",
    at: 0.91,
    index: "05",
    eyebrow: "REVENUE VAULT",
    title: "Forecast is not revenue. Evidence is.",
    body:
      "Verified payment, fulfilment, recognized revenue and realized GP close the loop.",
  },
] as const;

const CAMERA_PATH = [
  new THREE.Vector3(0, 0.35, 12),
  new THREE.Vector3(0, 0.1, 7),
  new THREE.Vector3(-0.8, 0.35, 1),
  new THREE.Vector3(1.6, -0.4, -8),
  new THREE.Vector3(-1.8, 0.55, -18),
  new THREE.Vector3(0.6, 0.2, -28),
  new THREE.Vector3(-1.1, -0.45, -39),
  new THREE.Vector3(1.3, 0.35, -49),
  new THREE.Vector3(0, 0.1, -61),
];

const CAMERA_CURVE = new THREE.CatmullRomCurve3(
  CAMERA_PATH,
  false,
  "catmullrom",
  0.45,
);

function CameraFlight() {
  const scroll = useScroll();
  const look = useRef(new THREE.Vector3());
  const tangent = useRef(new THREE.Vector3());

  useFrame((state, delta) => {
    const t = THREE.MathUtils.clamp(scroll.offset, 0, 1);
    const ahead = THREE.MathUtils.clamp(t + 0.018, 0, 1);
    const base = CAMERA_CURVE.getPointAt(t);
    const target = CAMERA_CURVE.getPointAt(ahead);
    CAMERA_CURVE.getTangentAt(t, tangent.current);

    const parallaxX = state.pointer.x * 0.32;
    const parallaxY = state.pointer.y * 0.18;
    const goal = base.clone().add(
      new THREE.Vector3(parallaxX, parallaxY, 0),
    );

    const damping = 1 - Math.exp(-delta * 7.5);
    state.camera.position.lerp(goal, damping);
    look.current.lerp(target, damping);
    state.camera.lookAt(look.current);

    const bank =
      THREE.MathUtils.clamp(tangent.current.x, -0.5, 0.5) * -0.22 +
      THREE.MathUtils.clamp(scroll.delta * 6, -0.15, 0.15);
    state.camera.rotation.z = THREE.MathUtils.lerp(
      state.camera.rotation.z,
      bank,
      damping * 0.5,
    );
  });

  return null;
}

function SignalDust() {
  const ref = useRef<THREE.InstancedMesh>(null);
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const particles = useMemo(
    () =>
      Array.from({ length: 180 }, (_, index) => {
        const z = 10 - (index / 180) * 68;
        const radius = 2.5 + ((index * 17) % 45) / 10;
        const a = index * 2.417;
        return {
          base: new THREE.Vector3(
            Math.sin(a) * radius,
            Math.cos(a * 0.73) * radius * 0.55,
            z,
          ),
          speed: 0.22 + (index % 9) * 0.02,
          scale: 0.014 + (index % 5) * 0.006,
        };
      }),
    [],
  );

  useFrame((state) => {
    if (!ref.current) return;
    const time = state.clock.elapsedTime;
    particles.forEach((particle, index) => {
      dummy.position.copy(particle.base);
      dummy.position.x += Math.sin(time * particle.speed + index) * 0.16;
      dummy.position.y += Math.cos(time * particle.speed * 0.8 + index) * 0.11;
      const pulse = 0.7 + Math.sin(time * 1.7 + index) * 0.3;
      dummy.scale.setScalar(particle.scale * pulse);
      dummy.updateMatrix();
      ref.current!.setMatrixAt(index, dummy.matrix);
    });
    ref.current.instanceMatrix.needsUpdate = true;
  });

  return (
    <instancedMesh ref={ref} args={[undefined, undefined, particles.length]}>
      <sphereGeometry args={[1, 6, 6]} />
      <meshBasicMaterial
        color="#a9ff6d"
        transparent
        opacity={0.45}
        toneMapped={false}
      />
    </instancedMesh>
  );
}

function Rail({
  points,
  color = "#9dff4a",
  speed = 0.07,
  offset = 0,
}: {
  points: V3[];
  color?: string;
  speed?: number;
  offset?: number;
}) {
  const pulse = useRef<THREE.Mesh>(null);
  const curve = useMemo(
    () =>
      new THREE.CatmullRomCurve3(
        points.map((point) => new THREE.Vector3(...point)),
      ),
    [points],
  );
  const line = useMemo(() => curve.getPoints(90), [curve]);

  useFrame((state) => {
    if (!pulse.current) return;
    pulse.current.position.copy(
      curve.getPointAt(
        (state.clock.elapsedTime * speed + offset) % 1,
      ),
    );
  });

  return (
    <group>
      <Line
        points={line}
        color={color}
        transparent
        opacity={0.28}
        lineWidth={0.75}
      />
      <mesh ref={pulse}>
        <sphereGeometry args={[0.07, 10, 10]} />
        <meshBasicMaterial color={color} toneMapped={false} />
      </mesh>
    </group>
  );
}

function Gate() {
  return (
    <group position={[0, 0, 4]}>
      <mesh position={[-3.3, 0, 0]}>
        <boxGeometry args={[0.5, 7.5, 1.3]} />
        <meshStandardMaterial
          color="#050806"
          metalness={0.92}
          roughness={0.18}
          emissive="#102a08"
          emissiveIntensity={0.25}
        />
      </mesh>
      <mesh position={[3.3, 0, 0]}>
        <boxGeometry args={[0.5, 7.5, 1.3]} />
        <meshStandardMaterial
          color="#050806"
          metalness={0.92}
          roughness={0.18}
          emissive="#102a08"
          emissiveIntensity={0.25}
        />
      </mesh>
      <mesh position={[0, 3.5, 0]}>
        <boxGeometry args={[7.1, 0.5, 1.3]} />
        <meshStandardMaterial
          color="#050806"
          metalness={0.92}
          roughness={0.18}
          emissive="#08252a"
          emissiveIntensity={0.28}
        />
      </mesh>
      <mesh position={[0, -3.5, 0]}>
        <boxGeometry args={[7.1, 0.16, 1.3]} />
        <meshBasicMaterial
          color="#9dff4a"
          transparent
          opacity={0.34}
          toneMapped={false}
        />
      </mesh>
    </group>
  );
}

function SignalAtrium() {
  return (
    <group position={[0, 0, -3]}>
      {Array.from({ length: 18 }, (_, index) => {
        const side = index % 2 ? 1 : -1;
        const row = Math.floor(index / 2);
        const z = -row * 0.92;
        const height = 0.9 + (index % 5) * 0.42;
        return (
          <mesh
            key={index}
            position={[
              side * (2.6 + (row % 3) * 0.42),
              -2.4 + height / 2,
              z,
            ]}
          >
            <boxGeometry args={[0.38, height, 0.38]} />
            <meshStandardMaterial
              color="#06100b"
              metalness={0.78}
              roughness={0.24}
              emissive={index % 3 === 0 ? "#17380d" : "#06252a"}
              emissiveIntensity={0.32}
            />
          </mesh>
        );
      })}
      <Rail
        points={[
          [-4.1, 2.2, 1.4],
          [-2.2, 1.25, 0],
          [-0.9, 0.6, -1],
          [0, 0.2, -2.2],
        ]}
      />
      <Rail
        color="#00d9ff"
        offset={0.42}
        points={[
          [4.1, -1.9, 1.1],
          [2.5, -0.9, -0.4],
          [1.2, -0.2, -1.2],
          [0, 0.2, -2.2],
        ]}
      />
    </group>
  );
}

function Reactor() {
  const rings = useRef<THREE.Group>(null);
  useFrame((state) => {
    if (!rings.current) return;
    const t = state.clock.elapsedTime;
    rings.current.rotation.x = t * 0.11;
    rings.current.rotation.y = t * -0.19;
  });

  return (
    <group position={[0, 0, -14]}>
      <pointLight color="#9dff4a" intensity={20} distance={12} />
      <pointLight
        color="#00d9ff"
        intensity={12}
        distance={10}
        position={[2, -1.2, 0]}
      />
      <group ref={rings}>
        {[2.8, 2.25, 1.72].map((radius, index) => (
          <mesh
            key={radius}
            rotation={[
              index * 0.72,
              index * 0.51,
              index * 0.34,
            ]}
          >
            <torusGeometry
              args={[radius, index === 0 ? 0.045 : 0.025, 12, 140]}
            />
            <meshBasicMaterial
              color={index === 1 ? "#00d9ff" : "#9dff4a"}
              transparent
              opacity={0.5 - index * 0.11}
              toneMapped={false}
            />
          </mesh>
        ))}
      </group>
      <mesh>
        <icosahedronGeometry args={[1.18, 2]} />
        <meshPhysicalMaterial
          color="#08120d"
          metalness={0.88}
          roughness={0.14}
          clearcoat={1}
          clearcoatRoughness={0.06}
          emissive="#183a10"
          emissiveIntensity={0.5}
        />
      </mesh>
      <mesh scale={1.03}>
        <icosahedronGeometry args={[1.18, 2]} />
        <meshBasicMaterial
          color="#b6ff88"
          wireframe
          transparent
          opacity={0.18}
          toneMapped={false}
        />
      </mesh>
    </group>
  );
}

function OpportunityVault() {
  const floating = useRef<THREE.Group>(null);
  useFrame((state) => {
    if (!floating.current) return;
    const t = state.clock.elapsedTime;
    floating.current.children.forEach((child, index) => {
      child.rotation.y += 0.0007 * (index % 2 ? 1 : -1);
      child.position.y += Math.sin(t * 0.45 + index) * 0.0008;
    });
  });

  return (
    <group position={[0, 0, -27]}>
      <group ref={floating}>
        {Array.from({ length: 14 }, (_, index) => {
          const side = index % 2 ? 1 : -1;
          const row = Math.floor(index / 2);
          return (
            <mesh
              key={index}
              position={[
                side * (2.1 + (row % 3) * 0.55),
                (row - 3) * 0.73,
                -row * 0.48,
              ]}
              rotation={[
                index * 0.05,
                side * 0.28,
                side * index * 0.025,
              ]}
            >
              <boxGeometry args={[1.28, 0.64, 0.12]} />
              <meshPhysicalMaterial
                color="#06100d"
                metalness={0.84}
                roughness={0.2}
                clearcoat={0.7}
                emissive={index % 3 === 0 ? "#16450d" : "#07303a"}
                emissiveIntensity={0.26}
              />
            </mesh>
          );
        })}
      </group>
      <Rail
        color="#d8ffc1"
        speed={0.055}
        points={[
          [-4.5, 2.6, 2.5],
          [-2.6, 1.4, 1],
          [-1.1, 0.65, 0],
          [0, 0, -1.4],
          [1.1, -0.6, -2.5],
        ]}
      />
    </group>
  );
}

function ExecutionTunnel() {
  return (
    <group>
      {Array.from({ length: 12 }, (_, index) => {
        const z = -34 - index * 1.25;
        const scale = 1 + index * 0.025;
        return (
          <group
            key={index}
            position={[0, 0, z]}
            scale={scale}
          >
            <mesh rotation={[0, 0, index * 0.12]}>
              <torusGeometry args={[2.8, 0.035, 8, 100]} />
              <meshBasicMaterial
                color={index % 3 === 0 ? "#9dff4a" : "#00d9ff"}
                transparent
                opacity={0.1 + index * 0.005}
                toneMapped={false}
              />
            </mesh>
            {[-1, 1].map((side) => (
              <mesh key={side} position={[side * 3.25, 0, 0]}>
                <boxGeometry args={[0.08, 4.8, 0.3]} />
                <meshStandardMaterial
                  color="#06100d"
                  emissive="#0f2910"
                  emissiveIntensity={0.18}
                  metalness={0.85}
                  roughness={0.24}
                />
              </mesh>
            ))}
          </group>
        );
      })}
    </group>
  );
}

function RevenueVault() {
  const monolith = useRef<THREE.Mesh>(null);
  useFrame((state) => {
    if (!monolith.current) return;
    monolith.current.rotation.y =
      Math.sin(state.clock.elapsedTime * 0.18) * 0.08;
  });

  return (
    <group position={[0, 0, -58]}>
      <pointLight
        color="#9dff4a"
        intensity={26}
        distance={12}
        position={[0, 0, 2]}
      />
      <mesh ref={monolith}>
        <boxGeometry args={[3.3, 5.8, 0.82]} />
        <meshPhysicalMaterial
          color="#020403"
          metalness={0.97}
          roughness={0.09}
          clearcoat={1}
          clearcoatRoughness={0.04}
          emissive="#0d1e0a"
          emissiveIntensity={0.18}
        />
      </mesh>
      <mesh position={[0, 0, 0.43]}>
        <planeGeometry args={[2.45, 4.92]} />
        <meshBasicMaterial color="#06100a" />
      </mesh>
      {Array.from({ length: 12 }, (_, index) => (
        <mesh
          key={index}
          position={[0, 2.08 - index * 0.37, 0.445]}
        >
          <planeGeometry
            args={[1.85 - (index % 4) * 0.19, 0.022]}
          />
          <meshBasicMaterial
            color={index < 9 ? "#9dff4a" : "#00d9ff"}
            transparent
            opacity={0.24 + (11 - index) * 0.035}
            toneMapped={false}
          />
        </mesh>
      ))}
    </group>
  );
}

function Hotspot({
  position,
  label,
  target,
}: {
  position: V3;
  label: string;
  target: number;
}) {
  const scroll = useScroll();
  const [hovered, setHovered] = useState(false);
  useCursor(hovered);

  const jump = () => {
    const max =
      scroll.el.scrollHeight - scroll.el.clientHeight;
    scroll.el.scrollTo({
      top: target * max,
      behavior: "smooth",
    });
  };

  return (
    <group position={position}>
      <mesh
        onPointerEnter={(event) => {
          event.stopPropagation();
          setHovered(true);
        }}
        onPointerLeave={() => setHovered(false)}
        onClick={(event) => {
          event.stopPropagation();
          jump();
        }}
        scale={hovered ? 1.24 : 1}
      >
        <sphereGeometry args={[0.14, 16, 16]} />
        <meshBasicMaterial
          color={hovered ? "#ffffff" : "#9dff4a"}
          toneMapped={false}
        />
      </mesh>
      <mesh
        rotation={[Math.PI / 2, 0, 0]}
        scale={hovered ? 1.4 : 1}
      >
        <torusGeometry args={[0.32, 0.012, 8, 48]} />
        <meshBasicMaterial
          color="#9dff4a"
          transparent
          opacity={hovered ? 0.85 : 0.32}
          toneMapped={false}
        />
      </mesh>
      <Html
        center
        distanceFactor={10}
        position={[0, 0.58, 0]}
        style={{ pointerEvents: "none" }}
      >
        <div
          className={
            "whitespace-nowrap rounded-full border px-3 py-1.5 text-[8px] font-black tracking-[0.16em] backdrop-blur-xl transition " +
            (hovered
              ? "border-[#9dff4a]/50 bg-[#081008]/85 text-white"
              : "border-white/10 bg-black/45 text-white/40")
          }
        >
          {label}
        </div>
      </Html>
    </group>
  );
}

function World() {
  return (
    <>
      <fog attach="fog" args={["#020403", 8, 34]} />
      <ambientLight intensity={0.2} />
      <directionalLight
        position={[5, 9, 7]}
        intensity={1.6}
        color="#e8ffe0"
      />
      <pointLight
        position={[-4, 3, -20]}
        color="#00d9ff"
        intensity={8}
        distance={18}
      />

      <CameraFlight />
      <SignalDust />
      <Gate />
      <SignalAtrium />
      <Reactor />
      <OpportunityVault />
      <ExecutionTunnel />
      <RevenueVault />

      <Hotspot
        position={[2.8, 1.9, -1.5]}
        label="SIGNALS"
        target={CHAPTERS[0].at}
      />
      <Hotspot
        position={[2.5, 1.8, -13.5]}
        label="REACTOR"
        target={CHAPTERS[1].at}
      />
      <Hotspot
        position={[-2.4, 1.75, -27]}
        label="OPPORTUNITY"
        target={CHAPTERS[2].at}
      />
      <Hotspot
        position={[2.45, 1.6, -40]}
        label="EXECUTION"
        target={CHAPTERS[3].at}
      />
      <Hotspot
        position={[-2.25, 1.6, -57.5]}
        label="REVENUE"
        target={CHAPTERS[4].at}
      />
    </>
  );
}

function ScrollNarrative() {
  return (
    <Scroll html>
      <div className="pointer-events-none w-screen">
        <section className="flex h-screen items-end px-5 pb-12 md:px-10 md:pb-16 lg:px-14">
          <div className="max-w-[800px]">
            <div className="mb-5 text-[9px] font-black tracking-[0.26em] text-[#9dff4a]">
              ENTER EMPIRE
            </div>
            <h1 className="max-w-[900px] text-[clamp(3.8rem,8.2vw,9rem)] font-[520] leading-[0.82] tracking-[-0.07em] text-[#f5fff6]">
              Walk through
              <span className="block text-white/28">
                predictive revenue.
              </span>
            </h1>
            <p className="mt-6 max-w-xl text-[14px] leading-7 text-white/45 sm:text-[16px]">
              Scroll to travel. Move your pointer to look around. Hover the
              glowing nodes to navigate the machine.
            </p>
          </div>
        </section>

        {CHAPTERS.map((chapter, index) => (
          <section
            key={chapter.id}
            className={
              "flex h-screen items-center px-5 md:px-10 lg:px-14 " +
              (index % 2 ? "justify-end" : "justify-start")
            }
          >
            <div
              className={
                "max-w-[510px] " +
                (index % 2 ? "text-right" : "")
              }
            >
              <div className="mb-4 text-[8px] font-black tracking-[0.24em] text-[#9dff4a]">
                {chapter.index} · {chapter.eyebrow}
              </div>
              <h2 className="text-[clamp(2.5rem,5vw,5.2rem)] font-[520] leading-[0.9] tracking-[-0.055em] text-white">
                {chapter.title}
              </h2>
              <p
                className={
                  "mt-6 max-w-[500px] text-[13px] leading-6 text-white/42 sm:text-[15px] " +
                  (index % 2 ? "ml-auto" : "")
                }
              >
                {chapter.body}
              </p>
            </div>
          </section>
        ))}

        <section className="flex h-screen items-center px-5 md:px-10 lg:px-14">
          <div className="max-w-[760px]">
            <div className="mb-5 text-[9px] font-black tracking-[0.25em] text-[#9dff4a]">
              THE LOOP CLOSES
            </div>
            <h2 className="text-[clamp(3.4rem,7vw,7.5rem)] font-[520] leading-[0.85] tracking-[-0.065em] text-white">
              Own the intelligence.
              <span className="block text-white/24">
                Own the outcome.
              </span>
            </h2>
            <div className="pointer-events-auto mt-8 flex flex-wrap gap-3">
              <a
                href="mailto:founder@empire-ai.co.uk"
                className="rounded-full bg-[#b6ff88] px-5 py-3 text-[9px] font-black tracking-[0.12em] text-black transition hover:-translate-y-0.5"
              >
                TALK TO EMPIRE
              </a>
              <a
                href="/trust"
                className="rounded-full border border-white/10 bg-black/35 px-5 py-3 text-[9px] font-black tracking-[0.12em] text-white/60 backdrop-blur-xl transition hover:border-white/20 hover:text-white"
              >
                TRUST & EVIDENCE
              </a>
            </div>
          </div>
        </section>
      </div>
    </Scroll>
  );
}

export default function EmpireWorld() {
  return (
    <div className="h-screen w-screen bg-[#020403]">
      <Canvas
        camera={{
          position: [0, 0.35, 12],
          fov: 48,
          near: 0.08,
          far: 100,
        }}
        dpr={[1, 1.45]}
        gl={{
          antialias: true,
          powerPreference: "high-performance",
        }}
      >
        <color attach="background" args={["#020403"]} />
        <ScrollControls
          pages={7}
          damping={0.16}
          distance={1}
          maxSpeed={0.18}
        >
          <World />
          <ScrollNarrative />
        </ScrollControls>
      </Canvas>
    </div>
  );
}
