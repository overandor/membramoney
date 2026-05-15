#!/usr/bin/env python3
"""
OLLAMA SERVER STARTER
Starts Ollama server automatically for trading bot
"""

import subprocess
import time
import os
import requests
import signal
import sys

def find_ollama():
    """Find Ollama installation"""
    # Check common paths
    paths = [
        '/Applications/Ollama.app/Contents/MacOS/ollama',
        '/usr/local/bin/ollama',
        'ollama'  # If in PATH
    ]
    
    for path in paths:
        try:
            if path == 'ollama':
                # Check if ollama is in PATH
                result = subprocess.run(['which', 'ollama'], capture_output=True, text=True)
                if result.returncode == 0:
                    return 'ollama'
            else:
                # Check if file exists
                if os.path.exists(path):
                    return path
        except:
            continue
    
    return None

def install_ollama():
    """Install Ollama if not found"""
    print("📦 Ollama not found. Installing...")
    
    try:
        # Download and install Ollama
        install_script = """
        curl -fsSL https://ollama.com/install.sh | sh
        """
        
        print("⏳ Downloading Ollama (this may take a few minutes)...")
        process = subprocess.run(['sh', '-c', install_script], capture_output=True, text=True)
        
        if process.returncode == 0:
            print("✅ Ollama installed successfully!")
            return True
        else:
            print(f"❌ Installation failed: {process.stderr}")
            return False
    
    except Exception as e:
        print(f"❌ Installation error: {e}")
        return False

def start_ollama_server():
    """Start Ollama server"""
    print("🚀 Starting Ollama server...")
    
    # Find Ollama
    ollama_path = find_ollama()
    
    if not ollama_path:
        print("❌ Ollama not found. Installing...")
        if not install_ollama():
            print("❌ Failed to install Ollama")
            return False
        
        # Try to find again after installation
        ollama_path = find_ollama()
        if not ollama_path:
            print("❌ Still cannot find Ollama after installation")
            return False
    
    print(f"✅ Found Ollama at: {ollama_path}")
    
    try:
        # Start Ollama server
        process = subprocess.Popen([ollama_path, 'serve'], 
                                 stdout=subprocess.PIPE, 
                                 stderr=subprocess.PIPE,
                                 text=True)
        
        print("⏳ Waiting for server to start...")
        time.sleep(5)
        
        # Check if server is running
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                print("✅ Ollama server is running!")
                models = response.json().get('models', [])
                if models:
                    print(f"📦 Available models: {[m['name'] for m in models]}")
                else:
                    print("📦 No models installed. Installing llama3.2...")
                    install_process = subprocess.run([ollama_path, 'pull', 'llama3.2'], 
                                                   capture_output=True, text=True)
                    if install_process.returncode == 0:
                        print("✅ llama3.2 model installed!")
                    else:
                        print(f"❌ Failed to install model: {install_process.stderr}")
                
                return process
            else:
                print(f"❌ Server not responding: {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            print(f"❌ Cannot connect to server: {e}")
            return None
    
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        return None

def main():
    print("🤖 OLLAMA SERVER STARTER")
    print("="*50)
    
    # Handle shutdown gracefully
    def signal_handler(sig, frame):
        print("\n🛑 Shutting down Ollama server...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Start server
    server_process = start_ollama_server()
    
    if server_process:
        print("🎉 Ollama server is ready!")
        print("💡 You can now run the trading bot")
        print("💡 Press Ctrl+C to stop the server")
        
        try:
            # Keep server running
            server_process.wait()
        except KeyboardInterrupt:
            print("\n🛑 Stopping server...")
            server_process.terminate()
            server_process.wait()
            print("✅ Server stopped")
    else:
        print("❌ Failed to start Ollama server")
        sys.exit(1)

if __name__ == "__main__":
    main()
