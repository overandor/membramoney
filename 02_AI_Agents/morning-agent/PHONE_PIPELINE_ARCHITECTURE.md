# Phone Pipeline Architecture - Multi-Service Integration

## Current Architecture (Morning Agent)

The Morning Agent uses a **unified Realtime API** approach that simplifies the multi-service pipeline:

```
Phone Call (Twilio)
    ↓ Twilio Media Streams (WebSocket)
    ↓ Audio frames (base64)
OpenAI Realtime API (WebSocket)
    ↓ Handles both:
    - Speech-to-Text (STT)
    - LLM Processing
    - Text-to-Speech (TTS)
    ↓ Audio frames (base64)
Twilio Media Streams (WebSocket)
    ↓
Phone Call (Twilio)
```

### How It Works

1. **Twilio** places the outbound call
2. **Twilio Media Streams** forks live call audio to your WebSocket server
3. **WebSocket Bridge** in `backend/app/main.py` (`/media-stream` endpoint):
   - Receives audio frames from Twilio
   - Forwards to OpenAI Realtime API
   - Receives processed audio back
   - Sends audio back to Twilio
4. **OpenAI Realtime API** handles:
   - **STT**: Converts caller's speech to text
   - **LLM**: Processes text with task instructions
   - **TTS**: Converts LLM response to speech

### Advantages of This Approach

- **Single API**: One WebSocket connection handles STT, LLM, and TTS
- **Low Latency**: Optimized for real-time conversations
- **Simplified Bridge**: Only need to bridge Twilio ↔ OpenAI
- **Built-in Coordination**: OpenAI handles turn-taking, interruptions, etc.

---

## Alternative: Modular Pipeline (Separate Services)

If you prefer using separate services for each component, here's the architecture:

```
Phone Call (Twilio)
    ↓ Twilio Media Streams
WebSocket Server
    ↓ Audio frames
STT Service (Whisper/Google/AWS)
    ↓ Text
LLM Service (OpenAI/Claude/Groq)
    ↓ Text
TTS Service (ElevenLabs/Google/AWS)
    ↓ Audio frames
WebSocket Server
    ↓ Audio frames
Twilio Media Streams
    ↓
Phone Call (Twilio)
```

### Service Options

#### STT (Speech-to-Text) Services
- **OpenAI Whisper**: `whisper-1` model, good accuracy
- **Google Cloud Speech-to-Text**: Low latency, streaming
- **AWS Transcribe**: Real-time streaming
- **AssemblyAI**: Optimized for phone calls
- **Deepgram**: Ultra-low latency

#### LLM Services
- **OpenAI GPT-4**: Best reasoning, higher cost
- **Anthropic Claude**: Good reasoning, safer
- **Groq Llama**: Very fast, open source
- **Local Ollama**: Free, runs locally

#### TTS (Text-to-Speech) Services
- **ElevenLabs**: Most natural, higher cost
- **Google Cloud TTS**: Good quality, standard pricing
- **AWS Polly**: Many voices, reliable
- **OpenAI TTS**: Good quality, simple
- **Azure Speech**: Enterprise-grade

---

## Implementation: Modular Pipeline

If you want to implement the modular pipeline, here's how to structure it:

### 1. Service Classes

```python
# backend/app/services/stt_service.py
class STTService:
    async def transcribe(self, audio_data: bytes) -> str:
        # Implement your STT service
        pass

# backend/app/services/llm_service.py
class LLMService:
    async def process(self, text: str, instructions: str) -> str:
        # Implement your LLM service
        pass

# backend/app/services/tts_service.py
class TTSService:
    async def synthesize(self, text: str) -> bytes:
        # Implement your TTS service
        pass
```

### 2. Updated WebSocket Bridge

```python
# backend/app/main.py - media_stream endpoint
@app.websocket("/media-stream")
async def media_stream(ws: WebSocket):
    await ws.accept()
    task_id = int(ws.query_params["task_id"])
    
    # Initialize services
    stt = STTService()
    llm = LLMService()
    tts = TTSService()
    
    conversation_history = []
    
    try:
        while True:
            message = await ws.receive_text()
            data = json.loads(message)
            
            if data.get("event") == "media":
                # 1. Decode Twilio audio
                audio_data = base64.b64decode(data["media"]["payload"])
                
                # 2. STT: Convert speech to text
                text = await stt.transcribe(audio_data)
                if not text:
                    continue
                
                conversation_history.append({"role": "user", "content": text})
                
                # 3. LLM: Process with instructions
                response_text = await llm.process(
                    text=text,
                    instructions=task.instructions
                )
                conversation_history.append({"role": "assistant", "content": response_text})
                
                # 4. TTS: Convert response to audio
                audio_response = await tts.synthesize(response_text)
                
                # 5. Send audio back to Twilio
                await ws.send(json.dumps({
                    "event": "media",
                    "media": {"payload": base64.b64encode(audio_response).decode()}
                }))
                
    except WebSocketDisconnect:
        pass
```

---

## Comparison: Unified vs Modular

