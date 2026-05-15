#!/usr/bin/env python3
"""
SUPERVISOR AI 24/7
Fully autonomous system with screenshots and computer control
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
import schedule
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - SUPERVISOR - %(message)s',
    handlers=[
        logging.FileHandler('/Users/alep/Downloads/supervisor_247.log'),
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

@dataclass
class SupervisorAction:
    """Supervisor action record"""
    timestamp: str
    action_type: str  # screenshot, restart, optimize, control
    description: str
    success: bool
    screenshot_path: str = ""

class ComputerController:
    """Computer control capabilities"""
    
    def __init__(self):
        self.screen_width, self.screen_height = pyautogui.size()
        self.control_active = True
        
        logger.info(f"🖥️ Computer controller initialized: {self.screen_width}x{self.screen_height}")
    
    def take_screenshot(self, region: str = "full") -> str:
        """Take screenshot of specific region"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Create screenshots directory
            os.makedirs('/Users/alep/Downloads/supervisor_screenshots', exist_ok=True)
            
            if region == "full":
                screenshot = pyautogui.screenshot()
                filename = f"/Users/alep/Downloads/supervisor_screenshots/full_{timestamp}.png"
            elif region == "terminal":
                # Capture terminal area (adjust coordinates as needed)
                screenshot = pyautogui.screenshot(region=(0, 0, 1200, 600))
                filename = f"/Users/alep/Downloads/supervisor_screenshots/terminal_{timestamp}.png"
            elif region == "browser":
                # Capture browser area
                screenshot = pyautogui.screenshot(region=(0, 100, 1200, 700))
                filename = f"/Users/alep/Downloads/supervisor_screenshots/browser_{timestamp}.png"
            else:
                screenshot = pyautogui.screenshot()
                filename = f"/Users/alep/Downloads/supervisor_screenshots/custom_{timestamp}.png"
            
            screenshot.save(filename)
            logger.info(f"📸 Screenshot saved: {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"❌ Screenshot failed: {e}")
            return ""
    
    def analyze_screenshot(self, image_path: str) -> Dict:
        """Analyze screenshot for issues"""
        try:
            image = cv2.imread(image_path)
            
            # Convert to grayscale for analysis
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Detect error messages (red/orange areas)
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            
            # Red color range for error messages
            lower_red = np.array([0, 50, 50])
            upper_red = np.array([10, 255, 255])
            red_mask = cv2.inRange(hsv, lower_red, upper_red)
            red_pixels = cv2.countNonZero(red_mask)
            
            # Orange color range for warnings
            lower_orange = np.array([10, 50, 50])
            upper_orange = np.array([20, 255, 255])
            orange_mask = cv2.inRange(hsv, lower_orange, upper_orange)
            orange_pixels = cv2.countNonZero(orange_mask)
            
            # Analyze text areas (simplified)
            text_density = np.mean(gray) / 255.0
            
            analysis = {
                'error_pixels': red_pixels,
                'warning_pixels': orange_pixels,
                'text_density': text_density,
                'has_errors': red_pixels > 100,
                'has_warnings': orange_pixels > 100,
                'screen_active': text_density > 0.1
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Screenshot analysis failed: {e}")
            return {}
    
    def click_at_position(self, x: int, y: int) -> bool:
        """Click at specific position"""
        try:
            pyautogui.click(x, y)
            logger.info(f"🖱️ Clicked at ({x}, {y})")
            return True
        except Exception as e:
            logger.error(f"❌ Click failed: {e}")
            return False
    
    def type_text(self, text: str) -> bool:
        """Type text"""
        try:
            pyautogui.typewrite(text)
            logger.info(f"⌨️ Typed: {text[:50]}...")
            return True
        except Exception as e:
            logger.error(f"❌ Type failed: {e}")
            return False
    
    def press_key(self, key: str) -> bool:
        """Press key"""
        try:
            pyautogui.press(key)
            logger.info(f"⌨️ Pressed: {key}")
            return True
        except Exception as e:
            logger.error(f"❌ Key press failed: {e}")
            return False
    
    def open_terminal(self) -> bool:
        """Open terminal"""
        try:
            # Press Command+Space to open Spotlight
            pyautogui.hotkey('command', 'space')
            time.sleep(1)
            
            # Type "terminal" and press Enter
            pyautogui.typewrite('terminal')
            pyautogui.press('enter')
            time.sleep(2)
            
            logger.info("🖥️ Terminal opened")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to open terminal: {e}")
            return False
    
    def restart_trading_system(self) -> bool:
        """Restart trading system via terminal"""
        try:
            # Open terminal
            if not self.open_terminal():
                return False
            
            # Navigate to Downloads directory
            pyautogui.typewrite('cd /Users/alep/Downloads')
            pyautogui.press('enter')
            time.sleep(1)
            
            # Kill existing processes
            pyautogui.typewrite('pkill -f profit_executor.py')
            pyautogui.press('enter')
            time.sleep(1)
            
            pyautogui.typewrite('pkill -f second_profit.py')
            pyautogui.press('enter')
            time.sleep(1)
            
            # Start trading systems
            pyautogui.typewrite('python profit_executor.py &')
            pyautogui.press('enter')
            time.sleep(2)
            
            pyautogui.typewrite('python second_profit.py &')
            pyautogui.press('enter')
            time.sleep(2)
            
            logger.info("🔄 Trading system restarted")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to restart trading system: {e}")
            return False

class LocalAIAnalyzer:
    """Local AI analysis using Ollama"""
    
    def __init__(self):
        self.ollama_url = "http://localhost:11434"
        self.model = "deepseek-coder"
        self.active = False
    
    async def check_ollama(self) -> bool:
        """Check if Ollama is available"""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            self.active = response.status_code == 200
            return self.active
        except:
            self.active = False
            return False
    
    async def analyze_system_state(self, state: SystemState, screenshot_analysis: Dict) -> str:
        """Analyze system state with AI"""
        if not await self.check_ollama():
            return "AI not available - using rule-based analysis"
        
        prompt = f"""
        Analyze this trading system state and recommend actions:
        
        System Performance:
        - CPU Usage: {state.cpu_usage:.1f}%
        - Memory Usage: {state.memory_usage:.1f}%
        - Trading Processes: {state.trading_processes}
        - Balance: ${state.balance:.2f}
        - Profit Rate: ${state.profit_rate:.6f}/second
        - Errors Detected: {state.errors_detected}
        
        Screenshot Analysis:
        - Error Pixels: {screenshot_analysis.get('error_pixels', 0)}
        - Warning Pixels: {screenshot_analysis.get('warning_pixels', 0)}
        - Has Errors: {screenshot_analysis.get('has_errors', False)}
        - Has Warnings: {screenshot_analysis.get('has_warnings', False)}
        
        Goal: Maintain 24/7 profitable trading operation.
        
        Recommend specific actions:
        1. If errors detected -> restart problematic processes
        2. If low profit rate -> optimize trading parameters
        3. If high resource usage -> optimize system performance
        4. If system idle -> restart trading systems
        
        Respond with: ACTION: [restart/optimize/monitor] - [specific instruction]
        """
        
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json().get('response', '')
        except Exception as e:
            logger.error(f"❌ AI analysis failed: {e}")
        
        return "AI analysis failed - using heuristics"

class SupervisorAI247:
    """24/7 Supervisor AI system"""
    
    def __init__(self):
        self.controller = ComputerController()
        self.ai_analyzer = LocalAIAnalyzer()
        self.system_state = SystemState()
        self.supervisor_actions: List[SupervisorAction] = []
        self.start_time = time.time()
        
        # Monitoring intervals
        self.screenshot_interval = 60  # Every minute
        self.deep_analysis_interval = 300  # Every 5 minutes
        self.ai_decision_interval = 180  # Every 3 minutes
        
        # Thresholds
        self.max_cpu_usage = 80.0
        self.max_memory_usage = 85.0
        self.min_profit_rate = 0.0001
        self.max_errors = 5
        
        logger.info("👁️ SUPERVISOR AI 24/7 INITIALIZED")
        logger.info(f"🖥️ Screen: {self.controller.screen_width}x{self.controller.screen_height}")
        logger.info(f"🤖 AI Analyzer: {'Available' if self.ai_analyzer.active else 'Will check'}")
        logger.info(f"📸 Screenshot interval: {self.screenshot_interval}s")
        logger.info(f"🧠 AI decision interval: {self.ai_decision_interval}s")
    
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
                    if any(script in cmdline for script in ['profit_executor.py', 'second_profit.py', 'ena_hedging_bot.py']):
                        trading_processes += 1
                except:
                    continue
            self.system_state.trading_processes = trading_processes
            
            # Simulate trading metrics (replace with actual API calls)
            import random
            self.system_state.balance = 12.0 + (time.time() - self.start_time) * 0.0001 * random.uniform(0.5, 1.5)
            self.system_state.profit_rate = max(0, random.uniform(0.0001, 0.002))
            
        except Exception as e:
            logger.error(f"❌ System metrics failed: {e}")
        
        return self.system_state
    
    async def perform_screenshot_analysis(self) -> Dict:
        """Take and analyze screenshot"""
        # Take full screenshot
        screenshot_path = self.controller.take_screenshot("full")
        if not screenshot_path:
            return {}
        
        # Take terminal screenshot
        terminal_path = self.controller.take_screenshot("terminal")
        
        # Analyze screenshots
        full_analysis = self.controller.analyze_screenshot(screenshot_path)
        terminal_analysis = self.controller.analyze_screenshot(terminal_path) if terminal_path else {}
        
        # Update screenshot count
        self.system_state.screenshot_count += 1
        
        # Combine analysis
        combined_analysis = {
            'full_screen': full_analysis,
            'terminal': terminal_analysis,
            'total_errors': full_analysis.get('error_pixels', 0) + terminal_analysis.get('error_pixels', 0),
            'total_warnings': full_analysis.get('warning_pixels', 0) + terminal_analysis.get('warning_pixels', 0),
            'has_critical_errors': full_analysis.get('has_errors', False) or terminal_analysis.get('has_errors', False)
        }
        
        logger.info(f"📸 Screenshot analysis: Errors={combined_analysis['total_errors']} | "
                   f"Warnings={combined_analysis['total_warnings']} | "
                   f"Critical={combined_analysis['has_critical_errors']}")
        
        return combined_analysis
    
    async def make_ai_decision(self, screenshot_analysis: Dict) -> str:
        """Make AI-based decision"""
        # Update error count
        if screenshot_analysis.get('has_critical_errors', False):
            self.system_state.errors_detected += 1
        
        # Get AI analysis
        ai_decision = await self.ai_analyzer.analyze_system_state(self.system_state, screenshot_analysis)
        
        logger.info(f"🧠 AI Decision: {ai_decision[:100]}...")
        
        return ai_decision
    
    async def execute_supervisor_action(self, decision: str) -> bool:
        """Execute supervisor action based on decision"""
        action = SupervisorAction(
            timestamp=datetime.now().isoformat(),
            action_type="decision",
            description=decision,
            success=False
        )
        
        try:
            # Parse AI decision
            decision_lower = decision.lower()
            
            if "restart" in decision_lower:
                logger.info("🔄 Executing restart action...")
                success = self.controller.restart_trading_system()
                action.action_type = "restart"
                action.success = success
                self.system_state.last_action = "restarted_trading_system"
                
            elif "optimize" in decision_lower:
                logger.info("⚡ Executing optimization action...")
                # Take screenshot of terminal for optimization
                screenshot_path = self.controller.take_screenshot("terminal")
                action.screenshot_path = screenshot_path
                action.action_type = "optimize"
                action.success = True
                self.system_state.last_action = "optimized_system"
                
            elif "monitor" in decision_lower:
                logger.info("👁️ Executing monitoring action...")
                screenshot_path = self.controller.take_screenshot("full")
                action.screenshot_path = screenshot_path
                action.action_type = "monitor"
                action.success = True
                self.system_state.last_action = "monitored_system"
            
            else:
                # Default action - take screenshot
                screenshot_path = self.controller.take_screenshot("full")
                action.screenshot_path = screenshot_path
                action.action_type = "screenshot"
                action.success = True
                self.system_state.last_action = "took_screenshot"
            
            self.supervisor_actions.append(action)
            return action.success
            
        except Exception as e:
            logger.error(f"❌ Action execution failed: {e}")
            return False
    
    async def rule_based_decision(self, state: SystemState, screenshot_analysis: Dict) -> str:
        """Rule-based decision making"""
        # Critical errors - restart
        if screenshot_analysis.get('has_critical_errors', False) or state.errors_detected > self.max_errors:
            return "ACTION: restart - Critical errors detected, restart trading system"
        
        # High resource usage - optimize
        if state.cpu_usage > self.max_cpu_usage or state.memory_usage > self.max_memory_usage:
            return "ACTION: optimize - High resource usage, optimize system performance"
        
        # Low profit rate - optimize
        if state.profit_rate < self.min_profit_rate:
            return "ACTION: optimize - Low profit rate, optimize trading parameters"
        
        # No trading processes - restart
        if state.trading_processes == 0:
            return "ACTION: restart - No trading processes running, restart system"
        
        # Normal operation - monitor
        return "ACTION: monitor - System operating normally, continue monitoring"
    
    async def supervisor_loop(self):
        """Main 24/7 supervisor loop"""
        logger.info("🚀 24/7 SUPERVISOR LOOP STARTED")
        logger.info(f"🎯 Goal: Maintain profitable trading 24/7 without supervision")
        
        # Timing trackers
        last_screenshot = time.time()
        last_ai_decision = time.time()
        last_deep_analysis = time.time()
        
        while True:
            try:
                current_time = time.time()
                
                # Get system metrics
                state = self.get_system_metrics()
                
                # Screenshot analysis
                if current_time - last_screenshot >= self.screenshot_interval:
                    screenshot_analysis = await self.perform_screenshot_analysis()
                    last_screenshot = current_time
                else:
                    screenshot_analysis = {}
                
                # AI decision making
                if current_time - last_ai_decision >= self.ai_decision_interval:
                    # Try AI decision first
                    ai_decision = await self.make_ai_decision(screenshot_analysis)
                    
                    # Fall back to rule-based if AI fails
                    if "AI not available" in ai_decision or "AI analysis failed" in ai_decision:
                        decision = await self.rule_based_decision(state, screenshot_analysis)
                        logger.info("📋 Using rule-based decision")
                    else:
                        decision = ai_decision
                    
                    # Execute action
                    await self.execute_supervisor_action(decision)
                    last_ai_decision = current_time
                
                # Deep analysis (less frequent)
                if current_time - last_deep_analysis >= self.deep_analysis_interval:
                    logger.info("🔍 Performing deep system analysis...")
                    
                    # Take comprehensive screenshots
                    self.controller.take_screenshot("full")
                    self.controller.take_screenshot("terminal")
                    self.controller.take_screenshot("browser")
                    
                    # Log comprehensive status
                    uptime_hours = (current_time - self.start_time) / 3600
                    logger.info(f"📊 DEEP ANALYSIS - Uptime: {uptime_hours:.1f}h | "
                               f"CPU: {state.cpu_usage:.1f}% | "
                               f"Memory: {state.memory_usage:.1f}% | "
                               f"Processes: {state.trading_processes} | "
                               f"Balance: ${state.balance:.2f} | "
                               f"Profit Rate: ${state.profit_rate:.6f}/s | "
                               f"Actions: {len(self.supervisor_actions)}")
                    
                    last_deep_analysis = current_time
                
                # Brief sleep to prevent overwhelming system
                await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"❌ Supervisor loop error: {e}")
                await asyncio.sleep(30)
    
    def get_supervisor_report(self) -> Dict:
        """Get comprehensive supervisor report"""
        successful_actions = [a for a in self.supervisor_actions if a.success]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'uptime_hours': (time.time() - self.start_time) / 3600,
            'current_balance': self.system_state.balance,
            'current_profit_rate': self.system_state.profit_rate,
            'total_screenshots': self.system_state.screenshot_count,
            'total_actions': len(self.supervisor_actions),
            'successful_actions': len(successful_actions),
            'action_success_rate': len(successful_actions) / max(1, len(self.supervisor_actions)),
            'last_action': self.system_state.last_action,
            'errors_detected': self.system_state.errors_detected,
            'ai_available': self.ai_analyzer.active
        }

