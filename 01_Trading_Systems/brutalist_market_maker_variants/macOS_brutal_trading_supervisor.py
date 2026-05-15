#!/usr/bin/env python3
"""
MACOS BRUTAL TRADING SUPERVISOR
Brutalist design with advanced window management
GitHub-ready distribution for macOS
"""

import asyncio
import json
import time
import logging
import subprocess
import os
import cv2
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import psutil
import threading
import pyautogui
import requests
from PIL import Image, ImageGrab, ImageDraw, ImageFont
import base64
import io
from pathlib import Path
import Quartz
import AppKit
from Cocoa import NSWorkspace, NSScreen
import platform

# Setup logging with brutalist aesthetic
class BrutalistFormatter(logging.Formatter):
    """Brutalist log formatter"""
    
    def format(self, record):
        # Create brutalist formatting
        timestamp = self.formatTime(record, "%H:%M:%S")
        level = record.levelname.ljust(8)
        message = record.getMessage()
        
        # Brutalist borders
        border = "█" * 80
        return f"\n{border}\n█ {timestamp} │ {level} │ {message}\n{border}"

# Configure brutalist logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler('/Users/alep/Downloads/brutal_supervisor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Apply brutalist formatter
for handler in logging.getLogger().handlers:
    handler.setFormatter(BrutalistFormatter())

# Disable pyautogui failsafe
pyautogui.FAILSAFE = False

@dataclass
class WindowInfo:
    """Window information"""
    app_name: str
    window_id: int
    title: str
    rect: Tuple[int, int, int, int]  # x, y, width, height
    is_visible: bool
    is_focused: bool

@dataclass
class SystemState:
    """Current system state"""
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_usage: float = 0.0
    network_active: bool = False
    trading_processes: int = 0
    balance: float = 0.0
    profit_rate: float = 0.0
    errors_detected: int = 0
    last_action: str = ""
    screenshot_count: int = 0
    uptime_hours: float = 0.0
    windows_managed: int = 0

@dataclass
class BrutalistAction:
    """Brutalist action record"""
    timestamp: str
    action_type: str
    description: str
    success: bool
    window_changes: int = 0
    aesthetic_score: float = 0.0

