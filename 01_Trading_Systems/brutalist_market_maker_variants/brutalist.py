import os
# Update volatility (EWMA) – simplified: use absolute returns
        if hasattr(ws_mgr, 'last_mid'):
            ret = abs(math.log(mid / ws_mgr.last_mid)) if ws_mgr.last_mid else 0.0
            sigma_bps = sigma_bps * 0.9 + ret * 10_000 * 0.1  # simple EMA
        ws_mgr.last_mid = mid

        # Bollinger
        bollinger.update(mid)
        touch, touch_side, touch_intensity = bollinger.touch(mid)

        # Imbalance (simple 5-level)
        bid_vol = sum(s for _, s in book["bids"][:5])
        ask_vol = sum(s for _, s in book["asks"][:5])
        total = bid_vol + ask_vol
        imbalance = (bid_vol - ask_vol) / total if total > 0 else 0.0

        # Z-score
        zscore = volume_weighted_zscore(book, mid)

        # Ricci curvature
        ricci = ricci_curvature(book, cfg.ricci_levels)

    async def on_fill(side, size, price):
        nonlocal position
        # Update position (long = positive)
        if side == "buy":
            position += size
        else:
            position -= size
        log.info("FILL %s %.6f @ %.4f, new pos=%.6f", side, size, price, position)
        # Immediate market exit
        await market_exit(api, side, size)
        # Cancel our resting order (it's gone anyway)
        ws_mgr.current_order_id = None

    async def order_loop():
        nonlocal last_quote_time, position
        while ws_mgr._running:
            # Refresh order every order_refresh_sec
            now = time.time()
            if now - last_quote_time >= cfg.order_refresh_sec:
                # Cancel old order if exists
                if ws_mgr.current_order_id:
                    await cancel_all_orders(api)
                    ws_mgr.current_order_id = None

                # Get current max position size based on balance
                available = await get_futures_balance(api)
                max_inv = adapt_position_size(available, ws_mgr.mid)

                # Compute quotes
                bid, ask = compute_quotes(
                    mid=ws_mgr.mid,
                    sigma_bps=sigma_bps,
                    inventory=position,
                    max_inv=max_inv,
                    imbalance=imbalance,
                    ricci=ricci,
                    t_elapsed=now - session_start,
                    bollinger=bollinger,
                    zscore=zscore,
                    band_touch_intensity=touch_intensity,
                    band_side=touch_side
                )

                # Decide side: if position is too long, quote ask; too short, quote bid; else both? For first-in-line, pick one.
                # Simple: alternate or use inventory skew
                if position > 0.1 * max_inv:
                    side = "sell"
                    price = ask
                elif position < -0.1 * max_inv:
                    side = "buy"
                    price = bid
                else:
                    # neutral: quote both? but "first in line" wants one side. Choose whichever has higher volume? Here we pick bid.
                    side = "buy"
                    price = bid

                # Compute size in base asset
                size = cfg.order_size_usd / price
                # Cap by remaining capacity
                if side == "buy":
                    max_buy = max_inv - position
                    size = min(size, max_buy)
                else:
                    max_sell = max_inv + position   # position negative -> increase capacity
                    size = min(size, max_sell)

                if size * price < 1.0:
                    log.warning("Order too small, skipping")
                else:
                    # Place limit order
                    await place_limit_order(api, side, price, size, "queue_mm")
                    last_quote_time = now

            await asyncio.sleep(0.1)

    # Start listeners
    tasks = [
        asyncio.create_task(ws_mgr.listen(on_order_book, lambda p,s: None, on_fill, lambda oid,stat: None)),
        asyncio.create_task(order_loop())
    ]
    try:
        await asyncio.gather(*tasks)


except KeyboardInterrupt:
        log.info("Shutting down")
        ws_mgr._running = False
        await cancel_all_orders(api)
        await ws_mgr.ws.close()

if name == "__main__":
    asyncio.run(main())