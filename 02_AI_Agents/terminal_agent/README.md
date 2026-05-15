# 24/7 Terminal Agent

A background process that executes scheduled terminal commands with logging and task management.

## Features

- **Scheduled Task Execution**: Run commands at intervals (seconds, minutes, hours, days) or specific times
- **Persistent State**: Tracks execution history and agent status
- **Comprehensive Logging**: All actions logged with timestamps
- **Graceful Shutdown**: Handles signals properly
- **Easy Management**: Start/stop/status scripts included
- **Hot Reload**: Reload configuration without restarting

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Make scripts executable:
```bash
chmod +x start_agent.sh stop_agent.sh status.sh
```

## Usage

### Start the Agent
```bash
./start_agent.sh
```

### Stop the Agent
```bash
./stop_agent.sh
```

### Check Status
```bash
./status.sh
```

### View Logs
```bash
tail -f logs/terminal_agent_$(date +%Y%m%d).log
```

## Configuration

Edit `config.json` to add/modify tasks:

```json
{
  "tasks": {
    "task_name": {
      "command": "your command here",
      "schedule": "every X minutes",
      "enabled": true,
      "description": "Task description"
    }
  }
}
```

### Schedule Formats

- `every X seconds` - Run every X seconds
- `every X minutes` - Run every X minutes
- `every X hours` - Run every X hours
- `every X days` - Run every X days
- `at HH:MM` - Run daily at specific time (24-hour format)

### Example Tasks

```json
{
  "backup_database": {
    "command": "pg_dump mydb > backup.sql",
    "schedule": "every 1 day",
    "enabled": true,
    "description": "Daily database backup"
  },
  "restart_service": {
    "command": "systemctl restart myservice",
    "schedule": "at 03:00",
    "enabled": true,
    "description": "Restart service daily at 3 AM"
  }
}
```

## Hot Reload

To reload configuration without stopping the agent:
```bash
python3 agent.py --reload
```

## View State

To view the agent's current state:
```bash
python3 agent.py --status
```

## Files

- `agent.py` - Main agent script
- `config.json` - Task configuration
- `agent_state.json` - Agent state and execution history
- `start_agent.sh` - Start script
- `stop_agent.sh` - Stop script
- `status.sh` - Status check script
- `logs/` - Log files directory

## Process Management

The agent runs as a background process with PID tracking in `agent.pid`. Use the provided scripts to manage the process safely.
