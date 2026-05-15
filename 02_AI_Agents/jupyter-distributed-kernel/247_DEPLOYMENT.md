# DistKernel Notebook - 24/7 Deployment Guide

## Quick Start (Auto-Restart)

```bash
cd jupyter-distributed-kernel
./start_distkernel.sh
```

This will:
- Start the server with auto-restart enabled
- Log to `logs/distkernel_YYYYMMDD_HHMMSS.log`
- Automatically restart on crash (up to 100 times)
- Exponential backoff: 5s, 10s, 15s... up to 60s

## Systemd Service (Linux)

For production 24/7 operation:

1. Edit `distkernel.service`:
   - Replace `YOUR_USER` with your username
   - Replace `/path/to/jupyter-distributed-kernel` with actual path

2. Install the service:
```bash
sudo cp distkernel.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable distkernel
sudo systemctl start distkernel
```

3. Check status:
```bash
sudo systemctl status distkernel
sudo journalctl -u distkernel -f
```

4. Manage the service:
```bash
sudo systemctl stop distkernel
sudo systemctl restart distkernel
sudo systemctl disable distkernel
```

## macOS Launch Agent

For macOS 24/7 operation:

1. Create `~/Library/LaunchAgents/com.distkernel.notebook.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.distkernel.notebook</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/path/to/jupyter-distributed-kernel/distkernel_notebook.py</string>
        <string>--host</string>
        <string>0.0.0.0</string>
        <string>--port</string>
        <string>8555</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/jupyter-distributed-kernel</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/path/to/jupyter-distributed-kernel/logs/distkernel.log</string>
    <key>StandardErrorPath</key>
    <string>/path/to/jupyter-distributed-kernel/logs/distkernel_error.log</string>
</dict>
</plist>
```

2. Replace paths with your actual paths

3. Load the agent:
```bash
launchctl load ~/Library/LaunchAgents/com.distkernel.notebook.plist
```

4. Unload the agent:
```bash
launchctl unload ~/Library/LaunchAgents/com.distkernel.notebook.plist
```

## Health Checks

Monitor server health:

```bash
# Basic health check
curl http://localhost:8555/health

# Detailed status
curl http://localhost:8555/status

# Check uptime
curl -s http://localhost:8555/health | python3 -m json.tool
```

## Monitoring

The server logs status every 30 seconds:
```
2026-04-18 17:20:43 INFO [distkernel] Uptime: 3600s | Sessions: 5 | Executions: 42
```

## Environment Variables

Required for full functionality:
```bash
GROQ_API_KEY=your_groq_key
GITHUB_API_KEY=your_github_key
HUGGING_FACE_API_KEY=your_hf_key
```

## Logs

Logs are stored in `logs/` directory:
- `distkernel_YYYYMMDD_HHMMSS.log` - Server output
- Auto-rotated on restart

## Troubleshooting

**Server won't start:**
```bash
# Check if port is in use
lsof -ti:8555 | xargs kill -9

# Check Python dependencies
pip3 install aiohttp python-dotenv
```

**Auto-restart loop:**
- Check logs for recurring errors
- Use `--no-restart` flag to disable auto-restart for debugging
```bash
python3 distkernel_notebook.py --no-restart
```

**Memory leaks:**
- The maintenance loop cleans up old executions (>1 hour)
- Monitor with `/status` endpoint
- Restart service periodically if needed

## Production Checklist

- [ ] Set environment variables in .env
- [ ] Configure firewall to allow port 8555
- [ ] Set up systemd service or Launch Agent
- [ ] Configure log rotation
- [ ] Set up monitoring (Prometheus/Grafana optional)
- [ ] Test health check endpoint
- [ ] Test auto-restart (kill process manually)
- [ ] Configure backup for .env and notebook data
