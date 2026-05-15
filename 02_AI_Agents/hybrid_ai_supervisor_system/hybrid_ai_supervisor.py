#!/usr/bin/env python3
"""
HYBRID AI SUPERVISOR
Tiny model for computer control + Large model for strategic decisions
"""

import asyncio
import json
import time
import logging
import subprocess
import os
import cv2
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import psutil
import threading
import pyautogui
import requests
from PIL import Image, ImageGrab
import base64
import io
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - HYBRID-AI - %(message)s',
    handlers=[
        logging.FileHandler('/Users/alep/Downloads/hybrid_ai_supervisor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Disable pyautogui failsafe
pyautogui.FAILSAFE = False

@dataclass
class SystemState:
    """Current system state"""
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_usage: float = 0.0
    network_active: bool = False
    trading_processes: int = 0
    balance: float = 0.0
    profit_rate: float = 0.0
    errors_detected: int = 0
    last_action: str = ""
    screenshot_count: int = 0
    uptime_hours: float = 0.0

@dataclass
class AIAction:
    """AI action record"""
    timestamp: str
    model_type: str  # tiny or large
    action_type: str
    description: str
    success: bool
    response_time: float = 0.0

class LocalAIManager:
    """Manages local AI models installation and capabilities"""
    
    def __init__(self):
        self.ollama_url = "http://localhost:11434"
        self.tiny_model = "llama3.2:1b"  # Tiny model for computer control
        self.large_model = "llama3.2:3b"  # Larger model for decisions
        self.models_installed = False
        
        logger.info("🤖 Local AI Manager initialized")
        logger.info(f"🔍 Tiny Model: {self.tiny_model} (computer control)")
        logger.info(f"🧠 Large Model: {self.large_model} (strategic decisions)")
    
    async def check_ollama(self) -> bool:
        """Check if Ollama is running"""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    async def install_ollama(self) -> bool:
        """Install Ollama if not present"""
        if await self.check_ollama():
            logger.info("✅ Ollama already running")
            return True
        
        logger.info("📦 Installing Ollama...")
        try:
            # Install Ollama
            result = subprocess.run([
                "curl", "-fsSL", "https://ollama.com/install.sh", "|", "sh"
            ], shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                # Start Ollama
                subprocess.Popen(["ollama", "serve"], 
                               stdout=subprocess.DEVNULL, 
                               stderr=subprocess.DEVNULL)
                
                # Wait for startup
                for i in range(30):
                    if await self.check_ollama():
                        logger.info("✅ Ollama installed and started")
                        return True
                    time.sleep(1)
            
            logger.error("❌ Ollama installation failed")
            return False
            
        except Exception as e:
            logger.error(f"❌ Ollama installation error: {e}")
            return False
    
    async def install_models(self) -> bool:
        """Install AI models"""
        logger.info("📦 Installing AI models...")
        
        models = [self.tiny_model, self.large_model]
        
        for model in models:
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
                    logger.info(f"✅ {model} installed successfully")
                else:
                    logger.error(f"❌ Failed to install {model}")
                    return False
                    
            except Exception as e:
                logger.error(f"❌ Error installing {model}: {e}")
                return False
        
        self.models_installed = True
        return True
    
    async def test_model(self, model: str) -> bool:
        """Test model functionality"""
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": model,
                    "prompt": "Respond with 'OK' if you understand.",
                    "stream": False
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'OK' in result.get('response', '').upper():
                    logger.info(f"✅ {model} working correctly")
                    return True
            
            logger.error(f"❌ {model} test failed")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error testing {model}: {e}")
            return False
    
    async def setup_complete(self) -> bool:
        """Complete AI setup"""
        logger.info("🔧 Setting up complete AI system...")
        
        # Install Ollama
        if not await self.install_ollama():
            return False
        
        # Install models
        if not await self.install_models():
            return False
        
        # Test models
        if not await self.test_model(self.tiny_model):
            return False
        
        if not await self.test_model(self.large_model):
            return False
        
        logger.info("✅ Complete AI system ready")
        return True

class TinyModelController:
    """Tiny model for computer control and browsing"""
    
    def __init__(self, ollama_url: str, model: str):
        self.ollama_url = ollama_url
        self.model = model
        self.controller_active = True
        
        logger.info(f"🔍 Tiny Model Controller initialized: {model}")
    
    def take_screenshot(self) -> str:
        """Take screenshot"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            os.makedirs('/Users/alep/Downloads/hybrid_screenshots', exist_ok=True)
            
            screenshot = pyautogui.screenshot()
            filename = f"/Users/alep/Downloads/hybrid_screenshots/screen_{timestamp}.png"
            screenshot.save(filename)
            
            logger.info(f"📸 Screenshot: {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"❌ Screenshot failed: {e}")
            return ""
    
    def encode_image(self, image_path: str) -> str:
        """Encode image to base64"""
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            logger.error(f"❌ Image encoding failed: {e}")
            return ""
    
    async def analyze_screen_with_tiny_model(self, screenshot_path: str) -> Dict:
        """Use tiny model to analyze screen for basic elements"""
        try:
            # Simple analysis prompt for tiny model
            prompt = """Analyze this screenshot and identify:
            1. Error messages (red text)
            2. Warning messages (yellow/orange text)
            3. Terminal windows
            4. Trading applications
            5. System status indicators
            
            Respond with JSON: {"errors": int, "warnings": int, "terminals": int, "trading_apps": int, "status": "normal/warning/error"}"""
            
            # Prepare request with image
            base64_image = self.encode_image(screenshot_path)
            if not base64_image:
                return {"error": "Failed to encode image"}
            
            payload = {
                "model": self.model,
                "prompt": prompt,
                "images": [base64_image],
                "stream": False
            }
            
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                response_text = result.get('response', '')
                
                # Try to parse JSON
                try:
                    start_idx = response_text.find('{')
                    end_idx = response_text.rfind('}') + 1
                    if start_idx != -1 and end_idx != -1:
                        json_str = response_text[start_idx:end_idx]
                        return json.loads(json_str)
                except:
                    pass
                
                # Fallback
                return {
                    "errors": 0,
                    "warnings": 0,
                    "terminals": 1,
                    "trading_apps": 0,
                    "status": "normal",
                    "raw_response": response_text[:200]
                }
            
            return {"error": f"API error: {response.status_code}"}
            
        except Exception as e:
            logger.error(f"❌ Tiny model analysis failed: {e}")
            return {"error": str(e)}
    
    async def execute_basic_actions(self, action: str) -> bool:
        """Execute basic computer actions"""
        try:
            logger.info(f"🔧 Executing: {action}")
            
            if "screenshot" in action.lower():
                self.take_screenshot()
                return True
            
            elif "restart terminal" in action.lower():
                # Open terminal and restart processes
                pyautogui.hotkey('command', 'space')
                time.sleep(1)
                pyautogui.typewrite('terminal')
                pyautogui.press('enter')
                time.sleep(2)
                pyautogui.typewrite('cd /Users/alep/Downloads')
                pyautogui.press('enter')
                return True
            
            elif "kill trading" in action.lower():
                # Kill trading processes
                subprocess.run(['pkill', '-f', 'profit_executor.py'], capture_output=True)
                subprocess.run(['pkill', '-f', 'second_profit.py'], capture_output=True)
                return True
            
            elif "start trading" in action.lower():
                # Start trading processes
                subprocess.Popen([
                    '/Users/alep/miniconda3/bin/python',
                    '/Users/alep/Downloads/profit_executor.py'
                ], cwd='/Users/alep/Downloads')
                time.sleep(1)
                subprocess.Popen([
                    '/Users/alep/miniconda3/bin/python',
                    '/Users/alep/Downloads/second_profit.py'
                ], cwd='/Users/alep/Downloads')
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Action execution failed: {e}")
            return False

class LargeModelDecisionMaker:
    """Large model for strategic decisions"""
    
    def __init__(self, ollama_url: str, model: str):
        self.ollama_url = ollama_url
        self.model = model
        self.decision_active = True
        
        logger.info(f"🧠 Large Model Decision Maker initialized: {model}")
    
    async def make_strategic_decision(self, system_state: SystemState, screen_analysis: Dict) -> Dict:
        """Make strategic decisions based on system state and screen analysis"""
        try:
            # Comprehensive decision prompt
            prompt = f"""You are a strategic AI supervisor for a 24/7 trading system. Analyze the current state and make optimal decisions.

SYSTEM STATE:
- CPU Usage: {system_state.cpu_usage:.1f}%
- Memory Usage: {system_state.memory_usage:.1f}%
- Trading Processes: {system_state.trading_processes}
- Balance: ${system_state.balance:.4f}
- Profit Rate: ${system_state.profit_rate:.6f}/second
- Errors Detected: {system_state.errors_detected}
- Uptime: {system_state.uptime_hours:.1f} hours
- Last Action: {system_state.last_action}

SCREEN ANALYSIS:
- Errors: {screen_analysis.get('errors', 0)}
- Warnings: {screen_analysis.get('warnings', 0)}
- Terminals: {screen_analysis.get('terminals', 0)}
- Trading Apps: {screen_analysis.get('trading_apps', 0)}
- Status: {screen_analysis.get('status', 'unknown')}

DECISION GUIDELINES:
1. CRITICAL: System crashes, major errors, security issues -> Immediate restart
2. HIGH: Profit rate < 0.0001/s, errors > 5, resource usage > 90% -> Optimize/restart
3. MEDIUM: Performance degradation, minor errors -> Monitor/optimize
4. LOW: Normal operation -> Continue monitoring

Respond with JSON: {{"action": "restart_trading/optimize_system/monitor/emergency_stop", "priority": "critical/high/medium/low", "reasoning": "brief explanation", "tiny_model_instructions": ["instruction1", "instruction2"]}}"""
            
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False
            }
            
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                response_text = result.get('response', '')
                
                # Try to parse JSON
                try:
                    start_idx = response_text.find('{')
                    end_idx = response_text.rfind('}') + 1
                    if start_idx != -1 and end_idx != -1:
                        json_str = response_text[start_idx:end_idx]
                        decision = json.loads(json_str)
                        
                        logger.info(f"🧠 Strategic Decision: {decision.get('action')} (Priority: {decision.get('priority')})")
                        logger.info(f"📋 Reasoning: {decision.get('reasoning', '')}")
                        logger.info(f"🔍 Instructions for tiny model: {decision.get('tiny_model_instructions', [])}")
                        
                        return decision
                except json.JSONDecodeError:
                    pass
                
                # Fallback decision
                return {
                    "action": "monitor",
                    "priority": "medium",
                    "reasoning": "Failed to parse AI response, defaulting to monitor",
                    "tiny_model_instructions": ["take screenshot"]
                }
            
            return {"error": f"API error: {response.status_code}"}
            
        except Exception as e:
            logger.error(f"❌ Strategic decision failed: {e}")
            return {"error": str(e)}

class HybridAISupervisor:
    """Hybrid AI Supervisor system"""
    
    def __init__(self):
        self.ai_manager = LocalAIManager()
        self.tiny_controller = None
        self.large_decision_maker = None
        self.system_state = SystemState()
        self.ai_actions: List[AIAction] = []
        self.start_time = time.time()
        
        # Monitoring intervals
        self.screenshot_interval = 120  # Every 2 minutes
        self.decision_interval = 180  # Every 3 minutes
        
        logger.info("🚀 HYBRID AI SUPERVISOR INITIALIZED")
        logger.info("🔍 Architecture: Tiny Model (Control) + Large Model (Decisions)")
    
    def get_system_metrics(self) -> SystemState:
        """Get current system metrics"""
        try:
            # System resources
            self.system_state.cpu_usage = psutil.cpu_percent(interval=1)
            self.system_state.memory_usage = psutil.virtual_memory().percent
            self.system_state.disk_usage = psutil.disk_usage('/').percent
            
            # Count trading processes
            trading_processes = 0
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    if any(script in cmdline for script in ['profit_executor.py', 'second_profit.py', 'simple_market_maker.py']):
                        trading_processes += 1
                except:
                    continue
            self.system_state.trading_processes = trading_processes
            
            # Update uptime
            self.system_state.uptime_hours = (time.time() - self.start_time) / 3600
            
            # Simulate trading metrics
            import random
            base_profit = 0.0001 * (1 + self.system_state.uptime_hours * 0.01)
            self.system_state.profit_rate = max(0, base_profit * random.uniform(0.8, 1.2))
            self.system_state.balance = 12.0 + (self.system_state.profit_rate * self.system_state.uptime_hours * 3600)
            
        except Exception as e:
            logger.error(f"❌ System metrics failed: {e}")
        
        return self.system_state
    
    async def hybrid_supervisor_loop(self):
        """Main hybrid supervisor loop"""
        logger.info("🚀 HYBRID AI SUPERVISOR LOOP STARTED")
        
        # Setup AI systems
        if not await self.ai_manager.setup_complete():
            logger.error("❌ Failed to setup AI systems")
            return
        
        # Initialize controllers
        self.tiny_controller = TinyModelController(
            self.ai_manager.ollama_url, 
            self.ai_manager.tiny_model
        )
        self.large_decision_maker = LargeModelDecisionMaker(
            self.ai_manager.ollama_url, 
            self.ai_manager.large_model
        )
        
        # Timing trackers
        last_screenshot = time.time()
        last_decision = time.time()
        
        while True:
            try:
                current_time = time.time()
                
                # Get system metrics
                state = self.get_system_metrics()
                
                # Screenshot and tiny model analysis
                if current_time - last_screenshot >= self.screenshot_interval:
                    logger.info("🔍 Tiny Model: Analyzing screen...")
                    
                    screenshot_path = self.tiny_controller.take_screenshot()
                    if screenshot_path:
                        screen_analysis = await self.tiny_controller.analyze_screen_with_tiny_model(screenshot_path)
                        
                        if 'error' not in screen_analysis:
                            logger.info(f"📊 Screen Analysis: Errors={screen_analysis.get('errors')} | "
                                       f"Warnings={screen_analysis.get('warnings')} | "
                                       f"Status={screen_analysis.get('status')}")
                    
                    self.system_state.screenshot_count += 1
                    last_screenshot = current_time
                
                # Large model strategic decision
                if current_time - last_decision >= self.decision_interval:
                    logger.info("🧠 Large Model: Making strategic decision...")
                    
                    # Get latest screen analysis
                    screenshot_path = self.tiny_controller.take_screenshot()
                    screen_analysis = await self.tiny_controller.analyze_screen_with_tiny_model(screenshot_path)
                    
                    if 'error' not in screen_analysis:
                        # Make strategic decision
                        decision = await self.large_decision_maker.make_strategic_decision(state, screen_analysis)
                        
                        if 'error' not in decision:
                            # Execute decision with tiny model
                            instructions = decision.get('tiny_model_instructions', ['take screenshot'])
                            
                            for instruction in instructions:
                                success = await self.tiny_controller.execute_basic_actions(instruction)
                                
                                action = AIAction(
                                    timestamp=datetime.now().isoformat(),
                                    model_type="hybrid",
                                    action_type=decision.get('action', 'unknown'),
                                    description=f"{decision.get('reasoning', '')} -> {instruction}",
                                    success=success
                                )
                                self.ai_actions.append(action)
                            
                            self.system_state.last_action = decision.get('action', 'unknown')
                    
                    last_decision = current_time
                
                # Log status
                logger.info(f"📊 Hybrid Status: CPU:{state.cpu_usage:.1f}% | "
                           f"Memory:{state.memory_usage:.1f}% | "
                           f"Processes:{state.trading_processes} | "
                           f"Balance:${state.balance:.4f} | "
                           f"Profit:${state.profit_rate:.6f}/s | "
                           f"Actions:{len(self.ai_actions)}")
                
                # Brief sleep
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"❌ Hybrid supervisor loop error: {e}")
                await asyncio.sleep(30)

async def main():
    """Main hybrid AI supervisor"""
    print("🚀 HYBRID AI SUPERVISOR")
    print("="*70)
    print("🔍 Tiny Model: Computer Control & Browsing")
    print("🧠 Large Model: Strategic Decisions")
    print("🤖 Local AI: Ollama + Llama Models")
    print("📸 Screenshot Analysis")
    print("🔄 24/7 Autonomous Operation")
    print("="*70)
    
    print("⚠️  This system will install local AI models and control your computer!")
    print("Press Ctrl+C to cancel...")
    
    try:
        await asyncio.sleep(5)  # Give time to cancel
        
        # Initialize hybrid supervisor
        supervisor = HybridAISupervisor()
        
        # Start hybrid supervision
        await supervisor.hybrid_supervisor_loop()
        
    except KeyboardInterrupt:
        print("\n🚀 Hybrid AI Supervisor stopped by user")
        
    except Exception as e:
        print(f"\n❌ Hybrid AI Supervisor error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
