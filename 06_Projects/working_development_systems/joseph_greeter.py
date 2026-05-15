#!/usr/bin/env python3
import os
"""
JOSEPH GREETER BOT
Navigates screen, turns on webcam, and greets Joseph
"""

import cv2
import numpy as np
import pyautogui
import pyttsx3
import time
import threading
from datetime import datetime

# Disable failsafe
pyautogui.FAILSAFE = False

class JosephGreeter:
    def __init__(self):
        self.webcam_active = False
        self.cap = None
        self.tts_engine = None
        self.screen_width, self.screen_height = pyautogui.size()
        
    def setup_voice(self):
        """Setup text-to-speech"""
        try:
            self.tts_engine = pyttsx3.init()
            self.tts_engine.setProperty('rate', 150)
            self.tts_engine.setProperty('volume', 1.0)
            
            # Try to get a good voice
            voices = self.tts_engine.getProperty('voices')
            for voice in voices:
                if 'Samantha' in voice.name or 'Alex' in voice.name:
                    self.tts_engine.setProperty('voice', voice.id)
                    break
            
            return True
        except Exception as e:
            print(f"❌ Voice setup error: {e}")
            return False
    
    def speak(self, text):
        """Speak text aloud"""
        if self.tts_engine:
            print(f"🔊 Speaking: {text}")
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()
    
    def navigate_screen(self):
        """Navigate through the screen with mouse movements"""
        print("🖱️  Navigating screen...")
        
        # Move to center
        center_x = self.screen_width // 2
        center_y = self.screen_height // 2
        
        pyautogui.moveTo(center_x, center_y, duration=1)
        time.sleep(0.5)
        
        # Move to corners to show navigation
        positions = [
            (100, 100),  # Top-left
            (self.screen_width - 100, 100),  # Top-right
            (self.screen_width - 100, self.screen_height - 100),  # Bottom-right
            (100, self.screen_height - 100),  # Bottom-left
            (center_x, center_y),  # Back to center
        ]
        
        for pos in positions:
            pyautogui.moveTo(pos[0], pos[1], duration=0.5)
            time.sleep(0.3)
        
        print("✅ Screen navigation complete")
    
    def start_webcam(self):
        """Turn on webcam"""
        print("📹 Starting webcam...")
        
        try:
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                print("❌ Cannot open webcam")
                return False
            
            # Set resolution
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            
            self.webcam_active = True
            
            # Start webcam display thread
            webcam_thread = threading.Thread(target=self._display_webcam)
            webcam_thread.daemon = True
            webcam_thread.start()
            
            print("✅ Webcam started")
            return True
            
        except Exception as e:
            print(f"❌ Webcam error: {e}")
            return False
    
    def _display_webcam(self):
        """Display webcam feed"""
        window_name = "Joseph - I Can See You"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 640, 480)
        
        while self.webcam_active:
            ret, frame = self.cap.read()
            if ret:
                # Add text overlay
                font = cv2.FONT_HERSHEY_SIMPLEX
                cv2.putText(frame, "Hi Joseph!", (20, 40), font, 1, (0, 255, 0), 2)
                cv2.putText(frame, "I can see you", (20, 80), font, 0.8, (255, 255, 255), 2)
                cv2.putText(frame, datetime.now().strftime("%H:%M:%S"), (20, 460), font, 0.6, (255, 255, 255), 1)
                
                cv2.imshow(window_name, frame)
                
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        cv2.destroyAllWindows()
    
    def greet_joseph(self):
        """Main greeting routine"""
        print("\n" + "=" * 60)
        print("🤖 JOSEPH GREETER BOT ACTIVATED")
        print("=" * 60 + "\n")
        
        # Setup voice
        if self.setup_voice():
            # Navigate screen first
            self.navigate_screen()
            
            # Speak introduction
            time.sleep(1)
            self.speak("Hello Joseph. I am navigating your screen now.")
            
            # Start webcam
            time.sleep(1)
            if self.start_webcam():
                # Main greeting
                time.sleep(2)
                self.speak("Hi Joseph, I can see you!")
                
                print("\n✅ Greeting complete!")
                print("📹 Webcam is active - press 'Q' in webcam window to close")
                print("🎤 The bot has spoken to you")
                
                # Keep webcam running
                try:
                    while self.webcam_active:
                        time.sleep(1)
                except KeyboardInterrupt:
                    pass
            else:
                self.speak("Hi Joseph, I cannot see you right now, but I am here!")
        else:
            print("❌ Voice not available, but continuing with webcam...")
            self.start_webcam()
        
        self.cleanup()
    
    def cleanup(self):
        """Cleanup resources"""
        print("\n🧹 Cleaning up...")
        
        self.webcam_active = False
        
        if self.cap:
            self.cap.release()
        
        cv2.destroyAllWindows()
        
        print("✅ Cleanup complete")
        print("👋 Goodbye Joseph!")

if __name__ == "__main__":
    greeter = JosephGreeter()
    greeter.greet_joseph()
