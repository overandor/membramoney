import os
import ccxt
import time
import threading
import random
from statistics import mean, stdev
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.live import Live

console = Console()

# === CONFIG ===
API_KEY          = "4efbe203fbac0e4bcd0003a0910c801b"
API_SECRET       = "8b0e9cf47fdd97f2a42bca571a74105c53a5f906cd4ada125938d05115d063a0"
SCORE_THRESHOLD  = 0.0
MAX_SYMBOLS      = 8
GA_GENERATIONS   = 5
GA_POP_SIZE      = 6

# Scoring weights including forbidden KPIs
WEIGHTS = {
    "volatility_edge":  0.28, "certainty_boost": 0.18,
    "risk_change":     -0.18, "risk_skew":      -0.06,
    "microcap":         0.12, "ai_alpha":       0.15,
    "noise_suppression":0.19, "entropy_filter": -0.09,
    "funding_bias":     0.05, "sac":             0.12,
    "entropy_drag":    -0.10, "alpha_decay":    -0.08,
    "pnl_compression": -0.14, "lfi":             0.09,
    "killzone":        -0.15
}

symbol_states = {}  # symbol -> { entry, last, pnl, roi, side, amount }

def create_exchange():
    return ccxt.gateio({
        'apiKey':       API_KEY,
        'secret':       API_SECRET,
        'enableRateLimit': True,
        'options': {
            'defaultType':   'swap',
            'defaultSettle': 'usdt',
        }
    })

# ——— Data Fetching —————————————————————————————————————————————————————
def fetch_metrics(symbol, ex):
    try:
        t = ex.fetch_ticker(symbol)
        o = ex.fetch_ohlcv(symbol, '5m', 20)
        prices = [x[4] for x in o]
        returns = [(prices[i+1]-prices[i])/prices[i] for i in range(len(prices)-1)]
        spread = (t['ask'] - t['bid']) / t['last']
        change_1h = (prices[-1] - prices[0]) / prices[0] * 100
        kurt = sum((x-mean(returns))**4 for x in returns)/len(returns)
        skew = sum((x-mean(returns))**3 for x in returns)/len(returns)
        fr = 0
        try:
            fr = ex.fetch_funding_rate(symbol).get('fundingRate', 0)
        except: pass

        # Placeholder forbidden metrics—replace with real calculations if desired
        return {
            "spread": spread, "certainty":1, "volume_certainty":1,
            "change_1h": change_1h, "skew": skew, "kurt": kurt,
            "cap_bonus":0.5, "funding_vol":0.3, "extract":0.7,
            "noise": stdev(returns) if returns else 0,
            "entropy": min(1, abs(mean(returns))/(stdev(returns)+1e-6)),
            "funding_rate": fr,
            "sac": random.random(), "entropy_drag": random.random(),
            "alpha_decay": random.random(), "pnl_compression": random.random(),
            "lfi": random.random(), "killzone": random.random()
        }
    except Exception as e:
        console.print(f"[{symbol}] fetch_metrics error: {e}", style="red")
        return None

# ——— Scoring ———————————————————————————————————————————————————————
def entry_score(data):
    s = 0
    s += WEIGHTS["volatility_edge"]  * ((data["spread"]*100)**1.15)*(1+0.1*data["certainty"])
    s += WEIGHTS["certainty_boost"]  * (((data["volume_certainty"]+data["certainty"])/2)**1.2)
    s += WEIGHTS["risk_change"]     * ( min(abs(data["change_1h"]),20)**1.2 )
    s += WEIGHTS["risk_skew"]       * ((abs(data["skew"])+abs(data["kurt"]))**1.1)
    s += WEIGHTS["microcap"]        * data["cap_bonus"]*(1-data["funding_vol"])
    s += WEIGHTS["ai_alpha"]        * data["extract"]*data["certainty"]
    s += WEIGHTS["noise_suppression"] * ((1-data["noise"])**1.1)
    s += WEIGHTS["entropy_filter"]  * ( abs(data["entropy"]-0.5)**1.3 )
    s += WEIGHTS["funding_bias"]    * max(min(data["funding_rate"],2),-2)
    # forbidden
    for k in ["sac","entropy_drag","alpha_decay","pnl_compression","lfi","killzone"]:
        s += WEIGHTS[k] * data.get(k,0)
    return s

# ——— GA Evolution ————————————————————————————————————————————————————
def random_config():
    return {
        "initial":    round(random.uniform(1,4),2),
        "dca":        round(random.uniform(0.2,1.2),2),
        "offset":     round(random.uniform(1e-5,8e-5),8),
        "gross":      round(random.uniform(0.01,0.04),3),
        "base_profit":round(random.uniform(0.005,0.02),4),
        "fee":        0.002
    }

