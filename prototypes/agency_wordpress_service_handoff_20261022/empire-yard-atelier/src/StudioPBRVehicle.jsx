import React, { useEffect, useMemo, useRef } from 'react'
import { useGLTF, OrbitControls } from '@react-three/drei'
import * as THREE from 'three'

/**
 * Third-party CC BY 4.0 Khronos Sample Assets / CarConcept derivative.
 * © 2024 Eric Chadwick, Darmstadt Graphics Group GmbH.
 * Two logo-bearing nodes were removed; see assets/models/MODEL_PROVENANCE.json.
 * Not real dealership stock, not an Empire AI model or manufacturer endorsement.
 * This component is lazy-imported ONLY after an explicit Studio PBR click.
 */
export default function StudioPBRVehicle({ modelUrl, paint, view, motionAllowed, onReady }) {
  const { scene } = useGLTF(modelUrl, false, true) // disable remote DRACO decoder; use bundled Meshopt
  const { model, scale, center, floor } = useMemo(() => {
    const copy = scene.clone(true)
    const bbox = new THREE.Box3().setFromObject(copy)
    const dimensions = bbox.getSize(new THREE.Vector3())
    if (!Number.isFinite(dimensions.x) || dimensions.length() < .01) {
      throw new Error('Invalid licensed showroom GLB geometry')
    }
    const maxHorizontal = Math.max(dimensions.x, dimensions.z)
    const factor = 4.65 / maxHorizontal
    copy.traverse(node => {
      if (!node.isMesh) return
      node.castShadow = false
      node.receiveShadow = false
      const materials = Array.isArray(node.material) ? node.material : [node.material]
      const replacements = materials.map(material => {
        if (!material) return material
        // Khronos high-end sample relies on costly transmission/iridescence
        // shader branches; clamp these in the on-demand website preview only.
        const needsPaint = /^Paint [12] Carmine$/.test(material.name || '')
        const expensive = !!material.isMeshPhysicalMaterial &&
          (material.transmission > 0 || material.iridescence > 0)
        if (!needsPaint && !expensive) return material
        const replacement = material.clone()
        replacement.userData.empireStudioDerived = true
        if (needsPaint) {
          replacement.color.set(paint.body)
          replacement.metalness = Math.max(replacement.metalness ?? .5, .66)
          replacement.roughness = .24
        }
        if ('transmission' in replacement) replacement.transmission = 0
        if ('iridescence' in replacement) replacement.iridescence = 0
        if ('clearcoat' in replacement) {
          replacement.clearcoat = .6
          replacement.clearcoatRoughness = .12
        }
        return replacement
      })
      node.material = Array.isArray(node.material) ? replacements : replacements[0]
    })
    return {
      model: copy, scale: factor,
      center: bbox.getCenter(new THREE.Vector3()),
      floor: bbox.min.y,
    }
  }, [scene, paint.body])

  useEffect(() => {
    onReady?.()
    return () => {
      model.traverse(node => {
        if (!node.isMesh) return
        const mats = Array.isArray(node.material) ? node.material : [node.material]
        mats.forEach(mat => {
          if (mat && mat.userData?.empireStudioDerived === true) mat.dispose()
        })
      })
    }
  }, [model, onReady, scene])

  // Imported CarConcept longitudinal axis is Z. Orient its nose towards the
  // default camera (+X,+Z) for front, perpendicular for side profile.
  const angle = view === 'front' ? .7 : view === 'side' ? -.85 : .1
  return <>
    <group position={[0, -.64, 0]} rotation={[0, angle, 0]}>
      <primitive object={model} scale={scale}
        position={[-center.x * scale, -floor * scale, -center.z * scale]} />
    </group>
    <OrbitControls makeDefault enableDamping={false}
      enablePan={false} enableZoom minDistance={5.4} maxDistance={12}
      minPolarAngle={.6} maxPolarAngle={1.75} target={[0, .18, 0]} />
  </>
}
