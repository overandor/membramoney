"""
MEMBRA Operator Voice Interface
TTS via macOS `say`. STT via speech_recognition (microphone optional).
"""
import subprocess
import threading
import time
import os

try:
    import speech_recognition as sr
    _HAS_SR = True
except Exception:
    sr = None  # type: ignore
    _HAS_SR = False

class VoiceInterface:
    def __init__(self, on_speech_callback=None):
        self.on_speech = on_speech_callback
        self.listening = False
        self._thread = None
        self._mic_available = False
        self.recognizer = None
        self.microphone = None
        if _HAS_SR:
            try:
                self.recognizer = sr.Recognizer()
                self.microphone = sr.Microphone()
                self._mic_available = True
            except Exception as e:
                print(f"[Voice] Microphone unavailable: {e}")
        # macOS voices: "Samantha", "Alex", "Daniel", "Karen", "Fred"
        self.voice = os.environ.get("MEMBRA_TTS_VOICE", "Samantha")
        self.speech_rate = int(os.environ.get("MEMBRA_TTS_RATE", "180"))

    def speak(self, text: str, block=True) -> None:
        """TTS using macOS `say` command."""
        clean = text.replace('"', '\\"')
        cmd = ["say", "-v", self.voice, "-r", str(self.speech_rate), clean]
        if block:
            subprocess.run(cmd, check=False)
        else:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def listen_once(self, timeout=5, phrase_time_limit=10) -> str | None:
        """Single STT capture."""
        if not self._mic_available:
            return None
        try:
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
            text = self.recognizer.recognize_google(audio)
            return text
        except sr.WaitTimeoutError:
            return None
        except sr.UnknownValueError:
            return None
        except sr.RequestError as e:
            print(f"[STT] API error: {e}")
            return None

    def start_background_listener(self):
        """Continuous background STT."""
        if not self._mic_available:
            print("[Voice] Microphone not available; install pyaudio or sox for STT.")
            return
        self.listening = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def stop_background_listener(self):
        self.listening = False
        if self._thread:
            self._thread.join(timeout=1)

    def _listen_loop(self):
        while self.listening:
            result = self.listen_once(timeout=3, phrase_time_limit=5)
            if result and self.on_speech:
                self.on_speech(result)
            time.sleep(0.2)