def mutate(cfg):
    c = cfg.copy()
    k = random.choice([x for x in cfg if x!="fee"])
    c[k] = max(1e-5, round(cfg[k] + random.uniform(-0.05,0.05),6))
    return c

def simulate_fitness(cfg, score):
    base = (cfg["initial"] + cfg["dca"]*0.5) * (cfg["base_profit"] + cfg["fee"])
    return base * (1 + score/20)

def evolve_config(data):
    score = entry_score(data)
    pop   = [random_config() for _ in range(GA_POP_SIZE)]
    best, best_fit = pop[0], -1
    for _ in range(GA_GENERATIONS):
        evald = [(c, simulate_fitness(c, score)) for c in pop]
        evald.sort(key=lambda x:-x[1])
        if evald[0][1] > best_fit:
            best, best_fit = evald[0]
        pop = [mutate(evald[0][0]) for _ in pop]
    return best

# ——— Parasite HedgeBot —————————————————————————————————————————————
def open_position(ex, sym, side, amt, offset):
    t = ex.fetch_ticker(sym)
    px = t['last'] * (1-offset if side=='buy' else 1+offset)
    ex.set_leverage(50, sym, {'type':'swap'})
    ex.create_limit_order(sym, side, amt, px, {'marginMode':'cross','type':'swap'})
    return px, amt, side

def close_position(ex, sym, state):
    # state: (entry_amt, side)
    amt, side = state["amount"], state["side"]
    px = ex.fetch_ticker(sym)['last']
    ex.create_limit_order(sym,
        ('sell' if side=='buy' else 'buy'),
        amt, px,
        {'reduceOnly':True,'marginMode':'cross','type':'swap'}
    )

# ——— PnL & ROI Tracking —————————————————————————————————————————————
def track(symbol, entry_px, amount, side):
    ex    = create_exchange()
    start = datetime.utcnow()
    symbol_states[symbol] = {
        "entry": entry_px, "last": entry_px,
        "pnl": 0, "roi": 0, "side": side, "amount": amount
    }
    while True:
        try:
            last = ex.fetch_ticker(symbol)['last']
            elapsed = (datetime.utcnow() - start).total_seconds()
            pnl = (last-entry_px)*amount * (1 if side=='buy' else -1)
            roi = (pnl/(entry_px*amount))*(3600/max(elapsed,1))
            symbol_states[symbol].update({"last":last,"pnl":pnl,"roi":roi})
        except: pass
        time.sleep(10)

# ——— Live Dashboard —————————————————————————————————————————————————
def build_table():
    tbl = Table("Sym","Side","Entry","Last","Amt","PnL","ROI/hr")
    for s,st in symbol_states.items():
        pc = "green" if st["pnl"]>=0 else "red"
        rc = "bold green" if st["roi"]>=0 else "bold red"
        tbl.add_row(
            s, st["side"].upper(),
            f"{st['entry']:.4f}", f"{st['last']:.4f}",
            f"{st['amount']:.2f}",
            f"[{pc}]{st['pnl']:.4f}[/{pc}]",
            f"[{rc}]{st['roi']:.2f}%[/{rc}]"
        )
    return tbl

# ——— Main Omnipotent Core —————————————————————————————————————————————
def main():
    ex = create_exchange()

    # 1) Import existing open positions
    positions = ex.fetch_positions(params={'type':'swap'})
    for p in positions:
        amt = float(p['contracts'])
        if amt <= 0: continue
        side = 'buy' if p['side']=='long' else 'sell'
        entry_px = float(p['entryPrice'])
        threading.Thread(
            target=track,
            args=(p['symbol'], entry_px, amt, side),
            daemon=True
        ).start()

    # 2) Scan and enter new positions
    markets = ex.load_markets()
    pairs   = [s for s,m in markets.items() if m['type']=='swap' and '/USDT' in s][:MAX_SYMBOLS]

    with Live(build_table(), refresh_per_second=1):
        for sym in pairs:
            if sym in symbol_states:
                continue  # already tracking existing or newly opened
            data = fetch_metrics(sym, ex)
            if not data: continue
            score = entry_score(data)
            console.print(f"[{sym}] score={score:.2f}")
            if score >= SCORE_THRESHOLD:
                cfg = evolve_config(data)
                px, amt, side = open_position(ex, sym, 'buy', cfg['initial'], cfg['offset'])
                threading.Thread(target=track, args=(sym, px, amt, side), daemon=True).start()
            time.sleep(0.5)

if __name__ == "__main__":
    main()