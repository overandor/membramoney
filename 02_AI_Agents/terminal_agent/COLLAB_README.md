# Collaborative Terminal Agent

A single-file 24/7 terminal agent with wallet-based authentication, shared terminal sessions, neomorphic UI, AI assistant integration, Web3 blockchain features, and autonomous trading bot capabilities.

## Features

- **Wallet-Based Auth**: Use MetaMask or any wallet address for authentication (no passwords)
- **Autonomous Trading**: Self-driving trading bots that run on local compute
- **Public API**: All endpoints accessible via link without auth (wallet is the auth)
- **Shared Terminal Sessions**: Create collaborative terminal sessions
- **Real-Time Collaboration**: See commands and output from other users
- **Neomorphic UI**: Beautiful soft-shadow design with modern aesthetics
- **AI Assistant**: Integrated Ollama AI chat for assistance
- **Web3 Integration**: Multi-chain blockchain operations (Ethereum, Polygon, BSC, Arbitrum)
- **Balance Checking**: Real-time balance queries for connected wallets
- **Gas Monitoring**: Current gas prices and gas estimation
- **Trading Bot**: Market analysis, order placement, and strategy execution
- **Strategy Runner**: Automated trading strategies across multiple symbols
- **Portfolio Tracking**: Real-time portfolio value and position monitoring
- **Web Interface**: Elegant neomorphic web terminal interface
- **REST API**: Full API for programmatic control
- **Scheduled Tasks**: Background task scheduling

## Quick Start

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. (Optional) Install and start Ollama for AI features:
```bash
# Install Ollama from https://ollama.ai
# Pull a model
ollama pull phi3:mini

# Start Ollama server
ollama serve
```

3. Start the agent:
```bash
./start_collab.sh [port]
```

Default port is 5000.

4. Access the web interface:
```
http://your-ip:5000/terminal
```

5. Connect your wallet (MetaMask or manual address) to authenticate

**No passwords needed - your wallet is your authentication!**

## Usage

### Web Interface

1. Open `http://your-ip:5000/terminal` in your browser
2. Login with your credentials
3. Click "New Session" to create a terminal session
4. Type commands and press Enter to execute
5. Share the session ID with other users to collaborate

### Creating Users

As admin, you can create new users via the API:

```bash
curl -X POST http://localhost:5000/api/users \
  -H "Authorization: YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"username": "newuser", "password": "password123", "role": "user"}'
```

### Using AI Assistant

The AI Assistant panel on the right side allows you to:

1. **Check AI Status**: Shows if Ollama is connected
2. **Chat with AI**: Ask questions, get command suggestions, explain outputs
3. **Context Awareness**: AI maintains conversation history per session

**AI API Endpoints:**
- `GET /api/ollama/status` - Check Ollama connection and available models
- `POST /api/ollama/chat` - Send message to AI
- `GET /api/ollama/models` - List available models
- `DELETE /api/ollama/history/<session_id>` - Clear conversation history

**Example AI Chat:**
```bash
curl -X POST http://localhost:5000/api/ollama/chat \
  -H "Authorization: YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "How do I check disk space in Linux?", "session_id": "my-session"}'
```

### Using Web3 Features

The Web3 panel allows you to:

1. **Connect MetaMask**: Click "Connect MetaMask" to connect your browser wallet
2. **Manual Connection**: Enter any Ethereum address manually
3. **Check Balances**: View real-time balance for connected addresses
4. **Monitor Gas**: See current gas prices on supported chains
5. **Multi-Chain**: Switch between Ethereum, Polygon, BSC, and Arbitrum

**Web3 API Endpoints:**
- `GET /api/web3/chains` - Get supported blockchain networks
- `POST /api/web3/wallet/connect` - Connect a wallet address
- `GET /api/web3/wallets` - List connected wallets
- `POST /api/web3/balance` - Get balance for an address
- `GET /api/web3/gas-price` - Get current gas price
- `POST /api/web3/estimate-gas` - Estimate gas for transaction
- `GET /api/web3/nonce` - Get transaction count (nonce)
- `POST /api/web3/transaction` - Record a transaction
- `GET /api/web3/transactions` - Get user's transaction history

**Example Web3 Usage:**
```bash
# Connect wallet
curl -X POST http://localhost:5000/api/web3/wallet/connect \
  -H "Authorization: YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"address": "0x1234...", "chain": "ethereum"}'

# Check balance
curl -X POST http://localhost:5000/api/web3/balance \
  -H "Authorization: YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"address": "0x1234...", "chain": "ethereum"}'

# Get gas price
curl http://localhost:5000/api/web3/gas-price?chain=ethereum \
  -H "Authorization: YOUR_TOKEN"
```

### Using Trading Features

The Trading panel allows you to:

1. **Market Analysis**: Analyze market conditions for any trading pair
2. **Quick Orders**: Place buy/sell orders with one click
3. **Strategy Runner**: Run automated trading strategies
4. **Portfolio Tracking**: Monitor portfolio value and positions
5. **Exchange Integration**: Configure exchange API credentials

**Trading API Endpoints:**
- `GET /api/trading/market/<symbol>` - Get market data
- `POST /api/trading/order` - Create trading order
- `GET /api/trading/orders` - Get user's orders
- `GET /api/trading/positions` - Get user's positions
- `GET /api/trading/analyze/<symbol>` - Analyze market
- `POST /api/trading/strategy` - Run trading strategy
- `POST /api/trading/strategy/set` - Set strategy parameters
- `GET /api/trading/portfolio` - Get portfolio value
- `POST /api/trading/exchange/configure` - Configure exchange

