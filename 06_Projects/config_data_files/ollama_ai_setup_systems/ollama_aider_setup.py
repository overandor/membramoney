#!/usr/bin/env python3
"""
OLLAMA + AIDER SETUP
Complete setup for local AI decision making and development
"""

import subprocess
import requests
import time
import logging
import os
import json
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OllamaAiderSetup:
    """Setup Ollama + AIDER for local AI development"""
    
    def __init__(self):
        self.ollama_url = "http://localhost:11434"
        self.models = [
            "deepseek-coder:1.3b",
            "deepseek-coder:6.7b",
            "codellama:7b",
            "qwen2.5-coder:1.5b"
        ]
        self.aider_config = {
            "model": "deepseek-coder",
            "editor": "vim",
            "yes": True,
            "stream": False
        }
    
    def check_ollama(self) -> bool:
        """Check if Ollama is running"""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def install_ollama(self) -> bool:
        """Install Ollama"""
        logger.info("📦 Installing Ollama...")
        
        try:
            # Install Ollama
            install_cmd = """
            curl -fsSL https://ollama.com/install.sh | sh
            """
            
            result = subprocess.run(install_cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("✅ Ollama installed successfully")
                return True
            else:
                logger.error(f"❌ Ollama installation failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Installation error: {e}")
            return False
    
    def start_ollama(self) -> bool:
        """Start Ollama server"""
        logger.info("🚀 Starting Ollama server...")
        
        try:
            # Check if already running
            if self.check_ollama():
                logger.info("✅ Ollama already running")
                return True
            
            # Start Ollama
            subprocess.Popen(['ollama', 'serve'], 
                           stdout=subprocess.DEVNULL, 
                           stderr=subprocess.DEVNULL)
            
            # Wait for server to start
            for i in range(30):
                if self.check_ollama():
                    logger.info("✅ Ollama server started")
                    return True
                time.sleep(1)
            
            logger.error("❌ Ollama server failed to start")
            return False
            
        except Exception as e:
            logger.error(f"❌ Start error: {e}")
            return False
    
    def install_models(self) -> bool:
        """Install AI models"""
        logger.info("📦 Installing AI models...")
        
        for model in self.models:
            logger.info(f"📥 Installing {model}...")
            
            try:
                # Check if already installed
                response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
                if response.status_code == 200:
                    installed = [m['name'] for m in response.json().get('models', [])]
                    if any(model.split(':')[0] in m for m in installed):
                        logger.info(f"✅ {model} already installed")
                        continue
                
                # Install model
                process = subprocess.Popen(['ollama', 'pull', model], 
                                       stdout=subprocess.PIPE, 
                                       stderr=subprocess.PIPE,
                                       text=True)
                
                # Monitor progress
                while True:
                    output = process.stdout.readline()
                    if output == '' and process.poll() is not None:
                        break
                    if output:
                        print(f"📥 {model}: {output.strip()}")
                
                if process.returncode == 0:
                    logger.info(f"✅ {model} installed")
                else:
                    logger.error(f"❌ Failed to install {model}")
                    return False
                    
            except Exception as e:
                logger.error(f"❌ Error installing {model}: {e}")
                return False
        
        return True
    
    def install_aider(self) -> bool:
        """Install AIDER"""
        logger.info("📦 Installing AIDER...")
        
        try:
            # Try installing with pip
            result = subprocess.run([
                '/Users/alep/miniconda3/bin/pip', 'install', 'aider-chat'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("✅ AIDER installed successfully")
                return True
            
            # If pip fails, try with conda
            result = subprocess.run([
                '/Users/alep/miniconda3/bin/conda', 'install', '-c', 'conda-forge', 'aider-chat', '-y'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("✅ AIDER installed via conda")
                return True
            
            logger.error(f"❌ AIDER installation failed: {result.stderr}")
            return False
            
        except Exception as e:
            logger.error(f"❌ AIDER installation error: {e}")
            return False
    
    def test_ollama_model(self, model: str) -> bool:
        """Test Ollama model"""
        logger.info(f"🧪 Testing {model}...")
        
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": model,
                    "prompt": "Write a simple Python function to calculate profit.",
                    "stream": False
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('response'):
                    logger.info(f"✅ {model} working correctly")
                    return True
            
            logger.error(f"❌ {model} test failed")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error testing {model}: {e}")
            return False
    
    def setup_aider_config(self) -> bool:
        """Setup AIDER configuration"""
        logger.info("⚙️ Setting up AIDER configuration...")
        
        config_dir = Path.home() / '.config' / 'aider'
        config_dir.mkdir(parents=True, exist_ok=True)
        
        config_file = config_dir / 'config.yml'
        
        config_content = f"""
# AIDER Configuration for Trading System
model: {self.aider_config['model']}
editor: {self.aider_config['editor']}
yes: {self.aider_config['yes']}
stream: {self.aider_config['stream']}

# Trading-specific settings
auto-commits: false
dark-mode: false
gitignore: true
lint-cmd: "flake8 --max-line-length=120"
test-cmd: "python -m pytest"

# Security settings
safe-mode: true
"""
        
        try:
            with open(config_file, 'w') as f:
                f.write(config_content)
            
            logger.info(f"✅ AIDER config saved to {config_file}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Config setup failed: {e}")
            return False
    
    def test_aider_integration(self) -> bool:
        """Test AIDER with Ollama"""
        logger.info("🧪 Testing AIDER + Ollama integration...")
        
        try:
            # Create test file
            test_file = '/Users/alep/Downloads/test_aider.py'
            with open(test_file, 'w') as f:
                f.write("""
# Test file for AIDER optimization
def simple_function():
    return "hello"
""")
            
            # Test AIDER command
            cmd = [
                '/Users/alep/miniconda3/bin/aider',
                '--model', 'deepseek-coder',
                '--message', 'Optimize this function for better performance',
                '--yes',
                test_file
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            # Cleanup
            if os.path.exists(test_file):
                os.remove(test_file)
            
            if result.returncode == 0:
                logger.info("✅ AIDER + Ollama integration working")
                return True
            else:
                logger.error(f"❌ AIDER test failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Integration test error: {e}")
            return False
    
    def create_trading_dev_script(self) -> bool:
        """Create trading development script"""
        logger.info("📝 Creating trading development script...")
        
        script_content = """#!/usr/bin/env python3
\"""
TRADING DEVELOPMENT AUTOMATOR
Uses Ollama + AIDER for continuous trading system improvement
\"""

import subprocess
import time
import logging
import requests
from datetime import datetime
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TradingDevAutomator:
    def __init__(self):
        self.ollama_url = "http://localhost:11434"
        self.trading_files = [
            'profit_executor.py',
            'second_profit.py', 
            'simple_market_maker.py',
            'ena_hedging_bot.py'
        ]
    
    async def analyze_with_ollama(self, code_content: str, file_name: str) -> str:
        \"\"\"Analyze code with Ollama\"\"\"
        prompt = f\"\"\"
        Analyze this trading code for optimization opportunities:
        
        File: {file_name}
        
        Code:
        {code_content}
        
        Provide specific suggestions to:
        1. Increase profit generation
        2. Reduce errors
        3. Improve execution speed
        4. Enhance decision making
        
        Respond with actionable optimization steps only.
        \"\"\"
        
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": "deepseek-coder",
                    "prompt": prompt,
                    "stream": False
                },
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json().get('response', '')
        except Exception as e:
            logger.error(f"Ollama analysis failed: {e}")
        
        return ""
    
    async def optimize_with_aider(self, file_path: str, optimization: str) -> bool:
        \"\"\"Optimize file with AIDER\"\"\"
        try:
            cmd = [
                'aider',
                '--model', 'deepseek-coder',
                '--message', optimization,
                '--yes',
                file_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"AIDER optimization failed: {e}")
            return False
    
    async def continuous_optimization_loop(self):
        \"\"\"Main optimization loop\"\"\"
        logger.info("🚀 Starting continuous optimization loop")
        
        while True:
            try:
                for file_name in self.trading_files:
                    file_path = f"/Users/alep/Downloads/{file_name}"
                    
                    if not os.path.exists(file_path):
                        continue
                    
                    # Read current code
                    with open(file_path, 'r') as f:
                        code_content = f.read()
                    
                    # Analyze with Ollama
                    logger.info(f"🔍 Analyzing {file_name}...")
                    optimization = await self.analyze_with_ollama(code_content, file_name)
                    
                    if optimization:
                        # Optimize with AIDER
                        logger.info(f"🔧 Optimizing {file_name}...")
                        success = await self.optimize_with_aider(file_path, optimization)
                        
                        if success:
                            logger.info(f"✅ Optimized {file_name}")
                        else:
                            logger.error(f"❌ Failed to optimize {file_name}")
                
                # Wait before next cycle
                await asyncio.sleep(300)  # 5 minutes
                
            except Exception as e:
                logger.error(f"Optimization loop error: {e}")
                await asyncio.sleep(60)
    
    async def start(self):
        \"\"\"Start the automation\"\"\"
        await self.continuous_optimization_loop()

if __name__ == "__main__":
    automator = TradingDevAutomator()
    asyncio.run(automator.start())
"""
        
        try:
            with open('/Users/alep/Downloads/trading_dev_automator.py', 'w') as f:
                f.write(script_content)
            
            logger.info("✅ Trading development script created")
            return True
            
        except Exception as e:
            logger.error(f"❌ Script creation failed: {e}")
            return False
    
    def run_complete_setup(self):
        """Run complete setup"""
        print("🤖 OLLAMA + AIDER COMPLETE SETUP")
        print("="*60)
        print("🎯 Setting up local AI for trading development")
        print("📦 Installing Ollama and models")
        print("🔧 Configuring AIDER")
        print("🧪 Testing integration")
        print("="*60)
        
        # Step 1: Install and start Ollama
        if not self.check_ollama():
            if not self.install_ollama():
                logger.error("❌ Failed to install Ollama")
                return False
        
        if not self.start_ollama():
            logger.error("❌ Failed to start Ollama")
            return False
        
        # Step 2: Install models
        if not self.install_models():
            logger.error("❌ Failed to install models")
            return False
        
        # Step 3: Install AIDER
        if not self.install_aider():
            logger.error("❌ Failed to install AIDER")
            return False
        
        # Step 4: Setup configuration
        if not self.setup_aider_config():
            logger.error("❌ Failed to setup AIDER config")
            return False
        
        # Step 5: Test integration
        if not self.test_aider_integration():
            logger.error("❌ AIDER + Ollama integration failed")
            return False
        
        # Step 6: Create automation script
        if not self.create_trading_dev_script():
            logger.error("❌ Failed to create automation script")
            return False
        
        # Step 7: Test models
        logger.info("🧪 Testing installed models...")
        for model in self.models[:2]:  # Test first 2 models
            self.test_ollama_model(model)
        
        print("\n✅ COMPLETE SETUP SUCCESSFUL!")
        print("="*60)
        print("🎯 Ready for 24/7 AI development")
        print("🤖 Ollama running on http://localhost:11434")
        print("🔧 AIDER configured and ready")
        print("📝 Automation script created: trading_dev_automator.py")
        print("\n🚀 Start automation with:")
        print("   python trading_dev_automator.py")
        print("="*60)
        
        return True

def main():
    """Main setup function"""
    setup = OllamaAiderSetup()
    success = setup.run_complete_setup()
    
    if not success:
        print("\n❌ Setup failed. Please check the logs.")
        print("💡 Manual setup steps:")
        print("   1. Install Ollama: https://ollama.com/")
        print("   2. Start Ollama: ollama serve")
        print("   3. Install models: ollama pull deepseek-coder")
        print("   4. Install AIDER: pip install aider-chat")

if __name__ == "__main__":
    main()