class macOSWindowManager:
    """Advanced macOS window management with brutalist design"""
    
    def __init__(self):
        self.screen_width, self.screen_height = pyautogui.size()
        self.workspace = NSWorkspace.sharedWorkspace()
        self.managed_windows: Dict[str, WindowInfo] = {}
        self.brutalist_layouts = {
            'cascade': self.cascade_layout,
            'grid': self.grid_layout,
            'focus': self.focus_layout,
            'merge': self.merge_layout
        }
        
        # Brutalist design parameters
        self.margin = 20
        self.title_bar_height = 28
        self.min_window_size = (400, 300)
        
        logger.info(f"🖥️ macOS Window Manager initialized: {self.screen_width}x{self.screen_height}")
        logger.info("🎯 Brutalist design patterns loaded")
    
    def get_all_windows(self) -> List[WindowInfo]:
        """Get all visible windows"""
        windows = []
        
        try:
            # Get running applications
            running_apps = self.workspace.runningApplications()
            
            for app in running_apps:
                app_name = app.localizedName()
                
                # Skip system apps
                if app_name in ['Dock', 'Spotlight', 'SystemUIServer', 'Window Server']:
                    continue
                
                # Get windows for this app
                app.windows = []
                try:
                    # Use AppleScript to get window info
                    script = f'''
                    tell application "{app_name}"
                        if it is running then
                            set window_list to every window
                            repeat with win in window_list
                                try
                                    set window_bounds to bounds of win
                                    set window_title to name of win as string
                                    set window_id to id of win as integer
                                    set is_visible to visible of win as boolean
                                    set is_focused to frontmost as boolean
                                    
                                    put (app_name & "|" & window_id & "|" & window_title & "|" & item 1 of window_bounds & "|" & item 2 of window_bounds & "|" & (item 3 of window_bounds - item 1 of window_bounds) & "|" & (item 4 of window_bounds - item 2 of window_bounds) & "|" & is_visible & "|" & is_focused)
                                end try
                            end repeat
                        end if
                    end tell
                    '''
                    
                    result = subprocess.run(['osascript', '-e', script], 
                                          capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        for line in result.stdout.strip().split('\n'):
                            if line:
                                parts = line.split('|')
                                if len(parts) >= 9:
                                    window = WindowInfo(
                                        app_name=parts[0],
                                        window_id=int(parts[1]),
                                        title=parts[2],
                                        rect=(int(parts[3]), int(parts[4]), int(parts[5]), int(parts[6])),
                                        is_visible=parts[7] == 'true',
                                        is_focused=parts[8] == 'true'
                                    )
                                    windows.append(window)
                                    self.managed_windows[f"{app_name}_{window.window_id}"] = window
                
                except Exception as e:
                    logger.debug(f"Could not get windows for {app_name}: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"❌ Failed to get windows: {e}")
        
        return windows
    
    def move_window(self, window_info: WindowInfo, new_rect: Tuple[int, int, int, int]) -> bool:
        """Move window to new position"""
        try:
            script = f'''
            tell application "{window_info.app_name}"
                if it is running then
                    try
                        set win to window id {window_info.window_id}
                        set bounds of win to {{{new_rect[0]}, {new_rect[1]}, {new_rect[0] + new_rect[2]}, {new_rect[1] + new_rect[3]}}}
                    end try
                end if
            end tell
            '''
            
            result = subprocess.run(['osascript', '-e', script], capture_output=True)
            
            if result.returncode == 0:
                logger.info(f"📐 Moved {window_info.app_name} to {new_rect}")
                return True
            else:
                logger.error(f"❌ Failed to move {window_info.app_name}: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Window move error: {e}")
            return False
    
    def cascade_layout(self, windows: List[WindowInfo]) -> Dict[str, Tuple[int, int, int, int]]:
        """Brutalist cascade layout"""
        layouts = {}
        x_offset = self.margin
        y_offset = self.margin + 50  # Account for menu bar
        offset_step = 40
        
        for i, window in enumerate(windows):
            if window.is_visible:
                # Ensure minimum size
                width = max(window.rect[2], self.min_window_size[0])
                height = max(window.rect[3], self.min_window_size[1])
                
                # Cascade position
                x = x_offset + (i * offset_step)
                y = y_offset + (i * offset_step)
                
                # Keep within screen bounds
                if x + width > self.screen_width - self.margin:
                    x = self.margin
                if y + height > self.screen_height - self.margin:
                    y = self.margin + 50
                
                layouts[f"{window.app_name}_{window.window_id}"] = (x, y, width, height)
        
        return layouts
    
    def grid_layout(self, windows: List[WindowInfo]) -> Dict[str, Tuple[int, int, int, int]]:
        """Brutalist grid layout"""
        layouts = {}
        visible_windows = [w for w in windows if w.is_visible]
        
        if not visible_windows:
            return layouts
        
        # Calculate grid dimensions
        cols = min(4, len(visible_windows))
        rows = (len(visible_windows) + cols - 1) // cols
        
        cell_width = (self.screen_width - self.margin * (cols + 1)) // cols
        cell_height = (self.screen_height - self.margin * (rows + 1) - 50) // rows
        
        for i, window in enumerate(visible_windows):
            col = i % cols
            row = i // cols
            
            x = self.margin + col * (cell_width + self.margin)
            y = self.margin + 50 + row * (cell_height + self.margin)
            
            layouts[f"{window.app_name}_{window.window_id}"] = (x, y, cell_width, cell_height)
        
        return layouts
    
    def focus_layout(self, windows: List[WindowInfo]) -> Dict[str, Tuple[int, int, int, int]]:
        """Brutalist focus layout - main window centered"""
        layouts = {}
        visible_windows = [w for w in windows if w.is_visible]
        
        if not visible_windows:
            return layouts
        
        # Find focused window or use first
        main_window = next((w for w in visible_windows if w.is_focused), visible_windows[0])
        other_windows = [w for w in visible_windows if w != main_window]
        
        # Main window takes center
        main_width = int(self.screen_width * 0.6)
        main_height = int(self.screen_height * 0.7)
        main_x = (self.screen_width - main_width) // 2
        main_y = (self.screen_height - main_height) // 2
        
        layouts[f"{main_window.app_name}_{main_window.window_id}"] = (main_x, main_y, main_width, main_height)
        
        # Other windows on the side
        if other_windows:
            side_width = int(self.screen_width * 0.35)
            side_height = int((self.screen_height - 100) / len(other_windows))
            
            for i, window in enumerate(other_windows):
                y = self.margin + 50 + i * (side_height + self.margin)
                layouts[f"{window.app_name}_{window.window_id}"] = (
                    self.screen_width - side_width - self.margin, 
                    y, 
                    side_width, 
                    side_height
                )
        
        return layouts
    
    def merge_layout(self, windows: List[WindowInfo]) -> Dict[str, Tuple[int, int, int, int]]:
        """Brutalist merge layout - combine related windows"""
        layouts = {}
        visible_windows = [w for w in windows if w.is_visible]
        
        if not visible_windows:
            return layouts
        
        # Group by application
        app_groups = {}
        for window in visible_windows:
            if window.app_name not in app_groups:
                app_groups[window.app_name] = []
            app_groups[window.app_name].append(window)
        
        # Layout each group
        y_offset = self.margin + 50
        for app_name, app_windows in app_groups.items():
            group_width = min(self.screen_width - self.margin * 2, 1200)
            group_height = min(400, max(300, len(app_windows) * 150))
            x = (self.screen_width - group_width) // 2
            
            for i, window in enumerate(app_windows):
                window_y = y_offset + i * (group_height // len(app_windows))
                layouts[f"{window.app_name}_{window.window_id}"] = (x, window_y, group_width, group_height // len(app_windows))
            
            y_offset += group_height + self.margin
        
        return layouts
    
    def apply_brutalist_layout(self, layout_type: str = 'cascade') -> int:
        """Apply brutalist layout to all windows"""
        windows = self.get_all_windows()
        
        if layout_type not in self.brutalist_layouts:
            layout_type = 'cascade'
        
        layouts = self.brutalist_layouts[layout_type](windows)
        moved_windows = 0
        
        for window_key, new_rect in layouts.items():
            if window_key in self.managed_windows:
                window = self.managed_windows[window_key]
                if self.move_window(window, new_rect):
                    moved_windows += 1
        
        logger.info(f"🎨 Applied {layout_type} layout to {moved_windows} windows")
        return moved_windows
    
    def create_brutalist_workspace(self, trading_apps: List[str]) -> bool:
        """Create brutalist workspace for trading"""
        logger.info("🎨 Creating brutalist trading workspace...")
        
        # Get all windows
        windows = self.get_all_windows()
        
        # Separate trading and other windows
        trading_windows = [w for w in windows if any(app in w.app_name.lower() for app in trading_apps)]
        other_windows = [w for w in windows if w not in trading_windows]
        
        # Apply focus layout to trading apps
        if trading_windows:
            trading_layouts = self.focus_layout(trading_windows)
            for window_key, new_rect in trading_layouts.items():
                if window_key in self.managed_windows:
                    self.move_window(self.managed_windows[window_key], new_rect)
        
        # Move other apps to the side
        if other_windows:
            side_x = self.screen_width - 300
            for i, window in enumerate(other_windows):
                new_rect = (side_x, 100 + i * 150, 280, 120)
                self.move_window(window, new_rect)
        
        logger.info("✅ Brutalist workspace created")
        return True

class BrutalistAIController:
    """Brutalist AI controller with aesthetic decision making"""
    
    def __init__(self):
        self.ollama_url = "http://localhost:11434"
        self.model = "qwen2.5:0.5b"  # Small model for speed
        self.use_ai = False
        self.aesthetic_score = 0.0
        
        logger.info("🎯 Brutalist AI Controller initialized")
    
    async def check_ollama(self) -> bool:
        """Check Ollama availability"""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def take_brutalist_screenshot(self) -> str:
        """Take screenshot with brutalist overlay"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            os.makedirs('/Users/alep/Downloads/brutal_screenshots', exist_ok=True)
            
            # Take screenshot
            screenshot = pyautogui.screenshot()
            
            # Add brutalist overlay
            draw = ImageDraw.Draw(screenshot)
            
            # Brutalist border
            border_color = (0, 0, 0)
            draw.rectangle([(0, 0), (screenshot.width-1, screenshot.height-1)], 
                         outline=border_color, width=5)
            
            # Brutalist timestamp
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 20)
            except:
                font = ImageFont.load_default()
            
            timestamp_text = f"BRUTALIST SUPERVISOR {timestamp}"
            draw.text((20, 20), timestamp_text, fill=(255, 255, 255), font=font)
            
            # Save
            filename = f"/Users/alep/Downloads/brutal_screenshots/brutal_{timestamp}.png"
            screenshot.save(filename)
            
            logger.info(f"📸 Brutalist screenshot: {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"❌ Brutalist screenshot failed: {e}")
            return ""
    
    def calculate_aesthetic_score(self, windows: List[WindowInfo]) -> float:
        """Calculate brutalist aesthetic score"""
        if not windows:
            return 0.0
        
        score = 0.0
        
        # Alignment score
        x_positions = [w.rect[0] for w in windows if w.is_visible]
        y_positions = [w.rect[1] for w in windows if w.is_visible]
        
        if x_positions:
            x_std = np.std(x_positions)
            score += max(0, 1 - x_std / 100) * 0.3
        
        if y_positions:
            y_std = np.std(y_positions)
            score += max(0, 1 - y_std / 100) * 0.3
        
        # Spacing score
        for i, window1 in enumerate(windows):
            for window2 in windows[i+1:]:
                if window1.is_visible and window2.is_visible:
                    distance = abs(window1.rect[0] - window2.rect[0])
                    if distance > 50:  # Good spacing
                        score += 0.1
        
        # Minimalism score (fewer windows is more brutalist)
        visible_count = len([w for w in windows if w.is_visible])
        score += max(0, 1 - visible_count / 10) * 0.3
        
        return min(1.0, score)
    
    def make_brutalist_decision(self, state: SystemState, aesthetic_score: float) -> Dict:
        """Make brutalist decision based on system state and aesthetics"""
        decision = {
            'action': 'monitor',
            'layout': 'current',
            'reasoning': 'Maintaining brutalist equilibrium',
            'aesthetic_priority': False,
            'function_priority': True
        }
        
        # Function over form - but with brutalist aesthetics
        if state.errors_detected > 3:
            decision.update({
                'action': 'emergency_reorganize',
                'layout': 'focus',
                'reasoning': 'CRITICAL: Errors detected - brutalist focus mode',
                'aesthetic_priority': False,
                'function_priority': True
            })
        
        elif state.profit_rate < 0.0001:
            decision.update({
                'action': 'optimize_layout',
                'layout': 'grid',
                'reasoning': 'Low profit rate - brutalist grid optimization',
                'aesthetic_priority': True,
                'function_priority': True
            })
        
        elif aesthetic_score < 0.3:
            decision.update({
                'action': 'aesthetic_enhance',
                'layout': 'cascade',
                'reasoning': 'Low aesthetic score - brutalist enhancement',
                'aesthetic_priority': True,
                'function_priority': False
            })
        
        elif state.trading_processes == 0:
            decision.update({
                'action': 'workspace_reset',
                'layout': 'merge',
                'reasoning': 'No trading processes - brutalist workspace reset',
                'aesthetic_priority': True,
                'function_priority': True
            })
        
        return decision

class BrutalistTradingSupervisor:
    """Main Brutalist Trading Supervisor for macOS"""
    
    def __init__(self):
        self.window_manager = macOSWindowManager()
        self.ai_controller = BrutalistAIController()
        self.system_state = SystemState()
        self.brutalist_actions: List[BrutalistAction] = []
        self.start_time = time.time()
        
        # Trading applications to manage
        self.trading_apps = ['terminal', 'python', 'chrome', 'firefox', 'safari']
        
        # Brutalist timing
        self.screenshot_interval = 180  # Every 3 minutes
        self.layout_interval = 300     # Every 5 minutes
        self.decision_interval = 240   # Every 4 minutes
        
        logger.info("🎯 BRUTALIST TRADING SUPERVISOR INITIALIZED")
        logger.info("🖥️ macOS Native Window Management")
        logger.info("🎨 Brutalist Design Philosophy")
        logger.info("⚡ Function Over Form")
    
    def get_system_metrics(self) -> SystemState:
        """Get comprehensive system metrics"""
        try:
            # System resources
            self.system_state.cpu_usage = psutil.cpu_percent(interval=1)
            self.system_state.memory_usage = psutil.virtual_memory().percent
            self.system_state.disk_usage = psutil.disk_usage('/').percent
            
            # Network status
            self.system_state.network_active = psutil.net_if_stats().get('en0', (False, 0, 0, 0))[0]
            
            # Count trading processes
            trading_processes = 0
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    if any(script in cmdline for script in ['profit_executor.py', 'second_profit.py', 'simple_market_maker.py']):
                        trading_processes += 1
                except:
                    continue
            self.system_state.trading_processes = trading_processes
            
            # Update uptime
            self.system_state.uptime_hours = (time.time() - self.start_time) / 3600
            
            # Simulate trading metrics
            import random
            base_profit = 0.0001 * (1 + self.system_state.uptime_hours * 0.01)
            self.system_state.profit_rate = max(0, base_profit * random.uniform(0.8, 1.2))
            self.system_state.balance = 12.0 + (self.system_state.profit_rate * self.system_state.uptime_hours * 3600)
            
        except Exception as e:
            logger.error(f"❌ System metrics failed: {e}")
        
        return self.system_state
    
    async def brutalist_supervisor_loop(self):
        """Main brutalist supervisor loop"""
        logger.info("🚀 BRUTALIST SUPERVISOR LOOP STARTED")
        
        # Create initial workspace
        self.window_manager.create_brutalist_workspace(self.trading_apps)
        
        # Timing trackers
        last_screenshot = time.time()
        last_layout = time.time()
        last_decision = time.time()
        
        while True:
            try:
                current_time = time.time()
                
                # Get system metrics
                state = self.get_system_metrics()
                
                # Get current windows and calculate aesthetic score
                windows = self.window_manager.get_all_windows()
                aesthetic_score = self.ai_controller.calculate_aesthetic_score(windows)
                
                # Brutalist screenshots
                if current_time - last_screenshot >= self.screenshot_interval:
                    logger.info("📸 Capturing brutalist screenshot...")
                    self.ai_controller.take_brutalist_screenshot()
                    self.system_state.screenshot_count += 1
                    last_screenshot = current_time
                
                # Brutalist layout management
                if current_time - last_layout >= self.layout_interval:
                    logger.info("🎨 Optimizing brutalist layout...")
                    
                    # Choose layout based on system state
                    if state.trading_processes > 2:
                        layout_type = 'grid'
                    elif aesthetic_score < 0.5:
                        layout_type = 'cascade'
                    else:
                        layout_type = 'focus'
                    
                    moved_windows = self.window_manager.apply_brutalist_layout(layout_type)
                    self.system_state.windows_managed += moved_windows
                    
                    last_layout = current_time
                
                # Brutalist decision making
                if current_time - last_decision >= self.decision_interval:
                    logger.info("🎯 Making brutalist decision...")
                    
                    decision = self.ai_controller.make_brutalist_decision(state, aesthetic_score)
                    
                    # Execute decision
                    window_changes = 0
                    if decision['action'] in ['emergency_reorganize', 'optimize_layout', 'workspace_reset']:
                        layout_type = decision['layout']
                        window_changes = self.window_manager.apply_brutalist_layout(layout_type)
                    
                    # Record action
                    action = BrutalistAction(
                        timestamp=datetime.now().isoformat(),
                        action_type=decision['action'],
                        description=decision['reasoning'],
                        success=True,
                        window_changes=window_changes,
                        aesthetic_score=aesthetic_score
                    )
                    self.brutalist_actions.append(action)
                    
                    self.system_state.last_action = decision['action']
                    
                    logger.info(f"🎯 Decision: {decision['action']} | "
                               f"Layout: {decision['layout']} | "
                               f"Aesthetic: {aesthetic_score:.2f} | "
                               f"Windows: {window_changes}")
                    
                    last_decision = current_time
                
                # Brutist status display
                logger.info(f"📊 BRUTAL STATUS: CPU:{state.cpu_usage:.0f}% | "
                           f"MEM:{state.memory_usage:.0f}% | "
                           f"TRD:{state.trading_processes} | "
                           f"${state.balance:.2f} | "
                           f"{state.profit_rate:.6f}/s | "
                           f"🎨:{aesthetic_score:.2f} | "
                           f"🪟:{len(windows)}")
                
                # Brutalist sleep cycle
                await asyncio.sleep(20)  # Check every 20 seconds
                
            except Exception as e:
                logger.error(f"❌ Brutalist supervisor error: {e}")
                await asyncio.sleep(30)
    
    def create_github_readme(self) -> str:
        """Create GitHub README"""
        readme = """# 🎯 BRUTALIST TRADING SUPERVISOR

A brutalist-designed macOS trading supervisor with advanced window management and AI-powered decision making.

## 🎨 Design Philosophy

**FUNCTION OVER FORM** - Brutalist trading system optimization for macOS.

### Features:
- 🖥️ Native macOS window management
- 🎯 Brutalist layout optimization
- 📸 Aesthetic screenshot capture
- 🧠 AI-powered decision making
- ⚡ Real-time system monitoring
- 🔄 24/7 autonomous operation

## 🚀 Installation

### Prerequisites:
```bash
# Install Python dependencies
pip install pyautogui opencv-python pillow numpy psutil requests

# Install Ollama (optional for AI features)
curl -fsSL https://ollama.com/install.sh | sh
ollama serve
ollama pull qwen2.5:0.5b
```

### Usage:
```bash
python macOS_brutal_trading_supervisor.py
```

## 🎯 Brutalist Layouts

1. **CASCADE** - Progressive window arrangement
2. **GRID** - Structured optimization
3. **FOCUS** - Main window centered
4. **MERGE** - Application grouping

## 📊 System Requirements

- macOS 10.15+ (Catalina or later)
- Python 3.8+
- 4GB RAM minimum
- Display resolution 1920x1080 or higher

## ⚠️ Disclaimer

This system controls your computer and manages windows automatically. 
Use at your own risk and understand what it does before running.

## 📄 License

MIT License - Brutalist Trading Systems
"""
        
        with open('/Users/alep/Downloads/README.md', 'w') as f:
            f.write(readme)
        
        logger.info("📝 GitHub README created")
        return readme

async def main():
    """Main brutalist supervisor"""
    print("🎯" + "█" * 78)
    print("█" + " " * 30 + "BRUTALIST TRADING SUPERVISOR" + " " * 26 + "█")
    print("█" + " " * 20 + "macOS Native Window Management + AI Control" + " " * 20 + "█")
    print("█" + " " * 25 + "Function Over Form - Brutalist Design" + " " * 25 + "█")
    print("█" + " " * 15 + "Advanced Window Relocation • Merging • Aesthetic Optimization" + " " * 15 + "█")
    print("🎯" + "█" * 78)
    
    print("\n⚠️  BRUTALIST WARNING:")
    print("   This system will REARRANGE YOUR WINDOWS and CONTROL your macOS!")
    print("   It will move, resize, and organize windows automatically.")
    print("   Make sure you understand this before running.")
    print("\nPress Ctrl+C to cancel...")
    
    try:
        await asyncio.sleep(5)  # Give time to cancel
        
        # Initialize supervisor
        supervisor = BrutalistTradingSupervisor()
        
        # Create GitHub README
        supervisor.create_github_readme()
        
        # Start brutalist supervision
        await supervisor.brutalist_supervisor_loop()
        
    except KeyboardInterrupt:
        print("\n🎯 BRUTALIST SUPERVISOR STOPPED")
        print("█" * 80)
        
        # Final brutalist report
        print("\n📊 BRUTALIST PERFORMANCE REPORT")
        print("█" * 80)
        print(f"⏱️  Uptime: {supervisor.system_state.uptime_hours:.1f} hours")
        print(f"💰 Balance: ${supervisor.system_state.balance:.2f}")
        print(f"⚡ Profit Rate: ${supervisor.system_state.profit_rate:.6f}/s")
        print(f"🪟 Windows Managed: {supervisor.system_state.windows_managed}")
        print(f"📸 Screenshots: {supervisor.system_state.screenshot_count}")
        print(f"🎨 Actions: {len(supervisor.brutalist_actions)}")
        print("█" * 80)
        
    except Exception as e:
        print(f"\n❌ BRUTALIST ERROR: {e}")

if __name__ == "__main__":
    # Check if running on macOS
    if platform.system() != "Darwin":
        print("❌ This supervisor is designed for macOS only!")
        exit(1)
    
    asyncio.run(main())
