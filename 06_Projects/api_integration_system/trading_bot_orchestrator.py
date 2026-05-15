#!/usr/bin/env python3
"""
Trading Bot Orchestrator - Connects all trading bots to Digital Gold Forge
Runs trading bots, analyzes results, and auto-posts to multiple platforms
"""

import os
import sys
import json
import subprocess
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from digital_gold_forge import DigitalGoldForge, load_credentials_from_env

class TradingBotOrchestrator:
    """Orchestrates all trading bots and connects to Digital Gold Forge"""
    
    def __init__(self, forge: DigitalGoldForge):
        self.forge = forge
        self.trading_bots = self._discover_trading_bots()
        self.results_dir = Path("./digital_gold_output/trading_results")
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
    def _discover_trading_bots(self) -> Dict[str, Dict]:
        """Discover all trading bot scripts in organized folders"""
        bots = {}
        base_path = Path(__file__).parent.parent
        
        # Map of folder names to bot scripts
        bot_mappings = {
            "algo_micro_cap_bot": "algo_trading_bot.py",
            "autogen_gate_mm": "autogen_ollama_gate_mm.py",
            "aider_ai_system": "aider_trading_system.py",
            "beast_market_maker": "beast.py",
            "deepseek_ai_council": "deepseek_council.py",
            "gate_multi_ticker_mm": "gate_multi_ticker_mm_prod.py",
            "gateio_market_maker_system": "gateio_market_maker.py",
            "godforbit_trading_system": "godforbit.py",
            "groq_supervisor_ai": "groq_supervisor_247.py",
            "hedge_beast_system": "hedge_beast.py",
            "hypweliquid_llm_trader": "hypweliquid.py",
            "hybrid_ai_supervisor_system": "hybrid_ai_supervisor.py",
            "llm_autonomous_agent": "llm_autonomous_agent.py",
            "local_ollama_trading_bot": "local_ollama_trader.py",
            "micro_cap_trading_system": "micro_cap_trading_bot.py",
            "micro_coin_market_maker": "micro_coin_maker.py",
            "openrouter_ai_trading_bot": "openrouter_ai_trader.py",
            "profit_executor_system": "profit_executor.py",
            "retro_terminal_trading_bot": "retro_terminal_bot.py",
            "second_profit_system": "second_profit.py",
            "simple_gateio_trading_bot": "simple_gateio_bot.py",
            "simple_market_maker_system": "simple_market_maker.py",
            "supervisor_ai_247_system": "supervisor_ai_247.py",
            "trading_governance_system": "trading_governance.py",
            "universal_maker_system": "universal_maker.py",
            "vanta_trading_system": "vanta.py",
            "vaultcore_trading_system": "vaultcore.py",
            "visual_trading_agent_system": "visual_trading_agent.py"
        }
        
        for folder, script in bot_mappings.items():
            bot_path = base_path / folder / script
            if bot_path.exists():
                bots[folder] = {
                    "path": str(bot_path),
                    "folder": folder,
                    "script": script,
                    "status": "discovered"
                }
                print(f"✅ Found bot: {folder}/{script}")
        
        return bots
    
    def run_bot(self, bot_name: str, args: List[str] = None) -> Dict:
        """Run a specific trading bot"""
        if bot_name not in self.trading_bots:
            print(f"❌ Bot not found: {bot_name}")
            return {"success": False, "error": "Bot not found"}
        
        bot_info = self.trading_bots[bot_name]
        print(f"🚀 Running bot: {bot_name}")
        
        try:
            cmd = ["python3", bot_info["path"]]
            if args:
                cmd.extend(args)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            output = {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "timestamp": datetime.now().isoformat()
            }
            
            # Save output to file
            output_file = self.results_dir / f"{bot_name}_output.json"
            with open(output_file, "w") as f:
                json.dump(output, f, indent=2)
            
            if output["success"]:
                print(f"✅ {bot_name} completed successfully")
            else:
                print(f"❌ {bot_name} failed with return code {result.returncode}")
            
            return output
            
        except subprocess.TimeoutExpired:
            print(f"⏱️ {bot_name} timed out")
            return {"success": False, "error": "Timeout"}
        except Exception as e:
            print(f"❌ Error running {bot_name}: {e}")
            return {"success": False, "error": str(e)}
    
    def run_all_bots(self, max_concurrent: int = 3) -> Dict[str, Dict]:
        """Run all trading bots with limited concurrency"""
        print(f"🔥 Running {len(self.trading_bots)} trading bots...")
        results = {}
        
        bot_names = list(self.trading_bots.keys())
        
        # Run bots in batches
        for i in range(0, len(bot_names), max_concurrent):
            batch = bot_names[i:i + max_concurrent]
            print(f"\n📦 Running batch {i//max_concurrent + 1}: {batch}")
            
            for bot_name in batch:
                result = self.run_bot(bot_name)
                results[bot_name] = result
        
        # Save summary
        summary_file = self.results_dir / "all_bots_summary.json"
        with open(summary_file, "w") as f:
            json.dump(results, f, indent=2)
        
        print(f"\n📊 Summary saved to: {summary_file}")
        return results
    
    def analyze_bot_results(self, bot_name: str) -> Optional[Dict]:
        """Analyze results from a specific bot"""
        result_file = self.results_dir / f"{bot_name}_output.json"
        
        if not result_file.exists():
            print(f"❌ No results found for {bot_name}")
            return None
        
        with open(result_file, "r") as f:
            return json.load(f)
    
    def auto_post_bot_results(self, bot_name: str) -> bool:
        """Automatically post bot results to social platforms"""
        result = self.analyze_bot_results(bot_name)
        
        if not result or not result["success"]:
            print(f"❌ Cannot post results for {bot_name} - no successful run")
            return False
        
        # Create a summary file
        summary = {
            "bot_name": bot_name,
            "timestamp": datetime.now().isoformat(),
            "success": result["success"],
            "output_length": len(result.get("stdout", "")),
            "error_length": len(result.get("stderr", ""))
        }
        
        # Save summary as JSON for posting
        summary_file = self.results_dir / f"{bot_name}_summary.json"
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2)
        
        # Use Digital Gold Forge to post
        try:
            forge_result = self.forge.forge_digital_gold(
                str(summary_file),
                f"Trading Bot Results: {bot_name} - {'SUCCESS' if result['success'] else 'FAILED'}"
            )
            print(f"✅ Auto-posted {bot_name} results")
            return True
        except Exception as e:
            print(f"❌ Failed to auto-post {bot_name}: {e}")
            return False
    
    def create_trading_report(self) -> str:
        """Create a comprehensive trading report from all bot results"""
        report_lines = [
            "# 🔥 Trading Bot Report",
            f"Generated: {datetime.now().isoformat()}",
            f"Total Bots: {len(self.trading_bots)}",
            ""
        ]
        
        for bot_name in self.trading_bots:
            result = self.analyze_bot_results(bot_name)
            if result:
                status = "✅ SUCCESS" if result["success"] else "❌ FAILED"
                report_lines.append(f"## {bot_name}")
                report_lines.append(f"Status: {status}")
                report_lines.append(f"Timestamp: {result['timestamp']}")
                
                if result["stdout"]:
                    report_lines.append("### Output Preview:")
                    report_lines.append("```")
                    report_lines.append(result["stdout"][:500])  # First 500 chars
                    report_lines.append("```")
                
                if result["stderr"]:
                    report_lines.append("### Errors:")
                    report_lines.append("```")
                    report_lines.append(result["stderr"][:500])
                    report_lines.append("```")
                
                report_lines.append("")
        
        report = "\n".join(report_lines)
        
        # Save report
        report_file = self.results_dir / "trading_report.md"
        with open(report_file, "w") as f:
            f.write(report)
        
        print(f"📄 Trading report saved to: {report_file}")
        return str(report_file)

