import { Canvas } from '@react-three/fiber'
import { OrbitControls, Environment } from '@react-three/drei'
import { Suspense } from 'react'
import type { Group } from 'three'
import AvatarModel from './AvatarModel'
import { useSignAnimation } from '../../hooks/useSignAnimation'

function LoadingFallback() {
  return (
    <mesh>
      <sphereGeometry args={[0.2, 16, 16]} />
      <meshStandardMaterial color="#00C2A8" wireframe />
    </mesh>
  )
}

// We accept playSentence as a prop so the UI can trigger signs
interface AvatarCanvasProps {
  onReady: (playSentence: (glossIds: string[]) => void) => void
}

export default function AvatarCanvas({ onReady }: AvatarCanvasProps) {
  const { registerBones, playSentence } = useSignAnimation()

  // When bones are registered, tell the parent the avatar is ready
  function handleBonesReady(scene: Group) {
    registerBones(scene)
    // Now hand the playSentence function up to App.tsx
    onReady(playSentence)
  }

  return (
    <div className="w-full h-full">
      <Canvas camera={{ position: [0, 1.5, 3], fov: 50 }} shadows>
        <ambientLight intensity={0.5} />
        <directionalLight position={[2, 4, 2]} intensity={1} castShadow />
        <directionalLight position={[-2, 2, -2]} intensity={0.3} />
        <Environment preset="city" />
        <OrbitControls enablePan={false} minDistance={1.5} maxDistance={5} />

        <Suspense fallback={<LoadingFallback />}>
          <AvatarModel
            url="/avatar.glb"
            onBonesReady={handleBonesReady}
          />
        </Suspense>
      </Canvas>
    </div>
  )
}