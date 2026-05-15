#!/usr/bin/env python3
"""
SYSTEM INTEGRATION LAYER
Complete API Integration for Self-Developing AI System
"""

import asyncio
import json
import time
import logging
import subprocess
import psutil
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import requests
from pathlib import Path

# Import our modules
from ai_control_center import AIControlCenter
from trading_governance import TradingGovernance
from ena_hedging_bot import HedgingApp

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class SystemModule:
    """System module definition"""
    name: str
    file_path: str
    process: Optional[subprocess.Popen] = None
    status: str = "stopped"
    last_restart: str = ""
    auto_restart: bool = True
    priority: int = 1

class SystemOrchestrator:
    """Main system orchestrator - controls all modules"""
    
    def __init__(self):
        self.modules: Dict[str, SystemModule] = {}
        self.ai_control: Optional[AIControlCenter] = None
        self.governance: Optional[TradingGovernance] = None
        self.hedging_bot: Optional[HedgingApp] = None
        
        # System state
        self.system_health = "INITIALIZING"
        self.start_time = datetime.now()
        self.total_restarts = 0
        self.system_log: List[Dict] = []
        
        # Control parameters
        self.auto_development = True
        self.self_optimization = True
        self.emergency_protocols = True
        
        logger.info("🎛️ System Orchestrator initialized")
    
    def register_module(self, name: str, file_path: str, priority: int = 1):
        """Register a system module"""
        module = SystemModule(
            name=name,
            file_path=file_path,
            priority=priority
        )
        self.modules[name] = module
        logger.info(f"📦 Module registered: {name}")
    
    async def start_module(self, name: str) -> bool:
        """Start a system module"""
        if name not in self.modules:
            logger.error(f"Module {name} not found")
            return False
        
        module = self.modules[name]
        
        try:
            # Start the module
            process = subprocess.Popen(
                ['/Users/alep/miniconda3/bin/python', module.file_path],
                cwd='/Users/alep/Downloads',
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            module.process = process
            module.status = "running"
            module.last_restart = datetime.now().isoformat()
            
            logger.info(f"🚀 Module started: {name} (PID: {process.pid})")
            
            # Log to system log
            self.system_log.append({
                'timestamp': datetime.now().isoformat(),
                'action': 'module_start',
                'module': name,
                'pid': process.pid,
                'status': 'success'
            })
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start module {name}: {e}")
            module.status = "error"
            return False
    
    async def stop_module(self, name: str) -> bool:
        """Stop a system module"""
        if name not in self.modules:
            return False
        
        module = self.modules[name]
        
        if module.process:
            try:
                module.process.terminate()
                module.process.wait(timeout=5)
                module.status = "stopped"
                logger.info(f"⏹️ Module stopped: {name}")
                
                self.system_log.append({
                    'timestamp': datetime.now().isoformat(),
                    'action': 'module_stop',
                    'module': name,
                    'status': 'success'
                })
                
                return True
            except subprocess.TimeoutExpired:
                module.process.kill()
                module.status = "killed"
                logger.warning(f"🔫 Module killed: {name}")
                return True
            except Exception as e:
                logger.error(f"❌ Failed to stop module {name}: {e}")
                return False
        
        return False
    
    def check_module_health(self, name: str) -> str:
        """Check if a module is healthy"""
        if name not in self.modules:
            return "not_found"
        
        module = self.modules[name]
        
        if not module.process:
            return "stopped"
        
        # Check if process is running
        if module.process.poll() is None:
            return "running"
        else:
            module.status = "crashed"
            return "crashed"
    
    async def restart_module(self, name: str) -> bool:
        """Restart a module"""
        logger.info(f"🔄 Restarting module: {name}")
        
        if await self.stop_module(name):
            await asyncio.sleep(2)  # Brief pause
            return await self.start_module(name)
        
        return False
    
    async def monitor_modules(self):
        """Monitor all modules and auto-restart if needed"""
        while True:
            try:
                for name, module in self.modules.items():
                    health = self.check_module_health(name)
                    
                    if health == "crashed" and module.auto_restart:
                        logger.warning(f"⚠️ Module {name} crashed, auto-restarting...")
                        await self.restart_module(name)
                        self.total_restarts += 1
                
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.error(f"Module monitoring error: {e}")
                await asyncio.sleep(5)
    
    async def start_ai_control(self):
        """Start AI Control Center"""
        logger.info("🧠 Starting AI Control Center...")
        
        self.ai_control = AIControlCenter()
        
        # Run in background
        asyncio.create_task(self.ai_control.autonomous_control_loop())
        
        logger.info("✅ AI Control Center started")
    
    async def start_governance(self):
        """Start Trading Governance"""
        logger.info("🏛️ Starting Trading Governance...")
        
        self.governance = TradingGovernance()
        
        # Run in background
        asyncio.create_task(self.governance.start_governance())
        
        logger.info("✅ Trading Governance started")
    
    async def start_hedging_bot(self):
        """Start ENA Hedging Bot"""
        logger.info("🤖 Starting ENA Hedging Bot...")
        
        # Start as subprocess for UI
        await self.start_module("hedging_bot")
    
    async def initialize_system(self):
        """Initialize the complete system"""
        logger.info("🚀 INITIALIZING SELF-DEVELOPING SYSTEM")
        
        # Register all modules
        self.register_module("hedging_bot", "/Users/alep/Downloads/ena_hedging_bot.py", priority=1)
        self.register_module("governance", "/Users/alep/Downloads/trading_governance.py", priority=2)
        self.register_module("ai_control", "/Users/alep/Downloads/ai_control_center.py", priority=3)
        
        # Start core systems
        await self.start_ai_control()
        await self.start_governance()
        
        # Start modules by priority
        sorted_modules = sorted(self.modules.items(), key=lambda x: x[1].priority)
        
        for name, module in sorted_modules:
            await self.start_module(name)
            await asyncio.sleep(2)  # Stagger starts
        
        # Start monitoring
        asyncio.create_task(self.monitor_modules())
        
        # Start system optimization
        if self.self_optimization:
            asyncio.create_task(self.system_optimization_loop())
        
        self.system_health = "RUNNING"
        logger.info("✅ SYSTEM INITIALIZATION COMPLETE")
    
    async def system_optimization_loop(self):
        """Continuous system optimization"""
        logger.info("⚡ System optimization loop started")
        
        while True:
            try:
                # Analyze system performance
                uptime = (datetime.now() - self.start_time).total_seconds()
                
                # Optimize based on performance
                if self.total_restarts > 10 and uptime > 3600:  # Too many restarts
                    logger.warning("⚠️ High restart rate detected - adjusting parameters")
                    
                    # Adjust AI parameters
                    if self.ai_control:
                        self.ai_control.state.learning_rate *= 0.9
                        self.ai_control.state.risk_tolerance *= 0.9
                
                # Memory cleanup
                if uptime % 1800 < 60:  # Every 30 minutes
                    await self.system_cleanup()
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"System optimization error: {e}")
                await asyncio.sleep(30)
    
    async def system_cleanup(self):
        """System cleanup and maintenance"""
        logger.info("🧹 System cleanup...")
        
        # Clean old logs
        log_files = list(Path('/Users/alep/Downloads').glob('*.log'))
        for log_file in log_files:
            if log_file.stat().st_size > 10 * 1024 * 1024:  # 10MB
                log_file.unlink()
                logger.info(f"🗑️ Cleaned large log: {log_file}")
        
        # Save system state
        await self.save_system_state()
    
    async def save_system_state(self):
        """Save complete system state"""
        try:
            system_state = {
                'timestamp': datetime.now().isoformat(),
                'system_health': self.system_health,
                'uptime_seconds': (datetime.now() - self.start_time).total_seconds(),
                'total_restarts': self.total_restarts,
                'modules': {
                    name: {
                        'status': module.status,
                        'last_restart': module.last_restart,
                        'auto_restart': module.auto_restart
                    }
                    for name, module in self.modules.items()
                },
                'ai_state': asdict(self.ai_control.state) if self.ai_control else None,
                'system_log': self.system_log[-100:]  # Last 100 entries
            }
            
            with open('/Users/alep/Downloads/system_state.json', 'w') as f:
                json.dump(system_state, f, indent=2)
            
            logger.info("💾 System state saved")
            
        except Exception as e:
            logger.error(f"Failed to save system state: {e}")
    
    def get_system_status(self) -> Dict:
        """Get complete system status"""
        return {
            'system_health': self.system_health,
            'uptime': str(datetime.now() - self.start_time),
            'total_restarts': self.total_restarts,
            'modules': {
                name: {
                    'status': self.check_module_health(name),
                    'priority': module.priority,
                    'auto_restart': module.auto_restart,
                    'last_restart': module.last_restart
                }
                for name, module in self.modules.items()
            },
            'ai_control': {
                'active': self.ai_control is not None,
                'evolution_count': self.ai_control.state.evolution_count if self.ai_control else 0,
                'performance_score': self.ai_control.state.performance_score if self.ai_control else 0.0
            } if self.ai_control else None
        }
    
    async def emergency_shutdown(self):
        """Emergency shutdown of all systems"""
        logger.critical("🚨 EMERGENCY SHUTDOWN INITIATED")
        
        self.system_health = "SHUTTING_DOWN"
        
        # Stop all modules
        for name in self.modules:
            await self.stop_module(name)
        
        # Save final state
        await self.save_system_state()
        
        if self.ai_control:
            self.ai_control.emergency_stop()
        
        logger.critical("🚨 EMERGENCY SHUTDOWN COMPLETE")
    
    def set_auto_development(self, enabled: bool):
        """Enable/disable auto-development"""
        self.auto_development = enabled
        status = "ENABLED" if enabled else "DISABLED"
        logger.info(f"🧠 Auto-development {status}")

