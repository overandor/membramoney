#!/usr/bin/env python3
"""
GROQ SUPERVISOR 24/7
Ultra-fast AI supervision using Groq API
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
    format='%(asctime)s - GROQ-SUPERVISOR - %(message)s',
    handlers=[
        logging.FileHandler('/Users/alep/Downloads/groq_supervisor_247.log'),
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
class SupervisorAction:
    """Supervisor action record"""
    timestamp: str
    action_type: str  # screenshot, restart, optimize, control
    description: str
    success: bool
    screenshot_path: str = ""
    response_time: float = 0.0

class GroqAIAnalyzer:
    """Groq AI analysis for ultra-fast decision making"""
    
    def __init__(self):
        self.api_key = "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"
        self.base_url = "https://api.groq.com/openai/v1"
        self.model = "llama3-70b-8192"  # Fastest model
        self.active = True
        self.request_count = 0
        
        logger.info("🚀 Groq AI Analyzer initialized")
        logger.info(f"🧠 Model: {self.model}")
    
    def encode_image(self, image_path: str) -> str:
        """Encode image to base64"""
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            logger.error(f"❌ Image encoding failed: {e}")
            return ""
    
    async def analyze_with_groq(self, state: SystemState, image_path: str = None) -> Dict:
        """Analyze system state with Groq AI"""
        start_time = time.time()
        
        try:
            # Prepare system prompt
            system_prompt = """You are an expert trading system supervisor AI. Your goal is to maintain profitable 24/7 trading operations.

            Analyze the provided system state and optionally screenshots, then recommend specific actions.

            Response format: JSON with these fields:
            {
                "action": "restart|optimize|monitor|emergency_stop",
                "priority": "low|medium|high|critical",
                "reasoning": "Brief explanation",
                "specific_steps": ["step1", "step2"],
                "confidence": 0.0-1.0
            }

            Guidelines:
            - CRITICAL: System crashes, major errors, security issues
            - HIGH: Profit rate < 0.0001/s, errors > 5, resource usage > 90%
            - MEDIUM: Performance degradation, minor errors
            - LOW: Routine optimization, monitoring
            
            Always prioritize maintaining profitable trading operations."""
            
            # Prepare user message
            user_message = f"""System State Analysis:
            
            Performance Metrics:
            - CPU Usage: {state.cpu_usage:.1f}%
            - Memory Usage: {state.memory_usage:.1f}%
            - Trading Processes: {state.trading_processes}
            - Balance: ${state.balance:.4f}
            - Profit Rate: ${state.profit_rate:.6f}/second
            - Errors Detected: {state.errors_detected}
            - Uptime: {state.uptime_hours:.1f} hours
            - Last Action: {state.last_action}
            
            Current Time: {datetime.now().isoformat()}
            
            Analyze this data and provide optimal supervision decision."""
            
            # Prepare messages
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
            
            # Add image if provided
            if image_path and os.path.exists(image_path):
                base64_image = self.encode_image(image_path)
                if base64_image:
                    messages.append({
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Screenshot analysis:"},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                        ]
                    })
            
            # Make API request
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": 500,
                "temperature": 0.1
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=10
            )
            
            response_time = time.time() - start_time
            self.request_count += 1
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                # Try to parse JSON response
                try:
                    analysis = json.loads(content)
                    analysis['response_time'] = response_time
                    analysis['raw_response'] = content
                    logger.info(f"🧠 Groq analysis completed in {response_time:.2f}s")
                    return analysis
                except json.JSONDecodeError:
                    # Fallback if not JSON
                    return {
                        "action": "monitor",
                        "priority": "medium",
                        "reasoning": content,
                        "specific_steps": ["Continue monitoring"],
                        "confidence": 0.5,
                        "response_time": response_time,
                        "raw_response": content
                    }
            else:
                logger.error(f"❌ Groq API error: {response.status_code}")
                return {"error": f"API error: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"❌ Groq analysis failed: {e}")
            return {"error": str(e)}
    
    async def test_connection(self) -> bool:
        """Test Groq API connection"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": "Respond with 'OK' if you can understand this."}
                ],
                "max_tokens": 10
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=5
            )
            
            if response.status_code == 200:
                logger.info("✅ Groq API connection successful")
                return True
            else:
                logger.error(f"❌ Groq API connection failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Groq connection test failed: {e}")
            return False

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
            os.makedirs('/Users/alep/Downloads/groq_screenshots', exist_ok=True)
            
            if region == "full":
                screenshot = pyautogui.screenshot()
                filename = f"/Users/alep/Downloads/groq_screenshots/full_{timestamp}.png"
            elif region == "terminal":
                screenshot = pyautogui.screenshot(region=(0, 0, 1200, 600))
                filename = f"/Users/alep/Downloads/groq_screenshots/terminal_{timestamp}.png"
            elif region == "trading":
                screenshot = pyautogui.screenshot(region=(0, 0, 800, 400))
                filename = f"/Users/alep/Downloads/groq_screenshots/trading_{timestamp}.png"
            else:
                screenshot = pyautogui.screenshot()
                filename = f"/Users/alep/Downloads/groq_screenshots/custom_{timestamp}.png"
            
            screenshot.save(filename)
            logger.info(f"📸 Screenshot saved: {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"❌ Screenshot failed: {e}")
            return ""
    
    def analyze_screenshot_basic(self, image_path: str) -> Dict:
        """Basic screenshot analysis without heavy processing"""
        try:
            image = Image.open(image_path)
            
            # Convert to numpy array
            img_array = np.array(image)
            
            # Basic color analysis for error detection
            # Red pixels (errors)
            red_mask = (img_array[:,:,0] > 150) & (img_array[:,:,1] < 100) & (img_array[:,:,2] < 100)
            red_count = np.sum(red_mask)
            
            # Orange/yellow pixels (warnings)
            orange_mask = (img_array[:,:,0] > 200) & (img_array[:,:,1] > 150) & (img_array[:,:,2] < 100)
            orange_count = np.sum(orange_mask)
            
            # Brightness analysis (screen activity)
            brightness = np.mean(img_array) / 255.0
            
            analysis = {
                'error_pixels': int(red_count),
                'warning_pixels': int(orange_count),
                'brightness': float(brightness),
                'has_errors': red_count > 500,
                'has_warnings': orange_count > 500,
                'screen_active': brightness > 0.2,
                'image_size': image.size
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Screenshot analysis failed: {e}")
            return {}
    
    def restart_trading_system(self) -> bool:
        """Restart trading system via terminal"""
        try:
            logger.info("🔄 Restarting trading system...")
            
            # Kill existing trading processes
            trading_scripts = ['profit_executor.py', 'second_profit.py', 'simple_market_maker.py']
            
            for script in trading_scripts:
                try:
                    subprocess.run(['pkill', '-f', script], capture_output=True)
                    logger.info(f"🔫 Killed {script}")
                except:
                    pass
            
            # Wait a moment
            time.sleep(2)
            
            # Start trading systems
            for script in trading_scripts:
                try:
                    subprocess.Popen([
                        '/Users/alep/miniconda3/bin/python',
                        f'/Users/alep/Downloads/{script}'
                    ], cwd='/Users/alep/Downloads')
                    logger.info(f"🚀 Started {script}")
                    time.sleep(1)
                except Exception as e:
                    logger.error(f"❌ Failed to start {script}: {e}")
            
            logger.info("✅ Trading system restart completed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Trading system restart failed: {e}")
            return False
    
    def execute_optimization(self, optimization_steps: List[str]) -> bool:
        """Execute optimization steps"""
        try:
            logger.info(f"⚡ Executing optimization: {len(optimization_steps)} steps")
            
            for step in optimization_steps:
                logger.info(f"🔧 Step: {step}")
                
                # Simulate optimization (in reality, this would modify code)
                if "restart" in step.lower():
                    return self.restart_trading_system()
                elif "monitor" in step.lower():
                    self.take_screenshot("full")
                elif "optimize" in step.lower():
                    # Take screenshot for documentation
                    self.take_screenshot("trading")
                
                time.sleep(1)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Optimization execution failed: {e}")
            return False

class GroqSupervisor247:
    """24/7 Groq-powered supervisor system"""
    
    def __init__(self):
        self.groq_analyzer = GroqAIAnalyzer()
        self.controller = ComputerController()
        self.system_state = SystemState()
        self.supervisor_actions: List[SupervisorAction] = []
        self.start_time = time.time()
        
        # Monitoring intervals
        self.screenshot_interval = 120  # Every 2 minutes
        self.groq_analysis_interval = 180  # Every 3 minutes
        self.deep_analysis_interval = 600  # Every 10 minutes
        
        # Performance thresholds
        self.max_cpu_usage = 80.0
        self.max_memory_usage = 85.0
        self.min_profit_rate = 0.0001
        self.max_errors = 5
        
        logger.info("🚀 GROQ SUPERVISOR 24/7 INITIALIZED")
        logger.info(f"🧠 AI: Groq {self.groq_analyzer.model}")
        logger.info(f"⚡ Ultra-fast analysis enabled")
        logger.info(f"📸 Screenshot interval: {self.screenshot_interval}s")
        logger.info(f"🧠 Analysis interval: {self.groq_analysis_interval}s")
    
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
            
            # Simulate trading metrics (replace with actual API calls)
            import random
            base_profit = 0.0001 * (1 + self.system_state.uptime_hours * 0.01)
            self.system_state.profit_rate = max(0, base_profit * random.uniform(0.8, 1.2))
            self.system_state.balance = 12.0 + (self.system_state.profit_rate * self.system_state.uptime_hours * 3600)
            
        except Exception as e:
            logger.error(f"❌ System metrics failed: {e}")
        
        return self.system_state
    
    async def perform_groq_analysis(self) -> Optional[Dict]:
        """Perform Groq AI analysis"""
        # Take screenshot for analysis
        screenshot_path = self.controller.take_screenshot("trading")
        
        # Analyze with Groq
        analysis = await self.groq_analyzer.analyze_with_groq(self.system_state, screenshot_path)
        
        if 'error' not in analysis:
            logger.info(f"🧠 Groq Analysis: {analysis.get('action', 'unknown')} | "
                       f"Priority: {analysis.get('priority', 'unknown')} | "
                       f"Confidence: {analysis.get('confidence', 0):.2f} | "
                       f"Response time: {analysis.get('response_time', 0):.2f}s")
        
        return analysis
    
    async def execute_groq_decision(self, analysis: Dict) -> bool:
        """Execute decision based on Groq analysis"""
        if 'error' in analysis:
            logger.error(f"❌ Cannot execute decision - analysis error: {analysis['error']}")
            return False
        
        action = SupervisorAction(
            timestamp=datetime.now().isoformat(),
            action_type=analysis.get('action', 'monitor'),
            description=analysis.get('reasoning', 'Groq AI decision'),
            success=False,
            response_time=analysis.get('response_time', 0)
        )
        
        try:
            action_type = analysis.get('action', 'monitor')
            priority = analysis.get('priority', 'medium')
            confidence = analysis.get('confidence', 0.5)
            
            # Only execute if confidence is high enough
            if confidence < 0.3:
                logger.info(f"⚠️ Low confidence ({confidence:.2f}) - skipping action")
                return False
            
            success = False
            
            if action_type == "restart" or priority == "critical":
                logger.info(f"🔄 Executing RESTART (Priority: {priority})")
                success = self.controller.restart_trading_system()
                self.system_state.last_action = "restarted_trading_system"
                
            elif action_type == "optimize":
                logger.info(f"⚡ Executing OPTIMIZATION (Priority: {priority})")
                steps = analysis.get('specific_steps', ['Continue monitoring'])
                success = self.controller.execute_optimization(steps)
                self.system_state.last_action = "optimized_system"
                
            elif action_type == "emergency_stop":
                logger.warning(f"🛑 EMERGENCY STOP (Priority: {priority})")
                # Kill all trading processes
                subprocess.run(['pkill', '-f', 'profit_executor.py'], capture_output=True)
                subprocess.run(['pkill', '-f', 'second_profit.py'], capture_output=True)
                success = True
                self.system_state.last_action = "emergency_stop"
                
            else:  # monitor
                logger.info(f"👁️ Monitoring (Priority: {priority})")
                screenshot_path = self.controller.take_screenshot("full")
                action.screenshot_path = screenshot_path
                success = True
                self.system_state.last_action = "monitored_system"
            
            action.success = success
            self.supervisor_actions.append(action)
            
            logger.info(f"✅ Action executed: {action_type} | Success: {success}")
            return success
            
        except Exception as e:
            logger.error(f"❌ Action execution failed: {e}")
            return False
    
    async def supervisor_loop(self):
        """Main 24/7 supervisor loop"""
        logger.info("🚀 24/7 GROQ SUPERVISOR LOOP STARTED")
        logger.info(f"🎯 Goal: Maintain profitable trading with ultra-fast AI decisions")
        
        # Test Groq connection
        if not await self.groq_analyzer.test_connection():
            logger.error("❌ Groq API connection failed - cannot continue")
            return
        
        # Timing trackers
        last_screenshot = time.time()
        last_groq_analysis = time.time()
        last_deep_analysis = time.time()
        
        while True:
            try:
                current_time = time.time()
                
                # Get system metrics
                state = self.get_system_metrics()
                
                # Groq analysis
                if current_time - last_groq_analysis >= self.groq_analysis_interval:
                    logger.info("🧠 Performing Groq AI analysis...")
                    
                    analysis = await self.perform_groq_analysis()
                    if analysis:
                        await self.execute_groq_decision(analysis)
                    
                    last_groq_analysis = current_time
                
                # Regular screenshots
                if current_time - last_screenshot >= self.screenshot_interval:
                    self.controller.take_screenshot("full")
                    self.system_state.screenshot_count += 1
                    last_screenshot = current_time
                
                # Deep analysis and reporting
                if current_time - last_deep_analysis >= self.deep_analysis_interval:
                    logger.info("🔍 DEEP SYSTEM ANALYSIS")
                    
                    # Comprehensive status
                    recent_actions = self.supervisor_actions[-10:]  # Last 10 actions
                    successful_recent = sum(1 for a in recent_actions if a.success)
                    avg_response_time = sum(a.response_time for a in recent_actions) / len(recent_actions) if recent_actions else 0
                    
                    logger.info(f"📊 SYSTEM STATUS:")
                    logger.info(f"   Uptime: {state.uptime_hours:.1f}h")
                    logger.info(f"   CPU: {state.cpu_usage:.1f}% | Memory: {state.memory_usage:.1f}%")
                    logger.info(f"   Trading Processes: {state.trading_processes}")
                    logger.info(f"   Balance: ${state.balance:.4f}")
                    logger.info(f"   Profit Rate: ${state.profit_rate:.6f}/s")
                    logger.info(f"   Screenshots: {state.screenshot_count}")
                    logger.info(f"   Total Actions: {len(self.supervisor_actions)}")
                    logger.info(f"   Recent Success Rate: {successful_recent}/{len(recent_actions)}")
                    logger.info(f"   Avg Response Time: {avg_response_time:.2f}s")
                    logger.info(f"   Groq Requests: {self.groq_analyzer.request_count}")
                    
                    last_deep_analysis = current_time
                
                # Brief sleep
                await asyncio.sleep(15)  # Check every 15 seconds
                
            except Exception as e:
                logger.error(f"❌ Supervisor loop error: {e}")
                await asyncio.sleep(30)
    
    def get_supervisor_report(self) -> Dict:
        """Get comprehensive supervisor report"""
        successful_actions = [a for a in self.supervisor_actions if a.success]
        recent_actions = self.supervisor_actions[-20:]  # Last 20 actions
        
        return {
            'timestamp': datetime.now().isoformat(),
            'uptime_hours': self.system_state.uptime_hours,
            'current_balance': self.system_state.balance,
            'current_profit_rate': self.system_state.profit_rate,
            'total_screenshots': self.system_state.screenshot_count,
            'total_actions': len(self.supervisor_actions),
            'successful_actions': len(successful_actions),
            'action_success_rate': len(successful_actions) / max(1, len(self.supervisor_actions)),
            'last_action': self.system_state.last_action,
            'errors_detected': self.system_state.errors_detected,
            'groq_requests': self.groq_analyzer.request_count,
            'avg_response_time': sum(a.response_time for a in recent_actions) / len(recent_actions) if recent_actions else 0,
            'trading_processes': self.system_state.trading_processes
        }

async def main():
    """Main Groq supervisor system"""
    print("🚀 GROQ SUPERVISOR 24/7")
    print("="*70)
    print("🧠 Ultra-Fast AI-Powered Supervision")
    print("⚡ Groq API for Real-time Decisions")
    print("📸 Screenshot Monitoring & Analysis")
    print("🖥️ Computer Control & Automation")
    print("🔄 24/7 System Maintenance")
    print("💰 Profit-Focused Operations")
    print("="*70)
    
    # Safety check
    print("⚠️  WARNING: This system will control your computer!")
    print("   It will take screenshots, analyze with Groq AI, and automate actions.")
    print("   Make sure you understand what this does before running.")
    print("")
    print("Press Ctrl+C to cancel...")
    
    try:
        await asyncio.sleep(5)  # Give time to cancel
        
        # Initialize supervisor
        supervisor = GroqSupervisor247()
        
        # Start 24/7 supervision
        await supervisor.supervisor_loop()
        
    except KeyboardInterrupt:
        print("\n🚀 Groq Supervisor stopped by user")
        
        # Final report
        report = supervisor.get_supervisor_report()
        print("\n" + "="*70)
        print("📊 GROQ SUPERVISOR PERFORMANCE REPORT")
        print("="*70)
        print(f"⏱️ Uptime: {report['uptime_hours']:.1f} hours")
        print(f"💰 Final Balance: ${report['current_balance']:.4f}")
        print(f"⚡ Profit Rate: ${report['current_profit_rate']:.6f}/second")
        print(f"📸 Total Screenshots: {report['total_screenshots']}")
        print(f"🤖 Total Actions: {report['total_actions']}")
        print(f"✅ Successful Actions: {report['successful_actions']}")
        print(f"🎯 Action Success Rate: {report['action_success_rate']:.1%}")
        print(f"🔄 Last Action: {report['last_action']}")
        print(f"❌ Errors Detected: {report['errors_detected']}")
        print(f"🧠 Groq Requests: {report['groq_requests']}")
        print(f"⚡ Avg Response Time: {report['avg_response_time']:.2f}s")
        print(f"🚀 Trading Processes: {report['trading_processes']}")
        print("="*70)
        
    except Exception as e:
        print(f"\n❌ Groq Supervisor error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
