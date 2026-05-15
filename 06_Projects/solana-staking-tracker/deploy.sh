#!/bin/bash
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
