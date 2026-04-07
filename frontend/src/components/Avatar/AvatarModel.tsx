import { useGLTF } from '@react-three/drei'
import { useEffect, useRef } from 'react'
import * as THREE from 'three'

interface AvatarModelProps {
  url: string
  // We pass the registerBones function in from outside
  onBonesReady: (scene: THREE.Group) => void
}

export default function AvatarModel({ url, onBonesReady }: AvatarModelProps) {
  const { scene } = useGLTF(url)
  const avatarRef = useRef<THREE.Group>(null)

  useEffect(() => {
    if (!avatarRef.current) return

    // Run the bone audit (same as before)
    console.log('=== SIGNBRIDGE BONE AUDIT ===')
    scene.traverse((object) => {
      if (object instanceof THREE.Bone) {
        console.log('BONE:', object.name)
      }
    })
    console.log('=== END OF BONE AUDIT ===')

    // Tell the animation system about all the bones
    // This is the new line — hands the scene to our hook
    onBonesReady(avatarRef.current as unknown as THREE.Group)

  }, [scene, onBonesReady])

  return (
    <group ref={avatarRef}>
      <primitive
        object={scene}
        position={[0, -1, 0]}
        scale={1}
      />
    </group>
  )
}

useGLTF.preload('/avatar.glb')