#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import base64
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

import aiohttp
from dotenv import load_dotenv
from solders.hash import Hash
from solders.instruction import AccountMeta, Instruction
from solders.keypair import Keypair
from solders.message import MessageV0
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction

USDC_MAINNET_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
WSOL_MAINNET_MINT = "So11111111111111111111111111111111111111112"
TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
ASSOCIATED_TOKEN_PROGRAM_ID = "ATokenGPvbdGVxr1b2hvZbsiqWqxWH25efTNsLJA8knL"
COMPUTE_BUDGET_PROGRAM_ID = "ComputeBudget111111111111111111111111111111"
KAMINO_KLEND_PROGRAM_ID = "KLend2g3cP87fffoy8q1mQSh3i5K3z3KZK7ytfqcJm7So"

DEFAULT_SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"
DEFAULT_JUPITER_QUOTE_URL = "https://api.jup.ag/swap/v1/quote"
DEFAULT_JUPITER_SWAP_INSTRUCTIONS_URL = "https://api.jup.ag/swap/v1/swap-instructions"

LOG_ORDER = {"debug": 10, "info": 20, "warn": 30, "error": 40}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def utc_day() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def getenv_str(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def getenv_bool(name: str, default: bool) -> bool:
    return getenv_str(name, "true" if default else "false").lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }


def getenv_int(name: str, default: int, minimum: Optional[int] = None, maximum: Optional[int] = None) -> int:
    raw = getenv_str(name, str(default))
    value = int(raw)
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {value}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be <= {maximum}, got {value}")
    return value


def getenv_atoms(name: str, default: int, minimum: int = 0) -> int:
    raw = getenv_str(name, str(default))
    if not raw.isdigit():
        raise ValueError(f"{name} must be a non-negative integer string, got {raw!r}")
    value = int(raw)
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {value}")
    return value


def parse_int_csv(raw: str, field_name: str) -> list[int]:
    values = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        if not item.isdigit():
            raise ValueError(f"{field_name} contains invalid integer: {item!r}")
        values.append(int(item))
    if not values:
        raise ValueError(f"{field_name} must contain at least one value")
    return values


def parse_str_csv(raw: str, field_name: str) -> list[str]:
    values = [item.strip() for item in raw.split(",") if item.strip()]
    if not values:
        raise ValueError(f"{field_name} must contain at least one value")
    return values


def atoms_to_usdc(atoms: int) -> Decimal:
    return Decimal(atoms) / Decimal(1_000_000)


def bps_of(amount_atoms: int, bps: int) -> int:
    return amount_atoms * bps // 10_000


def parse_price_impact_bps(value: Any) -> int:
    if value is None:
        return 0
    try:
        numeric = Decimal(str(value))
    except Exception:
        return 10**12
    if numeric < 0:
        return 10**12
    return int((numeric * Decimal(10_000)).to_integral_value())


def truncate_logs(logs: Optional[list[str]], max_lines: int) -> list[str]:
    safe = logs or []
    if max_lines <= 0:
        return []
    if len(safe) <= max_lines:
        return safe
    return safe[:max_lines] + [f"... truncated {len(safe) - max_lines} additional log lines"]


def derive_ata(owner: str, mint: str) -> Pubkey:
    owner_pk = Pubkey.from_string(owner)
    mint_pk = Pubkey.from_string(mint)
    token_program = Pubkey.from_string(TOKEN_PROGRAM_ID)
    ata_program = Pubkey.from_string(ASSOCIATED_TOKEN_PROGRAM_ID)
    ata, _bump = Pubkey.find_program_address(
        [bytes(owner_pk), bytes(token_program), bytes(mint_pk)],
        ata_program,
    )
    return ata


class Logger:
    def __init__(self, level: str) -> None:
        self.level = level.lower().strip()
        if self.level not in LOG_ORDER:
            self.level = "info"
        self.log_file = "/tmp/kamino_scanner.log"

    def _emit(self, level: str, message: str, **meta: Any) -> None:
        if LOG_ORDER[level] < LOG_ORDER[self.level]:
            return
        payload = {"ts": utc_now_iso(), "level": level, "message": message, **meta}
        line = json.dumps(payload, separators=(",", ":"), ensure_ascii=False, default=str)
        
        # Print to stdout/stderr
        print(line, file=sys.stderr if level in {"warn", "error"} else sys.stdout, flush=True)
        
        # Also write to log file for API server
        try:
            with open(self.log_file, 'a') as f:
                f.write(line + '\n')
                f.flush()
        except Exception:
            pass  # Don't fail logging if file write fails

    def debug(self, message: str, **meta: Any) -> None:
        self._emit("debug", message, **meta)

    def info(self, message: str, **meta: Any) -> None:
        self._emit("info", message, **meta)

    def warn(self, message: str, **meta: Any) -> None:
        self._emit("warn", message, **meta)

    def error(self, message: str, **meta: Any) -> None:
        self._emit("error", message, **meta)


