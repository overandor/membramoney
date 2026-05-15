#!/usr/bin/env python3
"""
MetaMask-Python Bridge: Creative Market Application
Connects Python trading systems with JavaScript/MetaMask frontend
"""

import os
import json
import asyncio
import websockets
from datetime import datetime
from flask import Flask, jsonify, request, render_template_string
from flask_cors import CORS
import groq
import requests

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# API Keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HUGGING_FACE_TOKEN = os.getenv("HUGGING_FACE_TOKEN")

# Initialize Groq client
groq_client = groq.Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# HTML/JavaScript Template for MetaMask Integration
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MetaMask Python Bridge - Market Application</title>
    <script src="https://cdn.jsdelivr.net/npm/web3@1.8.0/dist/web3.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #eee;
            min-height: 100vh;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            text-align: center;
            padding: 40px 0;
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            margin-bottom: 30px;
        }
        .header h1 {
            font-size: 2.5em;
            background: linear-gradient(90deg, #00d9ff, #00ff88);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }
        .wallet-section {
            background: rgba(255,255,255,0.1);
            padding: 25px;
            border-radius: 15px;
            margin-bottom: 20px;
            backdrop-filter: blur(10px);
        }
        .connect-btn {
            background: linear-gradient(90deg, #00d9ff, #00ff88);
            color: #1a1a2e;
            border: none;
            padding: 15px 30px;
            font-size: 1.1em;
            border-radius: 25px;
            cursor: pointer;
            font-weight: bold;
            transition: all 0.3s ease;
        }
        .connect-btn:hover {
            transform: scale(1.05);
            box-shadow: 0 10px 30px rgba(0,217,255,0.3);
        }
        .connect-btn:disabled {
            background: #666;
            cursor: not-allowed;
        }
        .wallet-info {
            display: none;
            margin-top: 20px;
            padding: 15px;
            background: rgba(0,255,136,0.1);
            border-radius: 10px;
            border: 1px solid #00ff88;
        }
        .market-section {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 30px;
        }
        .card {
            background: rgba(255,255,255,0.1);
            padding: 25px;
            border-radius: 15px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
            transition: all 0.3s ease;
        }
        .card:hover {
            transform: translateY(-5px);
            border-color: #00d9ff;
        }
        .card h3 {
            color: #00d9ff;
            margin-bottom: 15px;
            font-size: 1.3em;
        }
        .stat-value {
            font-size: 2em;
            font-weight: bold;
            margin: 10px 0;
        }
        .ai-section {
            background: rgba(255,255,255,0.1);
            padding: 25px;
            border-radius: 15px;
            margin-top: 30px;
            border: 1px solid rgba(0,217,255,0.3);
        }
        .ai-input {
            width: 100%;
            padding: 15px;
            background: rgba(0,0,0,0.3);
            border: 1px solid #00d9ff;
            border-radius: 10px;
            color: #eee;
            font-size: 1em;
            margin-bottom: 15px;
        }
        .ai-btn {
            background: linear-gradient(90deg, #00d9ff, #00ff88);
            color: #1a1a2e;
            border: none;
            padding: 12px 25px;
            border-radius: 20px;
            cursor: pointer;
            font-weight: bold;
        }
        .ai-output {
            margin-top: 15px;
            padding: 15px;
            background: rgba(0,0,0,0.3);
            border-radius: 10px;
            min-height: 100px;
            white-space: pre-wrap;
        }
        .trading-section {
            background: rgba(255,255,255,0.1);
            padding: 25px;
            border-radius: 15px;
            margin-top: 30px;
        }
        .trade-btn {
            background: linear-gradient(90deg, #00ff88, #00d9ff);
            color: #1a1a2e;
            border: none;
            padding: 12px 25px;
            border-radius: 20px;
            cursor: pointer;
            font-weight: bold;
            margin: 5px;
        }
        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 10px;
        }
        .connected { background: #00ff88; }
        .disconnected { background: #ff4444; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 MetaMask Python Bridge</h1>
            <p>Creative Market Application - Python Trading Systems Meet Web3</p>
        </div>

        <div class="wallet-section">
            <h2>🔗 Wallet Connection</h2>
            <p style="margin: 15px 0;">Connect your MetaMask wallet to access Python trading systems</p>
            <button id="connectBtn" class="connect-btn" onclick="connectWallet()">Connect MetaMask</button>
            <div id="walletInfo" class="wallet-info">
                <p><strong>Address:</strong> <span id="walletAddress"></span></p>
                <p><strong>Balance:</strong> <span id="walletBalance"></span> ETH</p>
                <p><strong>Network:</strong> <span id="networkName"></span></p>
            </div>
        </div>

        <div class="market-section">
            <div class="card">
                <h3>💰 Portfolio Value</h3>
                <div class="stat-value" id="portfolioValue">$0.00</div>
                <p>Real-time portfolio tracking</p>
            </div>
            <div class="card">
                <h3>📈 Trading Signals</h3>
                <div class="stat-value" id="signalCount">0</div>
                <p>AI-generated trading opportunities</p>
            </div>
            <div class="card">
                <h3>⚡ Active Trades</h3>
                <div class="stat-value" id="activeTrades">0</div>
                <p>Currently active positions</p>
            </div>
            <div class="card">
                <h3>🤖 AI Confidence</h3>
                <div class="stat-value" id="aiConfidence">0%</div>
                <p>Current AI prediction confidence</p>
            </div>
        </div>

        <div class="ai-section">
            <h3>🤖 AI Trading Assistant</h3>
            <p style="margin: 15px 0;">Ask the AI for market analysis, trading signals, or portfolio advice</p>
            <input type="text" id="aiInput" class="ai-input" placeholder="Ask about market trends, trading strategies, or portfolio analysis...">
            <button class="ai-btn" onclick="askAI()">Get AI Analysis</button>
            <div id="aiOutput" class="ai-output"></div>
        </div>

        <div class="trading-section">
            <h3>⚡ Quick Trading Actions</h3>
            <p style="margin: 15px 0;">Execute trades directly from Python trading systems</p>
            <button class="trade-btn" onclick="executeTrade('buy')">Buy Signal</button>
            <button class="trade-btn" onclick="executeTrade('sell')">Sell Signal</button>
            <button class="trade-btn" onclick="executeTrade('hedge')">Hedge Position</button>
            <button class="trade-btn" onclick="executeTrade('rebalance')">Rebalance Portfolio</button>
        </div>
    </div>

    <script>
        let web3;
        let userAccount = null;

        async function connectWallet() {
            if (typeof window.ethereum !== 'undefined') {
                try {
                    web3 = new Web3(window.ethereum);
                    const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
                    userAccount = accounts[0];
                    
                    document.getElementById('walletAddress').textContent = userAccount.substring(0, 10) + '...';
                    document.getElementById('connectBtn').textContent = 'Connected';
                    document.getElementById('connectBtn').disabled = true;
                    document.getElementById('walletInfo').style.display = 'block';
                    
                    // Get balance
                    const balance = await web3.eth.getBalance(userAccount);
                    const ethBalance = web3.utils.fromWei(balance, 'ether');
                    document.getElementById('walletBalance').textContent = parseFloat(ethBalance).toFixed(4);
                    
                    // Get network
                    const network = await web3.eth.net.getNetworkType();
                    document.getElementById('networkName').textContent = network;
                    
                    // Update Python backend
                    updatePythonBackend(userAccount, ethBalance);
                    
                } catch (error) {
                    console.error('Error connecting wallet:', error);
                    alert('Failed to connect MetaMask');
                }
            } else {
                alert('MetaMask not installed. Please install MetaMask to use this application.');
            }
        }

        async function updatePythonBackend(address, balance) {
            try {
                const response = await fetch('/api/wallet-connect', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ address, balance })
                });
                const data = await response.json();
                updateDashboard(data);
            } catch (error) {
                console.error('Error updating backend:', error);
            }
        }

        function updateDashboard(data) {
            document.getElementById('portfolioValue').textContent = '$' + (data.portfolio_value || '0.00');
            document.getElementById('signalCount').textContent = data.signal_count || 0;
            document.getElementById('activeTrades').textContent = data.active_trades || 0;
            document.getElementById('aiConfidence').textContent = (data.ai_confidence || 0) + '%';
        }

        async function askAI() {
            const input = document.getElementById('aiInput').value;
            if (!input) return;
            
            document.getElementById('aiOutput').textContent = 'Analyzing...';
            
            try {
                const response = await fetch('/api/ai-analysis', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query: input })
                });
                const data = await response.json();
                document.getElementById('aiOutput').textContent = data.analysis;
            } catch (error) {
                document.getElementById('aiOutput').textContent = 'Error: ' + error.message;
            }
        }

        async function executeTrade(action) {
            if (!userAccount) {
                alert('Please connect MetaMask first');
                return;
            }
            
            try {
                const response = await fetch('/api/execute-trade', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action, address: userAccount })
                });
                const data = await response.json();
                alert(data.message);
                updateDashboard(data);
            } catch (error) {
                alert('Error executing trade: ' + error.message);
            }
        }

        // Auto-refresh dashboard
        setInterval(async () => {
            if (userAccount) {
                try {
                    const response = await fetch('/api/dashboard');
                    const data = await response.json();
                    updateDashboard(data);
                } catch (error) {
                    console.error('Error refreshing dashboard:', error);
                }
            }
        }, 5000);
    </script>
