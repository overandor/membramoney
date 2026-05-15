# Chat Provenance API

A user-controlled API for managing ChatGPT conversation exports with public/private publishing controls.

## Architecture

**Flow:** User Export → Upload → Store → API → Public UI

Users explicitly provide their chat data (no scraping). Your API serves only what they own and upload.

## Features

- **User Authentication**: JWT-based auth with access/refresh tokens
- **Google OAuth Integration**: Connect to ChatGPT using your Google account
- **ChatGPT Connection**: Direct integration with ChatGPT's authentication system
- **Browser Extension**: Tampermonkey userscript for real-time ChatGPT integration
- **Chat Upload**: Upload ChatGPT export files (JSON format)
- **Chat Normalization**: Auto-detects and normalizes different ChatGPT export formats
- **Public/Private Control**: Toggle visibility of your chats
- **Role-Based Messages**: Preserves user vs assistant message structure
- **Model Tracking**: Captures which GPT model was used
- **Web UI**: Modern interface to view and manage chats
- **Real-time Status**: Live ChatGPT connection status in the UI

## Quick Start

### Backend (Python/FastAPI)

```bash
# Clone or navigate to the directory
cd chat-provenance-api

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your settings

# Start with Docker (recommended)
docker-compose up -d

# Or start manually
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Web UI

Once the backend is running:
- Open http://localhost:8000 in your browser
- The web UI will load automatically
- Register or login to access your chats
- **Connect to ChatGPT** using the "Sign in with Google" button
- Install the browser extension to enable real-time chat export
- Browse your chats and public conversations

### Google OAuth Integration

The system integrates with ChatGPT's Google OAuth authentication:

1. **Login Screen**: Click "Sign in with Google" to connect to ChatGPT
2. **ChatGPT Window**: Opens ChatGPT in a popup for Google OAuth
3. **Browser Extension**: Install the GPT Bridge extension to detect your ChatGPT login
4. **Real-time Status**: The UI shows your ChatGPT connection status
5. **Chat Export**: Use the extension to export chats directly from ChatGPT

**Note**: You must have a ChatGPT subscription to use this system. The system does not scrape ChatGPT - it only serves data you explicitly export.

### Browser Extension (Tampermonkey)

1. Install [Tampermonkey](https://www.tampermonkey.net/) for your browser
2. Open `gptbridge-provenance.user.js`
3. Copy the entire script
4. In Tampermonkey, create a new script and paste
5. Save

The extension will run on `chat.openai.com` and `chatgpt.com`.

## Usage

### Accessing the Web UI

1. Start the backend server:
```bash
cd chat-provenance-api
docker-compose up -d
```

2. Open your browser and navigate to:
   - http://localhost:8000 (auto-redirects to UI)
   - or http://localhost:8000/static/index.html

3. Register a new account or login

4. Use the browser extension to export chats from ChatGPT

5. View your chats in the web UI

### 1. Register User

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "securepassword"}'
```

