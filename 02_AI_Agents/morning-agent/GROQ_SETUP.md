# Groq Integration for Morning Agent

## Overview

Morning Agent now supports Groq as the LLM service for faster, cost-effective text processing. Groq provides ultra-low latency inference for open-source models like Llama.

## Benefits of Using Groq

- **Ultra-low latency**: ~10-50ms response time
- **Cost-effective**: Free tier available, very low paid tier pricing
- **Open-source models**: Llama 3.3, Mixtral, and more
- **High throughput**: Optimized for production workloads
- **No API rate limits**: Unlike some other providers

## Setup Instructions

### 1. Get Groq API Key

1. Go to [console.groq.com](https://console.groq.com)
2. Sign up or log in
3. Go to API Keys section
4. Create a new API key
5. Copy the key (starts with `gsk_`)

### 2. Add to Environment Variables

Add to your `backend/.env` file:

```bash
GROQ_API_KEY=gsk_your_actual_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```

### 3. Install Dependencies

```bash
cd backend
pip install groq
```

Or update requirements.txt (already included):
```bash
pip install -r requirements.txt
```

## Available Groq Models

### Recommended Models

| Model | Use Case | Speed | Cost |
|-------|----------|-------|------|
| `llama-3.3-70b-versatile` | General purpose, reasoning | Very fast | Low |
| `llama-3.1-70b-versatile` | General purpose | Very fast | Low |
| `mixtral-8x7b-32768` | Fast responses | Ultra fast | Lowest |
| `gemma-7b-it` | Quick tasks | Ultra fast | Lowest |

### Model Selection

**For Phone Calls:**
- Use `llama-3.3-70b-versatile` for best reasoning
- Use `mixtral-8x7b-32768` for faster responses

**For Summarization:**
- Use `llama-3.3-70b-versatile` for accuracy
- Use `gemma-7b-it` for speed

## How Groq is Used in Morning Agent

### 1. Real-time Processing (Modular Pipeline)

In the WebSocket media stream (`/media-stream`):

```python
# Process caller's speech with Groq
response = await groq_llm.process(
    text=caller_speech,
    instructions=task.instructions,
    conversation_history=conversation_history
)
```

### 2. Transcript Summarization

After call ends, Groq summarizes the transcript:

```python
summary = await groq_llm.summarize_transcript(
    transcript=full_transcript,
    instructions=task.instructions
)
```

### 3. Task Completion Check

Groq analyzes if the task was completed:

```python
completion = await groq_llm.check_task_completion(
    transcript=full_transcript,
    instructions=task.instructions
)
# Returns: {"completed": bool, "reason": str, "action_items": list}
```

## Groq Service API

### GroqLLMService Class

```python
from backend.app.services.groq_llm import get_groq_llm

# Get service
groq_llm = get_groq_llm()

# Process text
response = await groq_llm.process(
    text="Hello, I'm calling about...",
    instructions="Schedule a dentist appointment",
    conversation_history=[...]
)

# Summarize transcript
summary = await groq_llm.summarize_transcript(
    transcript="Full call transcript here...",
    instructions="Schedule a dentist appointment"
)

# Check completion
result = await groq_llm.check_task_completion(
    transcript="Full call transcript here...",
    instructions="Schedule a dentist appointment"
)
```

## Configuration Options

### Environment Variables

```bash
# Required
GROQ_API_KEY=gsk_...

# Optional (with defaults)
GROQ_MODEL=llama-3.3-70b-versatile
```

### Model Parameters

In `groq_llm.py`, you can adjust:

```python
response = self.client.chat.completions.create(
    model=self.model,
    messages=messages,
    temperature=0.7,      # Creativity (0.0-1.0)
    max_tokens=512,       # Response length
)
```

## Cost Comparison

### Per Call Estimates

| Provider | Model | Cost per 1K tokens |
|----------|-------|-------------------|
| Groq | Llama 3.3 70B | $0.00059 |
| OpenAI | GPT-4 | $0.03 |
| OpenAI | GPT-3.5 | $0.0015 |
| Groq | Mixtral 8x7B | $0.00024 |

**Typical phone call (~2000 tokens):**
- Groq: ~$0.001
- OpenAI GPT-4: ~$0.06
- OpenAI GPT-3.5: ~$0.003

## Free Tier

Groq offers a generous free tier:
- **Free tokens**: Daily limit (check console for current limits)
- **No credit card required** for free tier
- **No rate limits** on free tier

## Troubleshooting

### "GROQ_API_KEY not set"

Add to `.env`:
```bash
GROQ_API_KEY=gsk_your_key_here
```

### "Invalid API Key"

- Verify the key starts with `gsk_`
- Check it's not expired
- Ensure no extra spaces in `.env` file

### "Model not found"

- Verify model name in `GROQ_MODEL`
- Check [Groq console](https://console.groq.com) for available models
- Use `llama-3.3-70b-versatile` as fallback

### Slow Responses

- Groq is typically very fast
- If slow, check network connectivity
- Try a different model (e.g., `mixtral-8x7b-32768`)

## Migration from OpenAI

### Before (OpenAI Realtime)

```python
# Uses OpenAI Realtime API (unified STT+LLM+TTS)
bridge = RealtimeBridge(task_id, instructions)
await bridge.open()
```

### After (Groq + Modular)

```python
# Uses Groq for LLM, separate STT/TTS services
groq_llm = get_groq_llm()
response = await groq_llm.process(text, instructions, history)
```

**Benefits:**
- Lower cost
- Faster response time
- More control over each component
- Can swap STT/TTS services independently

## Testing

### Test Groq Integration

```python
import asyncio
from backend.app.services.groq_llm import get_groq_llm

async def test_groq():
    groq = get_groq_llm()
    response = await groq.process(
        text="Hello, I need to schedule an appointment",
        instructions="You are a dental office scheduler",
        conversation_history=[]
    )
    print(f"Response: {response}")

asyncio.run(test_groq())
```

### Test Summary

```python
async def test_summary():
    groq = get_groq_llm()
    summary = await groq.summarize_transcript(
        transcript="Caller: Hi, I need to schedule an appointment...",
        instructions="Schedule a dentist appointment"
    )
    print(f"Summary: {summary}")

asyncio.run(test_summary())
```

## Production Considerations

### Error Handling

The Groq service includes error handling:

```python
try:
    response = await groq_llm.process(text, instructions)
except Exception as e:
    # Fallback or retry logic
    logger.error(f"Groq error: {e}")
```

### Fallback

Consider adding a fallback LLM:

```python
try:
    response = await groq_llm.process(text, instructions)
except Exception as e:
    # Fallback to OpenAI
    response = await openai_llm.process(text, instructions)
```

### Monitoring

Track Groq usage:
- Response times
- Token usage
- Error rates
- Model performance

## Links

- [Groq Console](https://console.groq.com)
- [Groq Documentation](https://console.groq.com/docs)
- [Groq Models](https://console.groq.com/docs/models)
- [Llama 3.3 Documentation](https://llama.meta.com/)

## Summary

Groq provides:
- ✅ Ultra-low latency
- ✅ Very low cost
- ✅ Open-source models
- ✅ Easy integration
- ✅ Free tier available

Perfect for Morning Agent's phone call processing needs!
