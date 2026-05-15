# Jupyter Distributed Kernel

A JupyterLab extension that enables **live collaborative notebooks** where compute is backed by each participant's own device resources.

## Architecture

```
┌─────────────────────┐     ┌──────────────────────┐
│   JupyterLab UI     │     │  Participant Devices  │
│  (Extension Panel)  │     │                       │
│  ┌───────────────┐  │     │  ┌─────────────────┐  │
│  │ Notebook Cell  │  │     │  │  Worker Agent    │  │
│  │  → execute()  │──┼────▶│  │  (Python/WASM)   │  │
│  └───────────────┘  │     │  │  - exec cell     │  │
│  ┌───────────────┐  │     │  │  - stream output │  │
│  │ Kernel Select  │  │     │  └────────┬────────┘  │
│  │ Worker Status  │  │     │           │           │
│  └───────────────┘  │     │  ┌────────┴────────┐  │
└────────┬────────────┘     │  │  Worker Agent    │  │
         │                  │  │  (iPhone/Laptop) │  │
         ▼                  │  └─────────────────┘  │
┌─────────────────────┐     └──────────────────────┘
│   Kernel Gateway    │                ▲
│  (WebSocket Server) │────────────────┘
│  - session mgmt     │
│  - cell routing     │
│  - load balancing   │
│  - output relay     │
└─────────────────────┘
```

## Components

### 1. Gateway Server (`distkernel/gateway/`)
WebSocket coordination server that:
- Manages notebook sessions
- Routes cell execution requests to available workers
- Load-balances across connected workers
- Relays execution output back to JupyterLab
- Handles worker health checks and failover

### 2. Compute Worker (`distkernel/worker/`)
Lightweight Python agent that:
- Connects to the gateway via WebSocket
- Registers device capabilities (CPU, memory, GPU)
- Executes notebook cells in isolated namespaces
- Streams stdout/stderr/display_data back in real-time
- Runs on any device: laptop, desktop, iPhone (via Pythonista/Pyto), server

### 3. JupyterLab Extension (`distkernel/labextension/`)
Frontend extension that:
- Adds a "Distributed Workers" sidebar panel
- Shows connected workers and their status
- Provides a custom kernel provisioner that routes to the gateway
- Supports real-time output streaming from remote workers

## Quick Start

```bash
# Install the package
pip install -e .

# Start the gateway
distkernel-gateway --port 8555

# On each participant's device, start a worker
distkernel-worker --gateway ws://GATEWAY_HOST:8555/ws

# In JupyterLab, select "Distributed Kernel" as your kernel
jupyter lab
```

## Protocol

All messages are JSON over WebSocket:

```json
// Worker registration
{"type": "worker.register", "worker_id": "...", "capabilities": {...}}

// Cell execution request (gateway → worker)  
{"type": "cell.execute", "cell_id": "...", "session_id": "...", "code": "..."}

// Execution output (worker → gateway → client)
{"type": "cell.output", "cell_id": "...", "output_type": "stream", "data": {...}}

// Execution complete
{"type": "cell.complete", "cell_id": "...", "status": "ok|error"}
```

## License

MIT
