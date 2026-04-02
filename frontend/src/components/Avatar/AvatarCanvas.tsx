import { Canvas } from '@react-three/fiber'
import { OrbitControls, Environment } from '@react-three/drei'
import { Suspense } from 'react'
import AvatarModel from './AvatarModel'

// Simple loading spinner shown while the GLB file downloads
function LoadingFallback() {
  return (
    <mesh>
      <sphereGeometry args={[0.2, 16, 16]} />
      <meshStandardMaterial color="#00C2A8" wireframe />
    </mesh>
  )
}

export default function AvatarCanvas() {
  return (
    <div className="w-full h-full">
      <Canvas
        camera={{ position: [0, 1.5, 3], fov: 50 }}
        shadows
      >
        <ambientLight intensity={0.5} />
        <directionalLight position={[2, 4, 2]} intensity={1} castShadow />
        <directionalLight position={[-2, 2, -2]} intensity={0.3} />
        <Environment preset="city" />
        <OrbitControls enablePan={false} minDistance={1.5} maxDistance={5} />

        <Suspense fallback={<LoadingFallback />}>
          <AvatarModel url="/avatar.glb" />
        </Suspense>
      </Canvas>
    </div>
  )
}