@dataclass(frozen=True)
class Config:
    solana_rpc_url: str
    jupiter_quote_url: str
    jupiter_swap_instructions_url: str
    jupiter_api_key: str
    jupiter_priority_level: str
    jupiter_max_priority_fee_lamports: int
    scan_interval_ms: int
    quote_timeout_ms: int
    max_concurrency: int
    slippage_bps: int
    max_price_impact_bps: int
    min_profit_usdc_atoms: int
    min_execution_net_profit_usdc_atoms: int
    flash_loan_fee_bps: int
    estimated_network_fee_usdc_atoms: int
    usdc_mint: str
    target_mints: list[str]
    borrow_sizes_usdc_atoms: list[int]
    webhook_url: str
    log_level: str
    executor_enabled: bool
    simulation_only: bool
    require_manual_approval: bool
    wallet_keypair_path: str
    kamino_market_address: str
    kamino_usdc_reserve_address: str
    kamino_flash_ix_builder_cmd: str
    min_sol_balance_lamports: int
    max_daily_executions: int
    max_consecutive_executor_failures: int
    executor_cooldown_ms: int
    send_max_retries: int
    confirmation_timeout_ms: int
    confirmation_poll_ms: int
    max_simulation_log_lines: int
    allow_jupiter_alts: bool

    @staticmethod
    def load() -> "Config":
        load_dotenv()
        priority = getenv_str("JUPITER_PRIORITY_LEVEL", "high")
        if priority not in {"medium", "high", "veryHigh"}:
            raise ValueError("JUPITER_PRIORITY_LEVEL must be medium, high, or veryHigh")

        return Config(
            solana_rpc_url=getenv_str("SOLANA_RPC_URL", DEFAULT_SOLANA_RPC_URL),
            jupiter_quote_url=getenv_str("JUPITER_QUOTE_URL", DEFAULT_JUPITER_QUOTE_URL),
            jupiter_swap_instructions_url=getenv_str(
                "JUPITER_SWAP_INSTRUCTIONS_URL",
                DEFAULT_JUPITER_SWAP_INSTRUCTIONS_URL,
            ),
            jupiter_api_key=getenv_str("JUPITER_API_KEY", ""),
            jupiter_priority_level=priority,
            jupiter_max_priority_fee_lamports=getenv_int("JUPITER_MAX_PRIORITY_FEE_LAMPORTS", 250000, minimum=0),
            scan_interval_ms=getenv_int("SCAN_INTERVAL_MS", 3000, minimum=250),
            quote_timeout_ms=getenv_int("QUOTE_TIMEOUT_MS", 7000, minimum=500),
            max_concurrency=getenv_int("MAX_CONCURRENCY", 6, minimum=1, maximum=128),
            slippage_bps=getenv_int("SLIPPAGE_BPS", 30, minimum=1, maximum=1000),
            max_price_impact_bps=getenv_int("MAX_PRICE_IMPACT_BPS", 50, minimum=0, maximum=10000),
            min_profit_usdc_atoms=getenv_atoms("MIN_PROFIT_USDC_ATOMS", 100000),
            min_execution_net_profit_usdc_atoms=getenv_atoms("MIN_EXECUTION_NET_PROFIT_USDC_ATOMS", 100000),
            flash_loan_fee_bps=getenv_int("FLASH_LOAN_FEE_BPS", 5, minimum=0, maximum=10000),
            estimated_network_fee_usdc_atoms=getenv_atoms("ESTIMATED_NETWORK_FEE_USDC_ATOMS", 10000),
            usdc_mint=getenv_str("USDC_MINT", USDC_MAINNET_MINT),
            target_mints=parse_str_csv(getenv_str("TARGET_MINTS", WSOL_MAINNET_MINT), "TARGET_MINTS"),
            borrow_sizes_usdc_atoms=parse_int_csv(
                getenv_str("BORROW_SIZES_USDC_ATOMS", "100000000,500000000,1000000000"),
                "BORROW_SIZES_USDC_ATOMS",
            ),
            webhook_url=getenv_str("WEBHOOK_URL", ""),
            log_level=getenv_str("LOG_LEVEL", "info"),
            executor_enabled=getenv_bool("EXECUTOR_ENABLED", False),
            simulation_only=getenv_bool("SIMULATION_ONLY", True),
            require_manual_approval=getenv_bool("REQUIRE_MANUAL_APPROVAL", True),
            wallet_keypair_path=getenv_str("WALLET_KEYPAIR_PATH", ""),
            kamino_market_address=getenv_str("KAMINO_MARKET_ADDRESS", ""),
            kamino_usdc_reserve_address=getenv_str("KAMINO_USDC_RESERVE_ADDRESS", ""),
            kamino_flash_ix_builder_cmd=getenv_str("KAMINO_FLASH_IX_BUILDER_CMD", "node ./kamino_build_flash_ix.js"),
            min_sol_balance_lamports=getenv_int("MIN_SOL_BALANCE_LAMPORTS", 50000000, minimum=0),
            max_daily_executions=getenv_int("MAX_DAILY_EXECUTIONS", 20, minimum=0),
            max_consecutive_executor_failures=getenv_int("MAX_CONSECUTIVE_EXECUTOR_FAILURES", 3, minimum=1),
            executor_cooldown_ms=getenv_int("EXECUTOR_COOLDOWN_MS", 15000, minimum=0),
            send_max_retries=getenv_int("SEND_MAX_RETRIES", 3, minimum=0, maximum=20),
            confirmation_timeout_ms=getenv_int("CONFIRMATION_TIMEOUT_MS", 45000, minimum=1),
            confirmation_poll_ms=getenv_int("CONFIRMATION_POLL_MS", 1500, minimum=1),
            max_simulation_log_lines=getenv_int("MAX_SIMULATION_LOG_LINES", 40, minimum=0, maximum=500),
            allow_jupiter_alts=getenv_bool("ALLOW_JUPITER_ALTS", False),
        )


