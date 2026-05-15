#!/usr/bin/env python3
"""
Simple HTTP server to serve ChatGPT exported conversations
Run with: python serve_chatgpt.py
"""

import http.server
import socketserver
import os
from pathlib import Path

# Configuration
PORT = 8000
DIRECTORY = Path(__file__).parent / "chatgpt_exports"

# Create exports directory if it doesn't exist
DIRECTORY.mkdir(exist_ok=True)

class ChatGPTHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)
    
    def end_headers(self):
        # Enable CORS for easy access
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

def main():
    print(f"🚀 ChatGPT Export Server")
    print(f"📁 Serving directory: {DIRECTORY.absolute()}")
    print(f"🌐 URL: http://localhost:{PORT}")
    print(f"\n📋 Instructions:")
    print(f"1. Install ChatGPT Exporter userscript in Tampermonkey")
    print(f"2. Go to chat.openai.com")
    print(f"3. Use the exporter to save conversations to: {DIRECTORY}")
    print(f"4. Access them at http://localhost:{PORT}")
    print(f"\n💡 Tip: Export as HTML format for best web viewing")
    print(f"\nPress Ctrl+C to stop the server\n")

    with socketserver.TCPServer(("", PORT), ChatGPTHTTPRequestHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n👋 Server stopped")

if __name__ == "__main__":
    main()
