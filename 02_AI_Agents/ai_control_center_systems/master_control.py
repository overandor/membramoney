#!/usr/bin/env python3
"""
MASTER CONTROL SYSTEM
Complete Self-Developing AI Trading System
"""

import asyncio
import json
import time
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional
import signal
import sys

# Import all system components
from system_integration import SystemOrchestrator, SystemDashboard
from ai_control_center import AIControlCenter
from trading_governance import TradingGovernance

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/Users/alep/Downloads/master_control.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MasterControlSystem:
    """Master Control System - Complete AI control and management"""
    
    def __init__(self):
        self.orchestrator = SystemOrchestrator()
        self.running = True
        self.start_time = datetime.now()
        
        # System capabilities
        self.capabilities = {
            'autonomous_trading': True,
            'self_improvement': True,
            'risk_management': True,
            'system_optimization': True,
            'emergency_protocols': True,
            'continuous_learning': True
        }
        
        # Control interfaces
        self.command_interface = True
        self.api_interface = True
        self.monitoring_interface = True
        
        logger.info("🎛️ Master Control System initialized")
        logger.info(f"🧠 AI Capabilities: {len(self.capabilities)} systems active")
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Handle system signals"""
        logger.info(f"📡 Received signal {signum}")
        self.running = False
    
    async def initialize_complete_system(self):
        """Initialize the complete self-developing system"""
        logger.info("🚀 INITIALIZING COMPLETE SELF-DEVELOPING SYSTEM")
        logger.info("="*80)
        
        # Phase 1: Core Systems
        logger.info("📍 Phase 1: Initializing Core Systems...")
        
        # Start AI Control Center
        await self.orchestrator.start_ai_control()
        await asyncio.sleep(3)
        
        # Start Trading Governance
        await self.orchestrator.start_governance()
        await asyncio.sleep(3)
        
        # Phase 2: Trading Modules
        logger.info("📍 Phase 2: Initializing Trading Modules...")
        
        # Register all modules
        self.orchestrator.register_module("hedging_bot", "/Users/alep/Downloads/ena_hedging_bot.py", priority=1)
        self.orchestrator.register_module("governance", "/Users/alep/Downloads/trading_governance.py", priority=2)
        self.orchestrator.register_module("ai_control", "/Users/alep/Downloads/ai_control_center.py", priority=3)
        
        # Start modules by priority
        for name in ["hedging_bot", "governance", "ai_control"]:
            await self.orchestrator.start_module(name)
            await asyncio.sleep(2)
        
        # Phase 3: Monitoring and Optimization
        logger.info("📍 Phase 3: Starting Monitoring and Optimization...")
        
        # Start monitoring
        asyncio.create_task(self.orchestrator.monitor_modules())
        asyncio.create_task(self.orchestrator.system_optimization_loop())
        
        # Start master monitoring
        asyncio.create_task(self.master_monitoring_loop())
        
        # Phase 4: Self-Development Activation
        logger.info("📍 Phase 4: Activating Self-Development...")
        
        if self.orchestrator.ai_control:
            self.orchestrator.ai_control.set_autonomous_mode(True)
        
        logger.info("✅ COMPLETE SYSTEM INITIALIZATION FINISHED")
        logger.info("="*80)
        
        # Display system status
        await self.display_system_status()
    
    async def master_monitoring_loop(self):
        """Master monitoring loop for overall system health"""
        logger.info("👁️ Master monitoring loop started")
        
        while self.running:
            try:
                # Get system status
                status = self.orchestrator.get_system_status()
                
                # Log key metrics
                if status['system_health'] != "RUNNING":
                    logger.warning(f"⚠️ System health: {status['system_health']}")
                
                # Check AI evolution
                if status['ai_control'] and status['ai_control']['evolution_count'] > 0:
                    evolution = status['ai_control']['evolution_count']
                    performance = status['ai_control']['performance_score']
                    
                    if evolution % 10 == 0:  # Log every 10 evolutions
                        logger.info(f"🧠 AI Evolution #{evolution} | Performance: {performance:.3f}")
                
                # Check restart rate
                if status['total_restarts'] > 0 and status['total_restarts'] % 5 == 0:
                    logger.warning(f"🔄 High restart activity: {status['total_restarts']} total restarts")
                
                # System health check
                await self.system_health_check(status)
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Master monitoring error: {e}")
                await asyncio.sleep(10)
    
    async def system_health_check(self, status: Dict):
        """Comprehensive system health check"""
        issues = []
        
        # Check module health
        for name, module_status in status['modules'].items():
            if module_status['status'] == "crashed":
                issues.append(f"Module {name} crashed")
            elif module_status['status'] == "stopped":
                issues.append(f"Module {name} stopped")
        
        # Check AI performance
        if status['ai_control']:
            performance = status['ai_control']['performance_score']
            if performance < 0.3:
                issues.append(f"Low AI performance: {performance:.3f}")
        
        # Report issues
        if issues:
            logger.warning(f"⚠️ System health issues detected:")
            for issue in issues:
                logger.warning(f"   • {issue}")
    
    async def display_system_status(self):
        """Display comprehensive system status"""
        status = self.orchestrator.get_system_status()
        
        print("\n" + "="*80)
        print("🎛️ MASTER CONTROL SYSTEM - SELF-DEVELOPING AI")
        print("="*80)
        print(f"🚦 System Health: {status['system_health']}")
        print(f"⏱️ Uptime: {status['uptime']}")
        print(f"🔄 Total Restarts: {status['total_restarts']}")
        
        print(f"\n🧠 AI Capabilities:")
        for capability, enabled in self.capabilities.items():
            status_icon = "✅" if enabled else "❌"
            print(f"   {status_icon} {capability.replace('_', ' ').title()}")
        
        print(f"\n📦 Active Modules:")
        for name, module_status in status['modules'].items():
            status_icon = "🟢" if module_status['status'] == 'running' else "🔴"
            print(f"   {status_icon} {name}: {module_status['status']}")
        
        if status['ai_control']:
            ai = status['ai_control']
            print(f"\n🧠 AI Control Status:")
            print(f"   📊 Evolution Count: {ai['evolution_count']}")
            print(f"   📈 Performance Score: {ai['performance_score']:.3f}")
            print(f"   🤖 Autonomous Mode: {'Active' if self.orchestrator.ai_control.autonomous_mode else 'Inactive'}")
        
        print("="*80)
        print("🎯 SYSTEM READY FOR AUTONOMOUS OPERATION")
        print("="*80)
    
    async def command_interface(self):
        """Interactive command interface"""
        logger.info("💻 Command interface ready")
        
        while self.running:
            try:
                await asyncio.sleep(1)
                
                # Check for user commands (simplified for this demo)
                # In a full implementation, this would handle user input
                
            except Exception as e:
                logger.error(f"Command interface error: {e}")
                await asyncio.sleep(5)
    
    async def continuous_optimization(self):
        """Continuous system optimization"""
        logger.info("⚡ Continuous optimization started")
        
        while self.running:
            try:
                # Optimize AI parameters
                if self.orchestrator.ai_control:
                    ai = self.orchestrator.ai_control
                    
                    # Adaptive optimization based on performance
                    if ai.state.performance_score < 0.5:
                        # Reduce risk during poor performance
                        ai.state.risk_tolerance *= 0.99
                        logger.info("🔧 Reduced risk tolerance due to performance")
                    
                    elif ai.state.performance_score > 0.8:
                        # Increase risk during good performance
                        ai.state.risk_tolerance = min(ai.state.risk_tolerance * 1.01, 0.05)
                        logger.info("🔧 Increased risk tolerance due to performance")
                
                await asyncio.sleep(300)  # Optimize every 5 minutes
                
            except Exception as e:
                logger.error(f"Optimization error: {e}")
                await asyncio.sleep(60)
    
    async def save_master_state(self):
        """Save complete master system state"""
        try:
            master_state = {
                'timestamp': datetime.now().isoformat(),
                'system_start_time': self.start_time.isoformat(),
                'capabilities': self.capabilities,
                'orchestrator_state': self.orchestrator.get_system_status(),
                'ai_state': asdict(self.orchestrator.ai_control.state) if self.orchestrator.ai_control else None
            }
            
            with open('/Users/alep/Downloads/master_state.json', 'w') as f:
                json.dump(master_state, f, indent=2)
            
            logger.info("💾 Master state saved")
            
        except Exception as e:
            logger.error(f"Failed to save master state: {e}")
    
    async def run_master_system(self):
        """Run the complete master system"""
        logger.info("🎛️ STARTING MASTER CONTROL SYSTEM")
        
        try:
            # Initialize complete system
            await self.initialize_complete_system()
            
            # Start all background tasks
            tasks = [
                asyncio.create_task(self.command_interface()),
                asyncio.create_task(self.continuous_optimization()),
                asyncio.create_task(self.save_master_state_periodically())
            ]
            
            # Wait for system to run
            while self.running:
                await asyncio.sleep(1)
            
            # Cleanup
            for task in tasks:
                task.cancel()
            
            await self.orchestrator.emergency_shutdown()
            
        except Exception as e:
            logger.error(f"Master system error: {e}")
            await self.orchestrator.emergency_shutdown()
    
    async def save_master_state_periodically(self):
        """Save master state periodically"""
        while self.running:
            try:
                await self.save_master_state()
                await asyncio.sleep(1800)  # Save every 30 minutes
            except Exception as e:
                logger.error(f"Periodic save error: {e}")
                await asyncio.sleep(300)

def display_startup_banner():
    """Display system startup banner"""
    print("""
    🎛️ MASTER CONTROL SYSTEM
    ════════════════════════════════════════════════════════════════
    
    🤖 SELF-DEVELOPING AI TRADING SYSTEM
    🧠 Autonomous Control & Learning
    🏛️ Trading Governance & Risk Management
    📊 Real-time Optimization
    🛡️ Safety Protocols & Emergency Controls
    
    ════════════════════════════════════════════════════════════════
    
    Initializing Complete System...
    """)
    
    time.sleep(2)

async def main():
    """Main entry point"""
    display_startup_banner()
    
    # Create and run master control system
    master_system = MasterControlSystem()
    
    try:
        await master_system.run_master_system()
    except KeyboardInterrupt:
        print("\n🎛️ Master Control System stopped by user")
        logger.info("System stopped by user")
    except Exception as e:
        print(f"\n❌ Master Control System error: {e}")
        logger.error(f"System error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
