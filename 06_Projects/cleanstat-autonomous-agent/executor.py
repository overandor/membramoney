"""
Executor - Executes domain-specific actions
5 actions only: load_observation, process_image, create_observation_payload, send_to_cleanstat, finish
"""

import os
import time
import json
from pathlib import Path
from typing import Dict, Any, Optional
from PIL import Image
import requests

from governor import ExecutionResult


class Executor:
    """Executes autonomous agent actions"""
    
    def __init__(self, cleanstat_api_url: str, cleanstat_api_key: str):
        self.cleanstat_api_url = cleanstat_api_url.rstrip('/')
        self.cleanstat_api_key = cleanstat_api_key
        self.headers = {
            "Authorization": f"Bearer {cleanstat_api_key}",
            "Content-Type": "application/json"
        }
    
    def execute(self, action: str, input_data: Dict[str, Any]) -> ExecutionResult:
        """Execute an action and return the result"""
        start_time = time.perf_counter()
        
        try:
            if action == "load_observation":
                result = self._load_observation(input_data)
            elif action == "process_image":
                result = self._process_image(input_data)
            elif action == "create_observation_payload":
                result = self._create_observation_payload(input_data)
            elif action == "send_to_cleanstat":
                result = self._send_to_cleanstat(input_data)
            elif action == "finish":
                result = self._finish(input_data)
            else:
                return ExecutionResult(
                    status="error",
                    action=action,
                    input_data=input_data,
                    error=f"Unknown action: {action}"
                )
            
            duration_ms = (time.perf_counter() - start_time) * 1000
            result.duration_ms = duration_ms
            
            return result
            
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return ExecutionResult(
                status="error",
                action=action,
                input_data=input_data,
                error=str(e),
                duration_ms=duration_ms
            )
    
    def _load_observation(self, input_data: Dict[str, Any]) -> ExecutionResult:
        """Load observation from structured input"""
        observation_id = input_data.get("observation_id")
        
        if not observation_id:
            return ExecutionResult(
                status="error",
                action="load_observation",
                input_data=input_data,
                error="Missing observation_id"
            )
        
        # In real implementation, load from database or file
        # For now, return the input as the loaded data
        return ExecutionResult(
            status="success",
            action="load_observation",
            input_data=input_data,
            output_data=input_data
        )
    
    def _process_image(self, input_data: Dict[str, Any]) -> ExecutionResult:
        """Process image with AI classification"""
        image_path = input_data.get("image_path")
        
        if not image_path:
            return ExecutionResult(
                status="error",
                action="process_image",
                input_data=input_data,
                error="Missing image_path"
            )
        
        # Check if image exists
        if not Path(image_path).exists():
            return ExecutionResult(
                status="error",
                action="process_image",
                input_data=input_data,
                error=f"Image not found: {image_path}"
            )
        
        # Load image
        try:
            img = Image.open(image_path)
            width, height = img.size
        except Exception as e:
            return ExecutionResult(
                status="error",
                action="process_image",
                input_data=input_data,
                error=f"Failed to load image: {e}"
            )
        
        # In real implementation, use AI model here
        # For now, simulate classification
        # TODO: Integrate with actual AI model (Groq, Hugging Face, etc.)
        classification = "cigarette_butts"  # Simulated
        count = 5  # Simulated
        confidence = 0.85  # Simulated
        
        output = {
            "classification": classification,
            "estimated_count": count,
            "confidence": confidence,
            "image_width": width,
            "image_height": height
        }
        
        return ExecutionResult(
            status="success",
            action="process_image",
            input_data=input_data,
            output_data=output
        )
    
    def _create_observation_payload(self, input_data: Dict[str, Any]) -> ExecutionResult:
        """Create CleanStat observation payload"""
        observation_id = input_data.get("observation_id")
        image_result = input_data.get("image_result", {})
        location = input_data.get("location", {})
        
        if not observation_id:
            return ExecutionResult(
                status="error",
                action="create_observation_payload",
                input_data=input_data,
                error="Missing observation_id"
            )
        
        # Build CleanStat format payload
        payload = {
            "id": observation_id,
            "image_cid": f"ipfs://{observation_id}",  # In real implementation, upload to IPFS
            "gps_lat": location.get("lat"),
            "gps_lon": location.get("lng"),
            "fill_level": image_result.get("estimated_count", 0),
            "confidence": image_result.get("confidence", 0.0),
            "status": "pending_verification"
        }
        
        return ExecutionResult(
            status="success",
            action="create_observation_payload",
            input_data=input_data,
            output_data={"payload": payload}
        )
    
    def _send_to_cleanstat(self, input_data: Dict[str, Any]) -> ExecutionResult:
        """Send observation to CleanStat backend"""
        payload = input_data.get("payload")
        
        if not payload:
            return ExecutionResult(
                status="error",
                action="send_to_cleanstat",
                input_data=input_data,
                error="Missing payload"
            )
        
        # Send to CleanStat API
        url = f"{self.cleanstat_api_url}/observations"
        
        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            return ExecutionResult(
                status="success",
                action="send_to_cleanstat",
                input_data=input_data,
                output_data=result,
                cost_usd=0.001  # Simulated API cost
            )
            
        except requests.exceptions.RequestException as e:
            return ExecutionResult(
                status="error",
                action="send_to_cleanstat",
                input_data=input_data,
                error=f"API request failed: {e}"
            )
    
    def _finish(self, input_data: Dict[str, Any]) -> ExecutionResult:
        """Finish the task"""
        return ExecutionResult(
            status="done",
            action="finish",
            input_data=input_data,
            output_data={"message": "Task completed successfully"}
        )
