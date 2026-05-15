#!/usr/bin/env python3
"""
MINING MONITOR
Monitors the lamports generation progress
"""

import time
import psutil
import subprocess
import threading
from datetime import datetime

def monitor_mining():
    """Monitor the mining process"""
    print("🔥 LAMPORTS MINING MONITOR")
    print("=" * 50)
    
    process = None
    start_time = datetime.now()
    
    while True:
        try:
            # Find the mining process
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                if 'lamports_generator' in proc.info['name']:
                    process = proc
                    break
            
            if process:
                # Get CPU usage
                cpu_usage = process.cpu_percent()
                memory_usage = process.memory_percent()
                
                # Calculate elapsed time
                elapsed = (datetime.now() - start_time).total_seconds()
                
                print(f"⏰ Time: {elapsed:.1f}s")
                print(f"🖥️  CPU: {cpu_usage:.1f}% | Memory: {memory_usage:.1f}%")
                print(f"🔥 Process ID: {process.pid}")
                print("-" * 30)
                
                # Check if CPU is being utilized
                if cpu_usage < 5:
                    print("⚠️  Low CPU usage - mining may not be active")
                elif cpu_usage > 80:
                    print("🔥 HIGH CPU usage - M5 is working hard!")
                else:
                    print("✅ Normal CPU usage")
                
            else:
                print("❌ Mining process not found")
            
            time.sleep(5)
            
        except KeyboardInterrupt:
            print("\n🛑 Monitoring stopped")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    monitor_mining()
