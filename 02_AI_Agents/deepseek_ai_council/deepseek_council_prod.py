#!/usr/bin/env python3
"""
DEEPSEEK AGENT COUNCIL - PRODUCTION VERSION
Multi-Agent Discussion System using Local DeepSeek
Handles hardware issues gracefully
"""

import asyncio
import json
import time
import logging
import subprocess
import requests
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import platform

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - DEEPSEEK-COUNCIL - %(message)s',
    handlers=[
        logging.FileHandler('/Users/alep/Downloads/deepseek_council_prod.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class Agent:
    id: str
    name: str
    role: str
    personality: str
    expertise: List[str]
    status: str = "idle"
    last_message: str = ""

@dataclass
class CouncilMeeting:
    timestamp: str
    topic: str
    messages: List[Dict]
    decision: Optional[str] = None

class OllamaManager:
    """Manages Ollama connection with hardware issue handling"""
    
    def __init__(self):
        self.base_url = "http://localhost:11434"
        self.available = False
        self.issues = []
        self.working_model = None
        
    async def diagnose(self) -> Dict:
        """Diagnose Ollama installation and hardware"""
        diagnosis = {
            "ollama_running": False,
            "models_available": [],
            "hardware_issues": [],
            "recommended_fixes": [],
            "can_run": False
        }
        
        # Check if Ollama is running
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                diagnosis["ollama_running"] = True
                models = response.json().get('models', [])
                diagnosis["models_available"] = [m['name'] for m in models]
        except Exception as e:
            diagnosis["hardware_issues"].append(f"Ollama connection failed: {e}")
            diagnosis["recommended_fixes"].append("Start Ollama: ollama serve")
        
        # Check hardware
        if platform.system() == "Darwin":
            # macOS specific checks
            diagnosis["recommended_fixes"].extend([
                "Run in CPU mode: export OLLAMA_NO_GPU=1 && ollama serve",
                "Update Ollama: curl -fsSL https://ollama.com/install.sh | sh",
                "Check Metal compatibility with your Mac model"
            ])
        
        # Test each model
        for model in diagnosis["models_available"]:
            try:
                test_response = requests.post(
                    f"{self.base_url}/api/generate",
                    json={"model": model, "prompt": "Hi", "stream": False},
                    timeout=10
                )
                if test_response.status_code == 200:
                    self.working_model = model
                    diagnosis["can_run"] = True
                    break
            except:
                continue
        
        return diagnosis
    
    async def generate(self, prompt: str, model: str = None) -> Optional[str]:
        """Generate with fallback"""
        if not model:
            model = self.working_model or "llama3.2:1b"
        
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=30
            )
            if response.status_code == 200:
                return response.json().get('response', '')
        except Exception as e:
            logger.error(f"Generation failed: {e}")
        
        return None

class DeepSeekCouncilProd:
    """Production-ready DeepSeek Council"""
    
    def __init__(self):
        self.ollama = OllamaManager()
        self.agents = self._create_agents()
        self.meetings = []
        self.mode = "real"  # "real" or "diagnostic"
        
    def _create_agents(self) -> Dict[str, Agent]:
        """Create diverse agents"""
        return {
            "strategist": Agent(
                id="strategist",
                name="Strategos",
                role="strategist",
                personality="Analytical and forward-thinking",
                expertise=["market analysis", "strategic planning"]
            ),
            "executor": Agent(
                id="executor",
                name="Executor",
                role="executor", 
                personality="Action-oriented and efficient",
                expertise=["trade execution", "operations"]
            ),
            "analyst": Agent(
                id="analyst",
                name="Analytica",
                role="analyst",
                personality="Detail-oriented and data-driven",
                expertise=["data analysis", "pattern recognition"]
            ),
            "monitor": Agent(
                id="monitor",
                name="Vigil",
                role="monitor",
                personality="Vigilant and cautious",
                expertise=["system monitoring", "risk detection"]
            )
        }
    
    async def run_meeting(self, topic: str) -> Optional[CouncilMeeting]:
        """Run a complete council meeting"""
        
        # First, diagnose Ollama
        diagnosis = await self.ollama.diagnose()
        
        if not diagnosis["can_run"]:
            logger.error("❌ Cannot run council meeting - Ollama not working")
            logger.error("Issues found:")
            for issue in diagnosis["hardware_issues"]:
                logger.error(f"  - {issue}")
            logger.error("Recommended fixes:")
            for fix in diagnosis["recommended_fixes"]:
                logger.error(f"  - {fix}")
            
            # Create diagnostic meeting
            return self._create_diagnostic_meeting(topic, diagnosis)
        
        # Run real meeting
        logger.info(f"✅ Running REAL council meeting with {len(self.agents)} agents")
        return await self._run_real_meeting(topic)
    
    async def _run_real_meeting(self, topic: str) -> CouncilMeeting:
        """Run actual meeting with DeepSeek"""
        meeting = CouncilMeeting(
            timestamp=datetime.now().isoformat(),
            topic=topic,
            messages=[]
        )
        
        # Round 1: All agents speak
        context = f"Topic: {topic}\n\n"
        
        for agent_id, agent in self.agents.items():
            logger.info(f"🎭 {agent.name} is speaking...")
            
            prompt = f"""You are {agent.name}, a {agent.role} with expertise in {', '.join(agent.expertise)}.
Your personality: {agent.personality}

Current discussion:
{context}

Provide your perspective on the topic (2-3 sentences max)."""
            
            response = await self.ollama.generate(prompt)
            
            if response:
                agent.last_message = response
                message = {
                    "agent": agent.name,
                    "role": agent.role,
                    "message": response,
                    "timestamp": datetime.now().isoformat()
                }
                meeting.messages.append(message)
                context += f"{agent.name}: {response}\n"
                
                logger.info(f"  \"{response[:100]}...\"")
            else:
                logger.warning(f"⚠️  {agent.name} failed to respond")
            
            await asyncio.sleep(1)
        
        # Reach consensus
        consensus_prompt = f"""Based on this discussion:
{context}

Provide a final consensus decision (1-2 sentences) that addresses the topic."""
        
        decision = await self.ollama.generate(consensus_prompt)
        if decision:
            meeting.decision = decision
            logger.info(f"✅ Consensus reached: {decision}")
        
        self.meetings.append(meeting)
        return meeting
    
    def _create_diagnostic_meeting(self, topic: str, diagnosis: Dict) -> CouncilMeeting:
        """Create diagnostic meeting when Ollama fails"""
        meeting = CouncilMeeting(
            timestamp=datetime.now().isoformat(),
            topic=f"[DIAGNOSTIC] {topic}",
            messages=[],
            decision="DIAGNOSTIC MODE - Ollama hardware issues detected"
        )
        
        # Add diagnostic messages
        meeting.messages.append({
            "agent": "System",
            "role": "diagnostic",
            "message": f"Ollama diagnosis: {diagnosis}",
            "timestamp": datetime.now().isoformat()
        })
        
        return meeting

async def main():
    """Main execution"""
    print("\n" + "="*70)
    print("🏛️  DEEPSEEK AGENT COUNCIL - PRODUCTION")
    print("Multi-Agent System with Hardware Diagnostics")
    print("="*70 + "\n")
    
    council = DeepSeekCouncilProd()
    
    # Diagnose first
    print("🔍 Diagnosing Ollama...")
    diagnosis = await council.ollama.diagnose()
    
    print(f"\n📊 Diagnosis Results:")
    print(f"  Ollama running: {diagnosis['ollama_running']}")
    print(f"  Models available: {diagnosis['models_available']}")
    print(f"  Can run: {diagnosis['can_run']}")
    
    if diagnosis['hardware_issues']:
        print(f"\n⚠️  Issues found:")
        for issue in diagnosis['hardware_issues']:
            print(f"    - {issue}")
    
    if diagnosis['recommended_fixes']:
        print(f"\n🔧 Recommended fixes:")
        for fix in diagnosis['recommended_fixes']:
            print(f"    - {fix}")
    
    # Try to run meeting
    print(f"\n{'='*70}")
    print("🚀 Starting Council Meeting")
    print(f"{'='*70}\n")
    
    meeting = await council.run_meeting("How should we optimize the trading system?")
    
    if meeting:
        print(f"\n📋 Meeting Summary:")
        print(f"  Topic: {meeting.topic}")
        print(f"  Messages: {len(meeting.messages)}")
        print(f"  Decision: {meeting.decision or 'No consensus'}")
        
        if meeting.messages:
            print(f"\n💬 Discussion:")
            for msg in meeting.messages[:5]:  # Show first 5
                print(f"\n  {msg['agent']} ({msg['role']}):")
                print(f"    \"{msg['message'][:150]}...\"")
    
    print(f"\n{'='*70}")

if __name__ == "__main__":
    asyncio.run(main())
