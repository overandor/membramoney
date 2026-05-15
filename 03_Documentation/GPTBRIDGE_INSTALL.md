# GPT Bridge - Installation Guide

## What is GPT Bridge?

A browser extension that integrates ChatGPT with your Chat Provenance API. It:
- Uses your existing ChatGPT login (Google OAuth)
- Adds a floating UI to export chats
- Sends chats to your API
- Lets you control public/private publishing

## Installation

### Step 1: Install Tampermonkey

1. Go to [tampermonkey.net](https://www.tampermonkey.net/)
2. Download for your browser (Chrome, Firefox, Safari, Edge)
3. Install the extension
4. Grant necessary permissions

### Step 2: Install the Script

1. Open the file `gptbridge-provenance.user.js` (in Downloads folder)
2. Copy the entire content
3. Click the Tampermonkey icon in your browser
4. Click "Create a new script"
5. Paste the script content
6. Press `Ctrl+S` (or `Cmd+S` on Mac) to save
7. The script is now installed!

### Step 3: Start the Backend API

```bash
cd chat-provenance-api
docker-compose up -d
```

The API will be available at `http://localhost:8000`

### Step 4: Use GPT Bridge

1. Go to [chat.openai.com](https://chat.openai.com)
2. Log in with your Google account (as usual)
3. You'll see a purple floating button in the bottom-right corner
4. Click it to open the GPT Bridge panel
5. Enter your API credentials:
   - API URL: `http://localhost:8000/api` (default)
   - Email: your registered email
   - Password: your password
6. Click "Login" or "Register" (if new user)
7. Start a chat in ChatGPT
8. Click "Export Current Chat" to save it
9. Toggle "Make public" if you want to share it
10. Click "Publish" to make it available

## Features

### Chat Detection
- Automatically detects the current ChatGPT conversation
- Shows chat title and message count
- Updates in real-time as you chat

### Export
- Extracts all messages from current chat
- Normalizes ChatGPT format
- Sends to your API with title and timestamp

### Publishing
- Toggle public/private per chat
- Public chats visible to all users
- Private chats only visible to you

### Browsing
- "My Chats": View all your uploaded chats
- "Public Chats": Browse publicly shared chats

## Troubleshooting

### Extension not showing up
- Make sure Tampermonkey is enabled
- Check that the script is enabled in Tampermonkey dashboard
- Refresh the ChatGPT page

### Can't connect to API
- Verify the backend is running: `docker-compose ps`
- Check the API URL in settings
- Check browser console for errors (F12)

### Chat not extracting
- Make sure you're on a chat page (not the main menu)
- Wait for the chat to fully load
- Try refreshing the page

### Login fails
- Verify your email/password are correct
- Check that the API is running
- Check browser console for error details

## Security

- The extension uses your existing ChatGPT authentication
- Your ChatGPT credentials never leave the browser
- API credentials are stored locally in your browser
- All data is sent to your own API server

## Customization

### Change API URL

1. Open the GPT Bridge panel
2. In the API URL field, enter your server address
3. Login again with new URL

### Change Button Position

Edit the script, find this line:
```javascript
fab.style.cssText = `
    position: fixed;
    bottom: 20px;
    right: 20px;
```

Change `bottom` and `right` values as needed.

## Uninstallation

1. Click Tampermonkey icon
2. Go to "Dashboard"
3. Find "GPT Bridge - Chat Provenance"
4. Click the trash icon to delete
5. Refresh ChatGPT page

## Support

For issues:
1. Check browser console (F12) for errors
2. Verify API is running: `curl http://localhost:8000/health`
3. Check API logs: `docker-compose logs app`
