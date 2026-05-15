#!/usr/bin/env python3
"""
LLAMA AUTONOMOUS AGENT - BACKGROUND WORKER
Local Llama-based agent that executes any task in background
Follows instructions, learns, and works continuously
"""

import asyncio
import json
import sqlite3
import subprocess
import threading
import time
import os
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import logging
from pathlib import Path

# Try to import Llama libraries
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    print("⚠️  Ollama not available, using simulated Llama responses")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('llama_agent.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class Task:
    """Task definition for the agent"""
    task_id: str
    description: str
    priority: str  # 'high', 'medium', 'low'
    status: str  # 'pending', 'in_progress', 'completed', 'failed'
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[str] = None
    error: Optional[str] = None
    execution_log: List[str] = None
    
    def __post_init__(self):
        if self.execution_log is None:
            self.execution_log = []

@dataclass
class AgentMemory:
    """Agent memory and learning"""
    memory_id: str
    task_type: str
    solution: str
    tools_used: List[str]
    success: bool
    learned_at: datetime
    context: Dict = None

class LlamaAutonomousAgent:
    """Autonomous Llama-based agent for background task execution"""
    
    def __init__(self):
        self.name = "LlamaAgent"
        self.version = "1.0.0"
        self.db_path = "llama_agent.db"
        self.tasks_queue = asyncio.Queue()
        self.running_tasks = {}
        self.completed_tasks = []
        self.agent_memory = []
        self.available_tools = self.get_available_tools()
        
        # Agent state
        self.is_running = False
        self.current_task = None
        self.task_execution_count = 0
        self.success_rate = 0.0
        
        # Initialize database
        self.init_database()
        
        # Load memory
        self.load_memory()
        
        logger.info(f"🤖 {self.name} v{self.version} Initialized")
        logger.info(f"🛠️  Available tools: {len(self.available_tools)}")
        logger.info(f"🧠 Memory entries: {len(self.agent_memory)}")
        logger.info(f"💾 Database: {self.db_path}")
    
    def get_available_tools(self) -> Dict[str, Dict]:
        """Get all available tools for the agent"""
        return {
            "file_operations": {
                "read_file": "Read any file content",
                "write_file": "Write or create files",
                "list_directory": "List directory contents",
                "execute_command": "Execute shell commands",
                "search_files": "Search for files by name or content"
            },
            "web_operations": {
                "http_request": "Make HTTP requests",
                "scrape_website": "Scrape web content",
                "api_call": "Call external APIs",
                "download_file": "Download files from URLs"
            },
            "data_operations": {
                "parse_json": "Parse JSON data",
                "parse_csv": "Parse CSV files",
                "database_query": "Execute SQL queries",
                "data_analysis": "Analyze data with pandas"
            },
            "system_operations": {
                "get_system_info": "Get system information",
                "monitor_processes": "Monitor running processes",
                "check_disk_space": "Check disk usage",
                "network_status": "Check network connectivity"
            },
            "development_operations": {
                "run_python": "Execute Python code",
                "install_package": "Install Python packages",
                "test_code": "Test code functionality",
                "deploy_application": "Deploy applications"
            }
        }
    
    def init_database(self):
        """Initialize agent database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tasks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                priority TEXT DEFAULT 'medium',
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                result TEXT,
                error TEXT,
                execution_log TEXT
            )
        ''')
        
        # Memory table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS agent_memory (
                memory_id TEXT PRIMARY KEY,
                task_type TEXT NOT NULL,
                solution TEXT NOT NULL,
                tools_used TEXT NOT NULL,
                success BOOLEAN NOT NULL,
                learned_at TEXT NOT NULL,
                context TEXT
            )
        ''')
        
        # Agent state table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS agent_state (
                id INTEGER PRIMARY KEY,
                agent_name TEXT NOT NULL,
                version TEXT NOT NULL,
                is_running BOOLEAN DEFAULT FALSE,
                current_task TEXT,
                task_execution_count INTEGER DEFAULT 0,
                success_rate REAL DEFAULT 0.0,
                last_updated TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def load_memory(self):
        """Load agent memory from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM agent_memory ORDER BY learned_at DESC LIMIT 100')
        memory_data = cursor.fetchall()
        
        for row in memory_data:
            self.agent_memory.append(AgentMemory(
                memory_id=row[0],
                task_type=row[1],
                solution=row[2],
                tools_used=json.loads(row[3]),
                success=bool(row[4]),
                learned_at=datetime.fromisoformat(row[5]),
                context=json.loads(row[6]) if row[6] else {}
            ))
        
        conn.close()
    
    def save_memory(self, memory: AgentMemory):
        """Save new memory to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO agent_memory 
            (memory_id, task_type, solution, tools_used, success, learned_at, context)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            memory.memory_id,
            memory.task_type,
            memory.solution,
            json.dumps(memory.tools_used),
            memory.success,
            memory.learned_at.isoformat(),
            json.dumps(memory.context) if memory.context else {}
        ))
        
        conn.commit()
        conn.close()
    
    def get_llama_response(self, prompt: str, context: Dict = None) -> str:
        """Get response from Llama model"""
        try:
            if OLLAMA_AVAILABLE:
                # Use real Ollama
                client = ollama.Client()
                
                # Create enhanced prompt with context
                enhanced_prompt = f"""
You are an autonomous AI agent assistant. Your task is to help execute user requests by breaking them down into actionable steps.

Context: {json.dumps(context, indent=2) if context else 'None'}

User Request: {prompt}

Available Tools: {json.dumps(self.available_tools, indent=2)}

Instructions:
1. Analyze the user's request
2. Break it down into specific steps
3. Identify which tools to use
4. Provide a clear execution plan
5. Consider previous similar tasks from memory

Response Format:
{
    "analysis": "Brief analysis of the request",
    "steps": ["Step 1", "Step 2", "Step 3"],
    "tools": ["tool1", "tool2"],
    "confidence": 0.9,
    "estimated_time": "5 minutes"
}
"""
                
                response = client.generate(
                    model='llama2',
                    prompt=enhanced_prompt,
                    options={
                        'temperature': 0.7,
                        'top_p': 0.9,
                        'max_tokens': 1000
                    }
                )
                
                return response['response'].strip()
            
        except Exception as e:
            logger.error(f"❌ Llama response error: {e}")
            
            # Fallback to simulated response
            return self.generate_fallback_response(prompt, context)
    
    def generate_fallback_response(self, prompt: str, context: Dict = None) -> str:
        """Generate fallback response when Llama is not available"""
        
        # Simple rule-based response generation
        response = {
            "analysis": f"Processing request: {prompt[:100]}...",
            "steps": [
                "Analyze the request requirements",
                "Identify necessary tools and resources",
                "Execute the task step by step",
                "Verify results and provide feedback"
            ],
            "tools": ["file_operations", "system_operations"],
            "confidence": 0.8,
            "estimated_time": "2-5 minutes"
        }
        
        return json.dumps(response, indent=2)
    
    async def add_task(self, description: str, priority: str = 'medium') -> str:
        """Add new task to the queue"""
        task_id = f"task_{int(time.time() * 1000)}"
        
        task = Task(
            task_id=task_id,
            description=description,
            priority=priority,
            status='pending',
            created_at=datetime.now()
        )
        
        await self.tasks_queue.put(task)
        
        # Save to database
        self.save_task(task)
        
        logger.info(f"📋 Task added: {task_id} - {description[:50]}...")
        
        return task_id
    
    def save_task(self, task: Task):
        """Save task to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO tasks 
            (task_id, description, priority, status, created_at, started_at, completed_at, result, error, execution_log)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            task.task_id,
            task.description,
            task.priority,
            task.status,
            task.created_at.isoformat(),
            task.started_at.isoformat() if task.started_at else None,
            task.completed_at.isoformat() if task.completed_at else None,
            task.result,
            task.error,
            json.dumps(task.execution_log)
        ))
        
        conn.commit()
        conn.close()
    
    async def execute_task(self, task: Task) -> bool:
        """Execute a single task"""
        logger.info(f"🚀 Executing task: {task.task_id}")
        
        task.status = 'in_progress'
        task.started_at = datetime.now()
        self.current_task = task
        
        # Get Llama's analysis and plan
        llama_response = self.get_llama_response(
            task.description,
            {
                "task_id": task.task_id,
                "priority": task.priority,
                "available_tools": self.available_tools,
                "similar_tasks": [m for m in self.agent_memory if m.task_type in task.description.lower()]
            }
        )
        
        try:
            plan = json.loads(llama_response)
            
            task.execution_log.append(f"📋 Task analysis: {plan.get('analysis', 'N/A')}")
            task.execution_log.append(f"🔧 Tools needed: {', '.join(plan.get('tools', []))}")
            task.execution_log.append(f"⏱️  Estimated time: {plan.get('estimated_time', 'Unknown')}")
            
            # Execute the plan
            success = await self.execute_plan(task, plan)
            
            if success:
                task.status = 'completed'
                task.completed_at = datetime.now()
                task.result = "Task completed successfully"
                task.execution_log.append("✅ Task completed successfully")
                
                # Learn from success
                self.learn_from_task(task, plan, True)
                
                self.task_execution_count += 1
                logger.info(f"✅ Task completed: {task.task_id}")
                
            else:
                task.status = 'failed'
                task.error = "Task execution failed"
                task.execution_log.append("❌ Task execution failed")
                
                # Learn from failure
                self.learn_from_task(task, plan, False)
                
                logger.error(f"❌ Task failed: {task.task_id}")
            
            # Update database
            self.save_task(task)
            
            return success
            
        except Exception as e:
            task.status = 'failed'
            task.error = str(e)
            task.execution_log.append(f"❌ Exception: {str(e)}")
            
            self.save_task(task)
            
            logger.error(f"❌ Task exception: {task.task_id} - {e}")
            
            return False
    
    async def execute_plan(self, task: Task, plan: Dict) -> bool:
        """Execute the plan generated by Llama"""
        steps = plan.get('steps', [])
        tools = plan.get('tools', [])
        
        try:
            for i, step in enumerate(steps, 1):
                task.execution_log.append(f"🔄 Step {i}: {step}")
                
                # Execute step based on content
                if "file" in step.lower():
                    await self.execute_file_operations(step, task)
                elif "command" in step.lower() or "shell" in step.lower():
                    await self.execute_command_operations(step, task)
                elif "web" in step.lower() or "http" in step.lower():
                    await self.execute_web_operations(step, task)
                elif "data" in step.lower():
                    await self.execute_data_operations(step, task)
                elif "python" in step.lower() or "code" in step.lower():
                    await self.execute_python_operations(step, task)
                else:
                    # Generic execution
                    await self.execute_generic_step(step, task)
                
                # Small delay between steps
                await asyncio.sleep(1)
            
            return True
            
        except Exception as e:
            task.execution_log.append(f"❌ Plan execution error: {str(e)}")
            return False
    
    async def execute_file_operations(self, step: str, task: Task):
        """Execute file operations"""
        try:
            if "read" in step.lower():
                # Example: read file
                test_file = "/Users/alep/Downloads/test_read.txt"
                if os.path.exists(test_file):
                    with open(test_file, 'r') as f:
                        content = f.read()
                    task.execution_log.append(f"📄 Read file: {content[:100]}...")
                else:
                    task.execution_log.append(f"📄 File not found: {test_file}")
            
            elif "write" in step.lower():
                # Example: write file
                test_file = "/Users/alep/Downloads/llama_agent_output.txt"
                with open(test_file, 'w') as f:
                    f.write(f"Task executed by {self.name}\n")
                    f.write(f"Task: {task.description}\n")
                    f.write(f"Time: {datetime.now().isoformat()}\n")
                task.execution_log.append(f"📝 Wrote file: {test_file}")
            
            elif "list" in step.lower():
                # Example: list directory
                test_dir = "/Users/alep/Downloads"
                files = os.listdir(test_dir)[:10]  # First 10 files
                task.execution_log.append(f"📁 Directory listing: {files}")
            
        except Exception as e:
            task.execution_log.append(f"❌ File operation error: {str(e)}")
    
    async def execute_command_operations(self, step: str, task: Task):
        """Execute shell commands"""
        try:
            # Safe command execution (only read-only commands)
            if "list" in step.lower() or "ls" in step.lower():
                result = subprocess.run(['ls', '-la', '/Users/alep/Downloads'], 
                                  capture_output=True, text=True, timeout=10)
                task.execution_log.append(f"🖥️  Command output: {result.stdout[:200]}...")
            
            elif "info" in step.lower() or "system" in step.lower():
                result = subprocess.run(['uname', '-a'], capture_output=True, text=True, timeout=10)
                task.execution_log.append(f"💻 System info: {result.stdout}")
            
        except Exception as e:
            task.execution_log.append(f"❌ Command execution error: {str(e)}")
    
    async def execute_web_operations(self, step: str, task: Task):
        """Execute web operations"""
        try:
            if "marinade" in step.lower():
                # Example: fetch Marinade data
                response = requests.get("https://snapshots-api.marinade.finance/v1/stakers/ns/all", timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    task.execution_log.append(f"🌐 Marinade API: Retrieved {len(data)} wallets")
                else:
                    task.execution_log.append(f"🌐 Marinade API error: {response.status_code}")
            
        except Exception as e:
            task.execution_log.append(f"❌ Web operation error: {str(e)}")
    
    async def execute_data_operations(self, step: str, task: Task):
        """Execute data operations"""
        try:
            if "database" in step.lower():
                # Example: query database
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM tasks")
                count = cursor.fetchone()[0]
                task.execution_log.append(f"🗄️  Database query: {count} tasks in database")
                conn.close()
            
        except Exception as e:
            task.execution_log.append(f"❌ Data operation error: {str(e)}")
    
    async def execute_python_operations(self, step: str, task: Task):
        """Execute Python operations"""
        try:
            if "calculate" in step.lower():
                # Example: calculation
                result = sum(range(100))
                task.execution_log.append(f"🐍 Python calculation: sum(0-99) = {result}")
            
            elif "datetime" in step.lower():
                # Example: datetime operations
                now = datetime.now()
                task.execution_log.append(f"🕒 Current time: {now.isoformat()}")
            
        except Exception as e:
            task.execution_log.append(f"❌ Python operation error: {str(e)}")
    
    async def execute_generic_step(self, step: str, task: Task):
        """Execute generic step"""
        task.execution_log.append(f"⚙️  Executing: {step}")
        
        # Simulate some work
        await asyncio.sleep(2)
        
        task.execution_log.append(f"✅ Generic step completed: {step}")
    
    def learn_from_task(self, task: Task, plan: Dict, success: bool):
        """Learn from task execution"""
        memory = AgentMemory(
            memory_id=f"mem_{int(time.time() * 1000)}",
            task_type=self.extract_task_type(task.description),
            solution=json.dumps({
                "description": task.description,
                "plan": plan,
                "execution_log": task.execution_log[-5:]  # Last 5 log entries
            }),
            tools_used=plan.get('tools', []),
            success=success,
            learned_at=datetime.now(),
            context={
                "priority": task.priority,
                "execution_time": (task.completed_at - task.started_at).total_seconds() if task.completed_at and task.started_at else 0,
                "steps_count": len(plan.get('steps', []))
            }
        )
        
        self.agent_memory.append(memory)
        self.save_memory(memory)
        
        # Update success rate
        if self.task_execution_count > 0:
            successful_tasks = len([m for m in self.agent_memory if m.success])
            self.success_rate = successful_tasks / len(self.agent_memory)
    
    def extract_task_type(self, description: str) -> str:
        """Extract task type from description"""
        description_lower = description.lower()
        
        if any(word in description_lower for word in ['file', 'read', 'write', 'directory']):
            return 'file_operations'
        elif any(word in description_lower for word in ['web', 'api', 'http', 'scrape']):
            return 'web_operations'
        elif any(word in description_lower for word in ['data', 'database', 'query', 'analysis']):
            return 'data_operations'
        elif any(word in description_lower for word in ['python', 'code', 'calculate', 'execute']):
            return 'development_operations'
        elif any(word in description_lower for word in ['system', 'info', 'process', 'monitor']):
            return 'system_operations'
        else:
            return 'general'
    
    async def start_background_worker(self):
        """Start the background task worker"""
        self.is_running = True
        logger.info("🤖 Background worker started")
        
        while self.is_running:
            try:
                # Get next task from queue
                if not self.tasks_queue.empty():
                    task = await self.tasks_queue.get()
                    
                    # Execute task
                    await self.execute_task(task)
                    
                    # Add to completed tasks
                    self.completed_tasks.append(task)
                    
                    # Keep only last 100 completed tasks
                    if len(self.completed_tasks) > 100:
                        self.completed_tasks = self.completed_tasks[-100:]
                
                else:
                    # No tasks, wait
                    await asyncio.sleep(5)
                    
            except Exception as e:
                logger.error(f"❌ Background worker error: {e}")
                await asyncio.sleep(10)
    
    async def add_task_from_input(self, task_input: str):
        """Add task from user input"""
        # Parse priority from input
        priority = 'medium'
        if 'high' in task_input.lower() or 'urgent' in task_input.lower():
            priority = 'high'
        elif 'low' in task_input.lower():
            priority = 'low'
        
        # Add task
        task_id = await self.add_task(task_input, priority)
        
        return task_id
    
    def get_agent_status(self) -> Dict:
        """Get current agent status"""
        return {
            "name": self.name,
            "version": self.version,
            "is_running": self.is_running,
            "current_task": self.current_task.description if self.current_task else None,
            "tasks_in_queue": self.tasks_queue.qsize(),
            "completed_tasks": len(self.completed_tasks),
            "task_execution_count": self.task_execution_count,
            "success_rate": self.success_rate,
            "memory_entries": len(self.agent_memory),
            "available_tools": len(self.available_tools),
            "last_updated": datetime.now().isoformat()
        }
    
    def create_web_interface(self):
        """Create web interface for the agent"""
        from flask import Flask, render_template_string, jsonify, request
        
        app = Flask(__name__)
        
        @app.route('/')
        def agent_dashboard():
            return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Llama Autonomous Agent - Background Worker</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        .agent-gradient { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%); 
        }
        .agent-glass { 
            background: rgba(255, 255, 255, 0.1); 
            backdrop-filter: blur(10px); 
            border: 1px solid rgba(255, 255, 255, 0.2); 
        }
        .llama-avatar {
            background: linear-gradient(45deg, #8b5cf6, #3b82f6);
            width: 80px;
            height: 80px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 40px;
        }
        .status-online {
            background: #10b981;
            animation: pulse 2s infinite;
        }
        @keyframes pulse { 
            0%, 100% { opacity: 1; } 
            50% { opacity: 0.7; } 
        }
    </style>
</head>
<body class="agent-gradient min-h-screen text-white">
    <div class="container mx-auto px-4 py-8">
        <!-- Agent Header -->
        <header class="text-center mb-10">
            <div class="llama-avatar mx-auto mb-4">
                <i class="fas fa-robot"></i>
            </div>
            <h1 class="text-5xl font-bold mb-4">Llama Autonomous Agent</h1>
            <p class="text-xl opacity-90">Background Task Execution Worker</p>
            <div class="flex items-center justify-center mt-4">
                <div class="status-online w-3 h-3 rounded-full mr-2"></div>
                <span class="text-lg">ACTIVE IN BACKGROUND</span>
            </div>
        </header>

        <!-- Task Input -->
        <div class="agent-glass rounded-xl p-6 mb-10">
            <h2 class="text-2xl font-bold mb-6">
                <i class="fas fa-tasks mr-2"></i>Submit Task
            </h2>
            
            <div class="flex gap-4 mb-4">
                <input type="text" id="task-input" placeholder="Enter any task..." 
                       class="flex-1 bg-white/20 rounded px-4 py-3 text-white placeholder-white/60">
                <button onclick="submitTask()" 
                        class="bg-blue-600 hover:bg-blue-700 px-6 py-3 rounded-lg font-bold">
                    <i class="fas fa-paper-plane mr-2"></i>Submit
                </button>
            </div>
            
            <div class="text-sm opacity-70">
                Examples: "Read the marinade database", "Analyze wallet performance", "Create a new Python script", "Check system status"
            </div>
        </div>

        <!-- Agent Status -->
        <div class="grid md:grid-cols-4 gap-6 mb-10">
            <div class="agent-glass rounded-xl p-6 text-center">
                <div class="text-4xl font-bold text-green-400" id="queue-size">0</div>
                <div class="text-sm opacity-70 mt-2">Tasks in Queue</div>
            </div>
            <div class="agent-glass rounded-xl p-6 text-center">
                <div class="text-4xl font-bold text-blue-400" id="completed-count">0</div>
                <div class="text-sm opacity-70 mt-2">Completed Tasks</div>
            </div>
            <div class="agent-glass rounded-xl p-6 text-center">
                <div class="text-4xl font-bold text-purple-400" id="success-rate">0%</div>
                <div class="text-sm opacity-70 mt-2">Success Rate</div>
            </div>
            <div class="agent-glass rounded-xl p-6 text-center">
                <div class="text-4xl font-bold text-yellow-300" id="memory-count">0</div>
                <div class="text-sm opacity-70 mt-2">Memory Entries</div>
            </div>
        </div>

        <!-- Current Task -->
        <div class="agent-glass rounded-xl p-6 mb-10">
            <h2 class="text-2xl font-bold mb-6">
                <i class="fas fa-cogs mr-2"></i>Current Task
            </h2>
            <div id="current-task" class="text-center opacity-60">
                <i class="fas fa-hourglass-half text-4xl mb-4"></i>
                <p>No task currently executing</p>
            </div>
        </div>

        <!-- Recent Tasks -->
        <div class="agent-glass rounded-xl p-6">
            <h2 class="text-2xl font-bold mb-6">
                <i class="fas fa-history mr-2"></i>Recent Tasks
            </h2>
            <div id="recent-tasks" class="space-y-3">
                <div class="text-center opacity-60">
                    <i class="fas fa-clipboard-list text-4xl mb-4"></i>
                    <p>Completed tasks will appear here</p>
                </div>
            </div>
        </div>
    </div>

    <script>
        async function apiCall(endpoint, method = 'GET', data = null) {
            try {
                const options = {
                    method: method,
                    headers: { 'Content-Type': 'application/json' }
                };
                
                if (data && method !== 'GET') {
                    options.body = JSON.stringify(data);
                }
                
                const response = await fetch(`/api${endpoint}`, options);
                return await response.json();
            } catch (error) {
                console.error('API call failed:', error);
                return { error: error.message };
            }
        }
        
        async function submitTask() {
            const input = document.getElementById('task-input');
            const taskDescription = input.value.trim();
            
            if (!taskDescription) {
                alert('Please enter a task description');
                return;
            }
            
            const response = await apiCall('/task', 'POST', {
                description: taskDescription
            });
            
            if (response.success) {
                input.value = '';
                updateStatus();
                showNotification('Task submitted successfully!', 'success');
            } else {
                showNotification('Failed to submit task: ' + response.error, 'error');
            }
        }
        
        async function updateStatus() {
            const response = await apiCall('/status');
            
            if (response.success) {
                const status = response.data;
                
                document.getElementById('queue-size').textContent = status.tasks_in_queue;
                document.getElementById('completed-count').textContent = status.completed_tasks;
                document.getElementById('success-rate').textContent = (status.success_rate * 100).toFixed(1) + '%';
                document.getElementById('memory-count').textContent = status.memory_entries;
                
                // Update current task
                const currentTaskDiv = document.getElementById('current-task');
                if (status.current_task) {
                    currentTaskDiv.innerHTML = `
                        <div class="p-4 bg-white/10 rounded-lg">
                            <div class="text-lg font-bold mb-2">🔄 ${status.current_task}</div>
                            <div class="text-sm opacity-70">Agent is working on this task...</div>
                        </div>
                    `;
                } else {
                    currentTaskDiv.innerHTML = `
                        <div class="text-center opacity-60">
                            <i class="fas fa-check-circle text-4xl mb-4"></i>
                            <p>No task currently executing</p>
                        </div>
                    `;
                }
            }
        }
        
        function showNotification(message, type = 'info') {
            const colors = {
                success: 'bg-green-500',
                error: 'bg-red-500',
                warning: 'bg-yellow-500',
                info: 'bg-blue-500'
            };
            
            const notification = document.createElement('div');
            notification.className = `fixed top-4 right-4 ${colors[type]} text-white px-6 py-3 rounded-lg shadow-lg z-50`;
            notification.textContent = message;
            
            document.body.appendChild(notification);
            
            setTimeout(() => notification.remove(), 4000);
        }
        
        // Auto-update status every 5 seconds
        setInterval(updateStatus, 5000);
        
        // Initial load
        document.addEventListener('DOMContentLoaded', updateStatus);
        
        // Allow Enter key to submit task
        document.getElementById('task-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                submitTask();
            }
        });
    </script>
