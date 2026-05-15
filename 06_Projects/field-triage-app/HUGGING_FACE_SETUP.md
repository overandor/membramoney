# Field Triage App - Hugging Face Space Setup

**Space URL:** https://huggingface.co/spaces/luguog/field-triage-app

---

## Status

✅ **Successfully deployed to Hugging Face Spaces**
- All files pushed (app.py, Dockerfile, requirements.txt, README.md, .gitattributes)
- Space will automatically build and deploy

---

## Required Environment Variables

Navigate to the Space Settings → Secrets and add the following environment variables:

### Groq API (Required for OpenAI-Compatible backend)

```bash
OPENAI_COMPAT_BASE_URL=https://api.groq.com/openai/v1
OPENAI_COMPAT_API_KEY=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
OPENAI_COMPAT_MODEL=llama3-70b-8192
```

### Optional: Pinata/IPFS

```bash
PINATA_JWT=your_pinata_jwt
PINATA_UPLOAD_URL=https://uploads.pinata.cloud/v3/files
PINATA_GATEWAY=https://gateway.pinata.cloud/ipfs
PINATA_TIMEOUT=90
```

### Optional: Ollama (for local deployment)

```bash
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
```

---

## Default Configuration

The app will use these default values if environment variables are not set:

```bash
APP_TITLE=Field Triage App
TARGET_NAME=bud
PORT=7860
LOG_LEVEL=INFO
MODEL_ID=google/siglip-base-patch16-224
HF_LLM_MODEL_ID=distilgpt2
DEVICE=cpu
MAX_IMAGE_SIDE=1280
MAX_IMAGE_PIXELS=25000000
TILE_SIZE=224
TILE_STRIDE=160
TOP_K_TILES=8
MAX_TILES_TO_SCORE=120
CLASSIFY_THRESHOLD_LIKELY=0.72
CLASSIFY_THRESHOLD_REVIEW=0.50
REGION_THRESHOLD=0.65
HF_MAX_NEW_TOKENS=120
HF_TEMPERATURE=0.6
DB_PATH=observations.db
EXPORT_DIR=exports
```

---

## Setup Steps

1. **Visit the Space:** https://huggingface.co/spaces/luguog/field-triage-app
2. **Go to Settings → Secrets**
3. **Add the Groq API key** (required for OpenAI-compatible backend)
4. **Wait for build** - The Space will automatically build and deploy
5. **Test the app** - Once built, the app will be available at the Space URL

---

## Build Process

The Space uses the Docker SDK and will:
1. Pull the Python 3.11 slim base image
2. Install dependencies from requirements.txt
3. Copy the app.py file
4. Start the Gradio app on port 7860
5. Expose the app via Hugging Face's infrastructure

---

## Usage

Once deployed:

1. **Select Image Source** - Upload, webcam, or network camera URL
2. **Capture Location** - Use geolocation button for GPS coordinates
3. **Choose LLM Backend** - Template, HF Local, Ollama, or OpenAI-Compatible (Groq)
4. **Run Analysis** - Click "Analyze + Save" to process image
5. **Review Results** - Check summary, tiles, report, and map
6. **Export Data** - Download CSV of all observations

---

## Troubleshooting

### Build Fails

- Check the Logs tab for error messages
- Ensure all dependencies are in requirements.txt
- Verify Dockerfile syntax

### App Not Starting

- Check the App tab for runtime errors
- Verify environment variables are set correctly
- Ensure Groq API key is valid

### Groq API Errors

- Verify the API key is correct
- Check Groq API status
- Ensure the model name is correct (llama3-70b-8192)

---

## Security Notes

- API keys are stored in Hugging Face Space Secrets (not in code)
- The Space is public by default - consider making it private for production
- Add authentication for production use
- Implement rate limiting for production deployments

---

## Next Steps

1. **Monitor build** - Watch the Logs tab for build progress
2. **Test functionality** - Once built, test all features
3. **Add authentication** - For production use
4. **Configure monitoring** - Set up alerts for failures
5. **Customize labels** - Modify POSITIVE_LABELS and NEGATIVE_LABELS in app.py for your use case

---

*Hugging Face Space Setup v1.0*
