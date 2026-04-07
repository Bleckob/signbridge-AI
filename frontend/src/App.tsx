import { useState, useRef, useCallback } from 'react'
import AvatarCanvas from './components/Avatar/AvatarCanvas'
import ControlPanel from './components/UI/ControlPanel'

function App() {
  // Is the avatar fully loaded and ready?
  const [isReady, setIsReady] = useState(false)

  // What sign is currently being performed
  const [currentSign, setCurrentSign] = useState<string | null>(null)

  // Hold a reference to the playSentence function from the animation hook
  const playSentenceRef = useRef<((glossIds: string[]) => void) | null>(null)

  // Called when the avatar finishes loading and registers its bones
  const handleAvatarReady = useCallback((playSentence: (glossIds: string[]) => void) => {
    playSentenceRef.current = playSentence
    setIsReady(true)
    console.log('Avatar is ready to sign!')
  }, [])

  // Called when the user taps the button
  // For now this triggers a hardcoded test sentence
  // Later this will receive real gloss packets from the WebSocket
  function handleTriggerTest() {
    if (!playSentenceRef.current) return

    const testSentence = ['HELLO', 'MY', 'NAME']
    setCurrentSign('HELLO')

    // Play the sentence
    playSentenceRef.current(testSentence)

    // Update the caption as each sign plays
    // This is a simple simulation — in Week 3 this comes from the WebSocket
    const signs = ['HELLO', 'MY', 'NAME']
    signs.forEach((sign, index) => {
      setTimeout(() => {
        setCurrentSign(sign)
      }, index * 800)
    })

    // Clear caption when done
    setTimeout(() => {
      setCurrentSign(null)
    }, signs.length * 800 + 500)
  }

  return (
    // Full screen dark background — mobile first (375px min width)
    <div className="w-screen h-screen bg-[#0B1628] relative overflow-hidden"
         style={{ minWidth: '375px' }}>

      {/* The 3D avatar canvas fills the whole screen */}
      <AvatarCanvas onReady={handleAvatarReady} />

      {/* The UI floats on top of the canvas */}
      <ControlPanel
        currentSign={currentSign}
        onTriggerTest={handleTriggerTest}
        isReady={isReady}
      />

      {/* Top status bar */}
      <div className="absolute top-4 left-0 right-0 flex justify-center">
        <div className="bg-black bg-opacity-50 rounded-full px-4 py-1.5 flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${isReady ? 'bg-teal-400 animate-pulse' : 'bg-gray-500'}`} />
          <span className="text-white text-xs font-medium">
            {isReady ? 'SignBridge Live' : 'Loading...'}
          </span>
        </div>
      </div>
    </div>
  )
}

export default App