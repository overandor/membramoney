# Windsurf + ChatGPT Automation Agent

Automates the workflow of clicking "Accept All" on Windsurf and copying/pasting content from ChatGPT.

## Features

- **Automatic "Accept All" clicking**: Automatically finds and clicks the Accept All button on Windsurf
- **ChatGPT integration**: Copies the last message from ChatGPT
- **Smart pasting**: Pastes content to the specified destination
- **Workflow continuation**: Automatically presses Enter to continue
- **GUI Coordinate Recorder**: Easy-to-use graphical interface for capturing screen coordinates
- **Keyboard shortcuts**: Press 'r' to record, 's' to skip during setup
- **Real-time position display**: See current mouse position in the recorder
- **Configurable coordinates**: Set up custom coordinates for your specific setup
- **Safe automation**: Built-in failsafe (move mouse to corner to stop)
- **Loop automation**: Runs continuously until stopped
- **Terminal control**: Press Ctrl+C to stop at any time

## Installation

### Prerequisites

- Python 3.7 or higher
- macOS or Windows operating system
- Windsurf IDE running
- ChatGPT open in a browser tab
- Accessibility permissions (macOS only - required for GUI automation)

### Install Dependencies

```bash
pip install -r requirements.txt
```

### macOS Accessibility Permissions (Required)

On macOS, you must grant accessibility permissions to Python or your terminal:

1. Open **System Settings** > **Privacy & Security** > **Accessibility**
2. Click the **+** button
3. Add your terminal app (Terminal, iTerm2, etc.) or Python
4. Check the box next to it to enable accessibility
5. Restart the script after granting permissions

Without these permissions, the automation will not be able to control your mouse and keyboard.

## Usage

### Quick Start

1. Run the setup to configure coordinates:
```bash
python windsurf_automation_agent.py
```

2. Choose option **2** to set up coordinates
3. Follow the prompts to capture button positions
4. Choose option **1** to run with saved coordinates

### Setup Mode (GUI Recorder)

The setup launches a graphical coordinate recorder with the following features:

**GUI Features:**
- 📍 **Record Button**: Click to capture current mouse position
- ⏭️ **Skip Button**: Skip current step (e.g., if paste destination not needed)
- 💡 **Keyboard Shortcuts**: Press 'r' to record, 's' to skip
- 🖱️ **Real-time Position**: See current mouse coordinates update live
- 📋 **Coordinates Display**: View all recorded coordinates
- 🔄 **Always on Top**: Recorder window stays visible

**Setup Steps:**

1. **Accept All button**: Move mouse to the button and click "Record Position" (or press 'r')
2. **Paste destination**: Move to where you want to paste and click "Record Position" (or click "Skip" if not needed)
3. **Tab hotkeys**: Configure which tabs to switch between (default: command+1 for ChatGPT, command+2 for Windsurf)
   - **Note for Windows users**: Use 'ctrl' instead of 'command' in hotkeys (e.g., 'ctrl+1' instead of 'command+1')
4. **Loop delay**: Set seconds between iterations (default: 5.0)

### Running the Automation

Once configured, run with:
```bash
python windsurf_automation_agent.py
```

Choose option **1** to run with saved coordinates.

### Manual Coordinates Mode

If you know the exact coordinates, choose option **3** and enter them manually:
- Accept All: `x,y` format (e.g., `500,300`)
- ChatGPT tab hotkey: e.g., `command+1` (Mac) or `ctrl+1` (Windows)
- Windsurf tab hotkey: e.g., `command+2` (Mac) or `ctrl+2` (Windows)
- Loop delay: e.g., `5.0`

## Configuration

The configuration is saved to `automation_config.txt` in the same directory:

```python
{
    'accept_all': (500, 300),
    'paste_destination': (600, 400),
    'chatgpt_hotkey': 'ctrl+1',
    'windsurf_hotkey': 'ctrl+2',
    'loop_delay': 5.0
}
```

## Workflow

The automation performs these steps in a loop:

1. **Click Accept All** on Windsurf
2. **Switch to ChatGPT** tab (using configured hotkey)
3. **Copy last message** from ChatGPT (Command+End, select, Command+C on Mac; Ctrl+End, select, Ctrl+C on Windows)
4. **Switch to Windsurf** tab
5. **Paste content** to destination (click if coordinates set, then Command+V on Mac; Ctrl+V on Windows)
6. **Press Enter** to continue
7. **Wait** for configured delay
8. **Repeat** until stopped

## Safety Features

- **Failsafe**: Move mouse to top-left corner to emergency stop
- **Ctrl+C**: Press Ctrl+C in terminal to stop automation
- **Logging**: All actions logged to `windsurf_automation.log`
- **Error handling**: Continues on error with retry delay
- **Max iterations**: Optional limit on number of iterations

## Stopping the Automation

You can stop the automation in two ways:

1. **Move mouse** to top-left corner of screen (failsafe)
2. **Ctrl+C** in the terminal

## Troubleshooting

### Button not found

If the "Accept All" button isn't being clicked:
- Ensure Windsurf is visible and not minimized
- Check that coordinates are correct (run setup again)
- Try using image recognition by adding `windsurf_accept_all.png`

### ChatGPT copy not working

If copying from ChatGPT fails:
- Ensure ChatGPT tab is active
- Check that the tab hotkey is correct
- Adjust the number of Shift+Up presses in `copy_last_chatgpt_message()`

### Paste not working

If pasting fails:
- Ensure the destination field is focused
- Check paste destination coordinates
- Verify clipboard has content

### Timing issues

If automation is too fast/slow:
- Adjust `loop_delay` in configuration
- Modify `pyautogui.PAUSE` at the top of the script
- Add more `time.sleep()` calls where needed

## Advanced Configuration

### Image Recognition

To use image recognition instead of coordinates:

1. Take a screenshot of the "Accept All" button
2. Save as `windsurf_accept_all.png` in the script directory
3. The automation will try to find the button automatically

### Custom Workflow

Modify the `run_single_iteration()` method to customize the workflow:

```python
def run_single_iteration(self):
    # Your custom steps here
    self.click_accept_all()
    time.sleep(2.0)  # Custom delay
    # ... more steps
```

## Requirements

- Python 3.7+
- macOS or Windows OS
- Windsurf IDE
- ChatGPT in browser
- **macOS**: Grant accessibility permissions to Python/terminal (System Settings > Privacy & Security > Accessibility)
- **Windows**: Administrator privileges (may be required for some automation)

## License

MIT License

## Support

For issues or questions, check the log file `windsurf_automation.log` for detailed error messages.