class SystemDashboard:
    """System monitoring dashboard"""
    
    def __init__(self, orchestrator: SystemOrchestrator):
        self.orchestrator = orchestrator
    
    async def show_dashboard(self):
        """Show system dashboard"""
        while True:
            status = self.orchestrator.get_system_status()
            
            print("\n" + "="*80)
            print(f"🎛️ SELF-DEVELOPING SYSTEM DASHBOARD - {datetime.now().strftime('%H:%M:%S')}")
            print("="*80)
            print(f"🚦 System Health: {status['system_health']}")
            print(f"⏱️ Uptime: {status['uptime']}")
            print(f"🔄 Total Restarts: {status['total_restarts']}")
            
            print(f"\n📦 Modules ({len(status['modules'])}):")
            for name, module_status in status['modules'].items():
                status_icon = "🟢" if module_status['status'] == 'running' else "🔴"
                print(f"   {status_icon} {name}: {module_status['status']} (Priority: {module_status['priority']})")
            
            if status['ai_control']:
                ai = status['ai_control']
                print(f"\n🧠 AI Control:")
                print(f"   Active: {ai['active']}")
                print(f"   Evolution Count: {ai['evolution_count']}")
                print(f"   Performance Score: {ai['performance_score']:.3f}")
            
            print("="*80)
            
            await asyncio.sleep(30)  # Update every 30 seconds

async def main():
    """Main system integration"""
    print("🎛️ SYSTEM INTEGRATION LAYER")
    print("="*70)
    print("🤖 Self-Developing AI System")
    print("🧠 Autonomous Control")
    print("🏛️ Trading Governance")
    print("📊 Real-time Monitoring")
    print("="*70)
    
    # Initialize system orchestrator
    orchestrator = SystemOrchestrator()
    
    # Start dashboard
    dashboard = SystemDashboard(orchestrator)
    
    try:
        # Initialize complete system
        await orchestrator.initialize_system()
        
        # Start dashboard
        await dashboard.show_dashboard()
        
    except KeyboardInterrupt:
        print("\n🎛️ System stopped by user")
        await orchestrator.emergency_shutdown()
    except Exception as e:
        print(f"\n❌ System error: {e}")
        await orchestrator.emergency_shutdown()

if __name__ == "__main__":
    asyncio.run(main())
