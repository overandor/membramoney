#!/bin/bash

# GitHub Upload Script for Trading Development Systems

echo "🚀 GitHub Upload Script for Trading Development Systems"
echo "======================================================"

# Check if git remote exists
if git remote get-url origin 2>/dev/null; then
    echo "✅ Remote 'origin' already exists"
    echo "📍 Current remote: $(git remote get-url origin)"
else
    echo "❌ No remote 'origin' found"
    echo ""
    echo "📋 To complete the upload:"
    echo "1. Go to https://github.com and create a new repository"
    echo "2. Name it: trading-development-systems"
    echo "3. Copy the repository URL (HTTPS)"
    echo "4. Run: git remote add origin YOUR_REPO_URL"
    echo "5. Run: git push -u origin main"
    echo ""
    echo "🔗 Example:"
    echo "   git remote add origin https://github.com/YOUR_USERNAME/trading-development-systems.git"
    echo "   git push -u origin main"
fi

echo ""
echo "📊 Repository Status:"
echo "===================="
echo "📁 Files: $(git ls-files | wc -l) files"
echo "📝 Total lines: $(git ls-files | xargs wc -l | tail -1 | awk '{print $1}')"
echo "💾 Size: $(du -sh . | cut -f1)"
echo ""

echo "📋 Files to be uploaded:"
git ls-files | while read file; do
    size=$(du -h "$file" | cut -f1)
    lines=$(wc -l < "$file")
    echo "  📄 $file ($size, $lines lines)"
done

echo ""
echo "🎯 Ready to upload to GitHub!"
echo "============================="