@dataclass(frozen=True)
class ScanCandidate:
    base_mint: str
    target_mint: str
    borrow_amount_atoms: int
    forward_out_atoms: int
    reverse_out_atoms: int
    gross_profit_atoms: int
    flash_loan_fee_atoms: int
    estimated_network_fee_atoms: int
    net_profit_atoms: int
    profitable: bool
    forward_dexes: list[str]
    reverse_dexes: list[str]
    forward_price_impact_pct: str
    reverse_price_impact_pct: str
    context_slot: Optional[int]
    checked_at: str

    def log_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["borrow_amount_usdc"] = str(atoms_to_usdc(self.borrow_amount_atoms))
        data["gross_profit_usdc"] = str(atoms_to_usdc(self.gross_profit_atoms))
        data["flash_loan_fee_usdc"] = str(atoms_to_usdc(self.flash_loan_fee_atoms))
        data["estimated_network_fee_usdc"] = str(atoms_to_usdc(self.estimated_network_fee_atoms))
        data["net_profit_usdc"] = str(atoms_to_usdc(self.net_profit_atoms))
        return data


class ExecutorCircuitBreaker:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.consecutive_failures = 0
        self.daily_executions = 0
        self.daily_window_utc = utc_day()
        self.last_execution_at_ms = 0

    def _roll(self) -> None:
        today = utc_day()
        if today != self.daily_window_utc:
            self.daily_window_utc = today
            self.daily_executions = 0
            self.consecutive_failures = 0

    def assert_can_attempt(self) -> None:
        self._roll()
        if self.config.max_daily_executions > 0 and self.daily_executions >= self.config.max_daily_executions:
            raise RuntimeError("Daily execution limit reached")
        if self.consecutive_failures >= self.config.max_consecutive_executor_failures:
            raise RuntimeError("Circuit breaker open")
        if self.last_execution_at_ms > 0:
            elapsed = int(time.time() * 1000) - self.last_execution_at_ms
            if elapsed < self.config.executor_cooldown_ms:
                raise RuntimeError(f"Executor cooldown active: wait {self.config.executor_cooldown_ms - elapsed}ms")

    def record_send_attempt(self) -> None:
        self._roll()
        self.daily_executions += 1
        self.last_execution_at_ms = int(time.time() * 1000)

    def record_success(self) -> None:
        self.consecutive_failures = 0

    def record_failure(self) -> None:
        self.consecutive_failures += 1

    def snapshot(self) -> dict[str, Any]:
        self._roll()
        return {
            "consecutiveFailures": self.consecutive_failures,
            "dailyExecutions": self.daily_executions,
            "dailyWindowUtc": self.daily_window_utc,
            "lastExecutionAtMs": self.last_execution_at_ms,
        }


async def rpc_call(session: aiohttp.ClientSession, rpc_url: str, method: str, params: Optional[list[Any]] = None, timeout_seconds: float = 10) -> Any:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}
    async with session.post(rpc_url, json=payload, timeout=aiohttp.ClientTimeout(total=timeout_seconds)) as response:
        body = await response.text()
        if response.status < 200 or response.status >= 300:
            raise RuntimeError(f"RPC {method} failed HTTP {response.status}: {body[:500]}")
        parsed = json.loads(body)
    if "error" in parsed:
        raise RuntimeError(f"RPC {method} error: {parsed['error']}")
    return parsed.get("result")


async def get_sol_balance(session: aiohttp.ClientSession, config: Config, owner: str) -> int:
    result = await rpc_call(session, config.solana_rpc_url, "getBalance", [owner, {"commitment": "confirmed"}])
    return int(result["value"])


async def get_account_exists(session: aiohttp.ClientSession, config: Config, address: str) -> bool:
    result = await rpc_call(session, config.solana_rpc_url, "getAccountInfo", [address, {"encoding": "base64", "commitment": "confirmed"}])
    return result["value"] is not None


async def get_token_balance(session: aiohttp.ClientSession, config: Config, token_account: str) -> int:
    result = await rpc_call(session, config.solana_rpc_url, "getTokenAccountBalance", [token_account, {"commitment": "confirmed"}])
    return int(result["value"]["amount"])