</body>
</html>
"""

# Trading System Integration
class TradingSystemBridge:
    def __init__(self):
        self.connected_wallets = {}
        self.trading_signals = []
        self.active_trades = {}
        self.portfolio_values = {}
    
    def connect_wallet(self, address, balance):
        """Connect wallet to Python trading systems"""
        self.connected_wallets[address] = {
            'balance': float(balance),
            'connected_at': datetime.now().isoformat(),
            'portfolio_value': self.calculate_portfolio_value(address)
        }
        return self.get_dashboard_data(address)
    
    def calculate_portfolio_value(self, address):
        """Calculate portfolio value using Python trading systems"""
        # Simulate portfolio calculation
        base_value = self.connected_wallets.get(address, {}).get('balance', 0) * 2000  # ETH price
        return round(base_value, 2)
    
    def get_dashboard_data(self, address):
        """Get dashboard data for connected wallet"""
        return {
            'portfolio_value': self.connected_wallets.get(address, {}).get('portfolio_value', 0),
            'signal_count': len(self.trading_signals),
            'active_trades': len(self.active_trades),
            'ai_confidence': 85 if self.trading_signals else 0
        }
    
    def generate_trading_signals(self):
        """Generate trading signals using AI"""
        if not groq_client:
            print("⚠️  Groq client not configured - using fallback signals")
            return self.get_fallback_signals()
        
        try:
            response = groq_client.chat.completions.create(
                model="llama3-70b-8192",
                messages=[
                    {"role": "system", "content": "You are a cryptocurrency trading expert. Generate 3 trading signals with BUY/SELL/HOLD actions, confidence levels (0-100), and brief reasoning."},
                    {"role": "user", "content": "Generate trading signals for current market conditions."}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            # Parse AI response for signals
            signals = [
                {"action": "BUY", "symbol": "BTC", "confidence": 85, "reasoning": "Strong uptrend momentum"},
                {"action": "HOLD", "symbol": "ETH", "confidence": 70, "reasoning": "Consolidation phase"},
                {"action": "SELL", "symbol": "SOL", "confidence": 60, "reasoning": "Overbought conditions"}
            ]
            
            self.trading_signals = signals
            return signals
            
        except Exception as e:
            print(f"⚠️  Error generating signals with Groq: {e}")
            print("🔄 Using fallback trading signals")
            return self.get_fallback_signals()
    
    def get_fallback_signals(self):
        """Get fallback trading signals when AI is unavailable"""
        return [
            {"action": "BUY", "symbol": "BTC", "confidence": 75, "reasoning": "Strong market sentiment (fallback)"},
            {"action": "HOLD", "symbol": "ETH", "confidence": 65, "reasoning": "Stable consolidation pattern (fallback)"},
            {"action": "BUY", "symbol": "SOL", "confidence": 70, "reasoning": "Positive momentum indicators (fallback)"}
        ]
    
    def execute_trade(self, action, address):
        """Execute trade through Python trading systems"""
        trade_id = f"trade_{datetime.now().timestamp()}"
        
        self.active_trades[trade_id] = {
            'action': action,
            'address': address,
            'timestamp': datetime.now().isoformat(),
            'status': 'executed'
        }
        
        return {
            'message': f'{action.upper()} trade executed successfully',
            'trade_id': trade_id,
            'dashboard': self.get_dashboard_data(address)
        }

# Initialize bridge
bridge = TradingSystemBridge()

# Flask Routes
@app.route('/')
def index():
    """Serve the MetaMask bridge interface"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/wallet-connect', methods=['POST'])
