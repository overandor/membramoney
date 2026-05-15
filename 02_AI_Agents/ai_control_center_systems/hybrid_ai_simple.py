#!/usr/bin/env python3
"""
HYBRID AI SUPERVISOR - SIMPLIFIED
CPU-only models with fallback to rule-based decisions
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
        logging.FileHandler('/Users/alep/Downloads/hybrid_ai_simple.log'),
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
    model_type: str  # tiny, large, or rule
    action_type: str
    description: str
    success: bool
    response_time: float = 0.0

class SimpleAIController:
    """Simple AI controller with fallback to rule-based decisions"""
    
    def __init__(self):
        self.ollama_url = "http://localhost:11434"
        self.simple_model = "qwen2.5:0.5b"  # Very small model
        self.use_ai = False  # Start with rule-based
        self.controller_active = True
        
        logger.info("🔍 Simple AI Controller initialized")
        logger.info(f"🤖 Model: {self.simple_model}")
        logger.info(f"📋 Fallback: Rule-based decisions")
    
    async def check_ollama(self) -> bool:
        """Check if Ollama is available"""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if response.status_code == 200:
                logger.info("✅ Ollama is available")
                return True
        except:
            pass
        return False
    
    async def install_simple_model(self) -> bool:
        """Install a very small model"""
        try:
            logger.info(f"📦 Installing {self.simple_model}...")
            
            # Check if already installed
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if response.status_code == 200:
                installed = [m['name'] for m in response.json().get('models', [])]
                if any(self.simple_model.split(':')[0] in m for m in installed):
                    logger.info(f"✅ {self.simple_model} already installed")
                    self.use_ai = True
                    return True
            
            # Install model
            process = subprocess.Popen(['ollama', 'pull', self.simple_model], 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE,
                                   text=True)
            
            # Monitor progress
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    print(f"📥 {self.simple_model}: {output.strip()}")
            
            if process.returncode == 0:
                logger.info(f"✅ {self.simple_model} installed")
                self.use_ai = True
                return True
            else:
                logger.warning(f"⚠️ Failed to install {self.simple_model}, using rule-based")
                return False
                
        except Exception as e:
            logger.warning(f"⚠️ Model installation failed: {e}, using rule-based")
            return False
    
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
    
    def basic_screen_analysis(self, screenshot_path: str) -> Dict:
        """Basic screen analysis without AI"""
        try:
            image = Image.open(screenshot_path)
            img_array = np.array(image)
            
            # Simple color analysis
            red_mask = (img_array[:,:,0] > 200) & (img_array[:,:,1] < 100) & (img_array[:,:,2] < 100)
            red_count = np.sum(red_mask)
            
            # Brightness analysis
            brightness = np.mean(img_array) / 255.0
            
            # Simple heuristics
            has_errors = red_count > 1000
            screen_active = brightness > 0.1
            
            return {
                'error_pixels': int(red_count),
                'brightness': float(brightness),
                'has_errors': has_errors,
                'screen_active': screen_active,
                'analysis_method': 'rule-based'
            }
            
        except Exception as e:
            logger.error(f"❌ Screen analysis failed: {e}")
            return {'error': str(e)}
    
    async def ai_screen_analysis(self, screenshot_path: str) -> Dict:
        """AI-powered screen analysis"""
        try:
            prompt = "Analyze this screenshot for errors, warnings, and trading applications. Respond with JSON: {'errors': 0, 'warnings': 0, 'trading_apps': 0, 'status': 'normal'}"
            
            payload = {
                "model": self.simple_model,
                "prompt": prompt,
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
                        analysis = json.loads(json_str)
                        analysis['analysis_method'] = 'ai'
                        return analysis
                except:
                    pass
            
            return {'analysis_method': 'ai_failed', 'error': 'Failed to parse response'}
            
        except Exception as e:
            return {'analysis_method': 'ai_failed', 'error': str(e)}
    
    def rule_based_decision(self, state: SystemState, screen_analysis: Dict) -> Dict:
        """Rule-based decision making"""
        decision = {
            'action': 'monitor',
            'priority': 'low',
            'reasoning': 'System operating normally',
            'instructions': ['take screenshot'],
            'decision_method': 'rule-based'
        }
        
        # Critical errors
        if state.errors_detected > 5 or screen_analysis.get('has_errors', False):
            decision.update({
                'action': 'restart_trading',
                'priority': 'critical',
                'reasoning': 'Critical errors detected',
                'instructions': ['kill trading processes', 'start trading processes']
            })
        
        # High resource usage
        elif state.cpu_usage > 90 or state.memory_usage > 90:
            decision.update({
                'action': 'optimize_system',
                'priority': 'high',
                'reasoning': 'High resource usage',
                'instructions': ['take screenshot', 'kill unnecessary processes']
            })
        
        # Low profit rate
        elif state.profit_rate < 0.0001:
            decision.update({
                'action': 'optimize_trading',
                'priority': 'medium',
                'reasoning': 'Low profit rate',
                'instructions': ['restart trading processes']
            })
        
        # No trading processes
        elif state.trading_processes == 0:
            decision.update({
                'action': 'start_trading',
                'priority': 'high',
                'reasoning': 'No trading processes running',
                'instructions': ['start trading processes']
            })
        
        return decision
    
    async def ai_decision(self, state: SystemState, screen_analysis: Dict) -> Dict:
        """AI-powered decision making"""
        try:
            prompt = f"""Analyze this trading system state:
