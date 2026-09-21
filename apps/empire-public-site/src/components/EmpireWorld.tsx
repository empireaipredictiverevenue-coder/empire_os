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
  useEffect,
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
      scroll.el.scrollTo({
        top: target * max,
        behavior: "smooth",
      });
    };

    window.addEventListener("empire-jump", handleJump as EventListener);
    return () => {
      window.removeEventListener("empire-jump", handleJump as EventListener);
    };
  }, [scroll]);

  useFrame(() => {
    if (!onProgress) return;
    const value = scroll.offset;
    if (Math.abs(value - last.current) < 0.008) return;
    last.current = value;
    onProgress(value);
  });

  return null;
}

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
      Array.from({ length: 110 }, (_, index) => {
        const z = 10 - (index / 110) * 68;
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
  color = "#4f8cff",
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
          color="#050b1c"
          metalness={0.92}
          roughness={0.18}
          emissive="#0c1f4a"
          emissiveIntensity={0.25}
        />
      </mesh>
      <mesh position={[3.3, 0, 0]}>
        <boxGeometry args={[0.5, 7.5, 1.3]} />
        <meshStandardMaterial
          color="#050b1c"
          metalness={0.92}
          roughness={0.18}
          emissive="#0c1f4a"
          emissiveIntensity={0.25}
        />
      </mesh>
      <mesh position={[0, 3.5, 0]}>
        <boxGeometry args={[7.1, 0.5, 1.3]} />
        <meshStandardMaterial
          color="#050b1c"
          metalness={0.92}
          roughness={0.18}
          emissive="#08252a"
          emissiveIntensity={0.28}
        />
      </mesh>
      <mesh position={[0, -3.5, 0]}>
        <boxGeometry args={[7.1, 0.16, 1.3]} />
        <meshBasicMaterial
          color="#4f8cff"
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
      {Array.from({ length: 12 }, (_, index) => {
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
              color="#071127"
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
  const core = useRef<THREE.Group>(null);
  const [hovered, setHovered] = useState(false);
  const [charged, setCharged] = useState(false);
  useCursor(hovered);

  useFrame((state, delta) => {
    const t = state.clock.elapsedTime;
    if (rings.current) {
      const speed = charged ? 0.6 : hovered ? 0.34 : 0.18;
      rings.current.rotation.x += delta * speed * 0.7;
      rings.current.rotation.y -= delta * speed;
    }
    if (core.current) {
      const target = charged ? 1.22 : hovered ? 1.1 : 1;
      const lerp = 1 - Math.exp(-delta * 7);
      core.current.scale.lerp(
        new THREE.Vector3(target, target, target),
        lerp,
      );
      core.current.rotation.y += delta * (charged ? 0.5 : 0.16);
      core.current.rotation.x =
        Math.sin(t * 0.45) * (charged ? 0.22 : 0.08);
    }
  });

  return (
    <group position={[0, 0, -14]}>
      <pointLight
        color={charged ? "#dbeafe" : "#4f8cff"}
        intensity={charged ? 34 : 20}
        distance={14}
      />
      <pointLight
        color="#00d9ff"
        intensity={hovered ? 19 : 12}
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
              args={[radius, index === 0 ? 0.045 : 0.025, 10, 96]}
            />
            <meshBasicMaterial
              color={index === 1 ? "#00d9ff" : "#4f8cff"}
              transparent
              opacity={(charged ? 0.74 : 0.5) - index * 0.11}
              toneMapped={false}
            />
          </mesh>
        ))}
      </group>

      <group
        ref={core}
        onPointerEnter={(event) => {
          event.stopPropagation();
          setHovered(true);
        }}
        onPointerLeave={() => setHovered(false)}
        onClick={(event) => {
          event.stopPropagation();
          setCharged((value) => !value);
        }}
      >
        <mesh>
          <icosahedronGeometry args={[1.18, 2]} />
          <meshPhysicalMaterial
            color={charged ? "#102114" : "#08120d"}
            metalness={0.88}
            roughness={0.14}
            clearcoat={1}
            clearcoatRoughness={0.06}
            emissive={charged ? "#2563eb" : "#173b8f"}
            emissiveIntensity={charged ? 1.1 : 0.5}
          />
        </mesh>
        <mesh scale={1.03}>
          <icosahedronGeometry args={[1.18, 2]} />
          <meshBasicMaterial
            color={charged ? "#ffffff" : "#7dd3fc"}
            wireframe
            transparent
            opacity={charged ? 0.36 : 0.18}
            toneMapped={false}
          />
        </mesh>
      </group>

      <Html
        center
        position={[0, -2.2, 0]}
        distanceFactor={9}
        style={{ pointerEvents: "none" }}
      >
        <div className="whitespace-nowrap text-[7px] font-black tracking-[0.18em] text-white/25">
          {charged ? "REACTOR CHARGED" : "CLICK TO CHARGE"}
        </div>
      </Html>
    </group>
  );
}

function OpportunityVault() {
  const floating = useRef<THREE.Group>(null);
  const leftDoor = useRef<THREE.Group>(null);
  const rightDoor = useRef<THREE.Group>(null);
  const [hovered, setHovered] = useState(false);
  const [open, setOpen] = useState(false);
  useCursor(hovered);

  useFrame((state, delta) => {
    if (floating.current) {
      const t = state.clock.elapsedTime;
      floating.current.children.forEach((child, index) => {
        child.rotation.y += 0.0007 * (index % 2 ? 1 : -1);
        child.position.y += Math.sin(t * 0.45 + index) * 0.0008;
      });
    }

    const target = open ? 2.05 : 0.58;
    const ease = 1 - Math.exp(-delta * 5.5);
    if (leftDoor.current) {
      leftDoor.current.position.x = THREE.MathUtils.lerp(
        leftDoor.current.position.x,
        -target,
        ease,
      );
      leftDoor.current.rotation.y = THREE.MathUtils.lerp(
        leftDoor.current.rotation.y,
        open ? -0.24 : 0,
        ease,
      );
    }
    if (rightDoor.current) {
      rightDoor.current.position.x = THREE.MathUtils.lerp(
        rightDoor.current.position.x,
        target,
        ease,
      );
      rightDoor.current.rotation.y = THREE.MathUtils.lerp(
        rightDoor.current.rotation.y,
        open ? 0.24 : 0,
        ease,
      );
    }
  });

  return (
    <group position={[0, 0, -27]}>
      <group ref={floating}>
        {Array.from({ length: 10 }, (_, index) => {
          const side = index % 2 ? 1 : -1;
          const row = Math.floor(index / 2);
          return (
            <mesh
              key={index}
              position={[
                side * (2.35 + (row % 3) * 0.55),
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
                color="#071127"
                metalness={0.84}
                roughness={0.2}
                clearcoat={0.7}
                emissive={index % 3 === 0 ? "#1d4ed8" : "#07303a"}
                emissiveIntensity={0.26}
              />
            </mesh>
          );
        })}
      </group>

      <group
        onPointerEnter={(event) => {
          event.stopPropagation();
          setHovered(true);
        }}
        onPointerLeave={() => setHovered(false)}
        onClick={(event) => {
          event.stopPropagation();
          setOpen((value) => !value);
        }}
      >
        <group ref={leftDoor} position={[-0.58, 0, 0]}>
          <mesh>
            <boxGeometry args={[1.08, 4.8, 0.24]} />
            <meshPhysicalMaterial
              color="#050b1c"
              metalness={0.94}
              roughness={0.13}
              clearcoat={1}
              emissive="#12310c"
              emissiveIntensity={hovered ? 0.7 : 0.32}
            />
          </mesh>
        </group>
        <group ref={rightDoor} position={[0.58, 0, 0]}>
          <mesh>
            <boxGeometry args={[1.08, 4.8, 0.24]} />
            <meshPhysicalMaterial
              color="#050b1c"
              metalness={0.94}
              roughness={0.13}
              clearcoat={1}
              emissive="#062f38"
              emissiveIntensity={hovered ? 0.7 : 0.32}
            />
          </mesh>
        </group>
      </group>

      <LightShaft
        position={[0, 0.3, -0.5]}
        height={6.4}
        radius={1.05}
        color={open ? "#bfdbfe" : "#4f8cff"}
      />

      <Rail
        color="#a5f3fc"
        speed={0.055}
        points={[
          [-4.5, 2.6, 2.5],
          [-2.6, 1.4, 1],
          [-1.1, 0.65, 0],
          [0, 0, -1.4],
          [1.1, -0.6, -2.5],
        ]}
      />

      <Html
        center
        position={[0, -2.95, 0]}
        distanceFactor={9}
        style={{ pointerEvents: "none" }}
      >
        <div className="whitespace-nowrap text-[7px] font-black tracking-[0.18em] text-white/25">
          {open ? "VAULT OPEN" : "CLICK TO OPEN"}
        </div>
      </Html>
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
              <torusGeometry args={[2.8, 0.035, 8, 72]} />
              <meshBasicMaterial
                color={index % 3 === 0 ? "#4f8cff" : "#00d9ff"}
                transparent
                opacity={0.1 + index * 0.005}
                toneMapped={false}
              />
            </mesh>
            {[-1, 1].map((side) => (
              <mesh key={side} position={[side * 3.25, 0, 0]}>
                <boxGeometry args={[0.08, 4.8, 0.3]} />
                <meshStandardMaterial
                  color="#071127"
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
      <AgentStreams />
    </group>
  );
}

function AgentStreams() {
  const refs = useRef<Array<THREE.Mesh | null>>([]);
  const paths = useMemo(
    () => [
      new THREE.CatmullRomCurve3([
        new THREE.Vector3(-2.2, 1.1, -34),
        new THREE.Vector3(-1.2, 0.2, -38),
        new THREE.Vector3(1.4, -0.4, -43),
        new THREE.Vector3(2.4, 0.8, -48),
      ]),
      new THREE.CatmullRomCurve3([
        new THREE.Vector3(2.1, -1.3, -35),
        new THREE.Vector3(0.8, -0.2, -39),
        new THREE.Vector3(-1.8, 0.7, -44),
        new THREE.Vector3(-2.2, -0.1, -48),
      ]),
      new THREE.CatmullRomCurve3([
        new THREE.Vector3(-0.2, 2.2, -35),
        new THREE.Vector3(1.3, 1.0, -39),
        new THREE.Vector3(-0.8, -0.9, -44),
        new THREE.Vector3(0.3, 0.1, -49),
      ]),
    ],
    [],
  );

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    refs.current.forEach((mesh, index) => {
      if (!mesh) return;
      const curve = paths[index % paths.length];
      const offset = (t * (0.055 + index * 0.01) + index * 0.27) % 1;
      mesh.position.copy(curve.getPointAt(offset));
      const next = curve.getPointAt((offset + 0.01) % 1);
      mesh.lookAt(next);
      mesh.rotation.z = Math.sin(t * 0.8 + index) * 0.15;
    });
  });

  return (
    <group>
      {Array.from({ length: 6 }, (_, index) => (
        <mesh
          key={index}
          ref={(node) => {
            refs.current[index] = node;
          }}
        >
          <octahedronGeometry args={[0.12 + (index % 2) * 0.04, 0]} />
          <meshBasicMaterial
            color={index % 2 ? "#00d9ff" : "#7dd3fc"}
            toneMapped={false}
          />
        </mesh>
      ))}
    </group>
  );
}

function ArchitecturalSpine() {
  return (
    <group>
      {Array.from({ length: 24 }, (_, index) => {
        const z = 7 - index * 2.05;
        const width = 4.4 + (index % 5) * 0.18;
        return (
          <group key={index} position={[0, 0, z]}>
            <mesh position={[0, -3.15, 0]}>
              <boxGeometry args={[width * 2, 0.08, 1.5]} />
              <meshStandardMaterial
                color="#040a18"
                metalness={0.82}
                roughness={0.24}
                emissive={index % 4 === 0 ? "#0d2a64" : "#041014"}
                emissiveIntensity={0.18}
              />
            </mesh>
            <mesh position={[0, 3.25, 0]}>
              <boxGeometry args={[width * 2, 0.06, 1.1]} />
              <meshStandardMaterial
                color="#040a18"
                metalness={0.9}
                roughness={0.2}
                emissive={index % 3 === 0 ? "#06252a" : "#0c1c08"}
                emissiveIntensity={0.14}
              />
            </mesh>
            {[-1, 1].map((side) => (
              <mesh
                key={side}
                position={[side * width, 0, 0]}
              >
                <boxGeometry args={[0.08, 6.4, 0.55]} />
                <meshStandardMaterial
                  color="#050b1c"
                  metalness={0.92}
                  roughness={0.18}
                  emissive={index % 2 ? "#082329" : "#102a66"}
                  emissiveIntensity={0.2}
                />
              </mesh>
            ))}
          </group>
        );
      })}
    </group>
  );
}

function LightShaft({
  position,
  height = 6,
  radius = 1.3,
  color = "#4f8cff",
}: {
  position: V3;
  height?: number;
  radius?: number;
  color?: string;
}) {
  return (
    <group position={position}>
      <mesh rotation={[Math.PI, 0, 0]}>
        <coneGeometry args={[radius, height, 24, 1, true]} />
        <meshBasicMaterial
          color={color}
          transparent
          opacity={0.055}
          side={THREE.DoubleSide}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
          toneMapped={false}
        />
      </mesh>
      <pointLight
        color={color}
        intensity={5}
        distance={height * 1.1}
        position={[0, height * 0.28, 0]}
      />
    </group>
  );
}

function FloatingShardField() {
  const group = useRef<THREE.Group>(null);

  useFrame((state) => {
    if (!group.current) return;
    const t = state.clock.elapsedTime;
    group.current.children.forEach((child, index) => {
      child.rotation.x = t * (0.08 + (index % 4) * 0.02);
      child.rotation.y = t * (0.06 + (index % 5) * 0.015);
      child.position.y += Math.sin(t * 0.35 + index) * 0.0007;
    });
  });

  return (
    <group ref={group}>
      {Array.from({ length: 14 }, (_, index) => {
        const z = 2 - index * 2.55;
        const side = index % 2 ? 1 : -1;
        return (
          <mesh
            key={index}
            position={[
              side * (3.1 + (index % 4) * 0.34),
              ((index * 7) % 9) * 0.48 - 1.8,
              z,
            ]}
            rotation={[
              index * 0.17,
              index * 0.23,
              index * 0.09,
            ]}
          >
            <octahedronGeometry args={[0.18 + (index % 3) * 0.07, 0]} />
            <meshPhysicalMaterial
              color="#08142c"
              metalness={0.95}
              roughness={0.1}
              clearcoat={1}
              clearcoatRoughness={0.04}
              emissive={index % 3 === 0 ? "#1e40af" : "#062d35"}
              emissiveIntensity={0.34}
            />
          </mesh>
        );
      })}
    </group>
  );
}

function WorldChapter({
  position,
  chapter,
  side = "left",
}: {
  position: V3;
  chapter: (typeof CHAPTERS)[number];
  side?: "left" | "right";
}) {
  const scroll = useScroll();
  const ref = useRef<HTMLDivElement>(null);

  useFrame(() => {
    if (!ref.current) return;
    const distance = Math.abs(scroll.offset - chapter.at);
    const opacity = THREE.MathUtils.clamp(
      1 - distance / 0.12,
      0,
      1,
    );
    ref.current.style.opacity = String(opacity);
    ref.current.style.transform =
      "translate3d(0," + ((1 - opacity) * 14).toFixed(1) + "px,0)";
  });

  return (
    <Html
      transform
      sprite
      center
      position={position}
      distanceFactor={8.5}
      style={{ pointerEvents: "none" }}
    >
      <div
        ref={ref}
        className={
          "w-[320px] rounded-2xl border border-white/10 bg-black/55 p-5 text-white shadow-2xl backdrop-blur-2xl transition-opacity md:w-[390px] " +
          (side === "right" ? "text-right" : "text-left")
        }
      >
        <div className="text-[8px] font-black tracking-[0.24em] text-[#4f8cff]">
          {chapter.index} · {chapter.eyebrow}
        </div>
        <div className="mt-3 text-[26px] font-[520] leading-[0.94] tracking-[-0.045em] md:text-[34px]">
          {chapter.title}
        </div>
        <div className="mt-4 text-[10px] leading-5 text-white/42 md:text-[11px]">
          {chapter.body}
        </div>
      </div>
    </Html>
  );
}

function RevenueVault() {
  const scroll = useScroll();
  const shell = useRef<THREE.Group>(null);
  const left = useRef<THREE.Mesh>(null);
  const right = useRef<THREE.Mesh>(null);

  useFrame((state, delta) => {
    const proximity = THREE.MathUtils.smoothstep(
      scroll.offset,
      0.79,
      0.96,
    );
    const spread = proximity * 1.72;
    const ease = 1 - Math.exp(-delta * 5);

    if (shell.current) {
      shell.current.rotation.y = Math.sin(state.clock.elapsedTime * 0.18) * 0.045;
    }
    if (left.current) {
      left.current.position.x = THREE.MathUtils.lerp(
        left.current.position.x,
        -0.84 - spread,
        ease,
      );
    }
    if (right.current) {
      right.current.position.x = THREE.MathUtils.lerp(
        right.current.position.x,
        0.84 + spread,
        ease,
      );
    }
  });

  return (
    <group position={[0, 0, -58]}>
      <pointLight
        color="#4f8cff"
        intensity={30}
        distance={13}
        position={[0, 0, 2]}
      />
      <group ref={shell}>
        <mesh ref={left} position={[-0.84, 0, 0]}>
          <boxGeometry args={[1.58, 5.8, 0.82]} />
          <meshPhysicalMaterial
            color="#020817"
            metalness={0.97}
            roughness={0.09}
            clearcoat={1}
            clearcoatRoughness={0.04}
            emissive="#0f2458"
            emissiveIntensity={0.22}
          />
        </mesh>
        <mesh ref={right} position={[0.84, 0, 0]}>
          <boxGeometry args={[1.58, 5.8, 0.82]} />
          <meshPhysicalMaterial
            color="#020817"
            metalness={0.97}
            roughness={0.09}
            clearcoat={1}
            clearcoatRoughness={0.04}
            emissive="#06242b"
            emissiveIntensity={0.2}
          />
        </mesh>
      </group>

      <mesh position={[0, 0, 0.1]}>
        <boxGeometry args={[1.1, 4.5, 0.3]} />
        <meshBasicMaterial
          color="#4f8cff"
          transparent
          opacity={0.12}
          toneMapped={false}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>

      {Array.from({ length: 12 }, (_, index) => (
        <mesh
          key={index}
          position={[0, 2.08 - index * 0.37, 0.48]}
        >
          <planeGeometry
            args={[1.85 - (index % 4) * 0.19, 0.022]}
          />
          <meshBasicMaterial
            color={index < 9 ? "#4f8cff" : "#00d9ff"}
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
        <sphereGeometry args={[0.24, 18, 18]} />
        <meshBasicMaterial
          color={hovered ? "#ffffff" : "#4f8cff"}
          toneMapped={false}
        />
      </mesh>
      <mesh
        rotation={[Math.PI / 2, 0, 0]}
        scale={hovered ? 1.4 : 1}
      >
        <torusGeometry args={[0.48, 0.018, 8, 56]} />
        <meshBasicMaterial
          color="#4f8cff"
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
              ? "border-[#4f8cff]/50 bg-[#071329]/85 text-white"
              : "border-white/10 bg-black/45 text-white/40")
          }
        >
          {label}
        </div>
      </Html>
    </group>
  );
}

function World({
  onProgress,
}: {
  onProgress?: (progress: number) => void;
}) {
  return (
    <>
      <fog attach="fog" args={["#020817", 8, 34]} />
      <ambientLight intensity={0.2} />
      <directionalLight
        position={[5, 9, 7]}
        intensity={1.6}
        color="#dbeafe"
      />
      <pointLight
        position={[-4, 3, -20]}
        color="#00d9ff"
        intensity={8}
        distance={18}
      />

      <ScrollBridge onProgress={onProgress} />
      <CameraFlight />
      <ArchitecturalSpine />
      <SignalDust />
      <FloatingShardField />
      <Gate />
      <SignalAtrium />
      <Reactor />
      <OpportunityVault />
      <ExecutionTunnel />
      <RevenueVault />

      <LightShaft position={[-2.1, 0.4, -3]} height={7} radius={1.5} />
      <LightShaft position={[2.1, 0.2, -14]} height={7} radius={1.4} color="#00d9ff" />
      <LightShaft position={[-2.25, 0.25, -27]} height={7} radius={1.5} />
      <LightShaft position={[2.35, 0.1, -41]} height={7} radius={1.35} color="#00d9ff" />
      <LightShaft position={[-1.8, 0.15, -58]} height={8} radius={1.6} />

      <WorldChapter position={[-3.45, 1.15, -3.0]} chapter={CHAPTERS[0]} />
      <WorldChapter position={[3.35, 1.2, -14.2]} chapter={CHAPTERS[1]} side="right" />
      <WorldChapter position={[-3.4, 1.0, -27.4]} chapter={CHAPTERS[2]} />
      <WorldChapter position={[3.4, 1.0, -41.0]} chapter={CHAPTERS[3]} side="right" />
      <WorldChapter position={[-3.1, 0.9, -58.0]} chapter={CHAPTERS[4]} />

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
          <div className="max-w-[720px]">
            <div className="mb-5 text-[9px] font-black tracking-[0.26em] text-[#4f8cff]">
              ENTER EMPIRE
            </div>
            <h1 className="text-[clamp(3.8rem,8.2vw,8.8rem)] font-[520] leading-[0.82] tracking-[-0.07em] text-[#f5fff6]">
              Walk through
              <span className="block text-white/25">
                predictive revenue.
              </span>
            </h1>
            <p className="mt-6 max-w-lg text-[14px] leading-7 text-white/42">
              Scroll to move through the system. The world, objects and
              chapters exist in the space around you.
            </p>
          </div>
        </section>

        {Array.from({ length: 5 }, (_, index) => (
          <section
            key={index}
            aria-hidden="true"
            className="h-screen"
          />
        ))}

        <section className="flex h-screen items-center px-5 md:px-10 lg:px-14">
          <div className="max-w-[700px]">
            <div className="mb-5 text-[9px] font-black tracking-[0.25em] text-[#4f8cff]">
              THE LOOP CLOSES
            </div>
            <h2 className="text-[clamp(3.2rem,6.5vw,7.2rem)] font-[520] leading-[0.86] tracking-[-0.065em] text-white">
              Own the intelligence.
              <span className="block text-white/24">
                Own the outcome.
              </span>
            </h2>
            <div className="pointer-events-auto mt-8 flex flex-wrap gap-3">
              <a
                href="mailto:founder@empire-ai.co.uk"
                className="rounded-full bg-[#7dd3fc] px-5 py-3 text-[9px] font-black tracking-[0.12em] text-black transition hover:-translate-y-0.5"
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

export default function EmpireWorld({
  onReady,
  onProgress,
}: {
  onReady?: () => void;
  onProgress?: (progress: number) => void;
}) {
  return (
    <div className="h-screen w-screen bg-[#020817]">
      <Canvas
        onCreated={() => onReady?.()}
        camera={{
          position: [0, 0.35, 12],
          fov: 48,
          near: 0.08,
          far: 100,
        }}
        dpr={[1, 1.25]}
        gl={{
          antialias: false,
          alpha: false,
          stencil: false,
          powerPreference: "high-performance",
        }}
      >
        <color attach="background" args={["#020817"]} />
        <ScrollControls
          pages={7}
          damping={0.16}
          distance={1}
          maxSpeed={0.18}
        >
          <World onProgress={onProgress} />
          <ScrollNarrative />
        </ScrollControls>
      </Canvas>
    </div>
  );
}
