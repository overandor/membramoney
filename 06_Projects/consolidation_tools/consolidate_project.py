#!/usr/bin/env python3
"""
PROJECT CONSOLIDATOR - GITHUB READY
Consolidates all systems into one deployable project
"""

import os
import shutil
import json
from pathlib import Path

def consolidate_project():
    """Consolidate all systems into one project folder"""
    
    print("🔧 CONSOLIDATING PROJECT FOR GITHUB DEPLOYMENT")
    print("=" * 80)
    
    # Create main project folder
    project_name = "solana-staking-tracker"
    project_path = Path(project_name)
    
    # Clean and create project folder
    if project_path.exists():
        shutil.rmtree(project_path)
    
    project_path.mkdir()
    print(f"📁 Created project folder: {project_name}")
    
    # Core files to include
    core_files = [
        "real_marinade_extractor.py",
        "marinade_deploy.py", 
        "audio_prediction_system.py",
        "MARINADE.py",
        "dex.py"
    ]
    
    # Copy core files
    for file in core_files:
        src = Path(file)
        dst = project_path / file
        
        if src.exists():
            shutil.copy2(src, dst)
            print(f"✅ Copied: {file}")
        else:
            print(f"⚠️  Missing: {file}")
    
    # Create requirements.txt
    requirements = """flask==2.3.3
requests==2.31.0
pandas==2.0.3
numpy==1.24.3
sqlite3
pyaudio==0.2.11
speechrecognition==3.10.0
librosa==0.10.1
soundfile==0.12.1
websockets==11.0.3
solders==0.18.0
solana==0.30.2
driftpy==0.15.0
aiohttp==3.8.5
pyttsx3==2.90
"""
    
    with open(project_path / "requirements.txt", "w") as f:
        f.write(requirements)
    
    print("✅ Created: requirements.txt")
    
    # Create README.md
    readme = """# Solana Staking Tracker

Real-time Solana staking analysis system with wallet tracking and prediction.

## Features

- **Real Marinade Finance Integration** - Pulls actual staking data
- **Wallet Performance Analysis** - Track ROI and growth rates
- **$0 to $20,000 Wallet Detection** - Find high-growth wallets
- **Audio Prediction System** - Voice-based thought prediction
- **Web Dashboard** - Interactive analysis interface
- **Multi-Platform Deployment** - GitHub Actions, Vercel, Netlify

## Quick Start

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run Marinade data extraction:
```bash
python real_marinade_extractor.py
```

3. Start web dashboard:
```bash
python marinade_deploy.py
```

4. Start audio prediction:
```bash
python audio_prediction_system.py
```

## API Endpoints

- `GET /` - Main dashboard
- `POST /api/collect` - Collect Marinade data
- `GET /api/leaderboard` - Get top performers
- `GET /api/0-to-20k` - Find $0→$20K wallets
- `POST /api/recording/start` - Start audio recording

## Deployment

### GitHub Actions
Automatic deployment on push to main branch.

### Vercel
```bash
vercel --prod
```

### Netlify
```bash
netlify deploy --prod --dir=.
```

## Real Data Sources

- Marinade Finance API: https://snapshots-api.marinade.finance/v1/stakers/ns/all
- Solana Explorer: https://explorer.solana.com
- CoinGecko API: https://api.coingecko.com/api/v3/simple/price

## Database

Uses SQLite for local storage:
- `real_marinade_wallets.db` - Staking wallet data
- `audio_prediction.db` - Audio analysis data
- `marinade_deploy.db` - Deployment cache

## License

MIT License
"""
    
    with open(project_path / "README.md", "w") as f:
        f.write(readme)
    
    print("✅ Created: README.md")
    
    # Create GitHub Actions workflow
    workflows_dir = project_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True)
    
    github_workflow = """name: Deploy Solana Staking Tracker

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    
    - name: Test data extraction
      run: |
        python real_marinade_extractor.py
    
    - name: Test web app
      run: |
        python -c "from marinade_deploy import MarinadeDeploySystem; print('Web app import successful')"

  deploy-vercel:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Deploy to Vercel
      uses: amondnet/vercel-action@v25
      with:
        vercel-token: ${{ secrets.VERCEL_TOKEN }}
        vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
        vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
        vercel-args: '--prod'

  deploy-netlify:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Deploy to Netlify
      uses: nwtgck/actions-netlify@v2
      with:
        publish-dir: '.'
        production-branch: main
        github-token: ${{ secrets.GITHUB_TOKEN }}
        deploy-message: 'Deploy from GitHub Actions'
        enable-pull-request-comment: false
        enable-commit-comment: false
        overwrites-pull-request-comment: false
      env:
        NETLIFY_AUTH_TOKEN: ${{ secrets.NETLIFY_AUTH_TOKEN }}
        NETLIFY_SITE_ID: ${{ secrets.NETLIFY_SITE_ID }}
"""
    
    with open(workflows_dir / "deploy.yml", "w") as f:
        f.write(github_workflow)
    
    print("✅ Created: .github/workflows/deploy.yml")
    
    # Create Vercel configuration
    vercel_config = {
        "version": 2,
        "name": "solana-staking-tracker",
        "builds": [
            {
                "src": "marinade_deploy.py",
                "use": "@vercel/python"
            }
        ],
        "routes": [
            {
                "src": "/(.*)",
                "dest": "marinade_deploy.py"
            }
        ]
    }
    
    with open(project_path / "vercel.json", "w") as f:
        json.dump(vercel_config, f, indent=2)
    
    print("✅ Created: vercel.json")
    
    # Create Netlify configuration
    netlify_toml = """[build]
  publish = "."
  command = "echo 'Ready for deployment'"

[build.environment]
  PYTHON_VERSION = "3.9"

[[redirects]]
  from = "/*"
  to = "/.netlify/functions/server"
  status = 200

[functions]
  directory = "netlify/functions"
"""
    
    with open(project_path / "netlify.toml", "w") as f:
        f.write(netlify_toml)
    
    print("✅ Created: netlify.toml")
    
    # Create Netlify function
    netlify_functions_dir = project_path / "netlify" / "functions"
    netlify_functions_dir.mkdir(parents=True)
    
    netlify_function = """import json
from flask import Flask, request

app = Flask(__name__)

# Import Marinade system
import sys
sys.path.append('.')
from marinade_deploy import MarinadeDeploySystem

# Initialize system
system = MarinadeDeploySystem()

def handler(event, context):
    \"\"\"Netlify function handler\"\"\"
    
    # Create Flask test context
    with app.test_request_context(
        path=event.get('path', '/'),
        method=event.get('httpMethod', 'GET'),
        json=event.get('body', {}) if event.get('body') else None
    ):
        # Route to appropriate handler
        path = event.get('path', '/')
        
        if path == '/':
            return system.app.dispatch_request()
        elif path.startswith('/api/'):
            return system.app.dispatch_request()
        else:
            return {"statusCode": 404, "body": "Not found"}
"""

    with open(netlify_functions_dir / "server.py", "w") as f:
        f.write(netlify_function)
    
    print("✅ Created: netlify/functions/server.py")
    
    # Create deployment scripts
    deploy_script = """#!/bin/bash
# Deployment Script for Solana Staking Tracker

echo "🚀 Deploying Solana Staking Tracker..."

# Test the system
echo "📊 Testing data extraction..."
python real_marinade_extractor.py

echo "🌐 Testing web app..."
python -c "from marinade_deploy import MarinadeDeploySystem; print('✅ Web app ready')"

# Deploy to Vercel
if command -v vercel &> /dev/null; then
    echo "🔗 Deploying to Vercel..."
    vercel --prod
else
    echo "⚠️  Vercel CLI not found. Install with: npm i -g vercel"
fi

# Deploy to Netlify
if command -v netlify &> /dev/null; then
    echo "🔗 Deploying to Netlify..."
    netlify deploy --prod --dir=.
else
    echo "⚠️  Netlify CLI not found. Install with: npm i -g netlify-cli"
fi

echo "✅ Deployment complete!"
echo "🌐 Vercel: https://solana-staking-tracker.vercel.app"
echo "🌐 Netlify: https://solana-staking-tracker.netlify.app"
"""
    
    with open(project_path / "deploy.sh", "w") as f:
        f.write(deploy_script)
    
    # Make deploy script executable
    os.chmod(project_path / "deploy.sh", 0o755)
    
    print("✅ Created: deploy.sh")
    
    # Create Docker configuration
    dockerfile = """FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    portaudio19-dev \\
    gcc \\
    g++ \\
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8095

# Run the application
CMD ["python", "marinade_deploy.py"]
"""
    
    with open(project_path / "Dockerfile", "w") as f:
        f.write(dockerfile)
    
    print("✅ Created: Dockerfile")
    
    # Create docker-compose
    docker_compose = """version: '3.8'

services:
  solana-tracker:
    build: .
    ports:
      - "8095:8095"
    environment:
      - PYTHONUNBUFFERED=1
    volumes:
      - ./data:/app/data
    restart: unless-stopped
  
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - solana-tracker
"""
    
    with open(project_path / "docker-compose.yml", "w") as f:
        f.write(docker_compose)
    
    print("✅ Created: docker-compose.yml")
    
    # Create .gitignore
    gitignore = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
