import { useGLTF } from '@react-three/drei'
import { useEffect, useRef } from 'react'
import * as THREE from 'three'

interface AvatarModelProps {
  url: string
}

export default function AvatarModel({ url }: AvatarModelProps) {
  // useGLTF loads the GLB file — like opening the package
  const { scene } = useGLTF(url)

  // useRef gives us a handle to the 3D object in the scene
  const avatarRef = useRef<THREE.Group>(null)

  useEffect(() => {
    if (!avatarRef.current) return

    // ─── BONE AUDIT STARTS HERE ───
    // This runs once when the avatar loads
    // It walks through every single object inside the GLB file
    // and prints the name of anything that is a bone (SkinnedMesh or Bone)

    console.log('=== SIGNBRIDGE BONE AUDIT ===')
    console.log('Copy everything below and send to Isaac (Track 6)')
    console.log('─────────────────────────────')

    const boneNames: string[] = []

    scene.traverse((object) => {
      // Every joint/bone in a GLB file is of type "Bone"
      if (object instanceof THREE.Bone) {
        boneNames.push(object.name)
        console.log('BONE:', object.name)
      }
    })

    console.log('─────────────────────────────')
    console.log(`Total bones found: ${boneNames.length}`)
    console.log('=== END OF BONE AUDIT ===')
    // ─── BONE AUDIT ENDS HERE ───

  }, [scene])

  return (
    <group ref={avatarRef}>
      {/* primitive renders the loaded 3D scene directly */}
      <primitive
        object={scene}
        position={[0, -1, 0]}   // move down so feet are at the bottom
        scale={1}
      />
    </group>
  )
}

// This pre-loads the GLB file before the component even renders
// — faster loading experience
useGLTF.preload('/avatar.glb')