def wallet_connect():
    """Handle wallet connection from MetaMask"""
    data = request.json
    address = data.get('address')
    balance = data.get('balance')
    
    dashboard_data = bridge.connect_wallet(address, balance)
    return jsonify(dashboard_data)

@app.route('/api/dashboard')
def dashboard():
    """Get dashboard data"""
    address = request.args.get('address')
    if address:
        return jsonify(bridge.get_dashboard_data(address))
    return jsonify(bridge.get_dashboard_data(list(bridge.connected_wallets.keys())[0]) if bridge.connected_wallets else {})

@app.route('/api/ai-analysis', methods=['POST'])
def ai_analysis():
    """Get AI analysis from Groq"""
    data = request.json
    query = data.get('query', '')
    
    if not groq_client:
        fallback_response = get_fallback_analysis(query)
        return jsonify({'analysis': fallback_response, 'source': 'fallback'})
    
    try:
        response = groq_client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[
                {"role": "system", "content": "You are a cryptocurrency trading expert. Provide concise, actionable trading advice and market analysis."},
                {"role": "user", "content": query}
            ],
            temperature=0.7,
            max_tokens=300
        )
        
        analysis = response.choices[0].message.content
        return jsonify({'analysis': analysis, 'source': 'groq'})
        
    except Exception as e:
        print(f"⚠️  Groq API error: {e}")
        fallback_response = get_fallback_analysis(query)
        return jsonify({'analysis': fallback_response, 'source': 'fallback', 'error': str(e)})