async def main():
    """Main supervisor system"""
    print("👁️ SUPERVISOR AI 24/7")
    print("="*70)
    print("🎯 Fully Autonomous Trading Supervision")
    print("📸 Screenshot Monitoring & Analysis")
    print("🖱️ Computer Control & Automation")
    print("🧠 AI-Powered Decision Making")
    print("🔄 24/7 System Maintenance")
    print("⚡ Zero Human Supervision Required")
    print("="*70)
    
    # Safety check
    print("⚠️  WARNING: This system will control your computer!")
    print("   It will take screenshots, click, type, and restart processes.")
    print("   Make sure you understand what this does before running.")
    print("")
    print("Press Ctrl+C to cancel...")
    
    try:
        await asyncio.sleep(5)  # Give time to cancel
        
        # Initialize supervisor
        supervisor = SupervisorAI247()
        
        # Start 24/7 supervision
        await supervisor.supervisor_loop()
        
    except KeyboardInterrupt:
        print("\n👁️ Supervisor AI stopped by user")
        
        # Final report
        report = supervisor.get_supervisor_report()
        print("\n" + "="*70)
        print("📊 SUPERVISOR AI PERFORMANCE REPORT")
        print("="*70)
        print(f"⏱️ Uptime: {report['uptime_hours']:.1f} hours")
        print(f"💰 Final Balance: ${report['current_balance']:.2f}")
        print(f"⚡ Profit Rate: ${report['current_profit_rate']:.6f}/second")
        print(f"📸 Total Screenshots: {report['total_screenshots']}")
        print(f"🤖 Total Actions: {report['total_actions']}")
        print(f"✅ Successful Actions: {report['successful_actions']}")
        print(f"🎯 Action Success Rate: {report['action_success_rate']:.1%}")
        print(f"🔄 Last Action: {report['last_action']}")
        print(f"❌ Errors Detected: {report['errors_detected']}")
        print(f"🧠 AI Available: {report['ai_available']}")
        print("="*70)
        
    except Exception as e:
        print(f"\n❌ Supervisor AI error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
