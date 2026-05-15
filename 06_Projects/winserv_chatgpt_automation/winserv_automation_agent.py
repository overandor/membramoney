#!/usr/bin/env python3
"""
Windsurf + ChatGPT Automation Agent
Automatically clicks "Accept All" on Windsurf and copies/pastes from ChatGPT
"""

import pyautogui
import pyperclip
import time
import logging
import threading
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('windsurf_automation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class WindsurfAutomationAgent:
    def __init__(self, 
                 accept_all_coords=None,
                 chatgpt_tab_hotkey='command+1',
                 windsurf_tab_hotkey='command+2',
                 paste_destination_coords=None,
                 loop_delay=5.0):
        """
        Initialize the automation agent
        
        Args:
            accept_all_coords: (x, y) coordinates of "Accept All" button
            chatgpt_tab_hotkey: Hotkey to switch to ChatGPT tab
            windsurf_tab_hotkey: Hotkey to switch to Windsurf tab
            paste_destination_coords: (x, y) coordinates to click before pasting
            loop_delay: Seconds to wait between iterations
        """
        self.accept_all_coords = accept_all_coords
        self.chatgpt_tab_hotkey = chatgpt_tab_hotkey
        self.windsurf_tab_hotkey = windsurf_tab_hotkey
        self.paste_destination_coords = paste_destination_coords
        self.loop_delay = loop_delay
        self.running = False
        self.iteration_count = 0
        
        # Safety settings
        pyautogui.PAUSE = 0.5
        pyautogui.FAILSAFE = True
        
    def locate_accept_all_button(self):
        """Try to locate the 'Accept All' button in Windsurf using image recognition"""
        try:
            # Try to find the button by image
            button_location = pyautogui.locateOnScreen('windsurf_accept_all.png', confidence=0.8)
            if button_location:
                center = pyautogui.center(button_location)
                logger.info(f"Found 'Accept All' button at {center}")
                return center
            else:
                logger.warning("Could not locate 'Accept All' button by image")
                return None
        except Exception as e:
            logger.error(f"Error locating button: {e}")
            return None
    
    def click_accept_all(self):
        """Click the Accept All button in Windsurf"""
        try:
            if self.accept_all_coords:
                # Use predefined coordinates
                x, y = self.accept_all_coords
                pyautogui.click(x, y)
                logger.info(f"Clicked Accept All at ({x}, {y})")
            else:
                # Try to locate the button
                coords = self.locate_accept_all_button()
                if coords:
                    pyautogui.click(coords[0], coords[1])
                    logger.info(f"Clicked Accept All at {coords}")
                else:
                    logger.warning("No coordinates available for Accept All button")
                    return False
            return True
        except Exception as e:
            logger.error(f"Error clicking Accept All: {e}")
            return False
    
    def switch_to_chatgpt(self):
        """Switch to ChatGPT tab/window"""
        try:
            # Parse hotkey (e.g., 'ctrl+1' -> ['ctrl', '1'])
            keys = self.chatgpt_tab_hotkey.split('+')
            if len(keys) > 1:
                pyautogui.hotkey(*keys)
            else:
                pyautogui.press(keys[0])
            time.sleep(0.5)
            logger.info(f"Switched to ChatGPT using {self.chatgpt_tab_hotkey}")
        except Exception as e:
            logger.error(f"Error switching to ChatGPT: {e}")
    
    def switch_to_windsurf(self):
        """Switch to Windsurf tab/window"""
        try:
            # Parse hotkey (e.g., 'ctrl+2' -> ['ctrl', '2'])
            keys = self.windsurf_tab_hotkey.split('+')
            if len(keys) > 1:
                pyautogui.hotkey(*keys)
            else:
                pyautogui.press(keys[0])
            time.sleep(0.5)
            logger.info(f"Switched to Windsurf using {self.windsurf_tab_hotkey}")
        except Exception as e:
            logger.error(f"Error switching to Windsurf: {e}")
    
    def copy_last_chatgpt_message(self):
        """Copy the last message from ChatGPT"""
        try:
            # Navigate to the end of the conversation
            pyautogui.hotkey('command', 'end')
            time.sleep(0.3)
            
            # Select the last message (shift+up to select)
            pyautogui.keyDown('shift')
            for _ in range(5):  # Adjust number of lines as needed
                pyautogui.press('up')
                time.sleep(0.1)
            pyautogui.keyUp('shift')
            
            # Copy to clipboard (Mac uses command+c)
            pyautogui.hotkey('command', 'c')
            time.sleep(0.3)
            
            # Verify clipboard content
            clipboard_content = pyperclip.paste()
            if clipboard_content:
                logger.info(f"Copied ChatGPT message ({len(clipboard_content)} chars)")
                return clipboard_content
            else:
                logger.warning("Clipboard is empty after copy")
                return None
        except Exception as e:
            logger.error(f"Error copying from ChatGPT: {e}")
            return None
    
    def paste_to_destination(self):
        """Paste clipboard content to destination"""
        try:
            if self.paste_destination_coords:
                # Click at destination first
                x, y = self.paste_destination_coords
                pyautogui.click(x, y)
                time.sleep(0.2)
            
            # Paste content (Mac uses command+v)
            pyautogui.hotkey('command', 'v')
            time.sleep(0.3)
            logger.info("Pasted content to destination")
            return True
        except Exception as e:
            logger.error(f"Error pasting: {e}")
            return False
    
    def continue_workflow(self):
        """Press Enter or click continue button"""
        try:
            pyautogui.press('enter')
            time.sleep(0.3)
            logger.info("Pressed Enter to continue")
        except Exception as e:
            logger.error(f"Error continuing: {e}")
    
    def run_single_iteration(self):
        """Run one complete iteration of the automation"""
        self.iteration_count += 1
        logger.info(f"=== Iteration {self.iteration_count} ===")
        
        # Step 1: Click Accept All on Windsurf
        logger.info("Step 1: Clicking Accept All on Windsurf")
        if not self.click_accept_all():
            logger.error("Failed to click Accept All")
            return False
        
        time.sleep(1.0)
        
        # Step 2: Switch to ChatGPT
        logger.info("Step 2: Switching to ChatGPT")
        self.switch_to_chatgpt()
        
        # Step 3: Copy last message
        logger.info("Step 3: Copying last ChatGPT message")
        copied_text = self.copy_last_chatgpt_message()
        if not copied_text:
            logger.error("Failed to copy from ChatGPT")
            return False
        
        # Step 4: Switch back to Windsurf
        logger.info("Step 4: Switching back to Windsurf")
        self.switch_to_windsurf()
        
        # Step 5: Paste content
        logger.info("Step 5: Pasting content")
        if not self.paste_to_destination():
            logger.error("Failed to paste")
            return False
        
        # Step 6: Continue
        logger.info("Step 6: Continuing workflow")
        self.continue_workflow()
        
        logger.info(f"=== Iteration {self.iteration_count} completed ===")
        return True
    
    def run_automation_loop(self, max_iterations=None):
        """Run the automation loop"""
        self.running = True
        logger.info("Starting automation loop...")
        logger.info("Press Ctrl+C in terminal to stop the automation")
        
        try:
            while self.running:
                if max_iterations and self.iteration_count >= max_iterations:
                    logger.info(f"Reached max iterations ({max_iterations})")
                    break
                
                # Note: ESC key detection not available on Mac with pyautogui
                # Use Ctrl+C in terminal to stop instead
                
                # Run iteration
                success = self.run_single_iteration()
                
                if not success:
                    logger.error("Iteration failed, waiting before retry...")
                    time.sleep(5.0)
                    continue
                
                # Wait before next iteration
                logger.info(f"Waiting {self.loop_delay} seconds before next iteration...")
                time.sleep(self.loop_delay)
                
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt - stopping automation")
        finally:
            self.running = False
            logger.info(f"Automation stopped. Total iterations: {self.iteration_count}")
    
    def stop(self):
        """Stop the automation"""
        self.running = False
        logger.info("Automation stop requested")


class CoordinateRecorder:
    """GUI for recording screen coordinates"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Coordinate Recorder")
        self.root.geometry("400x300")
        self.root.attributes('-topmost', True)  # Keep window on top
        
        self.coords = {}
        self.recording_step = 0
        self.steps = [
            "Move mouse to 'Accept All' button in Windsurf",
            "Move mouse to paste destination (or skip)",
            "Setup complete!"
        ]
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the GUI"""
        # Main frame
        frame = ttk.Frame(self.root, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Instruction label
        self.instruction_label = ttk.Label(
            frame, 
            text=self.steps[0],
            font=('Arial', 12),
            wraplength=350
        )
        self.instruction_label.pack(pady=20)
        
        # Current position display
        self.position_label = ttk.Label(
            frame,
            text="Position: (0, 0)",
            font=('Courier', 10)
        )
        self.position_label.pack(pady=10)
        
        # Record button
        self.record_button = ttk.Button(
            frame,
            text="📍 Record Position",
            command=self.record_position,
            style='Accent.TButton'
        )
        self.record_button.pack(pady=10, fill=tk.X)
        
        # Skip button
        self.skip_button = ttk.Button(
            frame,
            text="⏭️ Skip",
            command=self.skip_step
        )
        self.skip_button.pack(pady=5, fill=tk.X)
        
        # Hotkey hint
        hint_label = ttk.Label(
            frame,
            text="💡 Tip: Press 'r' to record, 's' to skip",
            font=('Arial', 9),
            foreground='gray'
        )
        hint_label.pack(pady=20)
        
        # Coordinates display
        self.coords_display = ttk.Label(
            frame,
            text="Recorded coordinates:\nNone",
            font=('Courier', 9)
        )
        self.coords_display.pack(pady=10)
        
        # Bind keyboard shortcuts
        self.root.bind('r', lambda e: self.record_position())
        self.root.bind('s', lambda e: self.skip_step())
        
        # Start position update loop
        self.update_position()
        
    def update_position(self):
        """Update current mouse position display"""
        try:
            pos = pyautogui.position()
            self.position_label.config(text=f"Position: ({pos.x}, {pos.y})")
        except:
            pass
        self.root.after(100, self.update_position)
        
    def record_position(self):
        """Record current mouse position"""
        pos = pyautogui.position()
        
        if self.recording_step == 0:
            self.coords['accept_all'] = (pos.x, pos.y)
            self.instruction_label.config(text=self.steps[1])
            self.recording_step = 1
        elif self.recording_step == 1:
            self.coords['paste_destination'] = (pos.x, pos.y)
            self.instruction_label.config(text=self.steps[2])
            self.recording_step = 2
            self.record_button.config(state='disabled')
            self.skip_button.config(text="✓ Done")
        
        self.update_coords_display()
        
    def skip_step(self):
        """Skip current step"""
        if self.recording_step == 1:
            # Skip paste destination
            self.instruction_label.config(text=self.steps[2])
            self.recording_step = 2
            self.record_button.config(state='disabled')
            self.skip_button.config(text="✓ Done")
        elif self.recording_step == 2:
            # Done
            self.root.quit()
        
        self.update_coords_display()
        
    def update_coords_display(self):
        """Update coordinates display"""
        text = "Recorded coordinates:\n"
        if 'accept_all' in self.coords:
            text += f"Accept All: {self.coords['accept_all']}\n"
        if 'paste_destination' in self.coords:
            text += f"Paste Destination: {self.coords['paste_destination']}\n"
        self.coords_display.config(text=text)
        
    def run(self):
        """Run the GUI"""
        self.root.mainloop()
        return self.coords


def setup_coordinates():
    """Interactive setup to capture coordinates using GUI"""
    print("=== Windsurf Automation Setup ===")
    print("\nLaunching Coordinate Recorder GUI...")
    print("A window will appear to help you capture screen coordinates.\n")
    
    # Launch GUI recorder
    recorder = CoordinateRecorder()
    coords = recorder.run()
    
    # Ask for additional settings
    print("\n=== Additional Configuration ===")
    
    # Tab hotkeys
    print("\nConfigure tab hotkeys (default: command+1 for ChatGPT, command+2 for Windsurf)")
    chatgpt_hotkey = input("ChatGPT tab hotkey (default: command+1): ") or "command+1"
    windsurf_hotkey = input("Windsurf tab hotkey (default: command+2): ") or "command+2"
    
    coords['chatgpt_hotkey'] = chatgpt_hotkey
    coords['windsurf_hotkey'] = windsurf_hotkey
    
    # Loop delay
    print("\nConfigure loop delay (seconds between iterations)")
    delay = input("Loop delay (default: 5.0): ") or "5.0"
    coords['loop_delay'] = float(delay)
    
    print(f"\n✓ Configuration complete!")
    print(f"  Accept All: {coords.get('accept_all', 'Not set')}")
    print(f"  Paste Destination: {coords.get('paste_destination', 'Not set')}")
    print(f"  ChatGPT Hotkey: {coords['chatgpt_hotkey']}")
    print(f"  Windsurf Hotkey: {coords['windsurf_hotkey']}")
    print(f"  Loop Delay: {coords['loop_delay']}s")
    
    return coords


def main():
    """Main entry point"""
    print("=== Windsurf + ChatGPT Automation Agent ===\n")
    
    # Ask user what they want to do
    print("Choose an option:")
    print("1. Run automation with saved coordinates")
    print("2. Set up coordinates (with GUI recorder)")
    print("3. Run with manual coordinates")
    
    choice = input("\nEnter choice (1-3): ")
    
    if choice == "1":
        # Load coordinates from file
        config_file = Path("automation_config.txt")
        if config_file.exists():
            coords = eval(config_file.read_text())
            agent = WindsurfAutomationAgent(
                accept_all_coords=coords.get('accept_all'),
                chatgpt_tab_hotkey=coords.get('chatgpt_hotkey', 'command+1'),
                windsurf_tab_hotkey=coords.get('windsurf_hotkey', 'command+2'),
                paste_destination_coords=coords.get('paste_destination'),
                loop_delay=coords.get('loop_delay', 5.0)
            )
        else:
            print("No saved config found. Please run setup first.")
            return
    elif choice == "2":
        # Setup coordinates
        coords = setup_coordinates()
        
        # Save to file
        config_file = Path("automation_config.txt")
        config_file.write_text(str(coords))
        print(f"\nConfiguration saved to {config_file}")
        
        # Ask if they want to run now
        run_now = input("\nRun automation now? (y/n): ")
        if run_now.lower() == 'y':
            agent = WindsurfAutomationAgent(
                accept_all_coords=coords.get('accept_all'),
                chatgpt_tab_hotkey=coords.get('chatgpt_hotkey', 'command+1'),
                windsurf_tab_hotkey=coords.get('windsurf_hotkey', 'command+2'),
                paste_destination_coords=coords.get('paste_destination'),
                loop_delay=coords.get('loop_delay', 5.0)
            )
        else:
            return
    elif choice == "3":
        # Manual coordinates
        print("\nEnter coordinates manually:")
        accept_all = input("Accept All (x,y): ")
        if accept_all:
            x, y = map(int, accept_all.split(','))
            accept_all_coords = (x, y)
        else:
            accept_all_coords = None
        
        chatgpt_hotkey = input("ChatGPT tab hotkey (default: command+1): ") or "command+1"
        windsurf_hotkey = input("Windsurf tab hotkey (default: command+2): ") or "command+2"
        delay = float(input("Loop delay (default: 5.0): ") or "5.0")
        
        agent = WindsurfAutomationAgent(
            accept_all_coords=accept_all_coords,
            chatgpt_tab_hotkey=chatgpt_hotkey,
            windsurf_tab_hotkey=windsurf_hotkey,
            loop_delay=delay
        )
    else:
        print("Invalid choice")
        return
    
    # Ask for max iterations
    max_iter = input("\nMax iterations (leave empty for unlimited): ")
    max_iterations = int(max_iter) if max_iter else None
    
    # Give user time to get ready
    print("\n=== Automation will start in 5 seconds ===")
    print("Make sure Windsurf and ChatGPT are open and visible")
    print("Press Ctrl+C at any time to stop")
    print("===\n")
    time.sleep(5)
    
    # Run the automation
    agent.run_automation_loop(max_iterations=max_iterations)


if __name__ == "__main__":
    main()
