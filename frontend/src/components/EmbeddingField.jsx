import { useRef, useMemo, useState, useEffect } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import * as THREE from 'three'

/**
 * The signature visual for RepoScan: code chunks live as points scattered in
 * a 3D vector space. Nearby points are semantically similar — exactly what
 * cosine similarity search retrieves at query time. Idle, the field drifts
 * like a slowly turning galaxy of a codebase. When a query fires (see
 * `pulse` prop incrementing), one node lights up as the "question" and a
 * handful of its neighbors flare in sequence, echoing the real retrieval step.
 */

const NODE_COUNT = 260
const CLUSTER_COUNT = 6

function seedRandom(seed) {
  let s = seed
  return () => {
    s = (s * 9301 + 49297) % 233280
    return s / 233280
  }
}

function useFieldGeometry() {
  return useMemo(() => {
    const rand = seedRandom(42)
    const clusters = Array.from({ length: CLUSTER_COUNT }, () => {
      const theta = rand() * Math.PI * 2
      const phi = Math.acos(2 * rand() - 1)
      const r = 3.4 + rand() * 1.4
      return new THREE.Vector3(
        r * Math.sin(phi) * Math.cos(theta),
        r * Math.sin(phi) * Math.sin(theta) * 0.7,
        r * Math.cos(phi)
      )
    })

    const positions = new Float32Array(NODE_COUNT * 3)
    const basePositions = []
    const clusterOf = []
    for (let i = 0; i < NODE_COUNT; i++) {
      const c = clusters[i % CLUSTER_COUNT]
      const spread = 1.15
      const p = new THREE.Vector3(
        c.x + (rand() - 0.5) * spread * 2,
        c.y + (rand() - 0.5) * spread * 2,
        c.z + (rand() - 0.5) * spread * 2
      )
      positions[i * 3] = p.x
      positions[i * 3 + 1] = p.y
      positions[i * 3 + 2] = p.z
      basePositions.push(p)
      clusterOf.push(i % CLUSTER_COUNT)
    }

    // Precompute a handful of nearest-neighbor edges per node for the ambient mesh.
    const edges = []
    for (let i = 0; i < NODE_COUNT; i += 1) {
      if (i % 3 !== 0) continue
      let best = -1
      let bestDist = Infinity
      for (let j = 0; j < NODE_COUNT; j++) {
        if (i === j || clusterOf[i] !== clusterOf[j]) continue
        const d = basePositions[i].distanceToSquared(basePositions[j])
        if (d < bestDist) {
          bestDist = d
          best = j
        }
      }
      if (best >= 0) edges.push([i, best])
    }

    return { positions, basePositions, clusterOf, edges }
  }, [])
}

function Field({ pulse }) {
  const { positions, basePositions, clusterOf, edges } = useFieldGeometry()
  const pointsRef = useRef()
  const groupRef = useRef()
  const colorAttrRef = useRef()
  const activeRef = useRef({ nodes: [], t: 999 })

  const baseColors = useMemo(() => {
    const arr = new Float32Array(NODE_COUNT * 3)
    const palette = [
      [0.486, 0.435, 1.0], // vector
      [1.0, 0.72, 0.42], // amber
      [0.29, 0.87, 0.5], // green
      [0.6, 0.55, 1.0],
      [0.76, 0.73, 1.0],
      [0.5, 0.66, 1.0],
    ]
    for (let i = 0; i < NODE_COUNT; i++) {
      const [r, g, b] = palette[clusterOf[i] % palette.length]
      arr[i * 3] = r
      arr[i * 3 + 1] = g
      arr[i * 3 + 2] = b
    }
    return arr
  }, [clusterOf])

  // Fire a "query" pulse: pick a node + a few same-cluster neighbors, flare them
  // brighter for ~2s — a stand-in for "these are the chunks that just got retrieved".
  useEffect(() => {
    if (pulse === 0) return
    const origin = Math.floor(Math.random() * NODE_COUNT)
    const cluster = clusterOf[origin]
    const neighbors = []
    for (let i = 0; i < NODE_COUNT && neighbors.length < 6; i++) {
      if (clusterOf[i] === cluster) neighbors.push(i)
    }
    activeRef.current = { nodes: neighbors, t: 0 }
  }, [pulse, clusterOf])

  useFrame((state, delta) => {
    if (groupRef.current) {
      groupRef.current.rotation.y += delta * 0.045
      groupRef.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.08) * 0.08
    }
    const colorAttr = colorAttrRef.current
    if (colorAttr) {
      const active = activeRef.current
      active.t += delta
      const arr = colorAttr.array
      const inWindow = active.t < 2.4
      for (let i = 0; i < NODE_COUNT; i++) {
        const isActive = inWindow && active.nodes.includes(i)
        const flare = isActive ? Math.max(0, Math.sin(active.t * 3.2)) * 0.85 : 0
        arr[i * 3] = Math.min(1, baseColors[i * 3] + flare)
        arr[i * 3 + 1] = Math.min(1, baseColors[i * 3 + 1] + flare)
        arr[i * 3 + 2] = Math.min(1, baseColors[i * 3 + 2] + flare)
      }
      colorAttr.needsUpdate = true
    }
  })

  const lineSegments = useMemo(() => {
    const arr = new Float32Array(edges.length * 6)
    edges.forEach(([a, b], idx) => {
      arr[idx * 6] = basePositions[a].x
      arr[idx * 6 + 1] = basePositions[a].y
      arr[idx * 6 + 2] = basePositions[a].z
      arr[idx * 6 + 3] = basePositions[b].x
      arr[idx * 6 + 4] = basePositions[b].y
      arr[idx * 6 + 5] = basePositions[b].z
    })
    return arr
  }, [edges, basePositions])

  return (
    <group ref={groupRef}>
      <lineSegments>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[lineSegments, 3]} />
        </bufferGeometry>
        <lineBasicMaterial color="#7c6fff" transparent opacity={0.12} />
      </lineSegments>
      <points ref={pointsRef}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[positions, 3]} />
          <bufferAttribute ref={colorAttrRef} attach="attributes-color" args={[baseColors.slice(), 3]} />
        </bufferGeometry>
        <pointsMaterial
          size={0.14}
          vertexColors
          transparent
          opacity={0.9}
          sizeAttenuation
          depthWrite={false}
        />
      </points>
    </group>
  )
}

export default function EmbeddingField({ pulse = 0, className = '' }) {
  const [ready, setReady] = useState(false)
  useEffect(() => setReady(true), [])
  if (!ready) return <div className={className} aria-hidden="true" />

  return (
    <div className={className} aria-hidden="true">
      <Canvas
        camera={{ position: [0, 0, 8.5], fov: 45 }}
        dpr={[1, 1.75]}
        gl={{ antialias: true, alpha: true }}
      >
        <Field pulse={pulse} />
      </Canvas>
    </div>
  )
}
