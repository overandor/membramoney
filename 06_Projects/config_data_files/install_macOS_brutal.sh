#!/bin/bash
# macOS BRUTAL TRADING SUPERVISOR - Installation Script
# GitHub-ready distribution package

echo "🎯" + "█" * 60
echo "█" + " " * 20 + "BRUTALIST INSTALLATION" + " " * 20 + "█"
echo "🎯" + "█" * 60

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "❌ ERROR: This installer is for macOS only!"
    exit 1
fi

# Check Python version
python_version=$(python3 --version 2>&1 | grep -o '[0-9]\+\.[0-9]\+')
required_version="3.8"

if [[ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]]; then
    echo "❌ ERROR: Python 3.8+ required. Found: $python_version"
    echo "💡 Install Python 3.8+ from https://www.python.org/"
    exit 1
fi

echo "✅ Python version: $python_version"

# Create installation directory
INSTALL_DIR="$HOME/BrutalistSupervisor"
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

echo "📁 Installation directory: $INSTALL_DIR"

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip3 install --user pyautogui opencv-python pillow numpy psutil requests pyobjc-framework-quartz

# Check if pip installation was successful
if [ $? -eq 0 ]; then
    echo "✅ Python dependencies installed"
else
    echo "❌ ERROR: Failed to install Python dependencies"
    exit 1
fi

# Install Ollama (optional AI features)
echo "🤖 Installing Ollama for AI features..."
if command -v ollama &> /dev/null; then
    echo "✅ Ollama already installed"
else
    curl -fsSL https://ollama.com/install.sh | sh
    if [ $? -eq 0 ]; then
        echo "✅ Ollama installed"
    else
        echo "⚠️  WARNING: Ollama installation failed (AI features will be disabled)"
    fi
fi

# Start Ollama if installed
if command -v ollama &> /dev/null; then
    echo "🚀 Starting Ollama..."
    ollama serve &
    sleep 5
    
    # Install small AI model
    echo "📥 Installing AI model..."
    ollama pull qwen2.5:0.5b
    if [ $? -eq 0 ]; then
        echo "✅ AI model installed"
    else
        echo "⚠️  WARNING: AI model installation failed"
    fi
fi

# Copy supervisor script
echo "📋 Installing Brutalist Supervisor..."
cp "/Users/alep/Downloads/macOS_brutal_trading_supervisor.py" "$INSTALL_DIR/"

# Create launcher script
cat > "$INSTALL_DIR/brutal_launcher.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
python3 macOS_brutal_trading_supervisor.py
EOF

chmod +x "$INSTALL_DIR/brutal_launcher.sh"

# Create desktop shortcut
echo "🖥️ Creating desktop shortcut..."
cat > "$HOME/Desktop/BrutalistSupervisor.command" << EOF
#!/bin/bash
cd "$INSTALL_DIR"
./brutal_launcher.sh
EOF

chmod +x "$HOME/Desktop/BrutalistSupervisor.command"

# Create configuration file
cat > "$INSTALL_DIR/config.json" << EOF
{
    "screenshot_interval": 180,
    "layout_interval": 300,
    "decision_interval": 240,
    "trading_apps": ["terminal", "python", "chrome", "firefox", "safari"],
    "brutalist_mode": true,
    "ai_enabled": true,
    "aesthetic_priority": 0.3,
    "function_priority": 0.7
}
EOF

echo "✅ Configuration created"

# Installation complete
echo ""
echo "🎯" + "█" * 60
echo "█" + " " * 15 + "INSTALLATION COMPLETE!" + " " * 15 + "█"
echo "🎯" + "█" * 60
echo ""
echo "🚀 LAUNCH OPTIONS:"
echo "   1. Double-click 'BrutalistSupervisor' on Desktop"
echo "   2. Run: $INSTALL_DIR/brutal_launcher.sh"
echo "   3. Run: cd $INSTALL_DIR && python3 macOS_brutal_trading_supervisor.py"
echo ""
echo "📁 INSTALLATION LOCATION: $INSTALL_DIR"
echo "⚙️  CONFIGURATION: $INSTALL_DIR/config.json"
echo "📸 SCREENSHOTS: $INSTALL_DIR/brutal_screenshots/"
echo "📊 LOGS: $INSTALL_DIR/brutal_supervisor.log"
echo ""
echo "⚠️  IMPORTANT: This system will control your windows!"
echo "   Make sure you understand what it does before running."
echo ""
echo "🎯 BRUTALIST TRADING SYSTEM READY!"
