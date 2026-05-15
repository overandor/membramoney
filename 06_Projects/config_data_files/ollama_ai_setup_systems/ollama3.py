#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ollama_hf_gateio_sniper.py

🔁 Combines:
  - Google Drive virtualenv setup for Ollama deployment
  - Ollama-based agent swarm with autogen
  - Local HF models (TinyLlama, GPT-Neo, etc.)
  - Ollama deepseek-coder float scoring via REST API
  - Gate.io futures sniping across 600 contracts with micro order sizing

📍 Requires:
  - Google Colab (or /content access)
  - Ollama and local HF models
  - Gate.io API credentials in environment variables
"""

import os, sys, time, asyncio, subprocess, logging, json
from typing import List
import torch
import aiohttp
from aiolimiter import AsyncLimiter
from transformers import pipeline
from dotenv import load_dotenv
import autogen
import ccxt.async_support as ccxt

# ───── STEP 2: Path Setup ────────────────────────────────────────────────────
BASE_DIR   = "/content/drive/MyDrive/ollama_env"
BIN_PATH   = f"{BASE_DIR}/bin"
VENV_PATH  = f"{BASE_DIR}/venv"
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "deepseek-coder"
HF_MODELS = [
    "gpt2", "distilgpt2", "EleutherAI/gpt-neo-125M", "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
]

# ───── STEP 4: Logging ───────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ───── STEP 5: Ollama & HF Models ────────────────────────────────────────────
def ensure_ollama_model():
    try:
        out = subprocess.check_output([f"{BIN_PATH}/ollama", "list"], text=True)
        if OLLAMA_MODEL not in out:
            subprocess.check_call([f"{BIN_PATH}/ollama", "pull", OLLAMA_MODEL])
    except Exception as e:
        logger.error(f"❌ Failed to ensure Ollama model: {e}")
        sys.exit(1)

def run_hf_models(prompt: str):
    device = 0 if torch.cuda.is_available() else -1
    for name in HF_MODELS:
        print(f"▶ HF Model: {name}")
        try:
            gen = pipeline("text-generation", model=name, device=device)
            out = gen(prompt, max_new_tokens=50)[0]['generated_text']
            print(out)
        except Exception as e:
            print(f"[ERROR {name}]: {e}")
        print("-"*60)

async def query_ollama(session, limiter, prompt):
    async with limiter:
        payload = {"model": OLLAMA_MODEL, "prompt": prompt, "max_tokens": 10, "temperature": 0.2}
        async with session.post(OLLAMA_URL, json=payload) as resp:
            if resp.status != 200:
                return f"Ollama ❌ {resp.status}"
            j = await resp.json()
            return j.get("response", "").strip()

async def run_ollama_batch(prompt: str):
    limiter = AsyncLimiter(20, 1)
    sem     = asyncio.Semaphore(20)
    conn    = aiohttp.TCPConnector(limit=20)
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(connector=conn, timeout=timeout) as session:
        tasks = []
        for sym in ["BTC/USDT", "ETH/USDT", "SOL/USDT"]:
            async def worker(symbol=sym):
                async with sem:
                    mod_prompt = f"{prompt}\nSymbol: {symbol} → score between -1.0 and 1.0:"
                    resp = await query_ollama(session, limiter, mod_prompt)
                    print(f"[Ollama:{symbol}] {resp}")
            tasks.append(asyncio.create_task(worker()))
        await asyncio.gather(*tasks)

# ───── STEP 6: Autogen Swarm ─────────────────────────────────────────────────
def create_agents():
    agents = []
    for name in ["Scout", "Editor", "Uploader", "Clicker", "Transaction"]:
        try:
            agent = autogen.AssistantAgent(name=name, llm_config={"model": OLLAMA_MODEL, "api_type": "ollama"})
            agents.append(agent)
        except Exception as e:
            logger.error(f"💥 Failed to create {name}: {e}")
    return agents

def run_swarm():
    agents = create_agents()
    if not agents:
        logger.error("❌ No agents created.")
        return
    groupchat = autogen.GroupChat(agents=agents, messages=[])
    manager   = autogen.GroupChatManager(groupchat=groupchat)
    asyncio.run(groupchat)

# ───── STEP 7: Gate.io Micro Sniper ──────────────────────────────────────────
async def gateio_micro_sniper():
    exchange = ccxt.gateio({
        'apiKey': os.getenv("GATE_API_KEY"),
        'secret': os.getenv("GATE_API_SECRET"),
        'enableRateLimit': True,
        'options': {'defaultType': 'future'}
    })
    markets = await exchange.load_markets()
    usdt_perps = [s for s in markets if "/USDT:USDT" in s and markets[s]['type'] == 'future'][:600]
    logger.info(f"🎯 Loaded {len(usdt_perps)} symbols")

    for symbol in usdt_perps:
        try:
            order = await exchange.create_order(
                symbol=symbol,
                type='limit',
                side='buy',
                amount=0.001,  # adjust for micro $0.01 - $0.10
                price=markets[symbol]['info']['mark_price'],
                params={"time_in_force": "ioc"}
            )
            logger.info(f"✅ Sniped {symbol} → {order['id']}")
            await asyncio.sleep(0.25)
        except Exception as e:
            logger.warning(f"❌ {symbol}: {e}")

# ───── STEP 8: Entry ─────────────────────────────────────────────────────────
async def main():
    load_dotenv()
    prompt = sys.argv[1] if len(sys.argv) > 1 else "Analyze market sentiment for crypto"
    ensure_ollama_model()

    print("\n—— HuggingFace Local Models ——\n")
    run_hf_models(prompt)

    print("\n—— Ollama Float Scoring ——\n")
    await run_ollama_batch(prompt)

    print("\n—— Autogen Agent Swarm ——\n")
    run_swarm()

    print("\n—— Gate.io Micro Sniper Sweep ——\n")
    await gateio_micro_sniper()

if __name__ == "__main__":
    # Removed asyncio.run() as it conflicts with Colab's existing event loop
    # Using asyncio.create_task to schedule the main coroutine
    # or directly await main() if top-level await is desired.
    await main()