#!/usr/bin/env python3
"""
Hugging Face Space - On-Chain Profit Agent
Deploy this to Hugging Face Spaces for cloud execution
"""

import gradio as gr
import asyncio
import json
import os
from typing import List, Dict
import aiohttp
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
HUGGING_FACE_API_KEY = os.environ.get("HUGGING_FACE_API_KEY", "")

class GroqClient:
    def __init__(self, api_key: str = GROQ_API_KEY):
        self._api_key = api_key
        self._base_url = "https://api.groq.com/openai/v1"
        self._session = None

    async def _get_session(self):
        if self._session is None or self._session.closed:
            headers = {"Authorization": f"Bearer {self._api_key}"}
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session

    async def generate(self, model: str, prompt: str, system: str = "") -> str:
        if not self._api_key:
            return "Groq API key not set"
        session = await self._get_session()
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system} if system else {"role": "user", "content": prompt}],
            "temperature": 0.7
        }
        if system:
            payload["messages"].append({"role": "user", "content": prompt})
        async with session.post(f"{self._base_url}/chat/completions", json=payload) as resp:
            if resp.status != 200:
                return f"Groq error {resp.status}"
            data = await resp.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")

async def analyze_opportunities(prompt: str) -> str:
    """Analyze on-chain profit opportunities using AI"""
    system_prompt = """You are an expert on-chain profit analyzer. Identify profitable opportunities that start with 0 balance.
Focus on:
1. Arbitrage opportunities between DEXs
2. MEV (Maximal Extractable Value) strategies
3. Liquidation opportunities
4. Cross-chain arbitrage
5. Flash loan arbitrage

For each opportunity, provide:
- Strategy name
- Description
- Entry point (contract address, DEX, etc.)
- Expected profit (in USD)
- Risk level (low/medium/high)
- Timeframe (immediate/short/long)

Return as JSON array."""
    
    client = GroqClient()
    response = await client.generate(
        model="llama3-70b-8192",
        prompt=prompt,
        system=system_prompt
    )
    
    return response

def format_opportunities(response: str) -> str:
    """Format AI response for display"""
    try:
        # Extract JSON if present
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]
        
        data = json.loads(response.strip())
        
        formatted = []
        for i, item in enumerate(data if isinstance(data, list) else [data], 1):
            formatted.append(f"🎯 Strategy #{i}: {item.get('strategy', 'Unknown')}")
            formatted.append(f"📝 Description: {item.get('description', 'N/A')}")
            formatted.append(f"💰 Expected Profit: ${item.get('expected_profit', 0)}")
            formatted.append(f"⚠️ Risk Level: {item.get('risk_level', 'N/A')}")
            formatted.append(f"⏱️ Timeframe: {item.get('timeframe', 'N/A')}")
            formatted.append("---")
        
        return "\n".join(formatted)
    except:
        return response

def analyze_profit(prompt: str) -> str:
    """Gradio interface function"""
    result = asyncio.run(analyze_opportunities(prompt))
    formatted = format_opportunities(result)
    return formatted

# Gradio Interface
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🚀 On-Chain Profit Agent")
    gr.Markdown("AI-powered autonomous trading agent that starts with 0 balance and finds profitable on-chain opportunities")
    
    with gr.Row():
        with gr.Column():
            gr.Markdown("### 📊 Profit Strategy Prompt")
            prompt_input = gr.Textbox(
                label="Enter your profit strategy prompt",
                placeholder="Find arbitrage opportunities on Ethereum mainnet...",
                lines=4,
                value="Find profitable on-chain arbitrage opportunities on Ethereum mainnet starting with 0 balance. Focus on DEX arbitrage and flash loans."
            )
            
            analyze_btn = gr.Button("🔍 Analyze Opportunities", variant="primary", size="lg")
        
        with gr.Column():
            gr.Markdown("### 💡 Profit Opportunities")
            output = gr.Textbox(
                label="Analysis Results",
                lines=15,
                placeholder="AI analysis will appear here..."
            )
    
    gr.Markdown("---")
    gr.Markdown("### 📋 Example Prompts")
    gr.Markdown("""
    - "Find arbitrage opportunities between Uniswap and Sushiswap"
    - "Identify liquidation opportunities on Aave"
    - "Find flash loan arbitrage on Polygon"
    - "Analyze MEV opportunities on Solana"
    """)
    
    analyze_btn.click(analyze_profit, inputs=prompt_input, outputs=output)

if __name__ == "__main__":
    demo.launch()
