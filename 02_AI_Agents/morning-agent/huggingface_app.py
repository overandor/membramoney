"""
Morning Agent - Hugging Face Gradio App
Web interface for task management (desktop and mobile compatible)
"""

import gradio as gr
import httpx
import json
from typing import List, Dict, Optional
from datetime import datetime

# Configuration - update these for your deployed backend
BACKEND_URL = "http://localhost:8000"  # Change to your deployed backend URL

class MorningAgentClient:
    """Client for interacting with Morning Agent backend"""
    
    def __init__(self, base_url: str = BACKEND_URL):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def fetch_tasks(self) -> List[Dict]:
        """Fetch all tasks"""
        try:
            response = await self.client.get(f"{self.base_url}/tasks")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return [{"error": str(e)}]
    
    async def create_task(self, title: str, instructions: str, phone: str) -> Dict:
        """Create a new task"""
        try:
            payload = {
                "title": title,
                "instructions": instructions,
                "phone_number": phone
            }
            response = await self.client.post(
                f"{self.base_url}/tasks",
                json=payload
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    async def start_task(self, task_id: int) -> Dict:
        """Start a task (initiate call)"""
        try:
            response = await self.client.post(f"{self.base_url}/tasks/{task_id}/start")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    async def get_task(self, task_id: int) -> Dict:
        """Get task details"""
        try:
            response = await self.client.get(f"{self.base_url}/tasks/{task_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    async def close(self):
        """Close the client"""
        await self.client.aclose()

client = MorningAgentClient()

def format_task(task: Dict) -> str:
    """Format task for display"""
    if "error" in task:
        return f"❌ Error: {task['error']}"
    
    status_emoji = {
        "queued": "📋",
        "calling": "📞",
        "completed": "✅",
        "failed": "❌",
        "needs_review": "⚠️"
    }
    
    emoji = status_emoji.get(task.get("status", "queued"), "📋")
    return f"""
**{emoji} {task.get('title', 'Untitled')}**

**Status:** {task.get('status', 'unknown').upper()}
**Phone:** {task.get('phone_number', 'N/A')}
**ID:** {task.get('id', 'N/A')}

**Instructions:**
{task.get('instructions', 'No instructions')}

{f"**Summary:** {task.get('summary', 'No summary')}" if task.get('summary') else ""}
{f"**Transcript:** {task.get('transcript', 'No transcript')[:200]}..." if task.get('transcript') else ""}
**Created:** {task.get('created_at', 'Unknown')}
"""

async def refresh_tasks():
    """Refresh task list"""
    tasks = await client.fetch_tasks()
    if not tasks or ("error" in tasks[0] if tasks else False):
        return "No tasks available or backend not connected."
    
    if not tasks:
        return "No tasks yet. Create your first task below!"
    
    formatted = []
    for task in tasks[:10]:  # Show last 10 tasks
        formatted.append(format_task(task))
    
    return "\n\n---\n\n".join(formatted)

async def create_new_task(title: str, instructions: str, phone: str):
    """Create a new task"""
    if not title or not instructions or not phone:
        return "❌ Please fill in all fields", ""
    
    result = await client.create_task(title, instructions, phone)
    
    if "error" in result:
        return f"❌ Failed to create task: {result['error']}", ""
    
    # Auto-start the task
    start_result = await client.start_task(result["id"])
    
    if "error" in start_result:
        return f"✅ Task created (ID: {result['id']}) but failed to start: {start_result['error']}", ""
    
    return f"✅ Task created and started! ID: {result['id']}", await refresh_tasks()

async def get_task_details(task_id: str):
    """Get details for a specific task"""
    try:
        task_id_int = int(task_id)
        task = await client.get_task(task_id_int)
        return format_task(task)
    except ValueError:
        return "❌ Invalid task ID. Please enter a number."
    except Exception as e:
        return f"❌ Error: {str(e)}"

# Gradio Interface
with gr.Blocks(
    theme=gr.themes.Soft(),
    title="Morning Agent",
    css="""
        .gradio-container {
            max-width: 800px !important;
        }
        .task-card {
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 16px;
            margin: 8px 0;
            background: #fafafa;
        }
    """
) as app:
    
    gr.Markdown(
        """
        # 🌅 Morning Agent
        
        Create tasks and let AI handle phone calls on your behalf.
        
        > ⚠️ **Disclosure**: The AI assistant will disclose it is calling on your behalf.
        """
    )
    
    with gr.Tabs():
        # Task List Tab
        with gr.Tab("📋 Tasks"):
            tasks_output = gr.Markdown(
                value="Loading tasks...",
                label="Recent Tasks"
            )
            refresh_btn = gr.Button("🔄 Refresh", size="sm")
            refresh_btn.click(
                refresh_tasks,
                outputs=tasks_output
            )
        
        # Create Task Tab
        with gr.Tab("➕ New Task"):
            with gr.Group():
                title_input = gr.Textbox(
                    label="Task Title",
                    placeholder="e.g., Schedule dentist appointment"
                )
                phone_input = gr.Textbox(
                    label="Phone Number",
                    placeholder="+1234567890"
                )
                instructions_input = gr.Textbox(
                    label="Instructions",
                    placeholder="What should the AI say/do?",
                    lines=5
                )
                create_btn = gr.Button("📞 Create & Start Call", variant="primary")
                create_output = gr.Markdown()
            
            create_btn.click(
                create_new_task,
                inputs=[title_input, instructions_input, phone_input],
                outputs=[create_output, tasks_output]
            )
        
        # Task Details Tab
        with gr.Tab("🔍 Task Details"):
            task_id_input = gr.Textbox(
                label="Task ID",
                placeholder="Enter task ID number"
            )
            task_details_btn = gr.Button("Get Details")
            task_details_output = gr.Markdown()
            
            task_details_btn.click(
                get_task_details,
                inputs=task_id_input,
                outputs=task_details_output
            )
        
        # Settings Tab
        with gr.Tab("⚙️ Settings"):
            gr.Markdown(
                """
                ### Configuration
                
                **Backend URL:** Currently set to `http://localhost:8000`
                
                To connect to a deployed backend:
                1. Deploy the backend to Render/Fly.io/Railway
                2. Update `BACKEND_URL` in the app code
                3. Redeploy this Space
                
                ### About
                
                This assistant places calls on your behalf using:
                - **Twilio** for phone calls
                - **OpenAI Realtime API** for AI voice
                - **FastAPI** backend for task management
                
                ### Safety
                
                - The AI always discloses it is calling on behalf of the user
                - All calls are logged with transcripts
                - You can review call summaries after each call
                """
            )
    
    # Auto-refresh tasks on load
    app.load(
        refresh_tasks,
        outputs=tasks_output
    )

if __name__ == "__main__":
    app.launch()