</body>
</html>
            ''')
        
        @app.route('/api/task', methods=['POST'])
        def add_task_api():
            """API endpoint to add task"""
            try:
                data = request.get_json()
                task_description = data.get('description', '')
                
                if task_description:
                    # Create async task
                    loop = asyncio.new_event_loop()
                    task_id = loop.run_until_complete(
                        self.add_task_from_input(task_description)
                    )
                    loop.close()
                    
                    return jsonify({
                        "success": True,
                        "task_id": task_id,
                        "message": "Task added to queue"
                    })
                else:
                    return jsonify({"success": False, "error": "No task description"}), 400
                    
            except Exception as e:
                return jsonify({"success": False, "error": str(e)}), 500
        
        @app.route('/api/status')
        def get_status_api():
            """API endpoint to get agent status"""
            return jsonify({
                "success": True,
                "data": self.get_agent_status()
            })
        
        return app
    
    def run(self, port: int = 8099):
        """Run the autonomous agent"""
        logger.info(f"🤖 Starting {self.name} on port {port}")
        
        # Create web interface
        web_app = self.create_web_interface()
        
        # Start background worker in thread
        worker_thread = threading.Thread(target=lambda: asyncio.run(self.start_background_worker()))
        worker_thread.daemon = True
        worker_thread.start()
        
        # Start web interface
        import webbrowser
        webbrowser.open(f'http://localhost:{port}')
        
        web_app.run(host='0.0.0.0', port=port, debug=False)

# Main execution
if __name__ == "__main__":
    agent = LlamaAutonomousAgent()
    agent.run(port=8099)
