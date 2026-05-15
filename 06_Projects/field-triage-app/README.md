---
title: Field Triage App
emoji: 🌍
colorFrom: indigo
colorTo: purple
sdk: docker
pinned: false
---

# Field Triage App

**Visual triage and candidate region detection for field observations**

---

## Overview

A single-file Gradio application for field triage with multi-LLM support, camera connectivity, geolocation capture, overlay visualization, SQLite logging, CSV export, and optional IPFS upload.

**Positioning:** This is a pilot/demo artifact for visual triage, not confirmed botanical or forensic identification.

---

## Features

### Multi-LLM Backends
- **Template Mode** - Deterministic template-based reports
- **Local Hugging Face** - DistilGPT2 for local text generation
- **Ollama** - Local LLM via Ollama API
- **OpenAI-Compatible** - Groq, OpenRouter, OpenAI, LM Studio, vLLM, etc.

### Camera Connectivity
- Upload images from device
- Browser webcam capture
- Network camera snapshot URL
- Periodic refresh from snapshot cameras

### Analysis Features
- Visual triage using zero-shot image classification
- Tile-based candidate region detection
- Confidence scoring and thresholding
- Overlay visualization with bounding boxes

### Data Management
- SQLite database for observation logging
- CSV export functionality
- Geolocation capture and map display
- Optional Pinata/IPFS evidence storage

---

## Configuration

### Environment Variables

```bash
# Application
APP_TITLE=Field Triage App
TARGET_NAME=bud
PORT=7860
LOG_LEVEL=INFO

# Models
MODEL_ID=google/siglip-base-patch16-224
HF_LLM_MODEL_ID=distilgpt2
DEVICE=cuda  # or cpu

# Image Processing
MAX_IMAGE_SIDE=1280
MAX_IMAGE_PIXELS=25000000
TILE_SIZE=224
TILE_STRIDE=160
TOP_K_TILES=8
MAX_TILES_TO_SCORE=120

# Thresholds
CLASSIFY_THRESHOLD_LIKELY=0.72
CLASSIFY_THRESHOLD_REVIEW=0.50
REGION_THRESHOLD=0.65

# Hugging Face
HF_MAX_NEW_TOKENS=120
HF_TEMPERATURE=0.6

# Database
DB_PATH=observations.db
EXPORT_DIR=exports

# Pinata/IPFS
PINATA_JWT=your_pinata_jwt
PINATA_UPLOAD_URL=https://uploads.pinata.cloud/v3/files
PINATA_GATEWAY=https://gateway.pinata.cloud/ipfs
PINATA_TIMEOUT=90

# OpenAI-Compatible (Groq)
OPENAI_COMPAT_BASE_URL=https://api.groq.com/openai/v1
OPENAI_COMPAT_API_KEY=your_groq_api_key_here
OPENAI_COMPAT_MODEL=llama3-70b-8192

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
```

---

## Installation

### Local Installation

```bash
# Clone repository
git clone <repository-url>
cd field-triage-app

# Install dependencies
pip install -r requirements.txt

# Run application
python app.py
```

### Docker

```bash
# Build image
docker build -t field-triage-app .

# Run container
docker run -p 7860:7860 \
  -e OPENAI_COMPAT_API_KEY=your_groq_api_key_here \
  field-triage-app
```

### Hugging Face Spaces

The app is configured for Hugging Face Spaces with Docker SDK.

---

## Usage

### Basic Workflow

1. **Select Image Source** - Upload, webcam, or network camera URL
2. **Capture Location** - Use geolocation button for GPS coordinates
3. **Choose LLM Backend** - Template, HF Local, Ollama, or OpenAI-Compatible
4. **Run Analysis** - Click "Analyze + Save" to process image
5. **Review Results** - Check summary, tiles, report, and map
6. **Export Data** - Download CSV of all observations

### LLM Backend Configuration

**For Groq (OpenAI-Compatible):**
```bash
OPENAI_COMPAT_BASE_URL=https://api.groq.com/openai/v1
OPENAI_COMPAT_API_KEY=your_groq_api_key_here
OPENAI_COMPAT_MODEL=llama3-70b-8192
```

**For OpenAI:**
```bash
OPENAI_COMPAT_BASE_URL=https://api.openai.com/v1
OPENAI_COMPAT_API_KEY=your_openai_key
OPENAI_COMPAT_MODEL=gpt-4o-mini
```

**For OpenRouter:**
```bash
OPENAI_COMPAT_BASE_URL=https://openrouter.ai/api/v1
OPENAI_COMPAT_API_KEY=your_openrouter_key
OPENAI_COMPAT_MODEL=anthropic/claude-3-haiku
```

**For Ollama:**
```bash
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
```

---

## Honest Limitations

- **Visual Triage Only** - This performs visual similarity scoring, not confirmed substance identification
- **Candidate Regions** - `candidate_region_count` is not actual object count
- **Camera Support** - Assumes snapshot image URLs, not raw RTSP streaming
- **Identification** - Not represented as certified enforcement or forensic identification

### Next Upgrades

1. RTSP/OpenCV for live camera streaming
2. Real object detection instead of tile similarity scoring
3. Enhanced multi-camera support
4. Advanced verification pipelines

---

## Database Schema

### Observations Table

```sql
CREATE TABLE observations (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    filename TEXT,
    source_type TEXT,
    camera_url TEXT,
    verdict TEXT,
    overall_score REAL,
    whole_image_score REAL,
    best_tile_score REAL,
    candidate_region_count INTEGER,
    scene_description TEXT,
    report_text TEXT,
    llm_backend TEXT,
    image_width INTEGER,
    image_height INTEGER,
    lat REAL,
    lon REAL,
    accuracy REAL,
    location_source TEXT,
    original_cid TEXT,
    original_ipfs_url TEXT,
    overlay_cid TEXT,
    overlay_ipfs_url TEXT,
    summary_json TEXT
)
```

---

## Deployment

### Hugging Face Spaces

1. Create new Space with Docker SDK
2. Set environment variables in Space settings
3. Push code to Space
4. Space will automatically build and deploy

### Production Considerations

- Add authentication for production use
- Implement rate limiting
- Add backup and recovery for database
- Configure monitoring and alerting
- Set up SSL/TLS for HTTPS

---

## License

Commercial License v1.0

---

*Field Triage App v1.0*
*Visual triage and candidate region detection*
