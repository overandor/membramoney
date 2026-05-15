# Morning Agent

An iPhone app where users can type or dictate tasks in the morning, and the backend executes phone-call tasks autonomously during the day. The app is the control tower. The backend does the calling, AI reasoning, logging, retries, and summaries.

## Architecture

- **SwiftUI iPhone app** as the control surface
- **FastAPI backend** in Python
- **Twilio** for outbound phone calls and media streaming
- **OpenAI Realtime API** for speech-to-speech AI handling
- **SQLite** for data persistence (MVP)

## Features

- Create tasks with phone numbers and instructions
- **Groq LLM Integration**: Ultra-fast text processing with Groq API
- **Task Summarization**: Automatic call transcript summarization
- **Task Completion Detection**: AI-powered task completion checking
- AI voice assistant calls on your behalf with disclosure
- Real-time audio streaming via WebSockets
- Task status tracking and transcripts
- Simple polling for task updates

## Local Development

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your Twilio, OpenAI, and Groq credentials
uvicorn app.main:app --reload
```

Backend will run on `http://localhost:8000`

### iPhone App

**Important:** See `XCODE_WINDSURF_WORKFLOW.md` for the recommended workflow.

Quick start:
1. Create project in Xcode first
2. Copy the Swift files from `ios/MorningAgent` into your Xcode project
3. Add files to Xcode project navigator (right-click > Add Files)
4. Configure signing in Xcode
5. Run in simulator (Cmd+R)

For day-to-day coding, use Windsurf to edit Swift files, then test in Xcode.

The app expects the backend at `http://localhost:8000`. For device testing, update the baseURL in `APIClient.swift` to your machine's IP address.

## Environment Variables

Required in `backend/.env`:

```
APP_BASE_URL=https://your-backend.example.com
PUBLIC_WS_BASE=wss://your-backend.example.com
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_FROM_NUMBER=+15555550123
OPENAI_API_KEY=sk-...
OPENAI_REALTIME_MODEL=gpt-realtime-1.5
GROQ_API_KEY=gsk-...
GROQ_MODEL=llama-3.3-70b-versatile
SQLITE_PATH=./morning_agent.db
DISCLOSURE_LINE=Hello, this is Joseph's AI assistant calling on his behalf.
```

## API Endpoints

- `POST /tasks` - Create a new task
- `GET /tasks` - List all tasks
- `GET /tasks/{id}` - Get task details
- `POST /tasks/{id}/start` - Start calling for a task
- `POST /twilio/outbound-twiml` - TwiML for Twilio calls
- `POST /calls/status` - Call status webhook
- `GET /healthz` - Health check
- `WS /media-stream` - WebSocket for audio streaming

## Next Steps

The scaffold includes:
1. ✅ Complete backend structure with FastAPI
2. ✅ SwiftUI iPhone app with all views
3. ✅ Twilio integration for outbound calls
4. ✅ OpenAI Realtime API skeleton
5. ⚠️ WebSocket audio bridge (TODO - needs frame-by-frame conversion)

The main unfinished work is the full audio-frame bridge between Twilio Media Streams and OpenAI Realtime. This is documented in the `/media-stream` endpoint in `backend/app/main.py`.

## Deployment

### Backend
The backend can be deployed to:
- Render
- Fly.io
- Railway

### Web UI (Desktop/Mobile)
A Gradio web interface is available for Hugging Face Spaces deployment:
- **File**: `huggingface_app.py` (deploy as `app.py`)
- **Requirements**: `huggingface_requirements.txt` (deploy as `requirements.txt`)
- **Documentation**: See `HUGGINGFACE_DEPLOYMENT.md`
- **Features**: Mobile-responsive, task management, call monitoring

### iOS App
The iOS app can be deployed to the App Store after proper testing and configuration. See `XCODE_WINDSURF_WORKFLOW.md` for the recommended development workflow.

## License

MIT