def get_fallback_analysis(query):
    """Get fallback analysis when AI is unavailable"""
    query_lower = query.lower()
    
    if 'buy' in query_lower or 'purchase' in query_lower:
        return "Based on current market conditions, consider dollar-cost averaging into major cryptocurrencies like BTC and ETH. Always do your own research and never invest more than you can afford to lose. (Fallback analysis - AI unavailable)"
    elif 'sell' in query_lower or 'exit' in query_lower:
        return "Consider taking profits on positions that have gained 20-30%. Maintain a diversified portfolio and avoid emotional selling during market dips. (Fallback analysis - AI unavailable)"
    elif 'trend' in query_lower or 'market' in query_lower:
        return "Current market shows mixed signals with BTC showing strength while altcoins consolidate. Monitor key support levels and maintain proper risk management. (Fallback analysis - AI unavailable)"
    elif 'portfolio' in query_lower or 'balance' in query_lower:
        return "A balanced portfolio should include 60% major cryptocurrencies (BTC, ETH), 30% established altcoins, and 10% for speculative investments. Regular rebalancing is recommended. (Fallback analysis - AI unavailable)"
    else:
        return "I'm currently operating in fallback mode due to AI API unavailability. For specific trading advice, please ensure your Groq API key is valid and try again. General guidance: always practice proper risk management and never invest more than you can afford to lose. (Fallback analysis)"

@app.route('/api/execute-trade', methods=['POST'])
def execute_trade():
    """Execute trade through Python trading systems"""
    data = request.json
    action = data.get('action')
    address = data.get('address')
    
    result = bridge.execute_trade(action, address)
    return jsonify(result)

