#!/usr/bin/env python3
"""
24/7 Terminal Agent
A background process that executes scheduled terminal commands with logging and task management.
"""

import json
import subprocess
import time
import logging
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import threading
import schedule
from flask import Flask, jsonify, request, Response, stream_with_context


class TerminalAgent:
    def __init__(self, config_path: str = "config.json", state_path: str = "agent_state.json", enable_web: bool = False, web_port: int = 5000):
        self.config_path = Path(config_path)
        self.state_path = Path(state_path)
        self.running = False
        self.tasks: Dict = {}
        self.state = {
            "start_time": None,
            "last_check": None,
            "executed_tasks": []
        }
        self.enable_web = enable_web
        self.web_port = web_port
        self.app = None
        self.web_thread = None
        
        self.setup_logging()
        self.load_config()
        self.load_state()
        
        if self.enable_web:
            self.setup_web_server()
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def setup_web_server(self):
        """Setup Flask web server for remote access."""
        self.app = Flask(__name__)
        
        @self.app.route('/')
        def index():
            return jsonify({
                "status": "running",
                "message": "Terminal Agent Web API",
                "endpoints": {
                    "GET /": "API info",
                    "GET /status": "Agent status",
                    "GET /logs": "Recent logs",
                    "GET /tasks": "List tasks",
                    "POST /execute": "Execute command",
                    "POST /tasks": "Add/update task",
                    "DELETE /tasks/<name>": "Delete task",
                    "GET /terminal": "Web terminal interface"
                }
            })
        
        @self.app.route('/status')
        def get_status():
            return jsonify({
                "running": self.running,
                "start_time": self.state.get("start_time"),
                "last_check": self.state.get("last_check"),
                "scheduled_tasks": len(schedule.jobs),
                "executed_tasks_count": len(self.state.get("executed_tasks", [])),
                "uptime": self.get_uptime()
            })
        
        @self.app.route('/logs')
        def get_logs():
            log_file = Path("logs") / f"terminal_agent_{datetime.now().strftime('%Y%m%d')}.log"
            if log_file.exists():
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    return jsonify({"logs": lines[-100:]})  # Last 100 lines
            return jsonify({"logs": [], "message": "No log file found"})
        
        @self.app.route('/tasks', methods=['GET'])
        def get_tasks():
            return jsonify({"tasks": self.tasks})
        
        @self.app.route('/tasks', methods=['POST'])
        def add_task():
            data = request.json
            task_name = data.get("name")
            task_config = data.get("config")
            
            if not task_name or not task_config:
                return jsonify({"error": "Missing name or config"}), 400
            
            self.tasks[task_name] = task_config
            self.save_config()
            self.setup_schedules()
            
            self.logger.info(f"Added task '{task_name}' via web API")
            return jsonify({"message": f"Task '{task_name}' added successfully"})
        
        @self.app.route('/tasks/<task_name>', methods=['DELETE'])
        def delete_task(task_name):
            if task_name in self.tasks:
                del self.tasks[task_name]
                self.save_config()
                self.setup_schedules()
                self.logger.info(f"Deleted task '{task_name}' via web API")
                return jsonify({"message": f"Task '{task_name}' deleted"})
            return jsonify({"error": "Task not found"}), 404
        
        @self.app.route('/execute', methods=['POST'])
        def execute_command():
            data = request.json
            command = data.get("command")
            timeout = data.get("timeout", 60)
            
            if not command:
                return jsonify({"error": "Missing command"}), 400
            
            self.logger.info(f"Executing command via web API: {command}")
            
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
                
                return jsonify({
                    "exit_code": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "success": result.returncode == 0
                })
            except subprocess.TimeoutExpired:
                return jsonify({"error": "Command timed out"}), 500
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        
        @self.app.route('/terminal')
        def terminal():
            html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Terminal Agent - Web Terminal</title>
                <style>
                    body {
                        font-family: 'Courier New', monospace;
                        background: #1e1e1e;
                        color: #d4d4d4;
                        margin: 0;
                        padding: 20px;
                    }
                    .container {
                        max-width: 1200px;
                        margin: 0 auto;
                    }
                    .terminal {
                        background: #000;
                        border: 1px solid #333;
                        border-radius: 5px;
                        padding: 20px;
                        margin-bottom: 20px;
                        min-height: 400px;
                        max-height: 600px;
                        overflow-y: auto;
                    }
                    .output {
                        white-space: pre-wrap;
                        word-wrap: break-word;
                        margin-bottom: 10px;
                    }
                    .input-line {
                        display: flex;
                        align-items: center;
                        margin-top: 10px;
                    }
                    .prompt {
                        color: #4ec9b0;
                        margin-right: 10px;
                    }
                    #command-input {
                        flex: 1;
                        background: transparent;
                        border: none;
                        color: #d4d4d4;
                        font-family: 'Courier New', monospace;
                        font-size: 14px;
                        outline: none;
                    }
                    .status {
                        background: #252526;
                        padding: 15px;
                        border-radius: 5px;
                        margin-bottom: 20px;
                    }
                    .status h2 {
                        margin: 0 0 10px 0;
                        color: #4ec9b0;
                    }
                    button {
                        background: #0e639c;
                        color: white;
                        border: none;
                        padding: 10px 20px;
                        border-radius: 3px;
                        cursor: pointer;
                        margin-right: 10px;
                    }
                    button:hover {
                        background: #1177bb;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="status">
                        <h2>Terminal Agent Status</h2>
                        <div id="status-info">Loading...</div>
                    </div>
                    
                    <div class="terminal" id="terminal">
                        <div class="output">Welcome to Terminal Agent Web Terminal</div>
                        <div class="output">Type commands below and press Enter to execute</div>
                    </div>
                    
                    <div class="input-line">
                        <span class="prompt">$</span>
                        <input type="text" id="command-input" placeholder="Enter command..." autofocus>
                    </div>
                    
                    <div style="margin-top: 20px;">
                        <button onclick="clearTerminal()">Clear</button>
                        <button onclick="refreshStatus()">Refresh Status</button>
                    </div>
                </div>
                
                <script>
                    const terminal = document.getElementById('terminal');
                    const input = document.getElementById('command-input');
                    const statusInfo = document.getElementById('status-info');
                    
                    input.addEventListener('keypress', async (e) => {
                        if (e.key === 'Enter') {
                            const command = input.value.trim();
                            if (command) {
                                await executeCommand(command);
                                input.value = '';
                            }
                        }
                    });
                    
                    async function executeCommand(command) {
                        addOutput(`$ ${command}`);
                        
                        try {
                            const response = await fetch('/execute', {
                                method: 'POST',
                                headers: {'Content-Type': 'application/json'},
                                body: JSON.stringify({command: command})
                            });
                            const result = await response.json();
                            
                            if (result.stdout) {
                                addOutput(result.stdout);
                            }
                            if (result.stderr) {
                                addOutput(result.stderr, '#ff6b6b');
                            }
                            if (result.error) {
                                addOutput(result.error, '#ff6b6b');
                            }
                        } catch (error) {
                            addOutput(`Error: ${error.message}`, '#ff6b6b');
                        }
                    }
                    
                    function addOutput(text, color = '#d4d4d4') {
                        const div = document.createElement('div');
                        div.className = 'output';
                        div.style.color = color;
                        div.textContent = text;
                        terminal.appendChild(div);
                        terminal.scrollTop = terminal.scrollHeight;
                    }
                    
                    function clearTerminal() {
                        terminal.innerHTML = '';
                        addOutput('Terminal cleared');
                    }
                    
                    async function refreshStatus() {
                        try {
                            const response = await fetch('/status');
                            const status = await response.json();
                            statusInfo.innerHTML = `
                                <p><strong>Running:</strong> ${status.running}</p>
                                <p><strong>Start Time:</strong> ${status.start_time || 'N/A'}</p>
                                <p><strong>Uptime:</strong> ${status.uptime || 'N/A'}</p>
                                <p><strong>Scheduled Tasks:</strong> ${status.scheduled_tasks}</p>
                                <p><strong>Executed Tasks:</strong> ${status.executed_tasks_count}</p>
                            `;
                        } catch (error) {
                            statusInfo.innerHTML = `Error loading status: ${error.message}`;
                        }
                    }
                    
                    refreshStatus();
                    setInterval(refreshStatus, 30000);
                </script>
            </body>
            </html>
            """
            return Response(html, mimetype='text/html')
        
        self.logger.info(f"Web server configured on port {self.web_port}")
    
    def get_uptime(self):
        """Calculate agent uptime."""
        if not self.state.get("start_time"):
            return "N/A"
        
        start = datetime.fromisoformat(self.state["start_time"])
        uptime = datetime.now() - start
        
        days = uptime.days
        hours = uptime.seconds // 3600
        minutes = (uptime.seconds % 3600) // 60
        
        return f"{days}d {hours}h {minutes}m"
    
    def save_config(self):
        """Save current tasks to config file."""
        config = {"tasks": self.tasks}
        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=2)
    
    def start_web_server(self):
        """Start web server in a separate thread."""
        def run_server():
            self.app.run(host='0.0.0.0', port=self.web_port, threaded=True)
        
        self.web_thread = threading.Thread(target=run_server, daemon=True)
        self.web_thread.start()
        self.logger.info(f"Web server started on http://0.0.0.0:{self.web_port}")
    
    def setup_logging(self):
        """Setup logging configuration."""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / f"terminal_agent_{datetime.now().strftime('%Y%m%d')}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info("Terminal Agent initialized")
    
    def load_config(self):
        """Load task configuration from JSON file."""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                self.tasks = config.get("tasks", {})
            self.logger.info(f"Loaded {len(self.tasks)} tasks from config")
        else:
            self.logger.warning(f"Config file {self.config_path} not found, creating default")
            self.create_default_config()
    
    def create_default_config(self):
        """Create a default configuration file."""
        default_config = {
            "tasks": {
                "example_task": {
                    "command": "echo 'Hello from Terminal Agent'",
                    "schedule": "every 1 minute",
                    "enabled": false,
                    "description": "Example task that runs every minute"
                }
            }
        }
        
        with open(self.config_path, 'w') as f:
            json.dump(default_config, f, indent=2)
        
        self.tasks = default_config["tasks"]
        self.logger.info(f"Created default config at {self.config_path}")
    
    def load_state(self):
        """Load agent state from JSON file."""
        if self.state_path.exists():
            with open(self.state_path, 'r') as f:
                self.state = json.load(f)
            self.logger.info("Loaded agent state")
    
    def save_state(self):
        """Save agent state to JSON file."""
        self.state["last_check"] = datetime.now().isoformat()
        with open(self.state_path, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
        self.save_state()
        sys.exit(0)
    
    def execute_task(self, task_name: str, task_config: Dict):
        """Execute a single task."""
        if not task_config.get("enabled", True):
            return
        
        command = task_config["command"]
        description = task_config.get("description", "No description")
        
        self.logger.info(f"Executing task: {task_name} - {description}")
        self.logger.info(f"Command: {command}")
        
        try:
            start_time = time.time()
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            elapsed_time = time.time() - start_time
            
            # Log output
            if result.stdout:
                self.logger.info(f"STDOUT:\n{result.stdout}")
            if result.stderr:
                self.logger.warning(f"STDERR:\n{result.stderr}")
            
            # Record execution
            execution_record = {
                "task_name": task_name,
                "timestamp": datetime.now().isoformat(),
                "exit_code": result.returncode,
                "elapsed_time": elapsed_time,
                "success": result.returncode == 0
            }
            
            self.state["executed_tasks"].append(execution_record)
            
            # Keep only last 1000 executions
            if len(self.state["executed_tasks"]) > 1000:
                self.state["executed_tasks"] = self.state["executed_tasks"][-1000:]
            
            if result.returncode == 0:
                self.logger.info(f"Task '{task_name}' completed successfully in {elapsed_time:.2f}s")
            else:
                self.logger.error(f"Task '{task_name}' failed with exit code {result.returncode}")
            
        except subprocess.TimeoutExpired:
            self.logger.error(f"Task '{task_name}' timed out after 300 seconds")
        except Exception as e:
            self.logger.error(f"Task '{task_name}' encountered error: {str(e)}")
    
    def schedule_task(self, task_name: str, task_config: Dict):
        """Schedule a task based on its configuration."""
        schedule_str = task_config.get("schedule", "")
        
        if not schedule_str:
            self.logger.warning(f"Task '{task_name}' has no schedule, skipping")
            return
        
        try:
            # Parse schedule string and set up the job
            if schedule_str.startswith("every "):
                parts = schedule_str.split()
                if len(parts) >= 3:
                    interval = int(parts[1])
                    unit = parts[2]
                    
                    task_func = lambda: self.execute_task(task_name, task_config)
                    
                    if unit.startswith("second"):
                        schedule.every(interval).seconds.do(task_func)
                    elif unit.startswith("minute"):
                        schedule.every(interval).minutes.do(task_func)
                    elif unit.startswith("hour"):
                        schedule.every(interval).hours.do(task_func)
                    elif unit.startswith("day"):
                        schedule.every(interval).days.do(task_func)
                    else:
                        self.logger.warning(f"Unknown time unit: {unit}")
                        return
                    
                    self.logger.info(f"Scheduled task '{task_name}' to run {schedule_str}")
            
            elif schedule_str.startswith("at "):
                # Daily at specific time
                time_str = schedule_str.replace("at ", "")
                schedule.every().day.at(time_str).do(
                    lambda: self.execute_task(task_name, task_config)
                )
                self.logger.info(f"Scheduled task '{task_name}' to run daily at {time_str}")
            
            else:
                self.logger.warning(f"Unknown schedule format: {schedule_str}")
                
        except Exception as e:
            self.logger.error(f"Failed to schedule task '{task_name}': {str(e)}")
    
    def setup_schedules(self):
        """Setup all task schedules."""
        schedule.clear()
        
        for task_name, task_config in self.tasks.items():
            self.schedule_task(task_name, task_config)
        
        self.logger.info(f"Setup {len(schedule.jobs)} scheduled jobs")
    
    def reload_config(self):
        """Reload configuration and reschedule tasks."""
        self.logger.info("Reloading configuration...")
        self.load_config()
        self.setup_schedules()
        self.logger.info("Configuration reloaded")
    
    def run(self):
        """Main run loop."""
        self.running = True
        self.state["start_time"] = datetime.now().isoformat()
        self.save_state()
        
        if self.enable_web:
            self.start_web_server()
        
        self.setup_schedules()
        
        self.logger.info("Terminal Agent started 24/7 operation")
        self.logger.info(f"Monitoring {len(schedule.jobs)} scheduled tasks")
        if self.enable_web:
            self.logger.info(f"Web interface available at http://0.0.0.0:{self.web_port}")
        
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(1)
                
                # Save state periodically
                if int(time.time()) % 60 == 0:  # Every minute
                    self.save_state()
                    
            except KeyboardInterrupt:
                self.logger.info("Keyboard interrupt received")
                break
            except Exception as e:
                self.logger.error(f"Error in main loop: {str(e)}")
                time.sleep(5)
        
        self.logger.info("Terminal Agent stopped")
        self.save_state()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="24/7 Terminal Agent")
    parser.add_argument("--config", default="config.json", help="Path to config file")
    parser.add_argument("--state", default="agent_state.json", help="Path to state file")
    parser.add_argument("--reload", action="store_true", help="Reload config and exit")
    parser.add_argument("--status", action="store_true", help="Show agent status and exit")
    parser.add_argument("--web", action="store_true", help="Enable web server")
    parser.add_argument("--port", type=int, default=5000, help="Web server port (default: 5000)")
    
    args = parser.parse_args()
    
    agent = TerminalAgent(args.config, args.state, enable_web=args.web, web_port=args.port)
    
    if args.reload:
        agent.reload_config()
        return
    
    if args.status:
        print(json.dumps(agent.state, indent=2))
        print(f"\nScheduled tasks: {len(schedule.jobs)}")
        for job in schedule.jobs:
            print(f"  - {job}")
        return
    
    agent.run()


if __name__ == "__main__":
    main()
