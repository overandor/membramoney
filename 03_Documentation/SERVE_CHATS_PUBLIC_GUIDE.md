# How to Serve Your ChatGPT Chats to the Public

## Quick Start

The Chat Provenance system is now running on **http://localhost:8003**

## Step 1: Register an Account

1. Open http://localhost:8003 in your browser
2. Click **"Register"** button
3. Enter your email and password
4. Click **"Register"** to create your account

## Step 2: Install the Browser Extension

To export your ChatGPT conversations, you need the GPT Bridge extension:

1. Install [Tampermonkey](https://www.tampermonkey.net/) for your browser
2. Open the file: `/Users/alep/Downloads/gptbridge-provenance.user.js`
3. Copy the entire script
4. In Tampermonkey, create a new script and paste
5. Save the script

## Step 3: Configure the Extension

1. Go to [chat.openai.com](https://chat.openai.com)
2. Click the floating **GPT Bridge** button (bottom-right corner)
3. Click **"Settings"** (gear icon)
4. Set **API Base URL** to: `http://localhost:8003/api`
5. Enter the email and password you registered with in Step 1
6. Click **"Save Settings"**

## Step 4: Export Your Chats

1. Navigate to any ChatGPT conversation you want to share
2. Click the **GPT Bridge** button
3. You'll see the chat title, model, and message count
4. **Toggle "Public"** to make it visible to others
5. Click **"Export Chat"**
6. Wait for the success notification

## Step 5: View Your Public Chats

1. Go back to http://localhost:8003
2. Login with your credentials
3. Click **"Public Chats"** tab
4. Your exported chats will appear there
5. Anyone can view public chats without logging in

## Step 6: Share Your Public Chats

To share your public chats with others:

- **Direct Link**: Each chat has a unique ID (shown in the URL when viewing)
- **Public URL**: `http://localhost:8003/api/chats/public` - JSON API for all public chats
- **Web UI**: Share the web UI URL with others: `http://localhost:8003`

## Chat Visibility Settings

- **Private (default)**: Only you can see these chats
- **Public**: Anyone can view these chats (no login required)

## API Endpoints

### View All Public Chats
```bash
curl http://localhost:8003/api/chats/public
```

### View Your Chats (requires authentication)
```bash
curl http://localhost:8003/api/chats \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Get Chat Details
```bash
curl http://localhost:8003/api/chats/{chat_id}
```

## Making Chats Public

When exporting a chat via the browser extension:
1. Toggle the **"Public"** checkbox before clicking "Export"
2. The chat will be immediately visible to everyone
3. You can change visibility later via the API

## Troubleshooting

### Extension not showing up on ChatGPT
- Make sure Tampermonkey is enabled
- Refresh the ChatGPT page
- Check that the script is active in Tampermonkey

### API connection error
- Verify the backend is running on port 8003
- Check the API URL in extension settings
- Ensure CORS is enabled (it is by default)

### Chat not appearing in public list
- Make sure you toggled "Public" when exporting
- Check that the export was successful
- Refresh the web UI

## Security Notes

- **Private chats** are only accessible to you
- **Public chats** can be viewed by anyone with the URL
- Your ChatGPT login is separate from this system
- No scraping - you explicitly export each chat
- You control what becomes public

## Next Steps

After serving your chats locally, you can:

1. **Deploy to a server** to make it accessible from anywhere
2. **Add a custom domain** for professional sharing
3. **Set up authentication** for private viewing
4. **Add search/filtering** for large chat collections
5. **Export to other formats** (Markdown, PDF, etc.)

## Current Status

✅ Backend running on http://localhost:8003
✅ SQLite database created
✅ Web UI accessible
✅ Browser extension ready
✅ Ready to export and serve chats
