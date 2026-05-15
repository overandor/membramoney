# Roast My Startup

A dark-orange AI-powered startup critique engine that provides brutally honest, actionable feedback on landing pages.

## 🎯 Concept

Paste your startup URL and get roasted by a VC, engineer, customer, designer, and growth marketer. Funny enough to share. Useful enough to fix.

## 🎨 Visual Identity

- **Primary background**: #0B0B0D
- **Secondary surfaces**: #121216, #18181D, #202027
- **Primary orange**: #FF6A00
- **Hot orange accent**: #FF8A1F
- **Deep warning red-orange**: #E9441F
- **Muted text**: #A8A29E
- **Main text**: #F5F2EE

The UI feels like a startup interrogation room: dark, premium, hot, brutal, and funny.

## 🏗️ Architecture

### Frontend (Next.js)
- Next.js 14 with App Router
- Tailwind CSS with custom dark-orange theme
- Framer Motion for animations
- Lucide React for icons
- Recharts for score visualizations
- html-to-image for shareable PNG cards

### Backend (FastAPI)
- FastAPI for REST API
- httpx + BeautifulSoup for web scraping
- OpenAI GPT-4o for AI analysis
- In-memory storage for MVP (upgrade to Postgres later)

## 🚀 Quick Start

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Add your OpenAI API key to .env
# OPENAI_API_KEY=your_key_here

# Run the server
uvicorn app.main:app --reload --port 8000
```

Backend will run on http://localhost:8000

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

Frontend will run on http://localhost:3000

## 📡 API Endpoints

### POST /api/roasts
Create a new roast job.

**Request:**
```json
{
  "url": "https://yourstartup.com",
  "description": "Optional description",
  "intensity": "spicy",
  "visibility": "public"
}
```

**Response:**
```json
{
  "job_id": "abc123",
  "status": "queued"
}
```

### GET /api/roasts/{job_id}
Get roast job status.

**Response:**
```json
{
  "id": "abc123",
  "url": "https://yourstartup.com",
  "status": "processing",
  "stage": "Analyzing with AI agents...",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### GET /api/reports/{slug}
Get final roast report by slug.

### GET /api/gallery
Get public roast gallery.

## 📊 Report Structure

Each roast report includes:

1. **Executive Roast** - Brutal summary
2. **Agent Tribunal** - 5 expert agent critiques (VC, Customer, Engineer, Designer, Growth)
3. **Score Breakdown** - Positioning, Copy, Conversion, Pricing, Trust, Moat
4. **AI Wrapper Risk** - Risk assessment and reduction plan
5. **What to Fix First** - Prioritized fixes with impact estimates
6. **Landing Page Rewrite** - Hero, CTA, tagline, one-liner
7. **Share Card** - Viral-ready summary card

## 🔒 Security

The backend includes:
- URL validation and normalization
- SSRF protection (blocks localhost, private IPs)
- Rate limiting (to be added)
- Content safety rules (no personal attacks, protected traits)

## 🎯 MVP Build Order

1. ✅ URL input page
2. ✅ Basic URL scraper
3. ✅ LLM report generator
4. 🔄 Dark-orange report UI
5. ⏳ Shareable public report URL
6. ⏳ PNG share card
7. ⏳ Gallery
8. ⏳ Rate limiting
9. ⏳ Stripe private/deep roast
10. ⏳ Leaderboard
11. ⏳ Multi-agent backend
12. ⏳ GitHub/Product Hunt/PDF input

## 🚀 Deployment

### Frontend (Vercel)
```bash
cd frontend
vercel
```

### Backend (Render/Fly/Railway)
```bash
cd backend
# Deploy with your preferred platform
```

## 📝 License

MIT

## 🎯 Product Hunt Tagline

"Brutally honest AI feedback for your startup landing page."
