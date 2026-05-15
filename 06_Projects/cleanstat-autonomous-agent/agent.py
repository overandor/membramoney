"""
Agent - Plans actions and outputs strict JSON
No paragraphs, no explanations - just structured actions
"""

import json
from typing import Dict, Any, Optional
from groq import Groq


class Agent:
    """Autonomous agent that plans actions"""
    
    def __init__(self, groq_api_key: str, model: str = "llama3-70b-8192"):
        self.client = Groq(api_key=groq_api_key)
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
        """
        Plan the next action based on current state
        
        Returns:
            Dict with "action" and "input" keys
        """
        # Build prompt based on current state
        prompt = self._build_prompt(state)
        
        # Get LLM response
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=500
        )
        
        content = response.choices[0].message.content.strip()
        
        # Parse JSON response
        try:
            decision = json.loads(content)
            
            # Validate structure
            if "action" not in decision or "input" not in decision:
                raise ValueError("Missing required fields")
            
            return decision
            
        except json.JSONDecodeError:
            # Fallback to rule-based planning if LLM fails
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
