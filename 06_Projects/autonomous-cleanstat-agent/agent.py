"""
Agent - Plans actions using Ollama
Outputs strict JSON only - no paragraphs, no explanations
"""

import json
from typing import Dict, Any, Optional
import requests


class Agent:
    """Autonomous agent that plans actions using Ollama"""
    
    def __init__(self, ollama_base_url: str = "http://localhost:11434", model: str = "llama3.1:8b"):
        self.ollama_base_url = ollama_base_url.rstrip('/')
        self.model = model
        self.system_prompt = """You are an autonomous agent for CleanStat environmental intelligence.
Your job is to plan actions for processing waste observations.

You must output ONLY valid JSON in this exact format:
{
  "action": "action_name",
  "input": {
    "key": "value"
  }
}

Available actions:
1. load_observation - Load observation data
2. process_image - Process image with AI
3. create_observation_payload - Create CleanStat payload
4. send_to_cleanstat - Send to backend
5. finish - Complete the task

No explanations. No paragraphs. Only JSON."""
    
    def plan(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Plan the next action based on current state"""
        # Build prompt based on current state
        prompt = self._build_prompt(state)
        
        # Get LLM response from Ollama
        try:
            response = requests.post(
                f"{self.ollama_base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "system": self.system_prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 500
                    }
                },
                timeout=30
            )
            response.raise_for_status()
            content = response.json().get("response", "").strip()
            
            # Parse JSON response
            decision = json.loads(content)
            
            # Validate structure
            if "action" not in decision or "input" not in decision:
                raise ValueError("Missing required fields")
            
            return decision
            
        except Exception as e:
            print(f"LLM failed: {e}, using rule-based fallback")
            return self._rule_based_plan(state)
    
    def _build_prompt(self, state: Dict[str, Any]) -> str:
        """Build prompt for LLM based on current state"""
        current_step = state.get("step", 0)
        observation_id = state.get("observation_id", "")
        image_path = state.get("image_path", "")
        location = state.get("location", {})
        last_action = state.get("last_action", "")
        last_result = state.get("last_result", {})
        
        prompt = f"""Current state:
- Step: {current_step}
- Observation ID: {observation_id}
- Image path: {image_path}
- Location: {location}
- Last action: {last_action}
- Last result status: {last_result.get('status', 'none')}

Plan the next action. Output only JSON."""
        
        return prompt
    
    def _rule_based_plan(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback rule-based planning if LLM fails"""
        current_step = state.get("step", 0)
        
        # Simple state machine
        if current_step == 0:
            return {
                "action": "load_observation",
                "input": {
                    "observation_id": state.get("observation_id")
                }
            }
        elif current_step == 1:
            return {
                "action": "process_image",
                "input": {
                    "image_path": state.get("image_path")
                }
            }
        elif current_step == 2:
            return {
                "action": "create_observation_payload",
                "input": {
                    "observation_id": state.get("observation_id"),
                    "image_result": state.get("image_result", {}),
                    "location": state.get("location", {})
                }
            }
        elif current_step == 3:
            return {
                "action": "send_to_cleanstat",
                "input": {
                    "payload": state.get("payload", {})
                }
            }
        else:
            return {
                "action": "finish",
                "input": {}
            }
