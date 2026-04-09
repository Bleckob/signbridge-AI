import os
import io
import speech_recognition as sr
from groq import Groq
from dotenv import load_dotenv

# --- Load environment variables from .env file ---
load_dotenv()

# --- Initialize the Groq client once, at module level ---
# This is efficient — we don't recreate the client on every function call.
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def transcribe_speech() -> str | None:
    """
    Listens to the microphone for a single utterance, sends the audio
    to Groq Whisper, and returns the transcribed text.

    Returns:
        str: The transcribed text if successful.
        None: If silence, an audio error, or an API error occurs.
    """
    recognizer = sr.Recognizer()

    with sr.Microphone() as source:
        print("\n[ASR] 🎙️  Adjusting for ambient noise... please wait.")

        # This samples the background for 1 second to set the noise floor.
        # Audio quieter than this threshold will be ignored — no wasted API calls.
        recognizer.adjust_for_ambient_noise(source, duration=1)

        print("[ASR] ✅ Ready. Speak now...")

        try:
            # listen() captures ONE utterance (speech followed by silence).
            # timeout=5      → gives up if no speech starts within 5 seconds.
            # phrase_time_limit=30 → stops recording after 30 seconds max.
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=30)
            print("[ASR] 🔄 Audio captured. Sending to Groq Whisper...")

        except sr.WaitTimeoutError:
            # No speech detected within the timeout window — this is normal.
            print("[ASR] ⏱️  No speech detected. Listening again...")
            return None

    # --- Convert audio to a format Groq's API accepts (WAV bytes) ---
    audio_bytes = io.BytesIO(audio.get_wav_data())
    audio_bytes.name = "audio.wav"  # Groq needs a filename to detect format

    try:
        transcription = client.audio.transcriptions.create(
            model="whisper-large-v3-turbo",
            file=audio_bytes,
            response_format="text"
        )
        return transcription

    except Exception as api_error:
        # Catches network timeouts, invalid API key, rate limits, etc.
        print(f"[ASR] ❌ Groq API error: {api_error}")
        return None


def run_asr_loop():
    """
    Runs the ASR engine in a continuous loop.
    This is the entry point when running the script directly.
    Teammates should import transcribe_speech() instead.
    """
    print("=" * 45)
    print("   SignBridge ASR Engine — Groq Whisper")
    print("   Press Ctrl+C to stop.")
    print("=" * 45)

    while True:
        try:
            result = transcribe_speech()

            if result:
                print(f"\n[TRANSCRIPT] 📝 {result}\n")

        except KeyboardInterrupt:
            # Clean exit when the user presses Ctrl+C
            print("\n\n[ASR] 🛑 Engine stopped by user. Goodbye!")
            break


# --- Only runs the loop if this file is executed directly ---
# If a teammate does `from asr_engine import transcribe_speech`, this block
# is SKIPPED — their code won't accidentally start a microphone loop.
if __name__ == "__main__":
    run_asr_loop()
