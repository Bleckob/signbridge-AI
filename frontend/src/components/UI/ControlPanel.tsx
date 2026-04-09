interface ControlPanelProps {
  currentSign: string | null
  onTriggerTest: () => void
  isReady: boolean
}

export default function ControlPanel({
  currentSign,
  onTriggerTest,
  isReady
}: ControlPanelProps) {
  return (
    <div className="absolute bottom-0 left-0 right-0 flex flex-col items-center pb-8 gap-4">

      {/* Caption strip — shows what's being signed */}
      <div className="bg-black bg-opacity-70 rounded-xl px-6 py-3 min-w-64 text-center">
        {currentSign ? (
          <p className="text-white text-sm font-medium tracking-wide">
            Signing: <span className="text-teal-400">{currentSign}</span>
          </p>
        ) : (
          <p className="text-gray-500 text-sm">
            Tap the button to sign a test sentence
          </p>
        )}
      </div>

      {/* Microphone / trigger button */}
      <button
        onClick={onTriggerTest}
        disabled={!isReady}
        className={`
          w-20 h-20 rounded-full
          flex items-center justify-center
          text-3xl
          transition-all duration-200
          ${isReady
            ? 'bg-teal-500 hover:bg-teal-400 active:scale-95 shadow-lg shadow-teal-500/30'
            : 'bg-gray-700 cursor-not-allowed'
          }
        `}
      >
        {isReady ? '🎙' : '⏳'}
      </button>

      <p className="text-gray-600 text-xs">
        {isReady ? 'Tap to test — signs: HELLO → MY → NAME' : 'Loading avatar...'}
      </p>
    </div>
  )
}