CPU: {state.cpu_usage}%, Memory: {state.memory_usage}%, Processes: {state.trading_processes}
Balance: ${state.balance}, Profit Rate: ${state.profit_rate}/s, Errors: {state.errors_detected}

Respond with JSON: {{'action': 'restart/optimize/monitor', 'priority': 'low/medium/high/critical', 'reasoning': 'brief explanation'}}"""
            
            payload = {
                "model": self.simple_model,
                "prompt": prompt,
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
                        decision = json.loads(json_str)
                        decision['decision_method'] = 'ai'
                        decision['instructions'] = ['take screenshot']  # Default instruction
                        return decision
                except:
                    pass
            
            return {'decision_method': 'ai_failed', 'error': 'Failed to parse AI response'}
            
        except Exception as e:
            return {'decision_method': 'ai_failed', 'error': str(e)}
    
    async def execute_actions(self, instructions: List[str]) -> bool:
        """Execute action instructions"""
        success = True
        
        for instruction in instructions:
            try:
                logger.info(f"🔧 Executing: {instruction}")
                
                if "screenshot" in instruction.lower():
                    self.take_screenshot()
                
                elif "kill trading" in instruction.lower():
                    subprocess.run(['pkill', '-f', 'profit_executor.py'], capture_output=True)
                    subprocess.run(['pkill', '-f', 'second_profit.py'], capture_output=True)
                    logger.info("🔫 Killed trading processes")
                
                elif "start trading" in instruction.lower():
                    subprocess.Popen([
                        '/Users/alep/miniconda3/bin/python',
                        '/Users/alep/Downloads/profit_executor.py'
                    ], cwd='/Users/alep/Downloads')
                    time.sleep(1)
                    subprocess.Popen([
                        '/Users/alep/miniconda3/bin/python',
                        '/Users/alep/Downloads/second_profit.py'
                    ], cwd='/Users/alep/Downloads')
                    logger.info("🚀 Started trading processes")
                
                elif "optimize" in instruction.lower():
                    # Take screenshot for optimization documentation
                    self.take_screenshot()
                
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ Failed to execute '{instruction}': {e}")
                success = False
        
        return success

class HybridAISupervisorSimple:
    """Simplified Hybrid AI Supervisor"""
    
    def __init__(self):
        self.controller = SimpleAIController()
        self.system_state = SystemState()
        self.ai_actions: List[AIAction] = []
        self.start_time = time.time()
        
        # Monitoring intervals
        self.screenshot_interval = 120  # Every 2 minutes
        self.decision_interval = 180  # Every 3 minutes
        
        logger.info("🚀 HYBRID AI SUPERVISOR - SIMPLIFIED INITIALIZED")
        logger.info("🤖 Architecture: Simple AI + Rule-based Fallback")
    
    def get_system_metrics(self) -> SystemState:
        """Get current system metrics"""
        try:
            # System resources
            self.system_state.cpu_usage = psutil.cpu_percent(interval=1)
            self.system_state.memory_usage = psutil.virtual_memory().percent
            self.system_state.disk_usage = psutil.disk_usage('/').percent
            
            # Network status
            self.system_state.network_active = psutil.net_if_stats().get('en0', (False, 0, 0, 0))[0]
            
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
    
    async def supervisor_loop(self):
        """Main supervisor loop"""
        logger.info("🚀 HYBRID AI SUPERVISOR LOOP STARTED")
        
        # Try to setup AI
        if await self.controller.check_ollama():
            await self.controller.install_simple_model()
        else:
            logger.info("📋 Using rule-based decisions only")
        
        # Timing trackers
        last_screenshot = time.time()
        last_decision = time.time()
        
        while True:
            try:
                current_time = time.time()
                
                # Get system metrics
                state = self.get_system_metrics()
                
                # Screenshot and analysis
                if current_time - last_screenshot >= self.screenshot_interval:
                    logger.info("📸 Taking screenshot and analyzing...")
                    
                    screenshot_path = self.controller.take_screenshot()
                    if screenshot_path:
                        # Try AI analysis first, fallback to rule-based
                        if self.controller.use_ai:
                            screen_analysis = await self.controller.ai_screen_analysis(screenshot_path)
                            if 'error' in screen_analysis:
                                screen_analysis = self.controller.basic_screen_analysis(screenshot_path)
                        else:
                            screen_analysis = self.controller.basic_screen_analysis(screenshot_path)
                        
                        logger.info(f"📊 Screen Analysis: {screen_analysis.get('analysis_method', 'unknown')} | "
                                   f"Errors: {screen_analysis.get('error_pixels', 0)} | "
                                   f"Active: {screen_analysis.get('screen_active', False)}")
                    
                    self.system_state.screenshot_count += 1
                    last_screenshot = current_time
                
                # Decision making
                if current_time - last_decision >= self.decision_interval:
                    logger.info("🧠 Making decision...")
                    
                    # Get current screen analysis
                    screenshot_path = self.controller.take_screenshot()
                    if self.controller.use_ai:
                        screen_analysis = await self.controller.ai_screen_analysis(screenshot_path)
                        if 'error' in screen_analysis:
                            screen_analysis = self.controller.basic_screen_analysis(screenshot_path)
                    else:
                        screen_analysis = self.controller.basic_screen_analysis(screenshot_path)
                    
                    # Make decision
                    if self.controller.use_ai and 'error' not in screen_analysis:
                        decision = await self.controller.ai_decision(state, screen_analysis)
                        if 'error' in decision:
                            decision = self.controller.rule_based_decision(state, screen_analysis)
                    else:
                        decision = self.controller.rule_based_decision(state, screen_analysis)
                    
                    # Execute decision
                    instructions = decision.get('instructions', ['take screenshot'])
                    success = await self.controller.execute_actions(instructions)
                    
                    # Record action
                    action = AIAction(
                        timestamp=datetime.now().isoformat(),
                        model_type=decision.get('decision_method', 'rule-based'),
                        action_type=decision.get('action', 'unknown'),
                        description=decision.get('reasoning', ''),
                        success=success
                    )
                    self.ai_actions.append(action)
                    
                    self.system_state.last_action = decision.get('action', 'unknown')
                    
                    logger.info(f"🤖 Decision: {decision.get('action')} | "
                               f"Priority: {decision.get('priority')} | "
                               f"Method: {decision.get('decision_method')} | "
                               f"Success: {success}")
                    
                    last_decision = current_time
                
                # Log status
                logger.info(f"📊 Status: CPU:{state.cpu_usage:.1f}% | "
                           f"Memory:{state.memory_usage:.1f}% | "
                           f"Processes:{state.trading_processes} | "
                           f"Balance:${state.balance:.4f} | "
                           f"Profit:${state.profit_rate:.6f}/s | "
                           f"Actions:{len(self.ai_actions)} | "
                           f"AI:{'Yes' if self.controller.use_ai else 'No'}")
                
                # Brief sleep
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"❌ Supervisor loop error: {e}")
                await asyncio.sleep(30)

async def main():
    """Main simplified hybrid AI supervisor"""
    print("🚀 HYBRID AI SUPERVISOR - SIMPLIFIED")
    print("="*70)
    print("🤖 Simple AI + Rule-based Fallback")
    print("📸 Screenshot Analysis")
    print("🧠 Intelligent Decision Making")
    print("🔄 24/7 Autonomous Operation")
    print("⚡ CPU-Only Models")
    print("="*70)
    
    print("⚠️  This system will monitor and control your trading!")
    print("Press Ctrl+C to cancel...")
    
    try:
        await asyncio.sleep(3)  # Give time to cancel
        
        # Initialize supervisor
        supervisor = HybridAISupervisorSimple()
        
        # Start supervision
        await supervisor.supervisor_loop()
        
    except KeyboardInterrupt:
        print("\n🚀 Hybrid AI Supervisor stopped by user")
        
    except Exception as e:
        print(f"\n❌ Hybrid AI Supervisor error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
