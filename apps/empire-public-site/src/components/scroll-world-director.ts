import * as THREE from "three";

/**
 * Scroll World-style director for the EXISTING single Empire AI WebGL renderer.
 * Native document scroll is the source of truth; positions are deterministic,
 * reversible and independent of the discrete chapter selection.
 *
 * Do not add a second Canvas, paid rendered-video backend or independent wheel
 * listener. The host already handles reduced motion and low-spec fallbacks.
 */
const HERO_CAMERA = new THREE.Vector3(0.1, 0.3, 6.05);
const WORLD_CAMERA = new THREE.CatmullRomCurve3(
  [
    new THREE.Vector3(0, 0.5, 9),
    new THREE.Vector3(-0.36, 0.56, 4),
    new THREE.Vector3(0.48, 0.46, -1),
    new THREE.Vector3(-0.45, 0.6, -6),
    new THREE.Vector3(0, 0.8, -12),
  ],
  false,
  "catmullrom",
  0.3,
);

const clamp01 = (value: number) =>
  Number.isFinite(value) ? THREE.MathUtils.clamp(value, 0, 1) : 0;

export type ScrollWorldFrame = {
  progress: number;
  entry: number;
  chapter: number;
  chapterBlend: number;
  warmth: number;
};

/** Reuse a frame across animation ticks to avoid creating garbage at 60 fps. */
export const createScrollWorldFrame = (): ScrollWorldFrame => ({
  progress: 0, entry: 0, chapter: 0, chapterBlend: 0, warmth: 0,
});

/**
 * Populates the supplied reusable vectors: no allocations in the render loop.
 * The chapter indicator is metadata only; it cannot snap the camera.
 */
export function sampleScrollWorld(
  scrollProgress: number,
  crossingProgress: number,
  position: THREE.Vector3,
  lookTarget: THREE.Vector3,
  frame: ScrollWorldFrame = createScrollWorldFrame(),
): ScrollWorldFrame {
  const progress = clamp01(scrollProgress);
  const entry = clamp01(crossingProgress);

  // Five continuous spatial waypoints: signal, priority, match, execution, truth.
  WORLD_CAMERA.getPoint(progress, position);
  position.z -= 8;
  position.lerp(HERO_CAMERA, 1 - entry);
  position.z -= Math.sin(entry * Math.PI) * 1.15;

  // Aim ahead down the real data-centre corridor, rather than turning to face
  // a new disconnected scene for each text chapter.
  lookTarget.set(
    entry * Math.sin(progress * Math.PI * 2) * 0.16,
    0.1 + entry * (0.25 + 0.08 * Math.sin(progress * Math.PI)),
    entry * (-9 - 20 * progress),
  );

  const phase = progress * 4;
  const chapter = Math.min(4, Math.floor(phase + 0.5));
  const chapterBlend = THREE.MathUtils.smoothstep(phase % 1, 0, 1);
  const warmth = entry * THREE.MathUtils.smoothstep(progress, 0.6, 1);

  frame.progress = progress;
  frame.entry = entry;
  frame.chapter = chapter;
  frame.chapterBlend = chapterBlend;
  frame.warmth = warmth;
  return frame;
}
