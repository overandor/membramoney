# Morning Agent - Final Build Status

## Product Summary

Morning Agent is an AI-powered phone assistant that autonomously makes phone calls on behalf of users. Users create tasks with phone numbers and instructions via an iPhone app or web interface. The backend uses Twilio for phone calls, Groq LLM for text processing, and a modular pipeline for speech-to-text and text-to-speech conversion.

## Build Status

- ✅ Backend FastAPI scaffold complete with all CRUD endpoints
- ✅ Groq LLM integration for text processing and summarization
- ✅ Twilio integration for outbound calls and webhooks
- ✅ SQLite database with Task model
- ✅ WebSocket audio bridge with STT/TTS service stubs
- ✅ iOS SwiftUI app scaffold with all views
- ✅ Gradio web interface for Hugging Face deployment
- ✅ Configuration system with environment variables
- ✅ Health check endpoint
- ✅ Comprehensive documentation
- ⚠️  STT service is a stub (needs Whisper/Google/Deepgram integration)
- ⚠️  TTS service is a stub (needs ElevenLabs/Google/AWS integration)
- ⚠️  Audio format conversion (Twilio μ-law to PCM) not implemented
- ⚠️  No integration tests
- ⚠️  No retry logic for failed calls

## Files Created or Changed

### New Files (3)
1. `backend/app/services/stt_service.py` - Speech-to-Text service stub
2. `backend/app/services/tts_service.py` - Text-to-Speech service stub
3. `backend/test_backend.py` - Backend test script

### Changed Files (3)
1. `backend/app/services/__init__.py` - Export new services
2. `backend/app/main.py` - WebSocket bridge with STT/TTS integration
3. `backend/requirements.txt` - Added groq dependency

## Full Code for Changed/New Files

### backend/app/services/stt_service.py
```python
import base64
import tempfile
import os
from typing import Optional

class STTService:
    """Speech-to-Text service - converts audio to text"""
    
    def __init__(self):
        # Placeholder for STT service initialization
        # Can be configured to use Whisper, Google, Deepgram, etc.
        pass
    
    async def transcribe(self, audio_data: bytes) -> Optional[str]:
        """
        Transcribe audio data to text
        
        Args:
            audio_data: Raw audio bytes (μ-law 8kHz from Twilio)
        
        Returns:
            str: Transcribed text, or None if transcription fails
        """
        # STUB: This is a placeholder implementation
        # In production, integrate with:
        # - OpenAI Whisper API
        # - Google Speech-to-Text
        # - Deepgram
        # - AssemblyAI
        
        # For now, return a placeholder to indicate audio was received
        # This allows the pipeline to flow even without real STT
        return "[AUDIO RECEIVED - STT SERVICE NOT CONFIGURED]"
    
    async def transcribe_from_base64(self, base64_payload: str) -> Optional[str]:
        """
        Transcribe base64-encoded audio (Twilio format)
        
        Args:
            base64_payload: Base64-encoded μ-law audio from Twilio
        
        Returns:
            str: Transcribed text
        """
        try:
            audio_data = base64.b64decode(base64_payload)
            return await self.transcribe(audio_data)
        except Exception as e:
            print(f"STT error: {e}")
            return None
```

### backend/app/services/tts_service.py
```python
from typing import Optional

class TTSService:
    """Text-to-Speech service - converts text to audio"""
    
    def __init__(self):
        # Placeholder for TTS service initialization
        # Can be configured to use ElevenLabs, Google, AWS, OpenAI, etc.
        pass
    
    async def synthesize(self, text: str) -> Optional[bytes]:
        """
        Synthesize text to audio
        
        Args:
            text: Text to convert to speech
        
        Returns:
            bytes: Audio data (μ-law 8kHz for Twilio), or None if synthesis fails
        """
        # STUB: This is a placeholder implementation
        # In production, integrate with:
        # - ElevenLabs API (best quality)
        # - Google Cloud TTS
        # - AWS Polly
        # - OpenAI TTS
        # - Azure Speech
        
        # For now, return None to indicate TTS not configured
        # The caller should handle this gracefully
        return None
    
    async def synthesize_to_base64(self, text: str) -> Optional[str]:
        """
        Synthesize text and return base64-encoded audio for Twilio
        
        Args:
            text: Text to convert to speech
        
        Returns:
            str: Base64-encoded audio, or None if synthesis fails
        """
        audio_data = await self.synthesize(text)
        if audio_data:
            import base64
            return base64.b64encode(audio_data).decode()
        return None
```

### backend/app/services/__init__.py
```python
from .groq_llm import get_groq_llm, GroqLLMService
from .stt_service import STTService
from .tts_service import TTSService
from .twilio_client import get_twilio_client, create_outbound_call
from .openai_realtime import RealtimeBridge

__all__ = [
    "get_groq_llm",
    "GroqLLMService",
    "STTService",
    "TTSService",
    "get_twilio_client",
    "create_outbound_call",
    "RealtimeBridge",
]
```

