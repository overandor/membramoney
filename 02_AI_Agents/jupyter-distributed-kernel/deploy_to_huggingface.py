#!/usr/bin/env python3
"""
Deploy On-Chain Profit Agent to Hugging Face Spaces
Automated deployment script
"""

import os
import subprocess
import json
from pathlib import Path

# Configuration
SPACE_NAME = "onchain-profit-agent"
SPACE_SDK = "gradio"
SPACE_TYPE = "public"  # or "private"

# Files to upload
FILES_TO_UPLOAD = {
    "app.py": "huggingface_app.py",
    "requirements.txt": "huggingface_requirements.txt",
    "README.md": "HUGGINGFACE_DEPLOYMENT.md"
}

def run_command(cmd, check=True):
    """Run a shell command"""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Error: {result.stderr}")
        return False
    return True

def check_huggingface_cli():
    """Check if huggingface-cli is installed"""
    if not run_command("huggingface-cli --version", check=False):
        print("Installing huggingface-cli...")
        return run_command("pip install huggingface_hub")
    return True

def login_to_huggingface():
    """Login to Hugging Face"""
    token = os.environ.get("HUGGING_FACE_API_KEY", "")
    if token:
        print(f"Using token from environment (first 10 chars: {token[:10]}...)")
        return run_command(f"huggingface-cli login --token {token}")
    else:
        print("No token found in environment. Please login manually:")
        return run_command("huggingface-cli login")

def create_space():
    """Create a new Hugging Face Space"""
    print(f"Creating space: {SPACE_NAME}")
    cmd = f"huggingface-cli space create --name {SPACE_NAME} --sdk {SPACE_SDK} --type {SPACE_TYPE}"
    return run_command(cmd)

def upload_files():
    """Upload files to the space"""
    print("Uploading files to space...")
    
    # Copy files to temporary names
    for dest, src in FILES_TO_UPLOAD.items():
        if os.path.exists(src):
            print(f"Copying {src} to {dest}")
            subprocess.run(f"cp {src} {dest}", shell=True)
        else:
            print(f"Warning: {src} not found")
    
    # Upload to space
    for dest in FILES_TO_UPLOAD.keys():
        if os.path.exists(dest):
            print(f"Uploading {dest} to space...")
            run_command(f"huggingface-cli upload {dest} . --repo-type space --repo-id {SPACE_NAME}")

def add_secrets():
    """Add secrets to the space"""
    print("Adding secrets to space...")
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if groq_key:
        print(f"Adding GROQ_API_KEY to space secrets...")
        # Note: This requires huggingface-cli with secret support
        # For now, instruct user to add manually
        print("Please add GROQ_API_KEY manually in Space Settings → Secrets")

def main():
    """Main deployment function"""
    print("=" * 60)
    print("Deploying On-Chain Profit Agent to Hugging Face")
    print("=" * 60)
    
    # Check prerequisites
    if not check_huggingface_cli():
        print("Failed to install huggingface-cli")
        return
    
    # Login
    if not login_to_huggingface():
        print("Failed to login to Hugging Face")
        return
    
    # Create space
    if not create_space():
        print("Failed to create space (it may already exist)")
    
    # Upload files
    upload_files()
    
    # Add secrets
    add_secrets()
    
    print("\n" + "=" * 60)
    print("Deployment Complete!")
    print("=" * 60)
    print(f"Space URL: https://huggingface.co/spaces/YOUR_USERNAME/{SPACE_NAME}")
    print("\nNext steps:")
    print("1. Wait for the space to build (check the Space page)")
    print("2. Add GROQ_API_KEY in Space Settings → Secrets")
    print("3. Test the deployed app")
    print("\nNote: Replace YOUR_USERNAME with your actual Hugging Face username")

if __name__ == "__main__":
    main()