async def latest_blockhash(session: aiohttp.ClientSession, config: Config) -> tuple[str, int]:
    result = await rpc_call(session, config.solana_rpc_url, "getLatestBlockhash", [{"commitment": "confirmed"}])
    value = result["value"]
    return value["blockhash"], int(value["lastValidBlockHeight"])


async def simulate_transaction(session: aiohttp.ClientSession, config: Config, tx_base64: str) -> dict[str, Any]:
    return await rpc_call(
        session,
        config.solana_rpc_url,
        "simulateTransaction",
        [
            tx_base64,
            {"encoding": "base64", "replaceRecentBlockhash": True, "sigVerify": False, "commitment": "confirmed"},
        ],
        timeout_seconds=max(10, config.quote_timeout_ms / 1000 + 5),
    )


async def send_transaction(session: aiohttp.ClientSession, config: Config, tx_base64: str) -> str:
    return await rpc_call(
        session,
        config.solana_rpc_url,
        "sendTransaction",
        [
            tx_base64,
            {
                "encoding": "base64",
                "skipPreflight": False,
                "preflightCommitment": "confirmed",
                "maxRetries": config.send_max_retries,
            },
        ],
        timeout_seconds=20,
    )


async def confirm_transaction_strict(session: aiohttp.ClientSession, config: Config, signature: str, blockhash: str, last_valid_block_height: int) -> None:
    started = int(time.time() * 1000)
    while True:
        confirmation = await rpc_call(
            session,
            config.solana_rpc_url,
            "confirmTransaction",
            [{"signature": signature, "blockhash": blockhash, "lastValidBlockHeight": last_valid_block_height}, "confirmed"],
            timeout_seconds=10,
        )
        err = confirmation.get("value", {}).get("err")
        if err is not None:
            raise RuntimeError(f"Transaction failed confirmation: {err}")

        status = await rpc_call(
            session,
            config.solana_rpc_url,
            "getSignatureStatuses",
            [[signature], {"searchTransactionHistory": False}],
            timeout_seconds=10,
        )
        value = status["value"][0] if status.get("value") else None
        if value is not None:
            if value.get("err") is not None:
                raise RuntimeError(f"Transaction status error: {value['err']}")
            if value.get("confirmationStatus") in {"confirmed", "finalized"}:
                return

        if int(time.time() * 1000) - started > config.confirmation_timeout_ms:
            raise TimeoutError("Timed out waiting for transaction confirmation")
        await asyncio.sleep(config.confirmation_poll_ms / 1000)


class JupiterClient:
    def __init__(self, session: aiohttp.ClientSession, config: Config) -> None:
        self.session = session
        self.config = config

    def headers(self) -> dict[str, str]:
        headers = {"accept": "application/json", "content-type": "application/json"}
        if self.config.jupiter_api_key:
            headers["x-api-key"] = self.config.jupiter_api_key
        return headers

    async def quote_exact_in(self, input_mint: str, output_mint: str, amount_atoms: int) -> dict[str, Any]:
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount_atoms),
            "slippageBps": str(self.config.slippage_bps),
            "restrictIntermediateTokens": "true",
            "instructionVersion": "V2",
        }
        async with self.session.get(
            self.config.jupiter_quote_url,
            params=params,
            headers=self.headers(),
            timeout=aiohttp.ClientTimeout(total=self.config.quote_timeout_ms / 1000),
        ) as response:
            body = await response.text()
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(f"Jupiter quote failed HTTP {response.status}: {body[:500]}")
            parsed = json.loads(body)
        out_amount = parsed.get("outAmount")
        if not isinstance(out_amount, str) or not out_amount.isdigit():
            raise RuntimeError(f"Invalid Jupiter quote response: {str(parsed)[:500]}")
        return parsed

    def analyze_quote_dex(self, quote: dict[str, Any]) -> dict[str, Any]:
        """Analyze an existing Jupiter quote for DEX route details without extra API call"""
        route_plan = quote.get("routePlan", [])
        dex_names = []
        dex_quotes = []

        for leg in route_plan:
            swap_info = leg.get("swapInfo", {}) if isinstance(leg, dict) else {}
            dex_name = swap_info.get("label") or swap_info.get("ammKey", "Unknown")
            if dex_name and dex_name not in dex_names:
                dex_names.append(dex_name)
            in_amount = leg.get("inAmount", "0")
            out_amount = leg.get("outAmount", "0")
            if in_amount and out_amount:
                price = float(out_amount) / float(in_amount) if float(in_amount) > 0 else 0
                dex_quotes.append({
                    "dex": dex_name,
                    "in_amount": in_amount,
                    "out_amount": out_amount,
                    "price": price,
                    "price_impact_pct": swap_info.get("priceImpactPct", 0)
                })

        route_text = " ".join(dex_names).lower()
        return {
            "dex_names": dex_names,
            "dex_quotes": dex_quotes,
            "best_dex": max(dex_quotes, key=lambda x: x["price"]) if dex_quotes else None,
            "orca_used": "orca" in route_text or "whirlpool" in route_text,
            "raydium_used": "raydium" in route_text,
            "meteora_used": "meteora" in route_text
        }

    async def swap_instructions(self, user_public_key: str, quote_response: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "userPublicKey": user_public_key,
            "quoteResponse": quote_response,
            "dynamicComputeUnitLimit": True,
            "useSharedAccounts": False,
            "wrapAndUnwrapSol": False,
        }
        if self.config.jupiter_max_priority_fee_lamports > 0:
            payload["prioritizationFeeLamports"] = {
                "priorityLevelWithMaxLamports": {
                    "priorityLevel": self.config.jupiter_priority_level,
                    "maxLamports": self.config.jupiter_max_priority_fee_lamports,
                }
            }
        async with self.session.post(
            self.config.jupiter_swap_instructions_url,
            headers=self.headers(),
            json=payload,
            timeout=aiohttp.ClientTimeout(total=self.config.quote_timeout_ms / 1000),
        ) as response:
            body = await response.text()
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(f"Jupiter swap-instructions failed HTTP {response.status}: {body[:500]}")
            return json.loads(body)


