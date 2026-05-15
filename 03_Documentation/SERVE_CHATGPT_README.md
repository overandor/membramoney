# ChatGPT Public Export Server

Serve your ChatGPT conversations publicly using the ChatGPT Exporter userscript.

## Setup Instructions

### 1. Install the Userscript

1. Install [Tampermonkey](https://www.tampermonkey.net/) (Chrome/Edge) or [Greasemonkey](https://www.greasespot.net/) (Firefox)
2. Open the userscript file: `ChatGPT Exporter-2.30.0.user.js`
3. Tampermonkey should auto-detect it - click "Install"
4. Or manually: Tampermonkey Dashboard → Create new script → Paste content → Save

### 2. Export Your Conversations

1. Go to [chat.openai.com](https://chat.openai.com)
2. You'll see an "Export" button in the sidebar
3. Click it and choose export format:
   - **HTML** (recommended for web viewing)
   - Markdown
   - JSON
4. Save exports to: `/Users/alep/Downloads/chatgpt_exports/`

### 3. Start the Server

```bash
cd /Users/alep/Downloads
python serve_chatgpt.py
```

Server runs at: http://localhost:8000

### 4. Access Your Conversations

Open http://localhost:8000 in your browser to view all exported conversations.

## Export Formats

- **HTML**: Best for public web viewing, includes styling
- **Markdown**: Good for documentation, GitHub READMEs
- **JSON**: For programmatic access, data analysis

## Advanced Options

### Make Public (ngrok)

To share publicly over the internet:

```bash
# Install ngrok
brew install ngrok

# Run ngrok on port 8000
ngrok http 8000
```

Share the ngrok URL with others.

### Custom Port

Edit `serve_chatgpt.py` and change:
```python
PORT = 8000  # Change to your preferred port
```

### Custom Directory

Edit `serve_chatgpt.py` and change:
```python
DIRECTORY = Path(__file__).parent / "your_custom_folder"
```

## Features

- ✅ Auto-creates exports directory
- ✅ CORS enabled for easy access
- ✅ Supports all export formats
- ✅ Simple file listing
- ✅ No database required

## Security Note

This is a basic file server. For production use with sensitive content, consider:
- Adding authentication
- Using HTTPS
- Implementing access controls
- Using a proper web server (nginx, Apache)
