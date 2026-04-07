import { useRef, useCallback, useEffect } from 'react'
import * as THREE from 'three'
import type { SignDatabase, QueuedSign } from '../types/animation'
import signsData from '../data/signs.json'

// Load our sign database
const signDB = signsData as SignDatabase

// How long the crossfade between two signs takes — 80 milliseconds
const CROSSFADE_DURATION = 0.08

export function useSignAnimation() {
  // This holds a reference to all the bones in the avatar
  // Think of it as our handle on the puppet's strings
  const bonesRef = useRef<Record<string, THREE.Bone>>({})

  // The queue of signs waiting to be performed
  const queueRef = useRef<QueuedSign[]>([])

  // Is the avatar currently signing something?
  const isPlayingRef = useRef(false)

  // Which sign is currently being performed
  const currentSignRef = useRef<string | null>(null)

  // Ref to hold playNextSign so it can reference itself without circular declaration issues
  const playNextSignRef = useRef<() => void>(() => {})

  // ─── STEP A: Register all bones when the avatar loads ───
  // This is called once from AvatarModel when the GLB finishes loading
  // It walks through the avatar and saves every bone by name
  const registerBones = useCallback((scene: THREE.Group) => {
    const bones: Record<string, THREE.Bone> = {}

    scene.traverse((object) => {
      if (object instanceof THREE.Bone) {
        bones[object.name] = object
      }
    })

    bonesRef.current = bones
    console.log(`Animation system ready — ${Object.keys(bones).length} bones registered`)
  }, [])

  // ─── STEP B: Play the next sign from the queue ───
  const playNextSign = useCallback(() => {
    // Nothing in the queue — stop
    if (queueRef.current.length === 0) {
      isPlayingRef.current = false
      currentSignRef.current = null
      return
    }

    // Take the next sign off the front of the queue
    const next = queueRef.current.shift()!
    const signData = signDB[next.glossId]

    isPlayingRef.current = true
    currentSignRef.current = next.glossId

    // How long this sign takes in seconds (convert from ms)
    const durationSeconds = signData.duration / 1000

    // Record when we started
    const startTime = performance.now()

    // ─── STEP C: The animation loop ───
    // This runs every frame (60 times per second)
    // Each frame it calculates where the bones should be
    // based on how much time has passed
    function animate() {
      const now = performance.now()
      const elapsed = (now - startTime) / 1000  // seconds elapsed
      const progress = Math.min(elapsed / durationSeconds, 1)  // 0 to 1

      // Find which two keyframes we are currently between
      const keyframes = signData.keyframes
      let fromFrame = keyframes[0]
      let toFrame = keyframes[keyframes.length - 1]

      for (let i = 0; i < keyframes.length - 1; i++) {
        if (progress >= keyframes[i].time && progress <= keyframes[i + 1].time) {
          fromFrame = keyframes[i]
          toFrame = keyframes[i + 1]
          break
        }
      }

      // How far between those two keyframes are we? (0 to 1)
      const frameRange = toFrame.time - fromFrame.time
      const frameProgress = frameRange === 0 ? 1 :
        (progress - fromFrame.time) / frameRange

      // ─── STEP D: Apply SLERP to each bone ───
      // For every bone that this sign controls,
      // smoothly interpolate between the two keyframe positions
      const bones = bonesRef.current

      Object.keys(toFrame.bones).forEach((boneName) => {
        const bone = bones[boneName]
        if (!bone) return  // skip if bone not found

        const fromRot = fromFrame.bones[boneName] || toFrame.bones[boneName]
        const toRot = toFrame.bones[boneName]

        // Create THREE.js quaternion objects from our data
        const qFrom = new THREE.Quaternion(fromRot.x, fromRot.y, fromRot.z, fromRot.w)
        const qTo = new THREE.Quaternion(toRot.x, toRot.y, toRot.z, toRot.w)

        // SLERP — this is the smooth blend!
        // frameProgress goes from 0 (start) to 1 (end)
        qFrom.slerp(qTo, frameProgress)

        // Apply the result to the actual bone
        bone.quaternion.copy(qFrom)
      })

      // If we haven't finished yet, keep animating next frame
      if (progress < 1) {
        requestAnimationFrame(animate)
      } else {
        // This sign is done — wait 80ms (crossfade time) then play the next one
        setTimeout(() => {
          playNextSignRef.current()
        }, CROSSFADE_DURATION * 1000)
      }
    }

    // Kick off the animation loop
    requestAnimationFrame(animate)
  }, [])

  // Keep the ref in sync so the recursive setTimeout always calls the latest version
  useEffect(() => {
    playNextSignRef.current = playNextSign
  }, [playNextSign])

  // ─── STEP E: Add a sign to the queue ───
  // This is what gets called when a gloss packet arrives
  const queueSign = useCallback((glossId: string) => {
    // Check if we actually have this sign in our database
    if (!signDB[glossId]) {
      console.warn(`Sign "${glossId}" not found in database — skipping`)
      return
    }

    queueRef.current.push({
      glossId,
      timestamp: Date.now()
    })

    // If nothing is playing right now, start immediately
    if (!isPlayingRef.current) {
      playNextSign()
    }
  }, [playNextSign])

  // ─── STEP F: Play a full sentence ───
  // This takes an array like ["HELLO", "MY", "NAME"]
  // and queues them all up
  const playSentence = useCallback((glossIds: string[]) => {
    glossIds.forEach(id => queueSign(id))
  }, [queueSign])

  // Return these functions so components can use them
  return {
    registerBones,
    queueSign,
    playSentence,
    currentSign: currentSignRef
  }
}