# Arbitrage Opportunity Streaming API

Real-time data streaming endpoints for arbitrage opportunities.

## Architecture

The system now runs on multiple ports:
- **Port 7860**: FastAPI server (includes Gradio UI at `/`)
- **Port 8765**: WebSocket server for real-time streaming

## REST API Endpoints

### Base URL
```
http://localhost:7860
```

### Endpoints

#### GET /
API root with endpoint information.

**Response:**
```json
{
  "name": "Arbitrage Opportunity API",
  "version": "1.0.0",
  "endpoints": {
    "opportunities": "/api/opportunities",
    "metrics": "/api/metrics",
    "rules": "/api/rules",
    "websocket": "ws://localhost:8765"
  }
}
```

#### GET /api/opportunities
Get recent arbitrage opportunities.

**Parameters:**
- `limit` (optional, default: 50) - Number of opportunities to return

**Response:**
```json
{
  "opportunities": [
    {
      "token": "SOL",
      "buy_price": 145.23,
      "sell_price": 146.50,
      "spread": 0.0087,
      "zscore": 2.34,
      "liquidity": 125000,
      "timestamp": 1715023200.0,
      "validated": false
    }
  ],
  "total": 150
}
```

#### GET /api/opportunities/unverified
Get unverified opportunities (pending verification).

**Response:**
```json
{
  "opportunities": [...],
  "total": 23
}
```

#### GET /api/metrics
Get forward-testing metrics.

**Response:**
```json
{
  "win_rate": 0.67,
  "avg_delay": 45.2,
  "avg_spread": 0.0078,
  "avg_zscore": 2.1,
  "verified": 89,
  "total": 150
}
```

#### GET /api/rules
Get current LLM-learned trading rules.

**Response:**
```json
{
  "rules": {
    "min_spread": 0.005,
    "min_liquidity": 50000,
    "best_time_window": null,
    "avoid_tokens": [],
    "expected_latency_decay_sec": 30
  },
  "trades_analyzed": 150
}
```

#### POST /api/rules
Manually update trading rules (with validation).

**Request Body:**
```json
{
  "min_spread": 0.007,
  "min_liquidity": 75000,
  "expected_latency_decay_sec": 25
}
```

**Response:**
```json
{
  "status": "success",
  "rules": {
    "min_spread": 0.007,
    "min_liquidity": 75000,
    ...
  }
}
```

#### GET /api/trades
Get trade memory for analysis.

**Parameters:**
- `limit` (optional, default: 50) - Number of trades to return

**Response:**
```json
{
  "trades": [
    {
      "token": "SOL",
      "spread": 0.0087,
      "liquidity": 125000,
      "time_of_day": 14,
      "success": true,
      "delay": 42.3,
      "mfe": 0.0123,
      "timestamp": 1715023242.0
    }
  ],
  "total": 89
}
```

## WebSocket Streaming

### Connection
```
ws://localhost:8765
```

### Message Format

#### Connection Message
```json
{
  "type": "connected",
  "message": "Connected to arbitrage opportunity stream",
  "timestamp": "2024-05-06T21:00:00.000000"
}
```

#### Opportunity Message
```json
{
  "type": "opportunity",
  "data": {
    "token": "SOL",
    "buy_price": 145.23,
    "sell_price": 146.50,
    "spread": 0.0087,
    "zscore": 2.34,
    "liquidity": 125000,
    "timestamp": 1715023200.0,
    "validated": false
  },
  "timestamp": "2024-05-06T21:00:00.000000"
}
```

## Usage Examples

### Python Client

See `stream_client.py` for a complete example.

```python
import asyncio
import websockets
import json

async def websocket_client():
    uri = "ws://localhost:8765"
    
    async with websockets.connect(uri) as websocket:
        async for message in websocket:
            data = json.loads(message)
            
            if data["type"] == "opportunity":
                opp = data["data"]
                print(f"New opportunity: {opp['token']} - {opp['spread']*100:.2f}%")

asyncio.run(websocket_client())
```

### JavaScript Client

```javascript
const ws = new WebSocket('ws://localhost:8765');

ws.onopen = () => {
  console.log('Connected to WebSocket');
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  if (data.type === 'opportunity') {
    const opp = data.data;
    console.log(`New opportunity: ${opp.token} - ${(opp.spread * 100).toFixed(2)}%`);
  }
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};
```

### cURL Examples

```bash
# Get opportunities
curl http://localhost:7860/api/opportunities?limit=10

# Get metrics
curl http://localhost:7860/api/metrics

# Get rules
curl http://localhost:7860/api/rules

# Update rules
curl -X POST http://localhost:7860/api/rules \
  -H "Content-Type: application/json" \
  -d '{"min_spread": 0.007, "min_liquidity": 75000}'
```

## Running the Server

```bash
# Start the server (includes Gradio UI, REST API, and WebSocket)
python app.py
```

The server will start on:
- **http://localhost:7860** - Gradio UI + REST API
- **ws://localhost:7860** - WebSocket endpoint

## Running the Client

```bash
# Run the example client
python stream_client.py
```

## Deployment

For Hugging Face Spaces, the WebSocket server runs in the background and the REST API is available at the Space URL.

**Note:** Hugging Face Spaces may have restrictions on WebSocket connections. For production, consider deploying to a platform that supports WebSockets natively (e.g., Render, Railway, AWS ECS).