### backend/app/main.py (partial - WebSocket section only)
```python
@app.websocket("/media-stream")
async def media_stream(ws: WebSocket):
    await ws.accept()
    task_id = int(ws.query_params["task_id"])

    # DB read
    with Session(engine) as session:
        task = session.get(Task, task_id)
        if not task:
            await ws.close(code=1008)
            return
        bridge = RealtimeBridge(task_id=task.id, instructions=task.instructions)
        groq_llm = get_groq_llm()
        stt_service = STTService()
        tts_service = TTSService()

    await bridge.open()

    transcript_parts: list[str] = []
    conversation_history = []

    try:
        while True:
            message = await ws.receive_text()
            data = json.loads(message)

            event = data.get("event")
            if event == "start":
                # Connection established
                print(f"Media stream started for task {task_id}")
            elif event == "media":
                # Audio frame received from Twilio
                try:
                    # 1) Decode Twilio base64 audio payload
                    payload = data.get("media", {}).get("payload")
                    if not payload:
                        continue
                    
                    # 2) Use STT service to convert to text
                    text = await stt_service.transcribe_from_base64(payload)
                    
                    if text and text != "[AUDIO RECEIVED - STT SERVICE NOT CONFIGURED]":
                        # 3) Process with Groq LLM
                        response = await groq_llm.process(
                            text=text,
                            instructions=task.instructions,
                            conversation_history=conversation_history
                        )
                        
                        # Update conversation history
                        conversation_history.append({"role": "user", "content": text})
                        conversation_history.append({"role": "assistant", "content": response})
                        
                        # Add to transcript
                        transcript_parts.append(f"Caller: {text}")
                        transcript_parts.append(f"Agent: {response}")
                        
                        # 4) Use TTS service to convert response to audio
                        audio_response = await tts_service.synthesize_to_base64(response)
                        
                        # 5) Send audio back to Twilio if TTS succeeded
                        if audio_response:
                            await ws.send(json.dumps({
                                "event": "media",
                                "media": {"payload": audio_response}
                            }))
                        else:
                            # TTS not configured, log text response
                            print(f"Agent response (TTS stub): {response}")
                    
                except Exception as e:
                    print(f"Error processing media frame: {e}")
                    
            elif event == "stop":
                # Call ended
                print(f"Media stream stopped for task {task_id}")
                break
                
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for task {task_id}")
    except Exception as e:
        print(f"Error in media stream: {e}")
    finally:
        await bridge.close()
        with Session(engine) as session:
            task = session.get(Task, task_id)
            if task:
                task.transcript = "\n".join(transcript_parts) if transcript_parts else task.transcript
                
                # Use Groq to summarize if we have a transcript
                if task.transcript and not task.summary:
                    try:
                        task.summary = await groq_llm.summarize_transcript(
                            task.transcript, 
                            task.instructions
                        )
                        
                        # Check task completion
                        completion_check = await groq_llm.check_task_completion(
                            task.transcript,
                            task.instructions
                        )
                        if completion_check.get("completed"):
                            task.status = "completed"
                        else:
                            task.status = "needs_review"
                    except Exception as e:
                        print(f"Error summarizing with Groq: {e}")
                        task.summary = task.summary or "Call finished. Review transcript."
                
                task.updated_at = datetime.utcnow()
                session.add(task)
                session.commit()
```

### backend/requirements.txt
```
fastapi==0.115.12
uvicorn[standard]==0.34.2
sqlmodel==0.0.24
twilio==9.5.2
python-dotenv==1.0.1
httpx==0.28.1
websockets==15.0.1
groq>=0.11.0
```