def dex_labels(quote: dict[str, Any]) -> list[str]:
    labels = []
    route_plan = quote.get("routePlan")
    if not isinstance(route_plan, list):
        return labels
    for leg in route_plan:
        swap_info = leg.get("swapInfo") if isinstance(leg, dict) else None
        if not isinstance(swap_info, dict):
            continue
        label = swap_info.get("label") or swap_info.get("ammKey")
        if isinstance(label, str) and label and label not in labels:
            labels.append(label)
    return labels


def parse_serialized_instruction(ix: dict[str, Any]) -> Instruction:
    program_id = Pubkey.from_string(ix["programId"])
    data = base64.b64decode(ix.get("data") or ix.get("dataBase64") or "")
    accounts = [
        AccountMeta(
            pubkey=Pubkey.from_string(account["pubkey"]),
            is_signer=bool(account.get("isSigner", False)),
            is_writable=bool(account.get("isWritable", False)),
        )
        for account in ix.get("accounts", [])
    ]
    return Instruction(program_id, data, accounts)


def is_compute_budget_instruction(ix: Instruction) -> bool:
    return str(ix.program_id) == COMPUTE_BUDGET_PROGRAM_ID


def extract_jupiter_swap_instructions(response: dict[str, Any], config: Config) -> tuple[list[Instruction], int]:
    stripped = 0
    instructions = []
    compute_budget = response.get("computeBudgetInstructions") or []
    if isinstance(compute_budget, list):
        stripped += len(compute_budget)

    serialized = []
    for key in ["setupInstructions", "otherInstructions"]:
        value = response.get(key)
        if isinstance(value, list):
            serialized.extend(value)

    if isinstance(response.get("swapInstruction"), dict):
        serialized.append(response["swapInstruction"])
    if isinstance(response.get("cleanupInstruction"), dict):
        serialized.append(response["cleanupInstruction"])

    for raw_ix in serialized:
        ix = parse_serialized_instruction(raw_ix)
        if is_compute_budget_instruction(ix):
            stripped += 1
            continue
        instructions.append(ix)

    alt_addresses = response.get("addressLookupTableAddresses") or []
    if alt_addresses and not config.allow_jupiter_alts:
        raise RuntimeError("Jupiter returned ALTs; ALLOW_JUPITER_ALTS=false in this single-file Python build")
    if alt_addresses and config.allow_jupiter_alts:
        raise RuntimeError("ALT deserialization is intentionally disabled in this single-file Python build")
    return instructions, stripped


def load_keypair(path: str) -> Keypair:
    raw = json.loads(Path(path).read_text())
    if not isinstance(raw, list):
        raise RuntimeError("WALLET_KEYPAIR_PATH must point to a Solana JSON keypair array")
    return Keypair.from_bytes(bytes(raw))