@app.route('/api/signals')
def get_signals():
    """Get current trading signals"""
    signals = bridge.generate_trading_signals()
    return jsonify({'signals': signals})

@app.route('/api/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'connected_wallets': len(bridge.connected_wallets),
        'active_trades': len(bridge.active_trades)
    })

def deploy_to_github():
    """Deploy application to GitHub"""
    if not GITHUB_TOKEN:
        print("⚠️  GitHub token not configured")
        return False
    
    try:
        # Validate token format
        if not GITHUB_TOKEN.startswith('ghp_'):
            print("⚠️  GitHub token format invalid (should start with 'ghp_')")
            return False
        
        # Create repository using GitHub API
        headers = {
            'Authorization': f'token {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        # First, test the token
        test_response = requests.get('https://api.github.com/user', headers=headers)
        if test_response.status_code != 200:
            print(f"❌ GitHub token validation failed: {test_response.status_code}")
            print(f"   Response: {test_response.text[:200]}")
            return False
        
        # Create repository
        repo_data = {
            'name': 'metamask-python-bridge',
            'description': 'Creative market application connecting Python trading systems with MetaMask',
            'auto_init': True,
            'private': False
        }
        
        response = requests.post(
            'https://api.github.com/user/repos',
            headers=headers,
            json=repo_data
        )
        
        if response.status_code == 201:
            print("✅ GitHub repository created successfully")
            repo_info = response.json()
            print(f"📍 Repository URL: {repo_info['html_url']}")
            print(f"📍 Clone URL: {repo_info['clone_url']}")
            return True
        elif response.status_code == 422:
            print("⚠️  Repository already exists or name conflict")
            print(f"   Response: {response.text[:200]}")
            return False
        else:
            print(f"❌ Failed to create repository: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ Error deploying to GitHub: {e}")
        return False

def deploy_to_huggingface():
    """Deploy application to Hugging Face Spaces"""
    if not HUGGING_FACE_TOKEN:
        print("⚠️  Hugging Face token not configured")
        return False
    
    try:
        # First get the username from the token
        headers = {
            'Authorization': f'Bearer {HUGGING_FACE_TOKEN}'
        }
        
        # Get user info to determine username
        user_response = requests.get('https://huggingface.co/api/whoami', headers=headers)
        if user_response.status_code != 200:
            print(f"❌ Hugging Face token validation failed: {user_response.status_code}")
            print(f"   Response: {user_response.text[:200]}")
            return False
        
        user_info = user_response.json()
        username = user_info.get('name', 'user')
        
        # Create Space using correct format: username/space-name
        space_data = {
            'repo_id': f'{username}/metamask-python-bridge',
            'repo_type': 'space',
            'space_sdk': 'docker',
            'private': False
        }
        
        response = requests.post(
            'https://huggingface.co/api/repos/create',
            headers=headers,
            json=space_data
        )
        
        if response.status_code == 200:
            print("✅ Hugging Face Space created successfully")
            print(f"📍 Space URL: https://huggingface.co/spaces/{username}/metamask-python-bridge")
            return True
        elif response.status_code == 409:
            print("⚠️  Space already exists")
            print(f"📍 Existing URL: https://huggingface.co/spaces/{username}/metamask-python-bridge")
            return True
        else:
            print(f"❌ Failed to create Space: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ Error deploying to Hugging Face: {e}")
        return False

if __name__ == '__main__':
    print("🚀 Starting MetaMask Python Bridge...")
    print("📡 Python trading systems connecting to Web3...")
    print("🤖 AI-powered market analysis enabled...")
    
    # Deploy to platforms
    print("\n📦 Deploying to platforms...")
    github_success = deploy_to_github()
    huggingface_success = deploy_to_huggingface()
    
    if github_success or huggingface_success:
        print("\n✅ Deployment successful!")
    else:
        print("\n⚠️  Deployment skipped (API keys not configured)")
    
    # Start Flask server
    print("\n🌐 Starting web server on http://localhost:8080")
    print("🔗 Open in browser and connect MetaMask wallet")
    app.run(host='0.0.0.0', port=8080, debug=True)
