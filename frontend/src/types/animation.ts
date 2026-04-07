// This describes what one bone rotation looks like
export interface BoneRotation {
  x: number
  y: number
  z: number
  w: number
}

// This describes one moment in time during a sign
export interface Keyframe {
  time: number  // 0 to 1 — where we are in the sign
  bones: Record<string, BoneRotation>  // bone name → rotation
}

// This describes a complete sign
export interface SignPose {
  duration: number  // how long in milliseconds
  keyframes: Keyframe[]
}

// This describes the whole database
export type SignDatabase = Record<string, SignPose>

// This describes one item waiting in the queue
export interface QueuedSign {
  glossId: string
  timestamp: number
}