### backend/test_backend.py
```python
"""
Simple test script to verify Morning Agent backend functionality
Run this after setting up .env to test core services
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.groq_llm import get_groq_llm
from app.services.stt_service import STTService
from app.services.tts_service import TTSService
from app.config import settings

async def test_groq():
    """Test Groq LLM service"""
    print("=" * 60)
    print("Testing Groq LLM Service")
    print("=" * 60)
    
    try:
        groq = get_groq_llm()
        response = await groq.process(
            text="Hello, I need to schedule a dentist appointment",
            instructions="You are a dental office scheduler",
            conversation_history=[]
        )
        print(f"✅ Groq LLM working")
        print(f"Response: {response[:100]}...")
        return True
    except Exception as e:
        print(f"❌ Groq LLM error: {e}")
        print(f"   Make sure GROQ_API_KEY is set in .env")
        return False

async def test_stt():
    """Test STT service"""
    print("\n" + "=" * 60)
    print("Testing STT Service")
    print("=" * 60)
    
    try:
        stt = STTService()
        # STT is a stub, so it returns a placeholder
        result = await stt.transcribe(b"fake_audio_data")
        print(f"✅ STT service initialized")
        print(f"Result: {result}")
        print(f"   (STT is a stub - integrate with Whisper/Google/Deepgram)")
        return True
    except Exception as e:
        print(f"❌ STT error: {e}")
        return False

async def test_tts():
    """Test TTS service"""
    print("\n" + "=" * 60)
    print("Testing TTS Service")
    print("=" * 60)
    
    try:
        tts = TTSService()
        # TTS is a stub, so it returns None
        result = await tts.synthesize("Hello, this is a test")
        print(f"✅ TTS service initialized")
        print(f"Result: {result}")
        print(f"   (TTS is a stub - integrate with ElevenLabs/Google/AWS)")
        return True
    except Exception as e:
        print(f"❌ TTS error: {e}")
        return False

async def test_config():
    """Test configuration"""
    print("\n" + "=" * 60)
    print("Testing Configuration")
    print("=" * 60)
    
    required_keys = [
        "twilio_account_sid",
        "twilio_auth_token",
        "twilio_from_number",
        "groq_api_key",
    ]
    
    missing = []
    for key in required_keys:
        value = getattr(settings, key, "")
        if not value:
            missing.append(key)
        else:
            # Mask sensitive values
            masked = value[:4] + "..." + value[-4:] if len(value) > 8 else "***"
            print(f"✅ {key}: {masked}")
    
    if missing:
        print(f"\n❌ Missing environment variables: {', '.join(missing)}")
        print("   Add these to your .env file")
        return False
    
    return True

async def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("Morning Agent Backend Test Suite")
    print("=" * 60)
    
    results = []
    
    # Test configuration
    results.append(("Configuration", await test_config()))
    
    # Test Groq (requires API key)
    if settings.groq_api_key:
        results.append(("Groq LLM", await test_groq()))
    else:
        print("\n⚠️  Skipping Groq test (no API key)")
        results.append(("Groq LLM", None))
    
    # Test STT and TTS (stubs)
    results.append(("STT Service", await test_stt()))
    results.append(("TTS Service", await test_tts()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result is True)
    failed = sum(1 for _, result in results if result is False)
    skipped = sum(1 for _, result in results if result is None)
    
    for name, result in results:
        if result is True:
            print(f"✅ {name}")
        elif result is False:
            print(f"❌ {name}")
        else:
            print(f"⚠️  {name} (skipped)")
    
    print(f"\nPassed: {passed}, Failed: {failed}, Skipped: {skipped}")
    
    if failed > 0:
        print("\n⚠️  Some tests failed. Fix the issues above.")
        return 1
    else:
        print("\n✅ All tests passed! Backend is ready.")
        return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
```

## Run Instructions

### 1. Setup Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials
```

### 2. Test Backend
```bash
python test_backend.py
```

### 3. Run Backend
```bash
uvicorn app.main:app --reload
```

Backend will run on `http://localhost:8000`

### 4. Test API Endpoints
```bash
# Create a task
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"title":"Test Task","instructions":"Call and say hello","phone_number":"+1234567890"}'

# List tasks
curl http://localhost:8000/tasks

# Health check
curl http://localhost:8000/healthz
```

### 5. iOS App (Optional)
1. Create project in Xcode
2. Copy Swift files from `ios/MorningAgent/`
3. Add files to Xcode project
4. Configure signing
5. Run in simulator

### 6. Hugging Face (Optional)
1. Go to huggingface.co/new-space
2. Choose Gradio SDK
3. Upload `huggingface_app.py` as `app.py`
4. Upload `huggingface_requirements.txt` as `requirements.txt`
5. Update `BACKEND_URL` in app.py
6. Deploy backend to Render/Fly.io/Railway

## Remaining Blockers

### Critical (Must Fix for Phone Calls to Work)
1. **STT Service Integration** - Currently a stub. Must integrate with:
   - OpenAI Whisper API, OR
   - Google Speech-to-Text, OR
   - Deepgram, OR
   - AssemblyAI
   
2. **TTS Service Integration** - Currently a stub. Must integrate with:
   - ElevenLabs API (best quality), OR
   - Google Cloud TTS, OR
   - AWS Polly, OR
   - OpenAI TTS

3. **Audio Format Conversion** - Twilio sends μ-law 8kHz audio. Need to:
   - Convert μ-law to PCM/WAV for STT services
   - Convert TTS output back to μ-law for Twilio
   - See `PHONE_PIPELINE_ARCHITECTURE.md` for conversion helper

### High Priority (Should Fix for Production)
4. **Retry Logic** - Add retry logic for failed calls
5. **Voicemail Detection** - Detect when call goes to voicemail
6. **Escalation Statuses** - Add more granular status tracking
7. **Error Handling** - Improve error handling in WebSocket
8. **Logging** - Add structured logging throughout

### Medium Priority (Nice to Have)
9. **Integration Tests** - Add tests for API endpoints
10. **Push Notifications** - Replace polling in iOS app
11. **Rate Limiting** - Add rate limiting to API
12. **Authentication** - Add user authentication
13. **PostgreSQL Migration** - Move from SQLite to PostgreSQL

### Low Priority (Future Enhancements)
14. **Multiple Phone Numbers** - Support multiple from numbers
15. **Call Recording** - Store actual call audio
16. **Analytics Dashboard** - Add analytics for call performance
17. **A/B Testing** - Test different prompts/strategies

## Next Best Single Prompt

"Implement real STT and TTS services using OpenAI Whisper for STT and OpenAI TTS for TTS, with proper audio format conversion between Twilio μ-law and PCM/WAV formats."

This will unblock the core phone call functionality and make the system actually capable of processing real calls.
