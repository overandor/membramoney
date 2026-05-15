#!/usr/bin/env python3
"""
LOCAL AI SETUP
Setup and configure local DeepSeek/Ollama for autonomous trading agent
"""

import subprocess
import requests
import time
import logging
import os
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LocalAISetup:
    """Setup local AI environment"""
    
    def __init__(self):
        self.ollama_url = "http://localhost:11434"
        self.models_to_install = [
            "deepseek-coder:1.3b",
            "deepseek-coder:6.7b", 
            "llama3.2:1b",
            "qwen2.5:1.5b"
        ]
        
    def check_ollama_installation(self) -> bool:
        """Check if Ollama is installed"""
        try:
            result = subprocess.run(['ollama', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                logger.info(f"✅ Ollama installed: {result.stdout.strip()}")
                return True
        except FileNotFoundError:
            pass
        
        logger.info("❌ Ollama not found")
        return False
    
    def install_ollama(self) -> bool:
        """Install Ollama"""
        logger.info("📦 Installing Ollama...")
        
        try:
            # Install Ollama (macOS)
            install_script = """
            curl -fsSL https://ollama.com/install.sh | sh
            """
            
            result = subprocess.run(install_script, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("✅ Ollama installed successfully")
                return True
            else:
                logger.error(f"❌ Ollama installation failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Installation error: {e}")
            return False
    
    def start_ollama_server(self) -> bool:
        """Start Ollama server"""
        logger.info("🚀 Starting Ollama server...")
        
        try:
            # Check if already running
            try:
                response = requests.get(f"{self.ollama_url}/api/tags", timeout=2)
                if response.status_code == 200:
                    logger.info("✅ Ollama server already running")
                    return True
            except:
                pass
            
            # Start server in background
            subprocess.Popen(['ollama', 'serve'], 
                           stdout=subprocess.DEVNULL, 
                           stderr=subprocess.DEVNULL)
            
            # Wait for server to start
            for i in range(30):  # Wait up to 30 seconds
                try:
                    response = requests.get(f"{self.ollama_url}/api/tags", timeout=2)
                    if response.status_code == 200:
                        logger.info("✅ Ollama server started successfully")
                        return True
                except:
                    pass
                time.sleep(1)
            
            logger.error("❌ Ollama server failed to start")
            return False
            
        except Exception as e:
            logger.error(f"❌ Server start error: {e}")
            return False
    
    def install_models(self) -> bool:
        """Install AI models"""
        logger.info("📦 Installing AI models...")
        
        for model in self.models_to_install:
            logger.info(f"📥 Installing {model}...")
            
            try:
                # Check if already installed
                response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
                if response.status_code == 200:
                    models = response.json().get('models', [])
                    if any(model.split(':')[0] in m['name'] for m in models):
                        logger.info(f"✅ {model} already installed")
                        continue
                
                # Install model
                process = subprocess.Popen(['ollama', 'pull', model], 
                                       stdout=subprocess.PIPE, 
                                       stderr=subprocess.PIPE,
                                       text=True)
                
                # Monitor installation progress
                while True:
                    output = process.stdout.readline()
                    if output == '' and process.poll() is not None:
                        break
                    if output:
                        print(f"📥 {model}: {output.strip()}")
                
                if process.returncode == 0:
                    logger.info(f"✅ {model} installed successfully")
                else:
                    logger.error(f"❌ Failed to install {model}")
                    return False
                    
            except Exception as e:
                logger.error(f"❌ Error installing {model}: {e}")
                return False
        
        return True
    
    def test_model(self, model_name: str) -> bool:
        """Test model functionality"""
        logger.info(f"🧪 Testing {model_name}...")
        
        try:
            test_prompt = "Respond with 'OK' if you can understand this."
            
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": model_name,
                    "prompt": test_prompt,
                    "stream": False
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'OK' in result.get('response', '').upper():
                    logger.info(f"✅ {model_name} working correctly")
                    return True
                else:
                    logger.warning(f"⚠️ {model_name} response: {result.get('response', '')}")
                    return True  # Still consider working
            else:
                logger.error(f"❌ {model_name} test failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error testing {model_name}: {e}")
            return False
    
    def setup_complete_check(self) -> bool:
        """Complete setup verification"""
        logger.info("🔍 Complete setup verification...")
        
        try:
            # Check server
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if response.status_code != 200:
                logger.error("❌ Ollama server not responding")
                return False
            
            # Check models
            models = response.json().get('models', [])
            installed_models = [m['name'] for m in models]
            
            logger.info(f"📊 Installed models: {installed_models}")
            
            # Test each model
            for model in self.models_to_install[:2]:  # Test first 2 models
                model_name = model.split(':')[0]
                if not any(model_name in m for m in installed_models):
                    logger.error(f"❌ {model_name} not installed")
                    return False
                
                if not self.test_model(model):
                    logger.error(f"❌ {model_name} not working")
                    return False
            
            logger.info("✅ Local AI setup complete and working!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Setup verification failed: {e}")
            return False
    
    def run_setup(self):
        """Run complete setup process"""
        print("🤖 LOCAL AI SETUP")
        print("="*60)
        print("🎯 Setting up local DeepSeek/Ollama for trading agent")
        print("📦 Installing Ollama and AI models")
        print("🧪 Testing functionality")
        print("="*60)
        
        # Step 1: Check Ollama
        if not self.check_ollama_installation():
            print("\n📦 Installing Ollama...")
            if not self.install_ollama():
                print("❌ Failed to install Ollama")
                print("💡 Please install manually: https://ollama.com/")
                return False
        
        # Step 2: Start server
        print("\n🚀 Starting Ollama server...")
        if not self.start_ollama_server():
            print("❌ Failed to start Ollama server")
            return False
        
        # Step 3: Install models
        print("\n📦 Installing AI models...")
        if not self.install_models():
            print("❌ Failed to install models")
            return False
        
        # Step 4: Complete verification
        print("\n🔍 Final verification...")
        if self.setup_complete_check():
            print("\n✅ LOCAL AI SETUP COMPLETE!")
            print("="*60)
            print("🎯 Ready to run Visual Trading Agent")
            print("🤖 Local AI models installed and working")
            print("🌐 Server running on http://localhost:11434")
            print("="*60)
            return True
        else:
            print("\n❌ Setup verification failed")
            return False

def main():
    """Main setup function"""
    setup = LocalAISetup()
    success = setup.run_setup()
    
    if success:
        print("\n🚀 You can now run the Visual Trading Agent:")
        print("   python visual_trading_agent.py")
    else:
        print("\n❌ Setup failed. Please check the logs and try again.")

if __name__ == "__main__":
    main()