def main():
    """Main entry point"""
    print("🤖 Trading Bot Orchestrator")
    print("=" * 60)
    
    # Load credentials and initialize forge
    creds = load_credentials_from_env()
    forge = DigitalGoldForge(creds)
    
    # Initialize orchestrator
    orchestrator = TradingBotOrchestrator(forge)
    
    print(f"\n📊 Discovered {len(orchestrator.trading_bots)} trading bots")
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "list":
            print("\n📋 Available trading bots:")
            for bot_name in orchestrator.trading_bots:
                print(f"  - {bot_name}")
        
        elif command == "run":
            if len(sys.argv) > 2:
                bot_name = sys.argv[2]
                args = sys.argv[3:] if len(sys.argv) > 3 else None
                result = orchestrator.run_bot(bot_name, args)
                print(f"\nResult: {json.dumps(result, indent=2)}")
            else:
                print("Usage: python trading_bot_orchestrator.py run <bot_name> [args...]")
        
        elif command == "run-all":
            results = orchestrator.run_all_bots()
            print(f"\n📊 All bots completed. Results saved.")
        
        elif command == "post":
            if len(sys.argv) > 2:
                bot_name = sys.argv[2]
                orchestrator.auto_post_bot_results(bot_name)
            else:
                print("Usage: python trading_bot_orchestrator.py post <bot_name>")
        
        elif command == "report":
            report_file = orchestrator.create_trading_report()
            print(f"\n📄 Report generated: {report_file}")
            
            # Optionally post the report
            if len(sys.argv) > 2 and sys.argv[2] == "--post":
                print("\n🚀 Posting report to platforms...")
                forge.forge_digital_gold(report_file, "Daily Trading Bot Report")
        
        else:
            print(f"❌ Unknown command: {command}")
    else:
        print("\n📋 Usage:")
        print("  python trading_bot_orchestrator.py list                    - List all bots")
        print("  python trading_bot_orchestrator.py run <bot_name>         - Run specific bot")
        print("  python trading_bot_orchestrator.py run-all                - Run all bots")
        print("  python trading_bot_orchestrator.py post <bot_name>        - Post bot results")
        print("  python trading_bot_orchestrator.py report [--post]        - Generate and optionally post report")

if __name__ == "__main__":
    main()
