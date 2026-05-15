#!/usr/bin/env python3
"""
Collaborative Terminal Agent
A single-file 24/7 terminal agent with multi-user support, authentication, and shared terminal sessions.
Similar to Google Colab for terminal access.
"""

import json
import subprocess
import time
import logging
import signal
import sys
import hashlib
import secrets
import threading
import requests
import base64
import asyncio
import aiohttp
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set
from collections import defaultdict
from flask import Flask, jsonify, request, Response, session, send_from_directory
from functools import wraps

# ============== IMPORTS FROM REFACTORED MODULES ==============

from agent_modules import (
    Web3Agent,
    TradingAgent,
    OllamaAgent,
    UserManager,
    TerminalSession,
    TerminalSessionManager,
)

# ============== TERMINAL AGENT ==============

class TerminalAgent:
    def __init__(self, config_path: str = "config.json", state_path: str = "agent_state.json", 
                 enable_web: bool = False, web_port: int = 5000):
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
        
        # Initialize user and session managers
        self.user_manager = UserManager()
        self.session_manager = TerminalSessionManager()
        self.ollama_agent = OllamaAgent()
        self.web3_agent = Web3Agent()
        self.trading_agent = TradingAgent()
        
        self.setup_logging()
        self.load_config()
        self.load_state()
        
        if self.enable_web:
            self.setup_web_server()
        
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def setup_logging(self):
        """Setup logging configuration."""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / f"collab_agent_{datetime.now().strftime('%Y%m%d')}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info("Collaborative Terminal Agent initialized")
    
    def load_config(self):
        """Load task configuration."""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                self.tasks = config.get("tasks", {})
            self.logger.info(f"Loaded {len(self.tasks)} tasks from config")
        else:
            self.create_default_config()
    
    def create_default_config(self):
        """Create default configuration."""
        default_config = {
            "tasks": {
                "example_task": {
                    "command": "echo 'Hello from Collaborative Terminal Agent'",
                    "schedule": "every 1 minute",
                    "enabled": False,
                    "description": "Example task"
                }
            }
        }
        with open(self.config_path, 'w') as f:
            json.dump(default_config, f, indent=2)
        self.tasks = default_config["tasks"]
    
    def load_state(self):
        """Load agent state."""
        if self.state_path.exists():
            with open(self.state_path, 'r') as f:
                self.state = json.load(f)
    
    def save_state(self):
        """Save agent state."""
        self.state["last_check"] = datetime.now().isoformat()
        with open(self.state_path, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        self.logger.info(f"Shutting down (signal {signum})...")
        self.running = False
        self.save_state()
        sys.exit(0)
    
    def execute_task(self, task_name: str, task_config: Dict):
        """Execute a task."""
        if not task_config.get("enabled", True):
            return
        
        command = task_config["command"]
        self.logger.info(f"Executing task: {task_name}")
        
        try:
            start_time = time.time()
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300
            )
            elapsed_time = time.time() - start_time
            
            if result.stdout:
                self.logger.info(f"STDOUT: {result.stdout}")
            if result.stderr:
                self.logger.warning(f"STDERR: {result.stderr}")
            
            self.state["executed_tasks"].append({
                "task_name": task_name,
                "timestamp": datetime.now().isoformat(),
                "exit_code": result.returncode,
                "elapsed_time": elapsed_time,
                "success": result.returncode == 0
            })
            
            if len(self.state["executed_tasks"]) > 1000:
                self.state["executed_tasks"] = self.state["executed_tasks"][-1000:]
                
        except Exception as e:
            self.logger.error(f"Task error: {str(e)}")
    
    def schedule_task(self, task_name: str, task_config: Dict):
        """Schedule a task."""
        schedule_str = task_config.get("schedule", "")
        if not schedule_str:
            return
        
        try:
            if schedule_str.startswith("every "):
                parts = schedule_str.split()
                if len(parts) >= 3:
                    interval = int(parts[1])
                    unit = parts[2]
                    
                    task_func = lambda: self.execute_task(task_name, task_config)
                    
                    if unit.startswith("second"):
                        import schedule
                        schedule.every(interval).seconds.do(task_func)
                    elif unit.startswith("minute"):
                        import schedule
                        schedule.every(interval).minutes.do(task_func)
                    elif unit.startswith("hour"):
                        import schedule
                        schedule.every(interval).hours.do(task_func)
                    elif unit.startswith("day"):
                        import schedule
                        schedule.every(interval).days.do(task_func)
        except Exception as e:
            self.logger.error(f"Scheduling error: {str(e)}")
    
    def setup_schedules(self):
        """Setup all task schedules."""
        import schedule
        schedule.clear()
        for task_name, task_config in self.tasks.items():
            self.schedule_task(task_name, task_config)
    
    def get_uptime(self):
        """Calculate uptime."""
        if not self.state.get("start_time"):
            return "N/A"
        start = datetime.fromisoformat(self.state["start_time"])
        uptime = datetime.now() - start
        return f"{uptime.days}d {uptime.seconds // 3600}h {(uptime.seconds % 3600) // 60}m"
    
    def save_config(self):
        """Save config."""
        config = {"tasks": self.tasks}
        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=2)
    
    # ============== WEB SERVER ==============
    
    def setup_web_server(self):
        """Setup Flask web server."""
        self.app = Flask(__name__)
        self.app.secret_key = secrets.token_hex(32)
        
        # ============== AUTHENTICATION DECORATOR ==============

        def require_auth(f):
            @wraps(f)
            def decorated(*args, **kwargs):
                # Check for wallet address in header or query param
                wallet_address = request.headers.get('X-Wallet-Address') or request.args.get('wallet_address')
                
                if not wallet_address:
                    return jsonify({"error": "Wallet address required"}), 401
                
                # Validate wallet address format
                if not wallet_address.startswith('0x') or len(wallet_address) != 42:
                    return jsonify({"error": "Invalid wallet address"}), 401
                
                request.wallet_address = wallet_address
                request.username = wallet_address  # Use wallet address as username
                return f(*args, **kwargs)
            return decorated
        
        # Require admin
        def require_admin(f):
            @wraps(f)
            def decorated(*args, **kwargs):
                token = request.headers.get('Authorization') or request.cookies.get('session_token')
                if not token:
                    return jsonify({"error": "Authentication required"}), 401
                username = self.user_manager.verify_session(token)
                if not username:
                    return jsonify({"error": "Invalid session"}), 401
                if self.user_manager.users[username]["role"] != "admin":
                    return jsonify({"error": "Admin access required"}), 403
                request.username = username
                return f(*args, **kwargs)
            return decorated
        
        @self.app.route('/')
        def index():
            return jsonify({
                "name": "Collaborative Terminal Agent",
                "version": "1.0",
                "endpoints": {
                    "POST /auth/login": "Login and get session token",
                    "POST /auth/logout": "Logout",
                    "GET /api/status": "Agent status",
                    "GET /api/logs": "Recent logs",
                    "GET /api/tasks": "List tasks",
                    "POST /api/tasks": "Add task",
                    "DELETE /api/tasks/<name>": "Delete task",
                    "GET /api/users": "List users (admin)",
                    "POST /api/users": "Create user (admin)",
                    "DELETE /api/users/<username>": "Delete user (admin)",
                    "GET /api/sessions": "List terminal sessions",
                    "POST /api/sessions": "Create terminal session",
                    "DELETE /api/sessions/<id>": "Delete terminal session",
                    "POST /api/sessions/<id>/execute": "Execute command in session",
                    "GET /api/sessions/<id>/output": "Get session output",
                    "GET /terminal": "Web terminal interface"
                }
            })
        
        # Authentication
        @self.app.route('/auth/verify', methods=['POST'])
        def verify_wallet():
            """Verify wallet address and return session info."""
            data = request.json
            wallet_address = data.get("wallet_address")
            
            if not wallet_address:
                return jsonify({"error": "Wallet address required"}), 400
            
            if not wallet_address.startswith('0x') or len(wallet_address) != 42:
                return jsonify({"error": "Invalid wallet address"}), 400
            
            # Create or get user for this wallet
            if wallet_address not in self.user_manager.users:
                self.user_manager.create_user(wallet_address, "wallet_user", "user")
            
            token = self.user_manager.create_session(wallet_address)
            return jsonify({
                "token": token,
                "wallet_address": wallet_address,
                "authenticated": True
            })
        
        @self.app.route('/auth/me', methods=['GET'])
        def get_current_user():
            wallet_address = request.headers.get('X-Wallet-Address') or request.args.get('wallet_address')
            if wallet_address:
                return jsonify({
                    "wallet_address": wallet_address,
                    "authenticated": True
                })
            return jsonify({"error": "Wallet address required"}), 401
        
        # Agent status (public)
        @self.app.route('/api/status')
        def get_status():
            import schedule
            return jsonify({
                "running": self.running,
                "start_time": self.state.get("start_time"),
                "last_check": self.state.get("last_check"),
                "scheduled_jobs": len(schedule.get_jobs()),
                "tasks": self.tasks
            })
        
        @self.app.route('/api/logs')
        def get_logs():
            lines = int(request.args.get('lines', 50))
            log_file = Path("logs") / f"collab_agent_{datetime.now().strftime('%Y%m%d')}.log"
            if log_file.exists():
                with open(log_file, 'r') as f:
                    lines_content = f.readlines()[-lines:]
                return jsonify({"logs": lines_content})
            return jsonify({"logs": []})
        
        # Tasks
        @self.app.route('/api/tasks', methods=['GET'])
        @require_auth
        def get_tasks():
            return jsonify({"tasks": self.tasks})
        
        @self.app.route('/api/tasks', methods=['POST'])
        @require_admin
        def add_task():
            data = request.json
            task_name = data.get("name")
            task_config = data.get("config")
            
            if not task_name or not task_config:
                return jsonify({"error": "Missing name or config"}), 400
            
            self.tasks[task_name] = task_config
            self.save_config()
            self.setup_schedules()
            
            self.logger.info(f"Task '{task_name}' added by {request.username}")
            return jsonify({"message": "Task added"})
        
        @self.app.route('/api/tasks/<task_name>', methods=['DELETE'])
        @require_admin
        def delete_task(task_name):
            if task_name in self.tasks:
                del self.tasks[task_name]
                self.save_config()
                self.setup_schedules()
                return jsonify({"message": "Task deleted"})
            return jsonify({"error": "Task not found"}), 404
        
        # Users
        @self.app.route('/api/users', methods=['GET'])
        @require_admin
        def list_users():
            return jsonify({"users": self.user_manager.list_users()})
        
        @self.app.route('/api/users', methods=['POST'])
        @require_admin
        def create_user():
            data = request.json
            username = data.get("username")
            password = data.get("password")
            role = data.get("role", "user")
            
            if not username or not password:
                return jsonify({"error": "Username and password required"}), 400
            
            if self.user_manager.create_user(username, password, role):
                self.logger.info(f"User '{username}' created by {request.username}")
                return jsonify({"message": "User created"})
            return jsonify({"error": "User already exists"}), 400
        
        @self.app.route('/api/users/<username>', methods=['DELETE'])
        @require_admin
        def delete_user(username):
            if self.user_manager.delete_user(username):
                self.logger.info(f"User '{username}' deleted by {request.username}")
                return jsonify({"message": "User deleted"})
            return jsonify({"error": "Cannot delete user"}), 400
        
        @self.app.route('/api/sessions', methods=['GET'])
        @require_auth
        def list_sessions():
            return jsonify({"sessions": self.session_manager.list_sessions()})
        
        @self.app.route('/api/sessions', methods=['POST'])
        @require_auth
        def create_session():
            session = self.session_manager.create_session(request.username)
            self.logger.info(f"Terminal session '{session.session_id}' created by {request.username}")
            return jsonify({
                "session_id": session.session_id,
                "owner": session.owner,
                "created": session.created
            })
        
        @self.app.route('/api/sessions/<session_id>', methods=['DELETE'])
        @require_auth
        def delete_session(session_id):
            session = self.session_manager.get_session(session_id)
            if not session:
                return jsonify({"error": "Session not found"}), 404
            
            if session.owner != request.username and self.user_manager.users[request.username]["role"] != "admin":
                return jsonify({"error": "Not authorized"}), 403
            
            self.session_manager.delete_session(session_id)
            return jsonify({"message": "Session deleted"})
        
        @self.app.route('/api/sessions/<session_id>/join', methods=['POST'])
        @require_auth
        def join_session(session_id):
            session = self.session_manager.get_session(session_id)
            if not session:
                return jsonify({"error": "Session not found"}), 404
            
            session.add_participant(request.username)
            return jsonify({"message": "Joined session"})
        
        @self.app.route('/api/sessions/<session_id>/execute', methods=['POST'])
        @require_auth
        def execute_in_session(session_id):
            session = self.session_manager.get_session(session_id)
            if not session:
                return jsonify({"error": "Session not found"}), 404
            
            data = request.json
            command = data.get("command")
            
            if not command:
                return jsonify({"error": "Command required"}), 400
            
            session.add_output(f"$ {command}", "command", request.username)
            self.logger.info(f"Command executed in session {session_id} by {request.username}: {command}")
            
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.stdout:
                    session.add_output(result.stdout, "output")
                if result.stderr:
                    session.add_output(result.stderr, "error")
                
                return jsonify({
                    "exit_code": result.returncode,
                    "success": result.returncode == 0
                })
            except subprocess.TimeoutExpired:
                session.add_output("Command timed out", "error")
                return jsonify({"error": "Command timed out"}), 500
            except Exception as e:
                session.add_output(str(e), "error")
                return jsonify({"error": str(e)}), 500
        
        @self.app.route('/api/sessions/<session_id>/output')
        @require_auth
        def get_session_output(session_id):
            session = self.session_manager.get_session(session_id)
            if not session:
                return jsonify({"error": "Session not found"}), 404
            
            since = int(request.args.get('since', 0))
            return jsonify({
                "output": session.get_output(since),
                "total": len(session.output)
            })
        
        # Ollama AI endpoints (public)
        @self.app.route('/api/ollama/status')
        def ollama_status():
            connected = self.ollama_agent.check_connection()
            models = self.ollama_agent.get_models() if connected else []
            return jsonify({
                "connected": connected,
                "current_model": self.ollama_agent.model,
                "available_models": models
            })
        
        @self.app.route('/api/ollama/chat', methods=['POST'])
        def ollama_chat():
            data = request.json
            message = data.get("message")
            session_id = data.get("session_id", "default")
            model = data.get("model")
            system_prompt = data.get("system_prompt")
            
            if not message:
                return jsonify({"error": "Message required"}), 400
            
            if model:
                self.ollama_agent.set_model(model)
            
            response = self.ollama_agent.chat(session_id, message, system_prompt)
            return jsonify({
                "response": response,
                "model": self.ollama_agent.model
            })
        
        @self.app.route('/api/ollama/history/<session_id>', methods=['DELETE'])
        def clear_ollama_history(session_id):
            self.ollama_agent.clear_history(session_id)
            return jsonify({"message": "History cleared"})
        
        @self.app.route('/api/ollama/models')
        def get_ollama_models():
            return jsonify({
                "models": self.ollama_agent.get_models(),
                "current": self.ollama_agent.model
            })
        
        @self.app.route('/api/ollama/enable', methods=['POST'])
        def enable_ollama():
            self.ollama_agent.enable()
            return jsonify({"message": "AI re-enabled"})
        
        # Web3 Blockchain endpoints (public - wallet is the auth)
        @self.app.route('/api/web3/chains')
        def get_supported_chains():
            return jsonify({"chains": self.web3_agent.get_supported_chains()})
        
        @self.app.route('/api/web3/wallet/connect', methods=['POST'])
        def connect_wallet():
            data = request.json
            address = data.get("address")
            chain = data.get("chain", "ethereum")
            
            if not address:
                return jsonify({"error": "Address required"}), 400
            
            result = self.web3_agent.connect_wallet("public", address, chain)
            return jsonify(result)
        
        @self.app.route('/api/web3/balance', methods=['POST'])
        def get_balance():
            data = request.json
            address = data.get("address")
            chain = data.get("chain", "ethereum")
            
            if not address:
                return jsonify({"error": "Address required"}), 400
            
            result = self.web3_agent.get_balance(address, chain)
            return jsonify(result)
        
        @self.app.route('/api/web3/gas-price')
        def get_gas_price():
            chain = request.args.get('chain', 'ethereum')
            result = self.web3_agent.get_gas_price(chain)
            return jsonify(result)
        
        @self.app.route('/api/web3/estimate-gas', methods=['POST'])
        def estimate_gas():
            data = request.json
            to = data.get("to")
            from_address = data.get("from")
            data_hex = data.get("data", "0x")
            chain = data.get("chain", "ethereum")
            
            if not to or not from_address:
                return jsonify({"error": "to and from addresses required"}), 400
            
            result = self.web3_agent.estimate_gas(to, from_address, data_hex, chain)
            return jsonify(result)
        
        @self.app.route('/api/web3/nonce')
        def get_nonce():
            address = request.args.get('address')
            chain = request.args.get('chain', 'ethereum')
            
            if not address:
                return jsonify({"error": "Address required"}), 400
            
            result = self.web3_agent.get_transaction_count(address, chain)
            return jsonify(result)
        
        # Trading endpoints
        @self.app.route('/api/trading/market/<symbol>')
        def get_market_data(symbol):
            result = self.trading_agent.get_market_data(symbol)
            return jsonify(result)
        
        @self.app.route('/api/trading/order', methods=['POST'])
        def create_order():
            data = request.json
            symbol = data.get("symbol")
            side = data.get("side")
            amount = data.get("amount")
            price = data.get("price")
            order_type = data.get("type", "market")
            user = data.get("user", "anonymous")
            
            if not symbol or not side or not amount:
                return jsonify({"error": "Missing required fields"}), 400
            
            result = self.trading_agent.create_order(user, symbol, side, amount, price, order_type)
            return jsonify(result)
        
        @self.app.route('/api/trading/orders')
        def get_orders():
            user = request.args.get('user', 'anonymous')
            return jsonify({"orders": self.trading_agent.get_orders(user)})
        
        @self.app.route('/api/trading/positions')
        def get_positions():
            user = request.args.get('user', 'anonymous')
            return jsonify({"positions": self.trading_agent.get_positions(user)})
        
        @self.app.route('/api/trading/analyze/<symbol>')
        def analyze_market(symbol):
            use_ai = request.args.get('use_ai', 'false').lower() == 'true'
            result = self.trading_agent.analyze_market(symbol, use_ai)
            return jsonify(result)
        
        @self.app.route('/api/trading/strategy', methods=['POST'])
        def run_strategy():
            data = request.json
            strategy_name = data.get("strategy_name", "default")
            symbols = data.get("symbols", ["BTC/USDT", "ETH/USDT"])
            
            result = self.trading_agent.run_strategy(strategy_name, symbols)
            return jsonify(result)
        
        @self.app.route('/api/trading/strategy/set', methods=['POST'])
        def set_strategy():
            data = request.json
            strategy_name = data.get("strategy_name")
            params = data.get("params", {})
            user = data.get("user", "anonymous")
            
            if not strategy_name:
                return jsonify({"error": "Strategy name required"}), 400
            
            result = self.trading_agent.set_strategy(user, strategy_name, params)
            return jsonify(result)
        
        @self.app.route('/api/trading/portfolio')
        def get_portfolio():
            user = request.args.get('user', 'anonymous')
            result = self.trading_agent.get_portfolio_value(user)
            return jsonify(result)
        
        @self.app.route('/api/trading/exchange/configure', methods=['POST'])
        def configure_exchange():
            data = request.json
            exchange = data.get("exchange")
            api_key = data.get("api_key")
            secret = data.get("secret")
            
            if not exchange or not api_key or not secret:
                return jsonify({"error": "Missing credentials"}), 400
            
            result = self.trading_agent.configure_exchange(exchange, api_key, secret)
            return jsonify(result)
        
        # Autonomous trading endpoints
        @self.app.route('/api/trading/autonomous/start', methods=['POST'])
        def start_autonomous():
            data = request.json or {}
            symbols = data.get("symbols")
            interval = data.get("interval", 60)
            result = self.trading_agent.start_autonomous_trading(symbols, interval)
            return jsonify(result)
        
        @self.app.route('/api/trading/autonomous/stop', methods=['POST'])
        def stop_autonomous():
            result = self.trading_agent.stop_autonomous_trading()
            return jsonify(result)
        
        @self.app.route('/api/trading/autonomous/status')
        def autonomous_status():
            result = self.trading_agent.get_autonomous_status()
            return jsonify(result)
        
        # Web terminal interface
        @self.app.route('/terminal')
        def terminal():
            from flask import render_template
            return render_template('terminal.html')
        
        self.logger.info(f"Web server configured on port {self.web_port}")
    
    def start_web_server(self):
        """Start web server."""
        def run_server():
            self.app.run(host='0.0.0.0', port=self.web_port, threaded=True)
        
        self.web_thread = threading.Thread(target=run_server, daemon=True)
        self.web_thread.start()
        self.logger.info(f"Web server started on http://0.0.0.0:{self.web_port}")
    
    def run(self):
        """Main run loop."""
        self.running = True
        self.state["start_time"] = datetime.now().isoformat()
        self.save_state()
        
        if self.enable_web:
            self.start_web_server()
        
        self.setup_schedules()
        
        self.logger.info("Collaborative Terminal Agent started")
        self.logger.info(f"Web interface: http://0.0.0.0:{self.web_port}")
        self.logger.info(f"Default admin: admin / admin123")
        
        while self.running:
            try:
                import schedule
                schedule.run_pending()
                time.sleep(1)
                
                if int(time.time()) % 60 == 0:
                    self.save_state()
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                self.logger.error(f"Error: {str(e)}")
                time.sleep(5)
        
        self.logger.info("Agent stopped")
        self.save_state()

# ============== MAIN ==============

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Collaborative Terminal Agent")
    parser.add_argument("--config", default="config.json", help="Config file")
    parser.add_argument("--state", default="agent_state.json", help="State file")
    parser.add_argument("--web", action="store_true", help="Enable web server")
    parser.add_argument("--port", type=int, default=5000, help="Web port")
    
    args = parser.parse_args()
    
    agent = TerminalAgent(args.config, args.state, enable_web=args.web, web_port=args.port)
    agent.run()

if __name__ == "__main__":
    main()
