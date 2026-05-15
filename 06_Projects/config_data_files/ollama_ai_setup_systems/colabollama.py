# STEP 1: Setup for local macOS execution
import os
import subprocess
import time
import shutil

# Use local storage instead of Google Drive
OLLAMA_STORAGE = os.path.expanduser("~/ollama")
BIN_STORAGE_PATH = f"{OLLAMA_STORAGE}/bin"
LOCAL_BIN_PATH = "/usr/local/bin"
os.makedirs(BIN_STORAGE_PATH, exist_ok=True)
print(f"✅ Using local storage: {OLLAMA_STORAGE}")

# STEP 2: Install or Restore Ollama
ollama_stored_exec = f"{BIN_STORAGE_PATH}/ollama"
ollama_local_exec = f"{LOCAL_BIN_PATH}/ollama"

if not os.path.exists(ollama_stored_exec):
    print("℄ Installing Ollama to storage...")
    subprocess.run("curl -fsSL https://ollama.com/install.sh | sh", shell=True, check=True)
    if os.path.exists("/usr/local/bin/ollama"):
        shutil.copy2("/usr/local/bin/ollama", ollama_stored_exec)

# Always copy to local to fix PermissionError [Errno 13]
print("℄ Preparing local executable...")
if os.path.exists(ollama_stored_exec):
    shutil.copy2(ollama_stored_exec, ollama_local_exec)
    subprocess.run(["chmod", "+x", ollama_local_exec], check=True)
elif os.path.exists("/usr/local/bin/ollama"):
    # Use system ollama if available
    ollama_local_exec = "/usr/local/bin/ollama"
    print("✅ Using system Ollama installation")
else:
    print("❌ Ollama not found. Installing...")
    subprocess.run("curl -fsSL https://ollama.com/install.sh | sh", shell=True, check=True)
    ollama_local_exec = "/usr/local/bin/ollama"

# STEP 3: Start Ollama Server
print("℄ Refreshing Ollama process...")
subprocess.run("pkill -f ollama", shell=True, stderr=subprocess.DEVNULL)
time.sleep(2)

print("✱ Starting Ollama Server...")
subprocess.Popen([ollama_local_exec, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(5)

# STEP 4: Pull Model
print("⌒ Pulling qwen2.5:0.5b (small, fast model)...")
subprocess.run([ollama_local_exec, "pull", "qwen2.5:0.5b"], check=True)
print("✅ Ollama is ready for AutoGen.")