### 2. Login

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "securepassword"}'
```

Response:
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

### 3. Upload Chat (via Extension)

1. Log in to ChatGPT
2. Click the GPT Bridge floating button (bottom-right)
3. Enter your API credentials
4. Click "Export Current Chat"
5. Toggle "Make public" if desired
6. Click "Publish"

### 4. API Endpoints

#### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login and get tokens
- `POST /api/auth/refresh` - Refresh access token
- `GET /api/auth/me` - Get current user info

#### Chats
- `POST /api/chats/upload` - Upload chat (requires file)
- `GET /api/chats` - List your chats (authenticated)
- `GET /api/chats/public` - List public chats (public)
- `GET /api/chats/{id}` - Get specific chat
- `POST /api/chats/{id}/publish` - Toggle public/private
- `DELETE /api/chats/{id}` - Delete chat

#### System
- `GET /` - API info
- `GET /health` - Health check
- `GET /docs` - Interactive API documentation (Swagger)

## ChatGPT Export Formats

The system auto-detects and normalizes multiple formats:

### GPT Bridge Extension Format (Recommended)
```json
{
  "title": "Chat Title",
  "model": "GPT-4",
  "messages": [
    {"role": "user", "content": "Hello", "timestamp": "2024-01-01T00:00:00Z"},
    {"role": "assistant", "content": "Hi there!", "timestamp": "2024-01-01T00:00:01Z"}
  ],
  "message_count": 2,
  "timestamp": "2024-01-01T00:00:00Z",
  "source": "gptbridge-extension"
}
```

### ChatGPT Export Format
```json
{
  "mapping": {
    "node_id": {
      "message": {
        "author": {"role": "user"},
        "content": {
          "parts": ["text"]
        }
      }
    }
  }
}
```

### Generic Format
```json
[
  {"role": "user", "content": "text"},
  {"role": "assistant", "content": "text"}
]
```

## Browser Extension Features

- **Multi-method extraction**: React Fiber, DOM parsing, fallback methods
- **Role detection**: User vs assistant identification
- **Model tracking**: Captures which GPT model was used
- **Title extraction**: Multiple methods for accurate titles
- **Timestamp tracking**: When messages were sent
- **Code block handling**: Preserves code formatting
- **Real-time updates**: Detects chat changes automatically

## Security

- **User ownership**: JWT authentication required for uploads
- **Rate limiting**: 100 req/min general, 10 req/min uploads
- **File size limits**: 50MB max upload
- **Input validation**: Pydantic schemas
- **SQL injection prevention**: SQLAlchemy ORM
- **CORS**: Configurable origins

## Configuration

Environment variables in `.env`:

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/chat_provenance
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30

# Rate Limiting
RATE_LIMIT_PER_MINUTE=100
UPLOAD_RATE_LIMIT_PER_MINUTE=10

# File Upload
MAX_UPLOAD_SIZE_MB=50
ALLOWED_EXTENSIONS=json

# CORS
CORS_ORIGINS=["http://localhost:3000","http://localhost:8080"]
```

## Browser Extension Features

- **ChatGPT auth detection**: Uses existing ChatGPT login
- **Floating UI**: Non-intrusive overlay
- **Chat extraction**: Auto-extracts current conversation
- **API integration**: Direct upload to your backend
- **Publish controls**: Toggle public/private
- **Chat browsing**: View your chats and public chats

## Project Structure

```
chat-provenance-api/
├── app/
│   ├── api/
│   │   ├── auth.py          # Authentication endpoints
│   │   ├── chats.py         # Chat management endpoints
│   │   └── deps.py          # Dependencies (auth)
│   ├── core/
│   │   ├── config.py        # Settings
│   │   └── security.py      # JWT, password hashing
│   ├── db/
│   │   └── base.py          # Database connection
│   ├── models/
│   │   ├── user.py          # User model
│   │   └── chat.py          # Chat model
│   ├── schemas/
│   │   ├── user.py          # User schemas
│   │   └── chat.py          # Chat schemas
│   ├── services/
│   │   └── normalizer.py    # Chat normalization
│   └── main.py              # FastAPI app
├── docker-compose.yml       # Docker orchestration
├── Dockerfile               # Container build
├── requirements.txt         # Python dependencies
├── .env.example             # Environment template
└── gptbridge-provenance.user.js  # Browser extension
```

## Advanced Features (Future)

1. **Semantic indexing**: Embed messages for semantic search
2. **Monetization**: Lock messages behind paywall
3. **Identity (KYI)**: Attach chat to verified user
4. **Version control**: Track chat edits
5. **Analytics**: View counts, engagement metrics

## Deployment

### Docker (Recommended)

```bash
docker-compose up -d
```

### Manual

```bash
# Start PostgreSQL
# Start Redis
# Run migrations (when implemented)
# Start API
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Production Considerations

- Change `SECRET_KEY` in production
- Enable HTTPS
- Use environment variables for secrets
- Set up database backups
- Configure monitoring
- Use production-grade PostgreSQL/Redis

## License

MIT

## Philosophy

**Do NOT scrape directly from ChatGPT servers**
**DO let users upload/export**
**Serve via your own API**

This ensures:
- User consent and control
- Legal compliance
- Data ownership clarity
- Scalable architecture
