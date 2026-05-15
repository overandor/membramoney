# Google Drive Integration Guide

## Overview

The Chat Provenance system now integrates with Google Drive, allowing you to:
1. Log in to your Google Drive account
2. Browse and select files from your Google Drive
3. Automatically generate ChatGPT conversations from file content
4. Make conversations public or private

## Setup Instructions

### Step 1: Create Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google Drive API:
   - Go to "APIs & Services" > "Library"
   - Search for "Google Drive API"
   - Click "Enable"
4. Create OAuth 2.0 credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Application type: "Web application"
   - Name: "Chat Provenance"
   - Authorized redirect URIs: `http://localhost:8003/api/google/callback`
   - Click "Create"
5. Copy the **Client ID** and **Client Secret**

### Step 2: Configure Environment Variables

Edit `/Users/alep/Downloads/chat-provenance-api/.env` (create it if it doesn't exist):

```bash
# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id-here
GOOGLE_CLIENT_SECRET=your-google-client-secret-here
GOOGLE_REDIRECT_URI=http://localhost:8003/api/google/callback
```

### Step 3: Restart the Server

```bash
# Kill existing server
pkill -f "uvicorn app.main:app"

# Start server
cd /Users/alep/Downloads/chat-provenance-api
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8003
```

## Using the Google Drive Integration

### Step 1: Login to Chat Provenance

1. Open http://localhost:8003
2. Register or login to your account

### Step 2: Connect Google Drive

1. Click the **"📁 Google Drive"** tab
2. Click **"Connect Google Drive"**
3. A popup will open for Google OAuth authentication
4. Authorize the application to access your Google Drive
5. After authentication, you'll receive credentials JSON
6. Paste the credentials into the prompt
7. Your Google Drive is now connected!

### Step 3: Browse and Select Files

1. Use the search box to filter files
2. Click **"Refresh Files"** to load your Google Drive
3. Check the boxes next to files you want to process
4. Selected files appear in the "Selected Files" section

### Step 4: Generate ChatGPT Conversations

1. Optionally check **"Make chats public"** to share with others
2. Click **"Generate Chats"**
3. The system will:
   - Download each selected file
   - Analyze the content (language, topics, structure)
   - Generate a structured ChatGPT conversation
   - Save the conversation to your account

### Step 5: View Generated Chats

1. Switch to **"My Chats"** tab
2. Your generated conversations will appear there
3. Click any chat to view the full conversation
4. The conversation includes:
   - File analysis (word count, language, topics)
   - Detailed content breakdown
   - AI-generated insights and recommendations

## Supported File Types

- **Google Docs**: Exported as plain text
- **Google Sheets**: Exported as CSV
- **Plain Text Files**: Downloaded as-is
- **PDF Files**: Extracted text content
- **Code Files**: Analyzed for structure and topics

## What the System Does

### File Analysis

For each file, the system:
- Detects the language (English, Chinese, Russian, etc.)
- Counts words, lines, and characters
- Extracts key topics and keywords
- Identifies document structure (code, markdown, JSON, etc.)
- Generates a summary

### Conversation Generation

The system creates a realistic ChatGPT conversation:
1. **User message**: Uploads the file and asks for analysis
2. **Assistant response**: Provides initial overview with statistics
3. **User message**: Requests detailed analysis
4. **Assistant response**: Provides deep dive into content
5. **User message**: Asks for recommendations
6. **Assistant response**: Provides actionable insights

### Storage

- Conversations are stored in the Chat Provenance database
- Each conversation links back to the original filename
- Public/Private visibility is controlled per conversation
- All conversations are searchable and filterable

## Privacy & Security

- **User-controlled**: You explicitly select which files to process
- **No scraping**: Files are only accessed when you select them
- **Credential security**: OAuth tokens are stored securely
- **Privacy control**: You decide which conversations are public
- **Google OAuth**: Uses standard OAuth 2.0 flow

## Troubleshooting

### "Failed to initiate Google authentication"
- Verify GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are set
- Check that Google Drive API is enabled
- Ensure redirect URI matches exactly: `http://localhost:8003/api/google/callback`

### "Invalid credentials format"
- Make sure you paste the complete JSON credentials
- Check that the JSON is properly formatted

### "Failed to load Google Drive files"
- Ensure you've authenticated successfully
- Check that your Google Drive has accessible files
- Verify the credentials are still valid

### "Failed to process files"
- Check file size (large files may take longer)
- Verify file format is supported
- Check server logs for detailed error messages

## API Endpoints

### Google OAuth
- `GET /api/google/auth` - Initiate OAuth flow
- `GET /api/google/callback?code=...&state=...` - OAuth callback

### Google Drive
- `POST /api/google/files` - List files (requires credentials)
- `POST /api/google/files/{id}/metadata` - Get file metadata
- `POST /api/google/files/{id}/content` - Download file content
- `POST /api/google/files/process` - Process files into chats

## Next Steps

After setting up Google Drive integration:

1. **Batch Processing**: Process multiple files at once
2. **Custom Analysis**: Modify the conversation generation logic
3. **Advanced Filtering**: Add more sophisticated file filtering
4. **Export Options**: Export conversations to other formats
5. **Sharing**: Share public conversations with specific users

## Current Status

✅ Google OAuth integration complete
✅ Google Drive API integration complete
✅ File download and processing complete
✅ Conversation generation complete
✅ Web UI integration complete
✅ Server running on http://localhost:8003
