import os
except Exception as exc:
        event_log("cancel_all_fetch_error", error=str(exc))
        return

    for o in orders:
        order_id = str(o.get("id", ""))
        symbol   = str(o.get("contract", ""))
        if not order_id:
            continue
        try:
            if DRY_RUN:
                event_log("dry_cancel", order_id=order_id, symbol=symbol)
            else:
                self.client.cancel_order(order_id)
                event_log("cancel_order", order_id=order_id, symbol=symbol)
        except Exception as exc:
            event_log("cancel_order_error", order_id=order_id, symbol=symbol, error=str(exc))

def balance(self)        -> Dict[str, Any]:       return self.client.account()
def positions(self)      -> List[Dict[str, Any]]: return self.client.positions()
def book(self, sym: str) -> Dict[str, Any]:       return self.client.order_book(sym, limit=5)

# ------------------------------------------------------------------
# Main loop  (FIX: try/finally — cleanup guaranteed)
# ------------------------------------------------------------------

def run(self) -> None:
    self.refresh_universe(force=True)
    self.ensure_exchange_settings()

    log.info(
        "Starting %s %s  mode=%s  settle=%s  base_url=%s  "
        "max_nominal=%.4f  loop=%.2fs",
        APP_NAME, VERSION,
        "DRY" if DRY_RUN else "LIVE",
        SETTLE, BASE_URL,
        MAX_CONTRACT_NOMINAL_USD, LOOP_SECONDS,
    )
    event_log(
        "startup",
        mode         = "DRY" if DRY_RUN else "LIVE",
        settle       = SETTLE,
        base_url     = BASE_URL,
        max_nominal  = MAX_CONTRACT_NOMINAL_USD,
        loop_seconds = LOOP_SECONDS,
    )

    try:
        while True:
            cycle_start = wall_ts()
            self.state.cycle += 1

            try:
                if not DRY_RUN:
                    try:
                        self.client.countdown_cancel_all(COUNTDOWN_CANCEL_TIMEOUT)
                    except Exception as exc:
                        event_log("countdown_cancel_error", error=str(exc))

                self.quote_cycle()
                self.store.save(self.state)
                self.consecutive_errors = 0

                inv = self.fetch_inventory()
                net_usd, gross_usd = self.portfolio_exposure(inv)
                log.info(
                    "cycle=%d  symbols=%d  net=%+.6f  gross=%.6f",
                    self.state.cycle, len(self.contracts), net_usd, gross_usd,
                )

            except KeyboardInterrupt:
                raise

            except Exception as exc:
                self.consecutive_errors += 1
                log.error("Loop error: %s", exc)
                event_log(
                    "main_loop_error",
                    error              = str(exc),
                    traceback          = traceback.format_exc(),
                    consecutive_errors = self.consecutive_errors,
                )
                if self.consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    event_log("panic_stop", consecutive_errors=self.consecutive_errors)
                    break

            elapsed = wall_ts() - cycle_start
            time.sleep(max(0.0, LOOP_SECONDS - elapsed))

    except KeyboardInterrupt:
        log.info("Interrupted — shutting down.")
        event_log("shutdown", reason="keyboard_interrupt")

    finally:
        log.info("Cleanup: cancelling open quotes.")
        try:
            self.cancel_all()
        except Exception as exc:
            event_log("shutdown_cancel_error", error=str(exc))
# =============================================================================

# ENTRY POINT

# =============================================================================

def main() -> None:
global DRY_RUN
parser = argparse.ArgumentParser(description=f"Gate.io hedged market maker {VERSION}")
parser.add_argument("--dry",         action="store_true", help="Dry-run (default)")
parser.add_argument("--live",        action="store_true", help="Live trading")
parser.


add_argument("--balance",     action="store_true", help="Print account balance and exit")
parser.add_argument("--positions",   action="store_true", help="Print positions and exit")
parser.add_argument("--book",        metavar="SYMBOL",    help="Print order book for SYMBOL and exit")
parser.add_argument("--cancel-all",  action="store_true", help="Cancel all open orders and exit")
parser.add_argument("--flatten-all", action="store_true", help="Flatten all positions and exit")
args = parser.parse_args()

DRY_RUN = not args.live

if not DRY_RUN and (not GATE_API_KEY or not GATE_API_SECRET):
    sys.stderr.write("ERROR: GATE_API_KEY / GATE_API_SECRET not set.\n")
    sys.exit(1)

client = GateRestClient(
    key      = GATE_API_KEY,
    secret   = GATE_API_SECRET,
    base_url = BASE_URL,
    settle   = SETTLE,
)
store = StateStore(STATE_FILE)
state = store.load()
bot   = HedgeMarketMaker(client, store, state)

if   args.balance:     print(json.dumps(bot.balance(),       indent=2, ensure_ascii=False))
elif args.positions:   print(json.dumps(bot.positions(),     indent=2, ensure_ascii=False))
elif args.book:        print(json.dumps(bot.book(args.book), indent=2, ensure_ascii=False))
elif args.cancel_all:  bot.cancel_all()
elif args.flatten_all: bot.flatten_all()
else:                  bot.run()
if name == “**main**”:
main()