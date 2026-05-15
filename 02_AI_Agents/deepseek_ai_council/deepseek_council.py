#!/usr/bin/env python3
import os
"""
MULTI-AGENT DEEPSEEK COUNCIL
Real agent discussions through local DeepSeek/Ollama AI
No simulation - actual AI execution
"""

import asyncio
import json
import time
import logging
import subprocess
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import threading
import random

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - DEEPSEEK-COUNCIL - %(message)s',
    handlers=[
        logging.FileHandler('/Users/alep/Downloads/deepseek_council.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class Agent:
    """Agent with unique role and personality"""
    id: str
    name: str
    role: str  # 'strategist', 'executor', 'analyst', 'monitor'
    personality: str
    expertise: List[str]
    status: str = "idle"
    last_message: str = ""
    action_history: List[Dict] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "personality": self.personality,
            "expertise": self.expertise,
            "status": self.status,
            "last_message": self.last_message
        }

@dataclass
class CouncilDiscussion:
    """Discussion record"""
    timestamp: str
    topic: str
    initiator: str
    participants: List[str]
    messages: List[Dict]
    decision: Optional[str] = None
    consensus_reached: bool = False

class DeepSeekConnector:
    """Connects to local DeepSeek/Ollama - NO SIMULATION"""
    
    def __init__(self, model: str = "deepseek-coder:1.3b"):
        self.base_url = "http://localhost:11434"
        self.model = model
        self.available = False
        self.conversation_count = 0
        
        logger.info(f"🔌 DeepSeek Connector initialized: {model}")
    
    async def verify_connection(self) -> bool:
        """Verify real connection to Ollama"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [m['name'] for m in models]
                
                if self.model in model_names:
                    logger.info(f"✅ DeepSeek model '{self.model}' verified and ready")
                    self.available = True
                    return True
                else:
                    logger.warning(f"⚠️  Model '{self.model}' not found. Available: {model_names}")
                    return False
            else:
                logger.error(f"❌ Ollama returned status {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ Cannot connect to Ollama: {e}")
            return False
    
    async def generate_real_response(self, agent: Agent, context: str, topic: str, 
                                   other_agents: List[Agent]) -> str:
        """Generate REAL AI response from local DeepSeek - NO SIMULATION"""
        if not self.available:
            return "[ERROR: DeepSeek not available]"
        
        # Build the prompt for this agent
        other_agent_info = "\n".join([
            f"- {a.name} ({a.role}): {', '.join(a.expertise)}" 
            for a in other_agents if a.id != agent.id
        ])
        
        system_prompt = f"""You are {agent.name}, an AI agent with the following characteristics:

ROLE: {agent.role}
PERSONALITY: {agent.personality}
EXPERTISE: {', '.join(agent.expertise)}

You are participating in a council discussion with other AI agents:
{other_agent_info}

Rules:
1. Stay in character based on your role and personality
2. Provide substantive, actionable input
3. React to what other agents have said
4. Focus on your area of expertise
5. Be concise but thorough (2-4 sentences)
6. If you disagree, explain why and suggest alternatives"""
        
        full_prompt = f"{system_prompt}\n\nCURRENT DISCUSSION:\n{context}\n\nTOPIC: {topic}\n\nYour response as {agent.name}:"
        
        try:
            payload = {
                "model": self.model,
                "prompt": full_prompt,
                "stream": False,
                "max_tokens": 300,
                "temperature": 0.7
            }
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                ai_response = result.get('response', '').strip()
                
                self.conversation_count += 1
                logger.info(f"🧠 {agent.name} generated REAL response ({len(ai_response)} chars)")
                
                return ai_response
            else:
                logger.error(f"❌ DeepSeek error: {response.status_code}")
                return f"[ERROR: DeepSeek returned {response.status_code}]"
                
        except Exception as e:
            logger.error(f"❌ DeepSeek generation failed: {e}")
            return f"[ERROR: {e}]"
    
    async def reach_consensus(self, discussion: CouncilDiscussion) -> Optional[str]:
        """Use DeepSeek to analyze discussion and reach consensus"""
        if not self.available:
            return None
        
        # Build conversation history
        conversation = "\n\n".join([
            f"{msg['agent']}: {msg['message']}" 
            for msg in discussion.messages
        ])
        
        prompt = f"""Analyze this multi-agent discussion and determine if consensus can be reached:

TOPIC: {discussion.topic}

CONVERSATION:
{conversation}

Based on the discussion above:
1. Summarize the key points of agreement
2. Identify any remaining disagreements
3. Propose a final decision or action
4. State whether consensus is reached (yes/no)

Respond with JSON:
{{
    "consensus_reached": true/false,
    "summary": "brief summary",
    "proposed_action": "specific action to take",
    "reasoning": "explanation"
}}"""
        
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "max_tokens": 400,
                "temperature": 0.5
            }
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                response_text = result.get('response', '')
                
                # Try to extract JSON
                try:
                    start_idx = response_text.find('{')
                    end_idx = response_text.rfind('}') + 1
                    if start_idx != -1 and end_idx != -1:
                        json_str = response_text[start_idx:end_idx]
                        decision_data = json.loads(json_str)
                        
                        logger.info(f"✅ Consensus analysis complete: {decision_data.get('consensus_reached')}")
                        return decision_data
                except json.JSONDecodeError:
                    logger.warning("⚠️  Could not parse consensus JSON")
                    return None
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Consensus analysis failed: {e}")
            return None

class AgentCouncil:
    """Council of agents that discuss and make decisions"""
    
    def __init__(self):
        self.deepseek = DeepSeekConnector()
        self.agents: Dict[str, Agent] = {}
        self.discussions: List[CouncilDiscussion] = []
        self.current_discussion: Optional[CouncilDiscussion] = None
        self.decision_history: List[Dict] = []
        
        self._create_agents()
        
        logger.info("🏛️ Agent Council initialized")
    
    def _create_agents(self):
        """Create diverse agents with different roles"""
        agents_config = [
            {
                "id": "strategist_01",
                "name": "Strategos",
                "role": "strategist",
                "personality": "Analytical, forward-thinking, risk-aware",
                "expertise": ["market analysis", "risk assessment", "strategic planning"]
            },
            {
                "id": "executor_01", 
                "name": "Executor",
                "role": "executor",
                "personality": "Action-oriented, efficient, practical",
                "expertise": ["trade execution", "order management", "system operations"]
            },
            {
                "id": "analyst_01",
                "name": "Analytica", 
                "role": "analyst",
                "personality": "Detail-oriented, data-driven, skeptical",
                "expertise": ["data analysis", "pattern recognition", "performance metrics"]
            },
            {
                "id": "monitor_01",
                "name": "Vigil",
                "role": "monitor",
                "personality": "Vigilant, cautious, systematic",
                "expertise": ["system monitoring", "error detection", "safety protocols"]
            },
            {
                "id": "innovator_01",
                "name": "Innovator",
                "role": "innovator", 
                "personality": "Creative, experimental, optimistic",
                "expertise": ["optimization", "new strategies", "adaptation"]
            }
        ]
        
        for config in agents_config:
            agent = Agent(**config)
            self.agents[agent.id] = agent
            logger.info(f"👤 Agent created: {agent.name} ({agent.role})")
    
    async def initiate_discussion(self, topic: str, initiator_id: str) -> CouncilDiscussion:
        """Start a new discussion"""
        initiator = self.agents.get(initiator_id)
        
        discussion = CouncilDiscussion(
            timestamp=datetime.now().isoformat(),
            topic=topic,
            initiator=initiator.name if initiator else "System",
            participants=list(self.agents.keys()),
            messages=[]
        )
        
        self.current_discussion = discussion
        logger.info(f"📢 Discussion initiated: '{topic}' by {discussion.initiator}")
        
        return discussion
    
    async def run_agent_discussion_round(self, topic: str, rounds: int = 2) -> CouncilDiscussion:
        """Run a complete discussion round with all agents"""
        discussion = await self.initiate_discussion(topic, "strategist_01")
        
        logger.info(f"🔄 Starting discussion with {len(self.agents)} agents for {rounds} rounds")
        
        for round_num in range(rounds):
            logger.info(f"\n{'='*60}")
            logger.info(f"🗣️  DISCUSSION ROUND {round_num + 1}/{rounds}")
            logger.info(f"{'='*60}\n")
            
            # Build context from previous messages
            context = "\n".join([
                f"{msg['agent']}: {msg['message']}" 
                for msg in discussion.messages[-10:]  # Last 10 messages
            ])
            
            # Each agent speaks
            for agent_id, agent in self.agents.items():
                agent.status = "speaking"
                
                # Get REAL response from DeepSeek
                other_agents = [a for a in self.agents.values() if a.id != agent.id]
                response = await self.deepseek.generate_real_response(
                    agent, context, topic, other_agents
                )
                
                agent.last_message = response
                agent.status = "idle"
                
                # Record message
                message_record = {
                    "round": round_num + 1,
                    "agent": agent.name,
                    "role": agent.role,
                    "message": response,
                    "timestamp": datetime.now().isoformat()
                }
                discussion.messages.append(message_record)
                
                # Update context for next agent
                context += f"\n{agent.name}: {response}"
                
                # Log the discussion
                logger.info(f"🎭 [{agent.role.upper()}] {agent.name}:")
                logger.info(f"   \"{response}\"")
                logger.info("")
                
                # Small delay between agents
                await asyncio.sleep(0.5)
        
        # Save discussion
        self.discussions.append(discussion)
        
        return discussion
    
    async def make_council_decision(self, discussion: CouncilDiscussion) -> Optional[str]:
        """Analyze discussion and make collective decision"""
        logger.info(f"\n{'='*60}")
        logger.info("🎯 REACHING COUNCIL CONSENSUS")
        logger.info(f"{'='*60}\n")
        
        # Use DeepSeek to analyze and reach consensus
        decision_data = await self.deepseek.reach_consensus(discussion)
        
        if decision_data:
            discussion.decision = decision_data.get('proposed_action')
            discussion.consensus_reached = decision_data.get('consensus_reached', False)
            
            logger.info(f"📊 Consensus Analysis:")
            logger.info(f"   Reached: {discussion.consensus_reached}")
            logger.info(f"   Summary: {decision_data.get('summary')}")
            logger.info(f"   Proposed Action: {discussion.decision}")
            logger.info(f"   Reasoning: {decision_data.get('reasoning')}")
            
            # Record in history
            self.decision_history.append({
                "timestamp": discussion.timestamp,
                "topic": discussion.topic,
                "decision": discussion.decision,
                "consensus": discussion.consensus_reached,
                "participants": len(discussion.participants)
            })
            
            return discussion.decision
        else:
            logger.warning("⚠️  Could not reach consensus")
            return None
    
    async def execute_decision(self, decision: str) -> bool:
        """Execute the council's decision"""
        logger.info(f"\n{'='*60}")
        logger.info(f"⚡ EXECUTING DECISION")
        logger.info(f"{'='*60}")
        logger.info(f"Action: {decision}\n")
        
        # Here you would implement actual execution
        # For now, log that execution would happen
        
        execution_record = {
            "timestamp": datetime.now().isoformat(),
            "decision": decision,
            "executed": True,
            "executor": "System"
        }
        
        logger.info(f"✅ Decision execution recorded")
        
        return True
    
    async def council_meeting(self, topic: str) -> Optional[str]:
        """Complete council meeting: discuss, decide, execute"""
        # Verify DeepSeek is available
        if not await self.deepseek.verify_connection():
            logger.error("❌ DeepSeek not available. Cannot proceed with real AI discussion.")
            return None
        
        logger.info(f"\n{'='*70}")
        logger.info(f"🏛️  DEEPSEEK AGENT COUNCIL MEETING")
        logger.info(f"Topic: {topic}")
        logger.info(f"{'='*70}\n")
        
        # Step 1: Discussion
        discussion = await self.run_agent_discussion_round(topic, rounds=2)
        
        # Step 2: Decision
        decision = await self.make_council_decision(discussion)
        
        # Step 3: Execution (if consensus reached)
        if decision and discussion.consensus_reached:
            await self.execute_decision(decision)
        
        # Summary
        logger.info(f"\n{'='*70}")
        logger.info(f"📋 MEETING SUMMARY")
        logger.info(f"{'='*70}")
        logger.info(f"Topic: {discussion.topic}")
        logger.info(f"Messages exchanged: {len(discussion.messages)}")
        logger.info(f"Consensus reached: {discussion.consensus_reached}")
        logger.info(f"Final decision: {discussion.decision or 'None'}")
        logger.info(f"DeepSeek conversations: {self.deepseek.conversation_count}")
        logger.info(f"{'='*70}\n")
        
        return decision
    
    def get_council_report(self) -> Dict:
        """Get comprehensive council report"""
        return {
            "timestamp": datetime.now().isoformat(),
            "agents": len(self.agents),
            "agent_details": [agent.to_dict() for agent in self.agents.values()],
            "total_discussions": len(self.discussions),
            "total_decisions": len(self.decision_history),
            "deepseek_available": self.deepseek.available,
            "deepseek_model": self.deepseek.model,
            "conversations_count": self.deepseek.conversation_count
        }

async def main():
    """Main DeepSeek Council execution"""
    print("\n" + "="*70)
    print("🏛️  DEEPSEEK AGENT COUNCIL")
    print("Multi-Agent Discussion via Local DeepSeek AI")
    print("NO SIMULATION - Real Ollama Execution")
    print("="*70 + "\n")
    
    # Create council
    council = AgentCouncil()
    
    # Check DeepSeek availability
    if not await council.deepseek.verify_connection():
        print("\n❌ DeepSeek is not available!")
        print("\nTo setup DeepSeek:")
        print("1. Install Ollama: curl -fsSL https://ollama.com/install.sh | sh")
        print("2. Start Ollama: ollama serve")
        print("3. Install model: ollama pull deepseek-coder:1.3b")
        print("\nThen run this script again.")
        return
    
    # List available agents
    print("👥 Council Agents:")
    for agent in council.agents.values():
        print(f"   • {agent.name} ({agent.role}) - {', '.join(agent.expertise)}")
    print("")
    
    # Example council meetings
    topics = [
        "How should we optimize the trading system for better profitability?",
        "What risk management strategies should we implement?",
        "Should we add new trading pairs or focus on existing ones?"
    ]
    
    for topic in topics:
        print(f"\n{'='*70}")
        print(f"Starting council meeting: {topic}")
        print(f"{'='*70}\n")
        
        decision = await council.council_meeting(topic)
        
        if decision:
            print(f"\n✅ Council Decision: {decision}\n")
        else:
            print(f"\n⚠️  No consensus reached\n")
        
        # Pause between meetings
        await asyncio.sleep(3)
    
    # Final report
    report = council.get_council_report()
    print("\n" + "="*70)
    print("📊 FINAL COUNCIL REPORT")
    print("="*70)
    print(f"Total agents: {report['agents']}")
    print(f"Total discussions: {report['total_discussions']}")
    print(f"Total decisions: {report['total_decisions']}")
    print(f"DeepSeek conversations: {report['conversations_count']}")
    print(f"DeepSeek available: {report['deepseek_available']}")
    print("="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
