#!/usr/bin/env python3
"""
OLLAMA VISION - COMPLETE AI SYSTEM
Webcam + Voice + Ollama AI - All in One
Real-time conversation with visual and audio
"""

import asyncio
import cv2
import numpy as np
import threading
import time
import logging
import subprocess
import os
import sys
import json
import speech_recognition as sr
import pyttsx3
import requests
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, List, Dict
import platform

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - OLLAMA-VISION - %(message)s',
    handlers=[
        logging.FileHandler('ollama_vision.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class ConversationState:
    """Current conversation state"""
    is_listening: bool = False
    is_speaking: bool = False
    last_user_message: str = ""
    last_ai_response: str = ""
    conversation_history: List[Dict] = None
    webcam_active: bool = False
    ai_thinking: bool = False
    
    def __post_init__(self):
        if self.conversation_history is None:
            self.conversation_history = []

class WebcamManager:
    """Manages webcam capture and display"""
    
    def __init__(self):
        self.cap = None
        self.is_running = False
        self.frame = None
        self.lock = threading.Lock()
        
    def start_webcam(self) -> bool:
        """Start webcam capture"""
        try:
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                logger.error("❌ Cannot open webcam")
                return False
            
            # Set resolution
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            
            self.is_running = True
            
            # Start capture thread
            capture_thread = threading.Thread(target=self._capture_loop)
            capture_thread.daemon = True
            capture_thread.start()
            
            logger.info("📹 Webcam started")
            return True
            
        except Exception as e:
            logger.error(f"❌ Webcam error: {e}")
            return False
    
    def _capture_loop(self):
        """Continuous webcam capture"""
        while self.is_running:
            ret, frame = self.cap.read()
            if ret:
                with self.lock:
                    self.frame = frame
            time.sleep(0.03)  # ~30 FPS
    
    def get_frame(self) -> Optional[np.ndarray]:
        """Get current frame"""
        with self.lock:
            return self.frame.copy() if self.frame is not None else None
    
    def stop_webcam(self):
        """Stop webcam"""
        self.is_running = False
        if self.cap:
            self.cap.release()
        logger.info("📹 Webcam stopped")

class VoiceManager:
    """Manages voice input (speech-to-text) and output (text-to-speech)"""
    
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.tts_engine = None
        self.is_speaking = False
        self.setup_tts()
        
        # Calibrate for ambient noise
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
        
        logger.info("🎤 Voice manager initialized")
    
    def setup_tts(self):
        """Setup text-to-speech engine"""
        try:
            self.tts_engine = pyttsx3.init()
            
            # Configure voice
            voices = self.tts_engine.getProperty('voices')
            
            # Try to find a good voice
            preferred_voices = ['Samantha', 'Alex', 'Victoria', 'Karen']
            for voice in voices:
                if any(pref in voice.name for pref in preferred_voices):
                    self.tts_engine.setProperty('voice', voice.id)
                    break
            
            # Set properties
            self.tts_engine.setProperty('rate', 180)  # Speaking rate
            self.tts_engine.setProperty('volume', 0.9)  # Volume
            
            logger.info(f"🔊 TTS initialized with voice")
            
        except Exception as e:
            logger.error(f"❌ TTS setup error: {e}")
            self.tts_engine = None
    
    def listen(self, timeout: int = 5) -> Optional[str]:
        """Listen for user speech and convert to text"""
        try:
            logger.info("👂 Listening...")
            
            with self.microphone as source:
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=10)
            
            logger.info("🧠 Processing speech...")
            
            # Use Google's speech recognition
            text = self.recognizer.recognize_google(audio)
            
            logger.info(f"🗣️  You said: {text}")
            return text
            
        except sr.WaitTimeoutError:
            logger.info("⏱️  Listening timeout")
            return None
        except sr.UnknownValueError:
            logger.info("❓ Could not understand audio")
            return None
        except sr.RequestError as e:
            logger.error(f"❌ Speech recognition error: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Listen error: {e}")
            return None
    
    def speak(self, text: str) -> bool:
        """Convert text to speech"""
        if not self.tts_engine:
            logger.error("❌ TTS engine not available")
            return False
        
        try:
            logger.info(f"🔊 Speaking: {text[:50]}...")
            
            self.is_speaking = True
            
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()
            
            self.is_speaking = False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Speak error: {e}")
            self.is_speaking = False
            return False

class OllamaAI:
    """Ollama AI integration"""
    
    def __init__(self):
        self.base_url = "http://localhost:11434"
        self.model = "llama3.2:3b"  # Medium-sized model for good responses
        self.is_available = False
        
        logger.info("🤖 Ollama AI initialized")
    
    async def check_ollama(self) -> bool:
        """Check if Ollama is running"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            self.is_available = response.status_code == 200
            return self.is_available
        except:
            self.is_available = False
            return False
    
    async def install_ollama(self) -> bool:
        """Install Ollama if not present"""
        if platform.system() == "Darwin":  # macOS
            try:
                logger.info("📦 Installing Ollama...")
                result = subprocess.run(
                    "curl -fsSL https://ollama.com/install.sh | sh",
                    shell=True, capture_output=True, text=True
                )
                
                if result.returncode == 0:
                    # Start Ollama
                    subprocess.Popen(["ollama", "serve"], 
                                   stdout=subprocess.DEVNULL, 
                                   stderr=subprocess.DEVNULL)
                    
                    # Wait for startup
                    for i in range(30):
                        if await self.check_ollama():
                            logger.info("✅ Ollama installed and running")
                            return True
                        time.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ Ollama installation failed: {e}")
        
        return False
    
    async def install_model(self) -> bool:
        """Install AI model"""
        try:
            logger.info(f"📥 Installing {self.model}...")
            
            process = subprocess.Popen(
                ["ollama", "pull", self.model],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Monitor progress
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    logger.info(f"📥 {output.strip()}")
            
            if process.returncode == 0:
                logger.info(f"✅ {self.model} installed")
                return True
            else:
                logger.error(f"❌ Failed to install {self.model}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Model installation error: {e}")
            return False
    
    async def generate_response(self, prompt: str, context: str = "") -> str:
        """Generate AI response"""
        if not self.is_available:
            return "Ollama AI is not available. Please check the connection."
        
        try:
            # Prepare system prompt for personality
            system_prompt = """You are Ollama Vision, a helpful AI assistant with a webcam and voice. 
You can see the user through the webcam and speak to them. Be friendly, concise, and engaging. 
Respond as if you're having a natural conversation. Keep responses brief but informative."""
            
            full_prompt = f"{system_prompt}\n\nContext: {context}\n\nUser: {prompt}\n\nAssistant:"
            
            payload = {
                "model": self.model,
                "prompt": full_prompt,
                "stream": False,
                "max_tokens": 300
            }
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                ai_response = result.get('response', '').strip()
                
                # Clean up response
                ai_response = ai_response.replace("Assistant:", "").strip()
                
                return ai_response
            else:
                return f"Error: {response.status_code}"
                
        except Exception as e:
            logger.error(f"❌ AI generation error: {e}")
            return f"Sorry, I encountered an error: {e}"

class DisplayManager:
    """Manages on-screen display with AI responses"""
    
    def __init__(self):
        self.window_name = "Ollama Vision - AI Conversation"
        self.webcam_manager = None
        self.conversation_state = None
        
    def setup_display(self, webcam_manager: WebcamManager, state: ConversationState):
        """Setup display"""
        self.webcam_manager = webcam_manager
        self.conversation_state = state
        
        # Create window
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.window_name, 1000, 700)
        
        logger.info("🖥️ Display setup complete")
    
    def create_frame(self) -> np.ndarray:
        """Create display frame with webcam and text"""
        # Create base frame
        frame = np.zeros((700, 1000, 3), dtype=np.uint8)
        frame[:] = (30, 30, 30)  # Dark gray background
        
        # Get webcam frame
        webcam_frame = self.webcam_manager.get_frame()
        
        if webcam_frame is not None:
            # Resize webcam frame
            webcam_height = 400
            webcam_width = int(webcam_frame.shape[1] * (webcam_height / webcam_frame.shape[0]))
            webcam_frame = cv2.resize(webcam_frame, (webcam_width, webcam_height))
            
            # Place webcam in top-left
            x_offset = 20
            y_offset = 20
            
            # Ensure it fits
            if webcam_frame.shape[1] > 600:
                webcam_frame = cv2.resize(webcam_frame, (600, 400))
            
            frame[y_offset:y_offset+webcam_frame.shape[0], 
                  x_offset:x_offset+webcam_frame.shape[1]] = webcam_frame
            
            # Draw border around webcam
            cv2.rectangle(frame, (x_offset-2, y_offset-2), 
                         (x_offset+webcam_frame.shape[1]+2, y_offset+webcam_frame.shape[0]+2), 
                         (0, 255, 0), 2)
        
        # Add status indicators
        status_x = 650
        status_y = 30
        
        # Webcam status
        webcam_status = "🟢 ON" if self.conversation_state.webcam_active else "🔴 OFF"
        cv2.putText(frame, f"Webcam: {webcam_status}", (status_x, status_y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        # Listening status
        status_y += 35
        listen_status = "🟢 LISTENING" if self.conversation_state.is_listening else "⚪ IDLE"
        cv2.putText(frame, f"Listening: {listen_status}", (status_x, status_y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        
        # Speaking status
        status_y += 35
        speak_status = "🟢 SPEAKING" if self.conversation_state.is_speaking else "⚪ IDLE"
        cv2.putText(frame, f"Speaking: {speak_status}", (status_x, status_y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2)
        
        # AI thinking status
        status_y += 35
        thinking_status = "🟡 THINKING" if self.conversation_state.ai_thinking else "⚪ IDLE"
        cv2.putText(frame, f"AI: {thinking_status}", (status_x, status_y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 165, 0), 2)
        
        # Add conversation area
        conv_y = 450
        
        # User message
        cv2.putText(frame, "YOU:", (20, conv_y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 100, 255), 2)
        
        # Wrap user text
        user_text = self.conversation_state.last_user_message
        if len(user_text) > 70:
            user_text = user_text[:67] + "..."
        cv2.putText(frame, user_text, (20, conv_y + 25), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 255), 1)
        
        # AI response
        conv_y += 70
        cv2.putText(frame, "OLLAMA:", (20, conv_y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 255, 100), 2)
        
        # Wrap AI text (multiple lines if needed)
        ai_text = self.conversation_state.last_ai_response
        max_chars = 80
        words = ai_text.split()
        lines = []
        current_line = ""
        
        for word in words:
            if len(current_line) + len(word) + 1 <= max_chars:
                current_line += word + " "
            else:
                lines.append(current_line.strip())
                current_line = word + " "
        
        if current_line:
            lines.append(current_line.strip())
        
        # Display up to 5 lines
        for i, line in enumerate(lines[:5]):
            cv2.putText(frame, line, (20, conv_y + 25 + i * 20), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 255, 200), 1)
        
        # Add instructions at bottom
        instructions = "Press 'Q' to quit | 'L' to listen | 'R' to reset"
        cv2.putText(frame, instructions, (20, 680), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)
        
        return frame
    
    def show(self):
        """Show display"""
        frame = self.create_frame()
        cv2.imshow(self.window_name, frame)
    
    def close(self):
        """Close display"""
        cv2.destroyAllWindows()

class OllamaVisionSystem:
    """Complete Ollama Vision System"""
    
    def __init__(self):
        self.webcam = WebcamManager()
        self.voice = VoiceManager()
        self.ai = OllamaAI()
        self.display = DisplayManager()
        self.state = ConversationState()
        
        self.is_running = False
        
        logger.info("🚀 OLLAMA VISION SYSTEM INITIALIZED")
    
    async def setup(self) -> bool:
        """Setup all components"""
        print("\n" + "=" * 80)
        print("🚀 OLLAMA VISION - SETUP")
        print("=" * 80)
        
        # Start webcam
        print("\n📹 Starting webcam...")
        if not self.webcam.start_webcam():
            print("❌ Failed to start webcam")
            return False
        self.state.webcam_active = True
        print("✅ Webcam started")
        
        # Check Ollama
        print("\n🤖 Checking Ollama AI...")
        if not await self.ai.check_ollama():
            print("⚠️  Ollama not running, attempting installation...")
            if await self.ai.install_ollama():
                if await self.ai.install_model():
                    print("✅ Ollama AI ready")
                else:
                    print("❌ Failed to install AI model")
                    return False
            else:
                print("❌ Failed to install Ollama")
                return False
        else:
            # Check if model is installed
            response = requests.get(f"{self.ai.base_url}/api/tags")
            if response.status_code == 200:
                models = [m['name'] for m in response.json().get('models', [])]
                if self.ai.model not in models:
                    print(f"📥 Installing {self.ai.model}...")
                    await self.ai.install_model()
        
        # Setup display
        print("\n🖥️ Setting up display...")
        self.display.setup_display(self.webcam, self.state)
        print("✅ Display ready")
        
        print("\n" + "=" * 80)
        print("✅ SETUP COMPLETE - Starting conversation loop")
        print("=" * 80 + "\n")
        
        return True
    
    async def conversation_loop(self):
        """Main conversation loop"""
        self.is_running = True
        
        # Initial greeting
        greeting = "Hello! I'm Ollama Vision. I can see you through the webcam and we can have a voice conversation. How can I help you today?"
        self.state.last_ai_response = greeting
        self.voice.speak(greeting)
        
        last_listen_time = time.time()
        listen_interval = 5  # Check for speech every 5 seconds
        
        while self.is_running:
            try:
                # Update display
                self.display.show()
                
                # Check for key presses
                key = cv2.waitKey(1) & 0xFF
                
                if key == ord('q'):
                    break
                elif key == ord('l'):
                    # Manual listen trigger
                    await self.listen_and_respond()
                elif key == ord('r'):
                    # Reset conversation
                    self.state.conversation_history = []
                    self.state.last_user_message = ""
                    self.state.last_ai_response = "Conversation reset."
                    self.voice.speak("Conversation reset.")
                
                # Auto-listen periodically
                current_time = time.time()
                if current_time - last_listen_time >= listen_interval:
                    if not self.state.is_speaking and not self.voice.is_speaking:
                        user_text = self.voice.listen(timeout=2)
                        if user_text:
                            await self.process_conversation(user_text)
                    last_listen_time = current_time
                
                # Small delay to prevent high CPU usage
                await asyncio.sleep(0.01)
                
            except Exception as e:
                logger.error(f"❌ Conversation loop error: {e}")
                await asyncio.sleep(1)
    
    async def listen_and_respond(self):
        """Listen for user and respond"""
        self.state.is_listening = True
        self.display.show()  # Update display
        
        user_text = self.voice.listen(timeout=5)
        
        self.state.is_listening = False
        
        if user_text:
            await self.process_conversation(user_text)
    
    async def process_conversation(self, user_text: str):
        """Process conversation turn"""
        # Update state
        self.state.last_user_message = user_text
        
        # Add to history
        self.state.conversation_history.append({
            "role": "user",
            "content": user_text,
            "timestamp": datetime.now().isoformat()
        })
        
        # Show thinking state
        self.state.ai_thinking = True
        self.display.show()
        
        # Get context from history (last 3 exchanges)
        context = ""
        for msg in self.state.conversation_history[-6:]:
            context += f"{msg['role']}: {msg['content']}\n"
        
        # Generate AI response
        ai_response = await self.ai.generate_response(user_text, context)
        
        self.state.ai_thinking = False
        self.state.last_ai_response = ai_response
        
        # Add to history
        self.state.conversation_history.append({
            "role": "assistant",
            "content": ai_response,
            "timestamp": datetime.now().isoformat()
        })
        
        # Speak response
        self.state.is_speaking = True
        self.voice.speak(ai_response)
        self.state.is_speaking = False
        
        logger.info(f"💬 Conversation: {user_text} -> {ai_response[:50]}...")
    
    async def shutdown(self):
        """Shutdown all components"""
        print("\n🛑 Shutting down Ollama Vision...")
        
        self.is_running = False
        
        # Stop webcam
        self.webcam.stop_webcam()
        
        # Close display
        self.display.close()
        
        # Save conversation history
        if self.state.conversation_history:
            with open('conversation_history.json', 'w') as f:
                json.dump(self.state.conversation_history, f, indent=2)
            print("💾 Conversation saved to conversation_history.json")
        
        print("✅ Shutdown complete")
    
    async def run(self):
        """Run complete system"""
        try:
            if await self.setup():
                await self.conversation_loop()
            else:
                print("❌ Setup failed - cannot run")
        except KeyboardInterrupt:
            print("\n🛑 Interrupted by user")
        finally:
            await self.shutdown()

def create_repository():
    """Create repository structure"""
    repo_name = "OllamaVision-Complete-AI-System"
    
    # Create directory
    if not os.path.exists(repo_name):
        os.makedirs(repo_name)
    
    # Copy this file to repository
    import shutil
    current_file = os.path.abspath(__file__)
    shutil.copy(current_file, os.path.join(repo_name, "ollama_vision.py"))
    
    # Create README
    readme_content = """# 🎯 OLLAMA VISION - Complete AI System

**Webcam + Voice + Ollama AI - All in One File**

A complete conversational AI system with visual and voice interaction using local Ollama AI.

## ✨ Features

- 📹 **Webcam Integration** - AI can see you in real-time
- 🎤 **Voice Input** - Speak naturally to the AI (Speech-to-Text)
- 🔊 **Voice Output** - AI speaks responses aloud (Text-to-Speech)
- 🧠 **Local AI** - Uses Ollama for private, local AI processing
- 🖥️ **Visual Interface** - Real-time display with status indicators
- 💬 **Conversation History** - Maintains context across the conversation
- ⚡ **Real-time Processing** - Instant responses and interactions

## 🚀 Installation

### Prerequisites

**macOS:**
```bash
# Install Python dependencies
pip3 install opencv-python pyttsx3 SpeechRecognition pyobjc requests numpy

# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh
```

**Linux:**
```bash
# Install system dependencies
sudo apt-get install python3-opencv python3-pyaudio portaudio19-dev

# Install Python dependencies
pip3 install opencv-python pyttsx3 SpeechRecognition requests numpy

# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh
```

**Windows:**
```bash
# Install Python dependencies
pip install opencv-python pyttsx3 SpeechRecognition requests numpy

# Install Ollama from: https://ollama.com/download/windows
```

### Setup

1. **Clone or download this repository**
2. **Install dependencies** (see above for your OS)
3. **Run the system:**

```bash
python3 ollama_vision.py
```

## 🎮 Usage

### Controls:

- **'Q'** - Quit the application
- **'L'** - Manually trigger listening
- **'R'** - Reset conversation history

### How it works:

1. **Webcam** turns on automatically
2. **AI** introduces itself via voice
3. **Speak naturally** - the AI listens automatically every 5 seconds
4. **Visual feedback** - see the AI thinking, speaking, and listening
5. **Conversation history** is maintained for context

## 🎯 System Architecture

```
┌─────────────────────────────────────────┐
│         OLLAMA VISION SYSTEM            │
├─────────────────────────────────────────┤
│  📹 Webcam Manager                       │
│     └─> Captures real-time video         │
├─────────────────────────────────────────┤
│  🎤 Voice Manager                        │
│     ├─> Speech-to-Text (Listening)      │
│     └─> Text-to-Speech (Speaking)      │
├─────────────────────────────────────────┤
│  🤖 Ollama AI                            │
│     └─> Local AI processing              │
├─────────────────────────────────────────┤
│  🖥️ Display Manager                     │
│     └─> Real-time visual interface       │
└─────────────────────────────────────────┘
```

## 🛠️ Technical Details

- **Webcam**: OpenCV for video capture
- **Voice Input**: SpeechRecognition with Google API
- **Voice Output**: pyttsx3 text-to-speech engine
- **AI Engine**: Ollama with llama3.2:3b model
- **Display**: OpenCV for real-time visualization
- **Platform**: Cross-platform (macOS, Linux, Windows)

## ⚙️ Configuration

Edit the code to customize:

```python
# AI Model
self.model = "llama3.2:3b"  # Change to your preferred model

# Voice settings
self.tts_engine.setProperty('rate', 180)  # Speaking speed
self.tts_engine.setProperty('volume', 0.9)  # Volume level

# Listening intervals
listen_interval = 5  # Seconds between automatic listening
```

## 🔒 Privacy & Security

- **Local AI**: All AI processing happens locally with Ollama
- **No cloud dependencies**: Speech recognition uses Google's API
- **Private conversations**: Conversation history stored locally only
- **Webcam data**: Real-time only, no storage

## 🐛 Troubleshooting

### Webcam not working:
```bash
# Check webcam permissions
# macOS: System Preferences > Security & Privacy > Camera
# Linux: Check video device with `ls /dev/video*`
```

### Microphone not working:
```bash
# Check microphone permissions
# macOS: System Preferences > Security & Privacy > Microphone
# Linux: Check audio with `arecord -l`
```

### Ollama not responding:
```bash
# Start Ollama manually
ollama serve

# Check if model is installed
ollama list

# Pull model if needed
ollama pull llama3.2:3b
```

## 📄 License

MIT License - Open source and free to use

## 🤝 Contributing

Contributions welcome! This is a community project for AI experimentation.

## 🙏 Acknowledgments

- Ollama team for local AI capabilities
- OpenCV for computer vision
- SpeechRecognition library for voice input
- pyttsx3 for voice output

---

**🚀 Ready to have a conversation with AI that can see and hear you?**
```

Run the system now!
python3 ollama_vision.py
```
"""
    
    with open(os.path.join(repo_name, "README.md"), "w") as f:
        f.write(readme_content)
    
    # Create requirements.txt
    requirements = """opencv-python>=4.8.0
pyttsx3>=2.90
SpeechRecognition>=3.10.0
requests>=2.31.0
numpy>=1.24.0
pyobjc>=9.0; sys_platform == 'darwin'
PyAudio>=0.2.11; sys_platform == 'linux'
"""
    
    with open(os.path.join(repo_name, "requirements.txt"), "w") as f:
        f.write(requirements)
    
    print(f"\n📁 Repository created: ./{repo_name}/")
    print(f"📄 Files created:")
    print(f"   - {repo_name}/ollama_vision.py")
    print(f"   - {repo_name}/README.md")
    print(f"   - {repo_name}/requirements.txt")
    print(f"\n🚀 Ready to upload to GitHub!")

async def main():
    """Main entry point"""
    print("\n" + "=" * 80)
    print("🚀 OLLAMA VISION - COMPLETE AI SYSTEM")
    print("📹 Webcam + 🎤 Voice + 🤖 Ollama AI")
    print("=" * 80)
    
    print("\nWhat would you like to do?")
    print("1. 🚀 Start Ollama Vision conversation system")
    print("2. 📁 Create GitHub repository package")
    print("3. ❌ Exit")
    
    choice = input("\nEnter your choice (1/2/3): ").strip()
    
    if choice == "1":
        system = OllamaVisionSystem()
        await system.run()
    elif choice == "2":
        create_repository()
    else:
        print("Goodbye! 👋")

if __name__ == "__main__":
    # Create repository on first run if requested
    if len(sys.argv) > 1 and sys.argv[1] == "--create-repo":
        create_repository()
    else:
        asyncio.run(main())