**Example Trading Usage:**
```bash
# Analyze market (no auth needed)
curl http://localhost:5000/api/trading/analyze/BTC/USDT

# Place order (no auth needed)
curl -X POST http://localhost:5000/api/trading/order \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTC/USDT", "side": "buy", "amount": 0.01, "type": "market", "user": "mywallet"}'

# Run strategy (no auth needed)
curl -X POST http://localhost:5000/api/trading/strategy \
  -H "Content-Type: application/json" \
  -d '{"strategy_name": "default", "symbols": ["BTC/USDT", "ETH/USDT"]}'
```

### Autonomous Trading Bot

Start a self-driving trading bot that runs on your local compute:

```bash
# Start autonomous trading
curl -X POST http://localhost:5000/api/trading/autonomous/start \
  -H "Content-Type: application/json" \
  -d '{"symbols": ["BTC/USDT", "ETH/USDT", "SOL/USDT"], "interval": 60}'

# Check status
curl http://localhost:5000/api/trading/autonomous/status

# Stop autonomous trading
curl -X POST http://localhost:5000/api/trading/autonomous/stop
```

The autonomous bot will:
- Analyze markets every N seconds
- Execute trades based on signals
- Run entirely on your local compute
- Be accessible via public API link

### API Endpoints

#### Authentication
- `POST /auth/login` - Login and get session token
- `POST /auth/logout` - Logout
- `GET /auth/me` - Get current user info

#### Agent Control
- `GET /api/status` - Get agent status
- `GET /api/logs` - Get recent logs
- `GET /api/tasks` - List scheduled tasks
- `POST /api/tasks` - Add task (admin only)
- `DELETE /api/tasks/<name>` - Delete task (admin only)

#### User Management (admin only)
- `GET /api/users` - List all users
- `POST /api/users` - Create new user
- `DELETE /api/users/<username>` - Delete user

#### Terminal Sessions
- `GET /api/sessions` - List all sessions
- `POST /api/sessions` - Create new session
- `POST /api/sessions/<id>/join` - Join a session
- `DELETE /api/sessions/<id>` - Delete session
- `POST /api/sessions/<id>/execute` - Execute command in session
- `GET /api/sessions/<id>/output` - Get session output

#### AI Assistant
- `GET /api/ollama/status` - Check Ollama status and available models
- `POST /api/ollama/chat` - Chat with AI assistant
- `GET /api/ollama/models` - List available AI models
- `DELETE /api/ollama/history/<session_id>` - Clear conversation history

#### Web3 Blockchain
- `GET /api/web3/chains` - Get supported blockchain networks
- `POST /api/web3/wallet/connect` - Connect a wallet address
- `GET /api/web3/wallets` - List connected wallets
- `POST /api/web3/balance` - Get balance for an address
- `GET /api/web3/gas-price` - Get current gas price
- `POST /api/web3/estimate-gas` - Estimate gas for transaction
- `GET /api/web3/nonce` - Get transaction count (nonce)
- `POST /api/web3/transaction` - Record a transaction
- `GET /api/web3/transactions` - Get user's transaction history

#### Trading Bot
- `GET /api/trading/market/<symbol>` - Get market data
- `POST /api/trading/order` - Create trading order
- `GET /api/trading/orders` - Get user's orders
- `GET /api/trading/positions` - Get user's positions
- `GET /api/trading/analyze/<symbol>` - Analyze market
- `POST /api/trading/strategy` - Run trading strategy
- `POST /api/trading/strategy/set` - Set strategy parameters
- `GET /api/trading/portfolio` - Get portfolio value
- `POST /api/trading/exchange/configure` - Configure exchange
- `POST /api/trading/autonomous/start` - Start autonomous trading bot
- `POST /api/trading/autonomous/stop` - Stop autonomous trading bot
- `GET /api/trading/autonomous/status` - Get autonomous bot status

## Security

**Important Security Notes:**

1. **Change Default Password**: The default admin password is `admin123`. Change this immediately after first login.

2. **HTTPS in Production**: For production use, use HTTPS. You can use a reverse proxy like nginx with SSL.

3. **Network Access**: The server binds to `0.0.0.0`, making it accessible from any network. Use a firewall to restrict access.

4. **Session Tokens**: Session tokens are stored in HTTP-only cookies. They persist until logout.

## User Roles

- **Admin**: Full access including user management, task management, and can delete any session
- **User**: Can create sessions, execute commands, and manage their own sessions

## Example Session Workflow

1. User A logs in and creates a session
2. User A gets session ID: `abc123def456...`
3. User A shares the session ID with User B
4. User B logs in and joins the session
5. Both users can see each other's commands and output in real-time
6. Either user can execute commands
7. The session persists until deleted or the agent stops

## Files

- `collab_agent.py` - Single-file agent with all functionality
- `config.json` - Scheduled tasks configuration
- `users.json` - User database (created automatically)
- `agent_state.json` - Agent state and execution history
- `start_collab.sh` - Start script
- `stop_collab.sh` - Stop script
- `logs/` - Log files directory

## Remote Access

To access from another machine:

1. Ensure the agent machine's firewall allows the port
2. Use the machine's IP address: `http://machine-ip:5000/terminal`
3. For remote access over the internet, consider:
   - SSH tunneling: `ssh -L 5000:localhost:5000 user@remote-machine`
   - VPN
   - Reverse proxy with SSL

## Troubleshooting

**Can't access from another machine:**
- Check firewall settings
- Ensure the agent is running: `./status_collab.sh`
- Check the correct IP address

**Forgot admin password:**
- Delete `users.json` file
- Restart the agent (it will recreate with default credentials)
- Change the password immediately

**Session not updating:**
- The web interface polls every second for updates
- Check browser console for errors
- Verify the agent is still running

## Development

To run without background mode for development:

```bash
python3 collab_agent.py --web --port 5000
```

## License

Use freely for any purpose.
