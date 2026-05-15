#!/bin/bash
# Commands to push MetaMask Python Bridge to GitHub
# Run this AFTER creating the repository on GitHub

echo "Replace YOUR_USERNAME with your actual GitHub username below"
echo ""

# Add remote (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/metamask-python-bridge.git

# Set main branch
git branch -M main

# Push to GitHub
git push -u origin main

echo "Done! Repository pushed to GitHub"
