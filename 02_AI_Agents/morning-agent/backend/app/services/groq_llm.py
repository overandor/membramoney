from groq import Groq
from ..config import settings

class GroqLLMService:
    """Groq LLM service for text processing"""
    
    def __init__(self):
        if not settings.groq_api_key:
            raise ValueError("GROQ_API_KEY not set in environment variables")
        self.client = Groq(api_key=settings.groq_api_key)
        self.model = settings.groq_model
    
    async def process(self, text: str, instructions: str, conversation_history: list = None) -> str:
        """
        Process text with Groq LLM
        
        Args:
            text: Input text from caller
            instructions: Task instructions
            conversation_history: Optional conversation history for context
        
        Returns:
            str: LLM response
        """
        # Build messages
        messages = [
            {
                "role": "system",
                "content": f"{settings.disclosure_line}\n\nYou are a phone agent. Complete the task if possible. Do not claim to be the user.\n\nTask instructions: {instructions}"
            }
        ]
        
        # Add conversation history if provided
        if conversation_history:
            messages.extend(conversation_history)
        
        # Add current user input
        messages.append({
            "role": "user",
            "content": text
        })
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=512,
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"Groq LLM error: {str(e)}")
    
    async def summarize_transcript(self, transcript: str, instructions: str) -> str:
        """
        Summarize a call transcript
        
        Args:
            transcript: Full transcript of the call
            instructions: Original task instructions
        
        Returns:
            str: Summary of the call outcome
        """
        messages = [
            {
                "role": "system",
                "content": "You are a phone call summarizer. Summarize whether the task was completed, any action items, and the outcome."
            },
            {
                "role": "user",
                "content": f"Task: {instructions}\n\nTranscript:\n{transcript}\n\nProvide a concise summary (max 200 words)."
            }
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=200,
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"Groq summary error: {str(e)}")
    
    async def check_task_completion(self, transcript: str, instructions: str) -> dict:
        """
        Check if a task was completed based on transcript
        
        Args:
            transcript: Call transcript
            instructions: Task instructions
        
        Returns:
            dict: {"completed": bool, "reason": str, "action_items": list}
        """
        messages = [
            {
                "role": "system",
                "content": "You analyze phone call transcripts to determine if a task was completed. Respond in JSON format with: completed (boolean), reason (string), action_items (list of strings)."
            },
            {
                "role": "user",
                "content": f"Task: {instructions}\n\nTranscript:\n{transcript}\n\nAnalyze and respond in JSON."
            }
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,
                max_tokens=300,
                response_format={"type": "json_object"}
            )
            import json
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            # Fallback if JSON parsing fails
            return {
                "completed": False,
                "reason": f"Could not analyze: {str(e)}",
                "action_items": []
            }

# Singleton instance
_groq_llm_service = None

def get_groq_llm() -> GroqLLMService:
    """Get or create Groq LLM service singleton"""
    global _groq_llm_service
    if _groq_llm_service is None:
        _groq_llm_service = GroqLLMService()
    return _groq_llm_service