def call_kamino_builder(config: Config, user_public_key: str, reserve_mint: str, amount_atoms: int) -> tuple[Instruction, Instruction]:
    payload = {
        "userPublicKey": user_public_key,
        "reserveMint": reserve_mint,
        "amountAtoms": str(amount_atoms),
        "borrowIxIndex": 0,
        "programId": KAMINO_KLEND_PROGRAM_ID,
        "market": config.kamino_market_address,
        "reserveAddress": config.kamino_usdc_reserve_address,
    }
    proc = subprocess.run(
        config.kamino_flash_ix_builder_cmd,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        shell=True,
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Kamino builder failed: stdout={proc.stdout[:500]} stderr={proc.stderr[:500]}")
    parsed = json.loads(proc.stdout)
    return parse_serialized_instruction(parsed["flashBorrowInstruction"]), parse_serialized_instruction(parsed["flashRepayInstruction"])


@dataclass(frozen=True)
class BuiltTransaction:
    tx_base64: str
    blockhash: str
    last_valid_block_height: int
    expected_net_profit_atoms: int
    stripped_compute_budget_instruction_count: int
    pre_usdc_balance_atoms: int
    usdc_ata: str


class Executor:
    def __init__(self, config: Config, logger: Logger, session: aiohttp.ClientSession, jupiter: JupiterClient) -> None:
        self.config = config
        self.logger = logger
        self.session = session
        self.jupiter = jupiter
        self.circuit = ExecutorCircuitBreaker(config)
        self.assert_execution_config()
        self.payer = load_keypair(config.wallet_keypair_path)
        self.wallet = str(self.payer.pubkey())
        self.logger.warn("executor_initialized", wallet=self.wallet, simulationOnly=config.simulation_only)

    def assert_execution_config(self) -> None:
        if not self.config.executor_enabled:
            raise RuntimeError("Executor is disabled")
        for field, value in {
            "WALLET_KEYPAIR_PATH": self.config.wallet_keypair_path,
            "KAMINO_MARKET_ADDRESS": self.config.kamino_market_address,
            "KAMINO_USDC_RESERVE_ADDRESS": self.config.kamino_usdc_reserve_address,
            "KAMINO_FLASH_IX_BUILDER_CMD": self.config.kamino_flash_ix_builder_cmd,
        }.items():
            if not value:
                raise RuntimeError(f"{field} is required")

    async def execute_candidate(self, candidate: ScanCandidate) -> Optional[str]:
        try:
            self.circuit.assert_can_attempt()
            if candidate.net_profit_atoms < self.config.min_execution_net_profit_usdc_atoms:
                self.logger.warn("executor_skipped_profit_too_low")
                return None

            sol_balance = await get_sol_balance(self.session, self.config, self.wallet)
            if sol_balance < self.config.min_sol_balance_lamports:
                raise RuntimeError(f"Insufficient SOL balance: {sol_balance}")

            usdc_ata = str(derive_ata(self.wallet, self.config.usdc_mint))
            if not await get_account_exists(self.session, self.config, usdc_ata):
                raise RuntimeError(f"USDC ATA does not exist: {usdc_ata}")

            pre_usdc_balance = await get_token_balance(self.session, self.config, usdc_ata)
            built = await self.build_transaction(candidate, usdc_ata, pre_usdc_balance)

            if built.expected_net_profit_atoms < self.config.min_execution_net_profit_usdc_atoms:
                self.logger.warn("executor_skipped_refreshed_profit_too_low")
                return None

            simulation = await simulate_transaction(self.session, self.config, built.tx_base64)
            sim_value = simulation.get("value", {})
            if sim_value.get("err") is not None:
                self.circuit.record_failure()
                self.logger.warn("executor_simulation_failed", error=sim_value.get("err"), logs=truncate_logs(sim_value.get("logs"), self.config.max_simulation_log_lines))
                return None

            self.logger.warn(
                "executor_simulation_ok",
                unitsConsumed=sim_value.get("unitsConsumed"),
                strippedComputeBudgetInstructionCount=built.stripped_compute_budget_instruction_count,
                preUsdcBalanceAtoms=str(pre_usdc_balance),
                expectedNetProfitAtoms=str(built.expected_net_profit_atoms),
                expectedNetProfitUsdc=str(atoms_to_usdc(built.expected_net_profit_atoms)),
                logs=truncate_logs(sim_value.get("logs"), self.config.max_simulation_log_lines),
            )

            if self.config.simulation_only:
                self.logger.warn("executor_not_sent_simulation_only")
                return None

            if self.config.require_manual_approval and not self.manual_approval(candidate, built):
                self.logger.warn("executor_cancelled_by_user")
                return None

            self.circuit.record_send_attempt()
            signature = await send_transaction(self.session, self.config, built.tx_base64)
            self.logger.warn("executor_transaction_sent", signature=signature, blockhash=built.blockhash, lastValidBlockHeight=built.last_valid_block_height)

            await confirm_transaction_strict(self.session, self.config, signature, built.blockhash, built.last_valid_block_height)

            post_usdc_balance = await get_token_balance(self.session, self.config, built.usdc_ata)
            realized_delta = post_usdc_balance - built.pre_usdc_balance_atoms
            self.circuit.record_success()
            self.logger.warn("executor_transaction_confirmed", signature=signature, realizedDeltaAtoms=str(realized_delta), realizedDeltaUsdc=str(atoms_to_usdc(realized_delta)))
            return signature

        except Exception as exc:
            self.circuit.record_failure()
            self.logger.warn("executor_error_guarded", error=str(exc), errorType=type(exc).__name__, circuitBreaker=self.circuit.snapshot())
            return None

    async def build_transaction(self, candidate: ScanCandidate, usdc_ata: str, pre_usdc_balance: int) -> BuiltTransaction:
        refreshed_forward = await self.jupiter.quote_exact_in(candidate.base_mint, candidate.target_mint, candidate.borrow_amount_atoms)
        self.assert_acceptable_quote("forward", refreshed_forward)
        refreshed_forward_out = int(refreshed_forward["outAmount"])

        refreshed_reverse = await self.jupiter.quote_exact_in(candidate.target_mint, candidate.base_mint, refreshed_forward_out)
        self.assert_acceptable_quote("reverse", refreshed_reverse)

        reverse_out = int(refreshed_reverse["outAmount"])
        flash_fee = bps_of(candidate.borrow_amount_atoms, self.config.flash_loan_fee_bps)
        expected_net = reverse_out - candidate.borrow_amount_atoms - flash_fee - self.config.estimated_network_fee_usdc_atoms

        flash_borrow_ix, flash_repay_ix = call_kamino_builder(self.config, self.wallet, candidate.base_mint, candidate.borrow_amount_atoms)
        forward_bundle = await self.jupiter.swap_instructions(self.wallet, refreshed_forward)
        reverse_bundle = await self.jupiter.swap_instructions(self.wallet, refreshed_reverse)

        forward_ixs, forward_stripped = extract_jupiter_swap_instructions(forward_bundle, self.config)
        reverse_ixs, reverse_stripped = extract_jupiter_swap_instructions(reverse_bundle, self.config)

        instructions = [flash_borrow_ix, *forward_ixs, *reverse_ixs, flash_repay_ix]
        if str(instructions[0].program_id) != str(flash_borrow_ix.program_id):
            raise RuntimeError("Kamino flash borrow is not instruction index 0")

        blockhash, last_valid_block_height = await latest_blockhash(self.session, self.config)
        message = MessageV0.try_compile(
            payer=self.payer.pubkey(),
            instructions=instructions,
            address_lookup_table_accounts=[],
            recent_blockhash=Hash.from_string(blockhash),
        )
        tx = VersionedTransaction(message, [self.payer])
        tx_base64 = base64.b64encode(bytes(tx)).decode("utf-8")
        return BuiltTransaction(
            tx_base64=tx_base64,
            blockhash=blockhash,
            last_valid_block_height=last_valid_block_height,
            expected_net_profit_atoms=expected_net,
            stripped_compute_budget_instruction_count=forward_stripped + reverse_stripped,
            pre_usdc_balance_atoms=pre_usdc_balance,
            usdc_ata=usdc_ata,
        )

    def assert_acceptable_quote(self, label: str, quote: dict[str, Any]) -> None:
        out_amount = quote.get("outAmount")
        if not isinstance(out_amount, str) or not out_amount.isdigit() or int(out_amount) <= 0:
            raise RuntimeError(f"{label} quote invalid outAmount: {out_amount!r}")
        impact_bps = parse_price_impact_bps(quote.get("priceImpactPct"))
        if impact_bps > self.config.max_price_impact_bps:
            raise RuntimeError(f"{label} quote price impact too high: {impact_bps} bps")

    def manual_approval(self, candidate: ScanCandidate, built: BuiltTransaction) -> bool:
        print("\n=== MANUAL EXECUTION APPROVAL REQUIRED ===")
        print(f"Wallet: {self.wallet}")
        print(f"Borrow USDC: {atoms_to_usdc(candidate.borrow_amount_atoms)}")
        print(f"Target mint: {candidate.target_mint}")
        print(f"Expected net USDC: {atoms_to_usdc(built.expected_net_profit_atoms)}")
        print(f"USDC ATA: {built.usdc_ata}")
        print("Type EXECUTE to send, anything else to cancel.")
        return input("> ").strip() == "EXECUTE"


class Scanner:
    def __init__(self, config: Config, logger: Logger, session: aiohttp.ClientSession, jupiter: JupiterClient) -> None:
        self.config = config
        self.logger = logger
        self.session = session
        self.jupiter = jupiter
        self.sem = asyncio.Semaphore(config.max_concurrency)
        self.stopped = False
        self.executing = False
        self.executor = Executor(config, logger, session, jupiter) if config.executor_enabled else None

    def stop(self) -> None:
        self.stopped = True

    async def run_forever(self) -> None:
        self.logger.info("scanner_started", executorEnabled=self.config.executor_enabled, simulationOnly=self.config.simulation_only)
        while not self.stopped:
            started = time.monotonic()
            try:
                await self.scan_once()
            except Exception as exc:
                self.logger.error("scan_cycle_failed", error=str(exc), errorType=type(exc).__name__)
            sleep_ms = max(0, self.config.scan_interval_ms - int((time.monotonic() - started) * 1000))
            if sleep_ms > 0:
                await asyncio.sleep(sleep_ms / 1000)
        self.logger.info("scanner_stopped")

    async def scan_once(self) -> list[ScanCandidate]:
        tasks = []
        for target in self.config.target_mints:
            if target == self.config.usdc_mint:
                continue
            for amount in self.config.borrow_sizes_usdc_atoms:
                tasks.append(asyncio.create_task(self.guarded_scan_round_trip(self.config.usdc_mint, target, amount)))
        results = await asyncio.gather(*tasks)
        candidates = [x for x in results if x is not None]
        profitable = [x for x in candidates if x.profitable]
        best_net = max((x.net_profit_atoms for x in candidates), default=0)
        self.logger.info("scan_cycle_complete", candidates=len(candidates), profitable=len(profitable), bestNetProfitAtoms=str(best_net), bestNetProfitUsdc=str(atoms_to_usdc(best_net)))
        for candidate in profitable:
            self.logger.warn("profitable_candidate", **candidate.log_dict())
            await self.send_webhook(candidate)
            if self.executor is not None:
                if self.executing:
                    self.logger.warn("executor_skipped_already_executing")
                    continue
                self.executing = True
                try:
                    await self.executor.execute_candidate(candidate)
                finally:
                    self.executing = False
        return candidates

    async def guarded_scan_round_trip(self, base_mint: str, target_mint: str, amount: int) -> Optional[ScanCandidate]:
        async with self.sem:
            try:
                return await self.scan_round_trip(base_mint, target_mint, amount)
            except Exception as exc:
                self.logger.warn("candidate_scan_failed", baseMint=base_mint, targetMint=target_mint, amount=str(amount), error=str(exc))
                return None

    async def scan_round_trip(self, base_mint: str, target_mint: str, borrow_amount_atoms: int) -> ScanCandidate:
        forward = await self.jupiter.quote_exact_in(base_mint, target_mint, borrow_amount_atoms)
        forward_out = int(forward["outAmount"])

        # Analyze DEX route from existing forward quote (no extra API call)
        dex_analysis = self.jupiter.analyze_quote_dex(forward)
        dex_names = dex_analysis.get("dex_names", [])
        self.logger.info("dex_comparison", baseMint=base_mint, targetMint=target_mint,
                       amount=str(borrow_amount_atoms), dexCount=len(dex_names),
                       dexRoute=",".join(dex_names),
                       bestDex=dex_analysis.get("best_dex", {}).get("dex", "N/A") if dex_analysis.get("best_dex") else "N/A",
                       orcaUsed=dex_analysis.get("orca_used", False),
                       raydiumUsed=dex_analysis.get("raydium_used", False),
                       meteoraUsed=dex_analysis.get("meteora_used", False))
        
        reverse = await self.jupiter.quote_exact_in(target_mint, base_mint, forward_out)
        reverse_out = int(reverse["outAmount"])
        gross = reverse_out - borrow_amount_atoms
        flash_fee = bps_of(borrow_amount_atoms, self.config.flash_loan_fee_bps)
        net = gross - flash_fee - self.config.estimated_network_fee_usdc_atoms
        context_slot = reverse.get("contextSlot") or forward.get("contextSlot")
        
        # Store DEX comparison in candidate for dashboard
        candidate = ScanCandidate(
            base_mint=base_mint,
            target_mint=target_mint,
            borrow_amount_atoms=borrow_amount_atoms,
            forward_out_atoms=forward_out,
            reverse_out_atoms=reverse_out,
            gross_profit_atoms=gross,
            flash_loan_fee_atoms=flash_fee,
            estimated_network_fee_atoms=self.config.estimated_network_fee_usdc_atoms,
            net_profit_atoms=net,
            profitable=net >= self.config.min_profit_usdc_atoms,
            forward_dexes=dex_labels(forward),
            reverse_dexes=dex_labels(reverse),
            forward_price_impact_pct=str(forward.get("priceImpactPct", "unknown")),
            reverse_price_impact_pct=str(reverse.get("priceImpactPct", "unknown")),
            context_slot=context_slot if isinstance(context_slot, int) else None,
            checked_at=utc_now_iso(),
        )

    async def send_webhook(self, candidate: ScanCandidate) -> None:
        if not self.config.webhook_url:
            return
        text = f"🚨 Kamino scanner candidate\nBorrow: {atoms_to_usdc(candidate.borrow_amount_atoms)} USDC\nNet: {atoms_to_usdc(candidate.net_profit_atoms)} USDC"
        try:
            async with self.session.post(self.config.webhook_url, json={"text": text, "content": text, "candidate": candidate.log_dict()}, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status < 200 or response.status >= 300:
                    self.logger.warn("webhook_send_failed", status=response.status, body=(await response.text())[:500])
        except Exception as exc:
            self.logger.warn("webhook_error", error=str(exc))


async def async_main() -> int:
    config = Config.load()
    logger = Logger(config.log_level)
    timeout = aiohttp.ClientTimeout(total=max(10, config.quote_timeout_ms / 1000 + 3))
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            version = await rpc_call(session, config.solana_rpc_url, "getVersion")
            logger.info("rpc_connected", solanaCore=version.get("solana-core"), featureSet=version.get("feature-set"))
        except Exception as exc:
            logger.error("rpc_connection_failed", error=str(exc))
            return 1
        jupiter = JupiterClient(session, config)
        scanner = Scanner(config, logger, session, jupiter)
        loop = asyncio.get_running_loop()

        def stop() -> None:
            logger.warn("shutdown_signal_received")
            scanner.stop()

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop)
            except NotImplementedError:
                signal.signal(sig, lambda *_: stop())
        await scanner.run_forever()
    return 0


def main() -> None:
    try:
        code = asyncio.run(async_main())
    except KeyboardInterrupt:
        code = 130
    except Exception as exc:
        Logger("info").error("fatal_error", error=str(exc), errorType=type(exc).__name__)
        code = 1
    raise SystemExit(code)


if __name__ == "__main__":
    main()
