#!/usr/bin/env python3
"""
Google OAuth Setup Script for Chat Provenance

This script guides you through setting up Google OAuth credentials
so users can connect their own Google Drive accounts.

IMPORTANT: Each user will authenticate with THEIR OWN Google account.
These server credentials just enable the OAuth flow.
"""

import webbrowser
import json
import os

def print_header(text):
    print("\n" + "=" * 70)
    print(text)
    print("=" * 70 + "\n")

def print_step(step, text):
    print(f"\n{step}. {text}")
    print("-" * 70)

def main():
    print_header("Google OAuth Setup for Chat Provenance")
    
    print("""
This setup will enable users to connect THEIR OWN Google Drive accounts
to the Chat Provenance system. You are NOT connecting your personal account.

Each user will go through their own OAuth authentication flow.
    """)
    
    print_step(1, "Go to Google Cloud Console")
    print("Opening Google Cloud Console...")
    webbrowser.open("https://console.cloud.google.com/")
    
    input("\nPress Enter once you've opened the console...")
    
    print_step(2, "Create a New Project")
    print("""
    a. Click the project dropdown at the top
    b. Click "NEW PROJECT"
    c. Enter a project name (e.g., "Chat Provenance")
    d. Click "CREATE"
    """)
    input("\nPress Enter once you've created the project...")
    
    print_step(3, "Enable Google Drive API")
    print("Opening APIs & Services Library...")
    webbrowser.open("https://console.cloud.google.com/apis/library")
    
    print("""
    a. Search for "Google Drive API"
    b. Click on it
    c. Click "ENABLE"
    """)
    input("\nPress Enter once you've enabled the API...")
    
    print_step(4, "Configure OAuth Consent Screen")
    print("Opening OAuth consent screen...")
    webbrowser.open("https://console.cloud.google.com/apis/credentials/consent")
    
    print("""
    a. Click "OAuth consent screen" tab
    b. Select "External" user type
    c. Click "CREATE"
    d. Fill in:
       - App name: Chat Provenance
       - User support email: your email
       - Developer contact: your email
    e. Click "SAVE AND CONTINUE" (skip optional fields)
    f. Click "SAVE AND CONTINUE" on Test Users
    g. Click "SAVE AND CONTINUE" on Summary
    """)
    input("\nPress Enter once you've configured the consent screen...")
    
    print_step(5, "Create OAuth Credentials")
    print("Opening Credentials page...")
    webbrowser.open("https://console.cloud.google.com/apis/credentials")
    
    print("""
    a. Click "Create Credentials" → "OAuth client ID"
    b. Application type: "Web application"
    c. Name: Chat Provenance Web Client
    d. Authorized redirect URIs:
       - Click "ADD URI"
       - Enter: http://localhost:8003/api/google/callback
       - Click "ADD URI"
    e. Click "CREATE"
    f. You'll see a popup with Client ID and Client Secret
    g. Copy both values
    """)
    
    print_step(6, "Enter Your Credentials")
    
    client_id = input("\nEnter your Google Client ID: ").strip()
    client_secret = input("Enter your Google Client Secret: ").strip()
    
    if not client_id or not client_secret:
        print("\n❌ Error: Both Client ID and Client Secret are required!")
        return
    
    # Update .env file
    env_file = "/Users/alep/Downloads/chat-provenance-api/.env"
    
    print_step(7, "Saving Credentials to .env file")
    
    env_content = f"""# Google OAuth (for Google Drive integration)
GOOGLE_CLIENT_ID={client_id}
GOOGLE_CLIENT_SECRET={client_secret}
GOOGLE_REDIRECT_URI=http://localhost:8003/api/google/callback
"""
    
    with open(env_file, 'w') as f:
        f.write(env_content)
    
    print(f"✅ Credentials saved to {env_file}")
    
    print_step(8, "Restart the Server")
    print("The server needs to be restarted to pick up the new credentials.")
    
    restart = input("\nDo you want me to restart the server now? (y/n): ").strip().lower()
    
    if restart == 'y':
        print("\nRestarting server...")
        os.system("pkill -f 'uvicorn app.main:app'")
        os.system("cd /Users/alep/Downloads/chat-provenance-api && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8003 &")
        print("✅ Server restarted on http://localhost:8003")
    
    print_header("Setup Complete!")
    
    print("""
✅ Google OAuth is now configured!

HOW IT WORKS:
- Each user will click "Connect Google Drive" in the UI
- They will be redirected to Google's OAuth page
- They will authenticate with THEIR OWN Google account
- The system will receive an access token for that user
- The user can then browse THEIR OWN Google Drive files
- Files are processed with the user's own access token

PRIVACY:
- Users authenticate with their own Google accounts
- The system never sees user passwords
- Access tokens are stored securely
- Each user can only access their own files

NEXT STEPS:
1. Open http://localhost:8003
2. Register or login
3. Click "📁 Google Drive" tab
4. Click "Connect Google Drive"
5. Authenticate with your Google account
6. Browse and select your files
7. Generate ChatGPT conversations!

For other users to use this:
- They just need to access the web UI
- They will authenticate with their own Google accounts
- No additional setup required on their end
    """)

if __name__ == "__main__":
    main()