| Aspect | Unified (OpenAI Realtime) | Modular (Separate Services) |
|--------|--------------------------|------------------------------|
| **Complexity** | Low (1 API) | High (3+ APIs) |
| **Latency** | Very low | Higher (more hops) |
| **Cost** | Medium | Variable |
| **Customization** | Limited | High |
| **Turn-taking** | Built-in | Manual implementation |
| **Interruptions** | Built-in | Manual implementation |
| **Voice Quality** | Good | Best (with ElevenLabs) |
| **STT Accuracy** | Good | Best (with Whisper) |

---

## Recommended Configurations

### Configuration 1: All-in-One (Easiest)
- **STT**: OpenAI Realtime (built-in)
- **LLM**: OpenAI Realtime (built-in)
- **TTS**: OpenAI Realtime (built-in)
- **Use case**: MVP, quick prototype
- **Cost**: ~$0.01-0.10 per call

### Configuration 2: Premium Quality
- **STT**: OpenAI Whisper
- **LLM**: OpenAI GPT-4
- **TTS**: ElevenLabs
- **Use case**: Production, high quality
- **Cost**: ~$0.05-0.20 per call

### Configuration 3: Cost-Optimized
- **STT**: Deepgram
- **LLM**: Groq (Llama)
- **TTS**: Google Cloud TTS
- **Use case**: High volume, cost-sensitive
- **Cost**: ~$0.01-0.05 per call

### Configuration 4: Local/Private
- **STT**: Local Whisper
- **LLM**: Local Ollama
- **TTS**: Coqui TTS
- **Use case**: Privacy, no API costs
- **Cost**: Server costs only

---

## Service Integration Examples

### OpenAI Whisper (STT)

```python
import openai
import base64

class WhisperSTT:
    def __init__(self, api_key: str):
        openai.api_key = api_key
    
    async def transcribe(self, audio_data: bytes) -> str:
        # Save to temp file for Whisper API
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_data)
            temp_path = f.name
        
        try:
            with open(temp_path, "rb") as audio_file:
                transcript = openai.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file
                )
            return transcript.text
        finally:
            import os
            os.unlink(temp_path)
```

### ElevenLabs (TTS)

```python
import elevenlabs
import base64

class ElevenLabsTTS:
    def __init__(self, api_key: str, voice_id: str):
        self.client = elevenlabs.Client(api_key=api_key)
        self.voice_id = voice_id
    
    async def synthesize(self, text: str) -> bytes:
        audio = self.client.generate(
            text=text,
            voice=self.voice_id,
            model="eleven_multilingual_v2"
        )
        # Convert generator to bytes
        audio_bytes = b"".join(audio)
        return audio_bytes
```

### Groq (LLM)

```python
from groq import Groq

class GroqLLM:
    def __init__(self, api_key: str):
        self.client = Groq(api_key=api_key)
    
    async def process(self, text: str, instructions: str) -> str:
        response = self.client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": text}
            ]
        )
        return response.choices[0].message.content
```

---

## Twilio Media Stream Format

Twilio sends audio in this format:

```json
{
  "event": "media",
  "sequenceNumber": "123",
  "media": {
    "payload": "base64-encoded-mulaw-audio"
  }
}
```

**Important:**
- Audio format: μ-law 8kHz (standard telephony)
- Sample rate: 8000 Hz
- Encoding: base64
- You may need to convert to PCM/WAV for some STT services

---

## Audio Conversion Helper

```python
import base64
import io
import wave
import struct

def twilio_to_wav(base64_payload: str) -> bytes:
    """Convert Twilio μ-law audio to WAV format"""
    # Decode base64
    mulaw_data = base64.b64decode(base64_payload)
    
    # Convert μ-law to PCM
    pcm_data = bytearray()
    for byte in mulaw_data:
        # μ-law to 16-bit PCM conversion
        pcm = mu_law_to_linear(byte)
        pcm_data.extend(struct.pack('<h', pcm))
    
    # Create WAV file
    wav_io = io.BytesIO()
    with wave.open(wav_io, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(pcm_data)
    
    return wav_io.getvalue()

def mu_law_to_linear(mu_law_byte: int) -> int:
    """Convert μ-law byte to 16-bit PCM"""
    # μ-law decoding formula
    mu = 255
    mu_law_byte = ~mu_law_byte
    sign = (mu_law_byte & 0x80) >> 7
    exponent = (mu_law_byte >> 4) & 0x07
    mantissa = mu_law_byte & 0x0F
    
    sample = ((mantissa << 3) + 0x84) << exponent
    sample -= 0x84
    
    if sign:
        sample = -sample
    
    return sample
```

---

## Next Steps

### For Current Scaffold (OpenAI Realtime)
1. Implement the WebSocket bridge in `/media-stream`
2. Handle Twilio base64 audio decoding
3. Forward to OpenAI Realtime session
4. Receive and send back audio

### For Modular Pipeline
1. Choose your STT/LLM/TTS services
2. Implement service classes
3. Update WebSocket bridge for modular flow
4. Add audio conversion helpers
5. Test latency and quality

---

## Recommendations

**For MVP:** Start with OpenAI Realtime (unified)
- Easiest to implement
- Lowest latency
- Good enough quality
- One API key to manage

**For Production:** Consider modular pipeline
- Better voice quality (ElevenLabs)
- More control over each component
- Can optimize costs per service
- Can swap services independently

**For Privacy/Local:** Use local services
- No data leaves your infrastructure
- No API costs
- Requires server resources
- Higher setup complexity
