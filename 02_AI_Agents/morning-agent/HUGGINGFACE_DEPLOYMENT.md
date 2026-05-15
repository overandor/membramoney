# Morning Agent - Hugging Face Space Deployment

Web interface for Morning Agent that works on both desktop and mobile browsers.

## Overview

This Hugging Face Space provides a web-based interface for the Morning Agent system. Users can:
- Create tasks with phone numbers and instructions
- Start AI-powered phone calls
- View task status and call transcripts
- Review call summaries

## Architecture

```
Hugging Face Space (Gradio Web UI)
    ↓ HTTP API
FastAPI Backend (deployed separately)
    ↓
Twilio (phone calls)
    ↓
OpenAI Realtime API (AI voice)
```

## Deployment Options

### Option 1: Deploy Only the Web UI (Backend Local)

1. Create a new Hugging Face Space
2. Upload `huggingface_app.py` as `app.py`
3. Upload `huggingface_requirements.txt` as `requirements.txt`
4. Update `BACKEND_URL` in `app.py` to point to your local backend
5. The Space will connect to your local backend

### Option 2: Deploy Full Stack (Recommended)

1. **Deploy Backend** to Render/Fly.io/Railway:
   ```bash
   cd backend
   # Deploy using your platform's CLI
   ```

2. **Deploy Web UI** to Hugging Face:
   - Create a new Space
   - Upload `huggingface_app.py` as `app.py`
   - Upload `huggingface_requirements.txt` as `requirements.txt`
   - Update `BACKEND_URL` to your deployed backend URL

3. **Configure Environment Variables** (in Space settings):
   - `BACKEND_URL`: Your deployed backend URL
   - (Optional) Add API keys if needed

## Quick Start

### 1. Create Hugging Face Space

1. Go to [huggingface.co/new-space](https://huggingface.co/new-space)
2. Choose **Gradio** as the SDK
3. Name it: `morning-agent`
4. Make it **Public** or **Private**
5. Click **Create Space**

### 2. Upload Files

**Method A: Git (Recommended)**
```bash
git clone https://huggingface.co/spaces/YOUR_USERNAME/morning-agent
cd morning-agent
# Copy huggingface_app.py as app.py
# Copy huggingface_requirements.txt as requirements.txt
git add .
git commit -m "Initial deployment"
git push
```

**Method B: Web Interface**
1. Go to your Space on Hugging Face
2. Click "Files"
3. Click "Upload files"
4. Upload:
   - `huggingface_app.py` (rename to `app.py`)
   - `huggingface_requirements.txt` (rename to `requirements.txt`)

### 3. Configure Backend URL

Edit `app.py` and update:
```python
BACKEND_URL = "https://your-backend-url.com"  # Your deployed backend
```

Or use Hugging Face Secrets:
1. Go to Space Settings > Secrets
2. Add secret: `BACKEND_URL`
3. Value: Your deployed backend URL
4. Update `app.py` to read from environment:
```python
import os
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
```

### 4. Deploy Backend

#### Render
```bash
# Install Render CLI
npm install -g render-cli

# Login
render login

# Deploy
cd backend
render deploy
```

#### Fly.io
```bash
# Install Fly CLI
curl -L https://fly.io/install.sh | sh

# Login
fly auth login

# Deploy
cd backend
fly launch
fly deploy
```

#### Railway
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Deploy
cd backend
railway up
```

## Environment Variables

### Hugging Face Space Secrets
- `BACKEND_URL`: URL of your deployed backend (required)

### Backend Environment Variables
See `backend/.env.example` for required variables:
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_FROM_NUMBER`
- `OPENAI_API_KEY`
- `OPENAI_REALTIME_MODEL`
- `APP_BASE_URL`
- `PUBLIC_WS_BASE`

## Features

### Web UI Features
- **Task List**: View all recent tasks with status
- **Create Task**: Add new tasks with phone numbers and instructions
- **Task Details**: View full task information, transcripts, summaries
- **Auto-refresh**: Tasks refresh automatically and on demand
- **Mobile Responsive**: Works on phones, tablets, and desktops

### Backend Features
- REST API for task management
- Twilio integration for phone calls
- OpenAI Realtime API for AI voice
- WebSocket audio streaming
- SQLite/PostgreSQL persistence
- Call status tracking

## Usage

1. Open the Hugging Face Space URL
2. Go to "New Task" tab
3. Enter:
   - Task title (e.g., "Schedule dentist appointment")
   - Phone number (e.g., +1234567890)
   - Instructions (what the AI should say/do)
4. Click "Create & Start Call"
5. Monitor task status in "Tasks" tab
6. View call details in "Task Details" tab

## Troubleshooting

### "Backend not connected"
- Check `BACKEND_URL` is correct
- Verify backend is deployed and running
- Check backend health endpoint: `https://your-backend.com/healthz`

### "Failed to create task"
- Verify backend is accessible
- Check backend logs for errors
- Ensure all required environment variables are set

### "Failed to start call"
- Verify Twilio credentials
- Check Twilio account has credits
- Verify phone number format (E.164: +1234567890)

### Mobile UI Issues
- The Gradio interface is responsive by default
- If issues occur, try landscape mode on mobile
- Use Chrome/Safari for best compatibility

## Security

- **Disclosure**: AI always discloses it's calling on behalf of user
- **Logging**: All calls are logged with transcripts
- **HTTPS**: Use HTTPS for production deployments
- **Secrets**: Store API keys in platform secrets, not in code
- **Rate Limiting**: Consider adding rate limiting to backend

## Cost Estimates

### Hugging Face Space
- **Free tier**: Available for public spaces
- **CPU Basic**: ~$0.10/hour
- **CPU Upgrade**: ~$0.50/hour

### Backend (Render/Fly.io/Railway)
- **Free tier**: Available on some platforms
- **Standard**: ~$5-25/month
- **Pro**: ~$50-100/month

### Twilio
- **Phone calls**: ~$0.013/minute (US)
- **Phone number**: ~$1/month

### OpenAI
- **Realtime API**: Pricing varies by model
- **Estimated**: ~$0.01-0.10 per call

## Next Steps

1. Deploy backend to cloud platform
2. Deploy web UI to Hugging Face
3. Configure environment variables
4. Test with Twilio trial account
5. Add authentication (optional)
6. Add user accounts (optional)
7. Add push notifications (optional)

## Links

- [Hugging Face Spaces Documentation](https://huggingface.co/docs/hub/spaces)
- [Gradio Documentation](https://gradio.app/docs/)
- [Render Documentation](https://render.com/docs)
- [Fly.io Documentation](https://fly.io/docs/)
- [Railway Documentation](https://docs.railway.app/)
- [Twilio Documentation](https://www.twilio.com/docs)
- [OpenAI Realtime API](https://platform.openai.com/docs/guides/realtime)

## License

MIT