env/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Database
*.db
*.sqlite
*.sqlite3

# Logs
*.log

# Audio files
*.wav
*.mp3
audio_sessions/

# Environment
.env
.env.local

# Node modules (for deployment)
node_modules/
"""
    
    with open(project_path / ".gitignore", "w") as f:
        f.write(gitignore)
    
    print("✅ Created: .gitignore")
    
    # Copy any existing databases
    db_files = ["real_marinade_wallets.db", "marinade_deploy.db", "solana_wallets.db"]
    
    for db_file in db_files:
        src = Path(db_file)
        if src.exists():
            dst = project_path / db_file
            shutil.copy2(src, dst)
            print(f"✅ Copied database: {db_file}")
    
    print(f"\n🎉 PROJECT CONSOLIDATION COMPLETE!")
    print(f"📁 Project folder: {project_name}")
    print(f"📊 Ready for GitHub deployment")
    print(f"🚀 Run 'cd {project_name} && ./deploy.sh' to deploy")
    
    return project_name

if __name__ == "__main__":
    project_folder = consolidate_project()
    
    print(f"\n📋 NEXT STEPS:")
    print(f"1. cd {project_folder}")
    print(f"2. git init")
    print(f"3. git add .")
    print(f"4. git commit -m 'Initial commit'")
    print(f"5. git remote add origin <your-repo-url>")
    print(f"6. git push -u origin main")
    print(f"7. Set up GitHub secrets for deployment")
    print(f"8. ./deploy.sh")
