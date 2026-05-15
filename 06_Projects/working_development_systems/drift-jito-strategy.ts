// drift-jito-strategy.ts
// Minimal declarations so the file type-checks without @types/node.
declare const process: any;
declare const Buffer: any;
//
// npm i @drift-labs/sdk @solana/web3.js bs58 dotenv
//
// Required env vars:
//   RPC_URL=https://your-rpc-endpoint
//   JITO_BLOCK_ENGINE_URL=https://mainnet.block-engine.jito.wtf/api/v1/bundles
//   PRIVATE_KEY_JSON=[12,34,...]   // full Uint8Array secret key
//
// ─── ALPHA OVERVIEW ────────────────────────────────────────────────────────────
//
//  1. POST-ONLY LIMIT → collect the maker rebate (~2 bps). Never cross the
//     book accidentally. Your tx reverts if it would take liquidity.
//
//  2. IOC (Immediate-Or-Cancel) → market-like aggression with a price cap.
//     Fills what it can at ≤ your price, cancels the rest. Better than pure
//     market orders because you can't get rekt by a thin book.
//
//  3. ORACLE OFFSET → anchor to the oracle price, not a stale limit. Use a
//     negative offset to stay slightly inside the spread (maker) or a small
//     positive offset to cross it (taker). Adjusts dynamically with the mark.
//
//  4. TRIGGER / STOP ORDERS → place server-side conditional orders via Drift's
//     keeper network. No keeper fee for the submitter, but keepers execute
//     async so add slippage tolerance.
//
//  5. BRACKET (ENTRY + TP + SL) → all three instructions in ONE Jito bundle.
//     Atomic: either the whole bracket lands or nothing does.
//
//  6. JITO BUNDLE TIP SIZING → the minimum is 1000 lamports, but competitive
//     slots need ~10k–50k. Check https://jito.wtf/ for the 50th-pct tip.
//     Tip too low → bundle silently dropped. Tip too high → wasted SOL.
//
//  7. PRIORITY FEE vs TIP → setPriorityFee only matters for non-Jito landing.
//     When using Jito bundles you are paying the validator through the tip ix,
//     so the microLamport fee is largely irrelevant — keep it low (5_000) to
//     not bloat the tx unnecessarily.
//
// ──────────────────────────────────────────────────────────────────────────────

import "dotenv/config";
import {
  BN,
  DriftClient,
  Wallet,
  OrderType,
  PositionDirection,
  PostOnlyParams,
  TriggerCondition,
} from "@drift-labs/sdk";
import {
  ComputeBudgetProgram,
  Connection,
  Keypair,
  PublicKey,
  SystemProgram,
  TransactionInstruction,
  VersionedTransaction,
} from "@solana/web3.js";

// ─── HELPERS ──────────────────────────────────────────────────────────────────

function loadKeypair(): Keypair {
  const raw = process.env.PRIVATE_KEY_JSON;
  if (!raw) throw new Error("Missing PRIVATE_KEY_JSON");
  return Keypair.fromSecretKey(Uint8Array.from(JSON.parse(raw)));
}

async function rpc<T>(url: string, method: string, params: unknown[]): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
  const body = await res.json();
  if (body.error) throw new Error(`${method} error: ${JSON.stringify(body.error)}`);
  return body.result as T;
}

function isDryRun(): boolean {
  const v = (process.env.DRY_RUN || "").toLowerCase();
  return v === "1" || v === "true" || v === "yes";
}

// Drift precisions:
//   base (contracts) = 1e9   e.g. 0.01 SOL-PERP → BN(10_000_000)
//   price            = 1e6   e.g. $180.50       → BN(180_500_000)
//   oracle offset    = 1e6   e.g. -$0.10        → BN(-100_000)
const BASE  = (n: number) => new BN(Math.round(n * 1e9));
const PRICE = (n: number) => new BN(Math.round(n * 1e6));

// ALPHA: positive offset = you're willing to pay above oracle (taker aggression)
//        negative offset = you want to sit below oracle (maker patience)
const ORACLE_OFFSET = (dollarOffset: number) => new BN(Math.round(dollarOffset * 1e6));

// ─── ORDER STRATEGY FACTORIES ─────────────────────────────────────────────────

/**
 * Passive maker limit — collects the rebate, won't cross the book.
 * ALPHA: combine with a small oracle offset (e.g. -0.05) so the price
 * tracks the mark and doesn't go stale if the market moves before fill.
 */
function makerLimitParams(
  marketIndex: number,
  direction: PositionDirection,
  size: number,
  limitPrice: number
) {
  return {
    marketIndex,
    direction,
    baseAssetAmount: BASE(size),
    price: PRICE(limitPrice),
    orderType: OrderType.LIMIT,
    postOnly: PostOnlyParams.MUST_POST_ONLY, // reverts if it would cross
    reduceOnly: false,
  };
}

/**
 * Aggressive IOC — taker fill up to limitPrice, then cancel remainder.
 * ALPHA: prefer this over pure MARKET orders. You control max slippage
 * and avoid getting ladder-walked on a thin perp book.
 */
function iocParams(
  marketIndex: number,
  direction: PositionDirection,
  size: number,
  maxPrice: number
) {
  return {
    marketIndex,
    direction,
    baseAssetAmount: BASE(size),
    price: PRICE(maxPrice),
    orderType: OrderType.LIMIT,
    immediateOrCancel: true,
    postOnly: false,
    reduceOnly: false,
  };
}

/**
 * Oracle-pegged limit — price floats with the oracle + your offset.
 * ALPHA: this is the cleanest way to queue a resting maker order.
 * Set oracleOffsetDollar = -(half spread) to sit at the inside bid/ask.
 * Drift keepers auto-cancel if the oracle moves the pegged price into
 * crossing territory — no ghost orders.
 */
function oraclePegParams(
  marketIndex: number,
  direction: PositionDirection,
  size: number,
  oracleOffsetDollar: number
) {
  return {
    marketIndex,
    direction,
    baseAssetAmount: BASE(size),
    oraclePriceOffset: ORACLE_OFFSET(oracleOffsetDollar).toNumber(),
    orderType: OrderType.ORACLE,
    postOnly: PostOnlyParams.MUST_POST_ONLY,
    reduceOnly: false,
  };
}

/**
 * Reduce-only close — exits an existing position, won't open a new one.
 * ALPHA: always use reduceOnly for TP/SL legs. Without it, if you
 * accidentally fire the order twice you'll flip to the opposite side.
 */
function reduceOnlyCloseParams(
  marketIndex: number,
  direction: PositionDirection,  // OPPOSITE of your entry direction
  size: number,
  limitPrice: number
) {
  return {
    marketIndex,
    direction,
    baseAssetAmount: BASE(size),
    price: PRICE(limitPrice),
    orderType: OrderType.LIMIT,
    reduceOnly: true,
    postOnly: false,
  };
}

/**
 * Server-side stop (trigger order) — executed by Drift keepers.
 * ALPHA: keepers execute within ~1 block typically, but under congestion
 * you can get 2-5 block slippage. Use a LIMIT price that has buffer vs
 * triggerPrice (e.g. 0.5-1% worse). Avoid MARKET stop-losses on illiquid
 * perps — the fill price can be brutal.
 */
function stopLossParams(
  marketIndex: number,
  direction: PositionDirection,  // OPPOSITE of entry
  size: number,
  triggerPrice: number,
  limitPrice: number             // price floor/ceil on the stop fill
) {
  return {
    marketIndex,
    direction,
    baseAssetAmount: BASE(size),
    price: PRICE(limitPrice),
    triggerPrice: PRICE(triggerPrice),
    triggerCondition: direction === PositionDirection.SHORT
      ? TriggerCondition.ABOVE
      : TriggerCondition.BELOW,
    orderType: OrderType.TRIGGER_LIMIT,
    reduceOnly: true,
    postOnly: false,
  };
}

// ─── JITO HELPERS ─────────────────────────────────────────────────────────────

async function getJitoTipAccount(jitoUrl: string): Promise<PublicKey> {
  // ALPHA: rotate through tip accounts to spread load. Jito's block engine
  // accepts any of the 8 tip addresses. Picking the same one repeatedly can
  // cause occasional rejects under high bundle volume.
  const accounts = await rpc<string[]>(jitoUrl, "getTipAccounts", []);
  if (!accounts.length) throw new Error("No Jito tip accounts returned");
  const idx = Math.floor(Math.random() * accounts.length);
  return new PublicKey(accounts[idx]);
}

function buildTipIx(from: PublicKey, tipAccount: PublicKey, lamports: number): TransactionInstruction {
  return SystemProgram.transfer({ fromPubkey: from, toPubkey: tipAccount, lamports });
}

async function sendJitoBundle(
  jitoUrl: string,
  txs: VersionedTransaction[]
): Promise<string> {
  // ALPHA: Jito bundles can contain up to 5 transactions.
  // Ordering is guaranteed — tx[0] executes before tx[1], etc.
  // Atomicity is NOT guaranteed across multiple txs in a bundle
  // (only the tip tx itself is required to land for the bundle to count).
  // If true atomicity matters, pack everything into ONE transaction.
  const encoded = txs.map((tx) => Buffer.from(tx.serialize()).toString("base64"));
  return rpc<string>(jitoUrl, "sendBundle", [encoded, { encoding: "base64" }]);
}

// ─── STRATEGY: BRACKET ENTRY ──────────────────────────────────────────────────
//
//  Packs THREE order instructions into ONE versioned transaction, then
//  wraps it in a Jito bundle. This means:
//    • Entry + TP + SL all land in the same slot or not at all.
//    • No race condition where entry fills but TP/SL miss due to congestion.
//
//  ALPHA: Drift enforces that you can only have one active order per side
//  per market per subaccount by default. If you have an existing open
//  order on the same side, this will fail at the contract level. Cancel
//  stale orders first or use a separate subaccount per strategy.

async function placeBracketEntry(
  driftClient: DriftClient,
  signer: Keypair,
  jitoUrl: string,
  params: {
    marketIndex: number;
    subAccountId: number;
    entryPrice: number;
    takeProfitPrice: number;
    stopLossPrice: number;
    stopLossLimitPrice: number;  // typically 0.5-1% below stopLossPrice for longs
    size: number;
    tipLamports: number;
  }
) {
  const {
    marketIndex,
    subAccountId,
    entryPrice,
    takeProfitPrice,
    stopLossPrice,
    stopLossLimitPrice,
    size,
    tipLamports,
  } = params;

  // 1. Entry: passive maker limit (collects rebate)
  const entryIx = await driftClient.getPlacePerpOrderIx(
    makerLimitParams(marketIndex, PositionDirection.LONG, size, entryPrice),
    subAccountId
  );

  // 2. Take-profit: reduce-only limit on the opposite side
  const tpIx = await driftClient.getPlacePerpOrderIx(
    reduceOnlyCloseParams(marketIndex, PositionDirection.SHORT, size, takeProfitPrice),
    subAccountId
  );

  // 3. Stop-loss: trigger-limit (keeper-executed, reduce-only)
  const slIx = await driftClient.getPlacePerpOrderIx(
    stopLossParams(
      marketIndex,
      PositionDirection.SHORT,
      size,
      stopLossPrice,
      stopLossLimitPrice
    ),
    subAccountId
  );

  // ALPHA: keep CU budget tight — 3 Drift order ixs ≈ 250k–300k CU.
  // Overpaying CU limit wastes blockspace; underpaying causes sim failure.
  const cuLimitIx = ComputeBudgetProgram.setComputeUnitLimit({ units: 350_000 });

  // ALPHA: microLamport priority fee is largely irrelevant when using Jito,
  // because inclusion priority is determined by the tip, not the fee.
  // Keep it at minimum to avoid bloating the fee payer unnecessarily.
  const cuPriceIx = ComputeBudgetProgram.setComputeUnitPrice({ microLamports: 5_000 });

  const tipAccount = await getJitoTipAccount(jitoUrl);
  const tipIx = buildTipIx(signer.publicKey, tipAccount, tipLamports);

  // Pack all ixs into a single versioned transaction
  const tx = await driftClient.buildTransaction(
    [cuLimitIx, cuPriceIx, entryIx, tpIx, slIx, tipIx],
    undefined,
    0
  );

  if (!(tx instanceof VersionedTransaction)) {
    throw new Error("Expected a VersionedTransaction");
  }

  tx.sign([signer]);

  if (isDryRun()) {
    const b64 = Buffer.from(tx.serialize()).toString("base64");
    console.log("[bracket] DRY_RUN=1; not sending bundle. tx_base64=", b64);
    return "dry_run";
  }

  const bundleId = await sendJitoBundle(jitoUrl, [tx]);
  console.log("[bracket] bundle_id =", bundleId);
  return bundleId;
}

// ─── STRATEGY: ORACLE-PEG MAKER ───────────────────────────────────────────────
//
//  Places a single oracle-pegged maker order. No TP/SL — use this as a
//  standalone liquidity-provision strategy or pair it with a separate
//  hedge transaction.
//
//  ALPHA: Oracle-pegged orders with MUST_POST_ONLY are the closest thing to
//  a proper market-maker order on Drift. The order reprices continuously as
//  the oracle moves, so you always sit at the inside of the spread without
//  needing to cancel and re-submit. Latency edge comes from choosing a fast
//  RPC endpoint, not order management speed.

async function placeOraclePegMaker(
  driftClient: DriftClient,
  signer: Keypair,
  jitoUrl: string,
  params: {
    marketIndex: number;
    subAccountId: number;
    direction: PositionDirection;
    size: number;
    oracleOffsetDollar: number;  // negative = bid below oracle (long), positive = ask above (short)
    tipLamports: number;
  }
) {
  const { marketIndex, subAccountId, direction, size, oracleOffsetDollar, tipLamports } = params;

  const orderIx = await driftClient.getPlacePerpOrderIx(
    oraclePegParams(marketIndex, direction, size, oracleOffsetDollar),
    subAccountId
  );

  const cuLimitIx = ComputeBudgetProgram.setComputeUnitLimit({ units: 200_000 });
  const cuPriceIx = ComputeBudgetProgram.setComputeUnitPrice({ microLamports: 5_000 });
  const tipAccount = await getJitoTipAccount(jitoUrl);
  const tipIx = buildTipIx(signer.publicKey, tipAccount, tipLamports);

  const tx = await driftClient.buildTransaction(
    [cuLimitIx, cuPriceIx, orderIx, tipIx],
    undefined,
    0
  );

  if (!(tx instanceof VersionedTransaction)) throw new Error("Expected VersionedTransaction");

  tx.sign([signer]);

  if (isDryRun()) {
    const b64 = Buffer.from(tx.serialize()).toString("base64");
    console.log("[oracle-peg] DRY_RUN=1; not sending bundle. tx_base64=", b64);
    return "dry_run";
  }

  const bundleId = await sendJitoBundle(jitoUrl, [tx]);
  console.log("[oracle-peg] bundle_id =", bundleId);
  return bundleId;
}

// ─── STRATEGY: IOC AGGRESSIVE ENTRY ──────────────────────────────────────────
//
//  Fires an aggressive immediate-or-cancel order via Jito for guaranteed
//  slot priority. Best for directional trades where speed matters.
//
//  ALPHA: Size your tip based on the dollar value of the edge you expect.
//  If you expect 5 bps of edge on a $10,000 notional trade that's $5 edge.
//  Paying 50k lamports (~$0.005 at 0.1 SOL) to protect $5 of edge is fine.
//  Paying 50k lamports for $0.50 of expected edge is irrational.

async function placeIocAggressive(
  driftClient: DriftClient,
  signer: Keypair,
  jitoUrl: string,
  params: {
    marketIndex: number;
    subAccountId: number;
    direction: PositionDirection;
    size: number;
    maxPrice: number;   // for longs: max price you'll pay; shorts: min you'll accept
    tipLamports: number;
  }
) {
  const { marketIndex, subAccountId, direction, size, maxPrice, tipLamports } = params;

  const orderIx = await driftClient.getPlacePerpOrderIx(
    iocParams(marketIndex, direction, size, maxPrice),
    subAccountId
  );

  const cuLimitIx = ComputeBudgetProgram.setComputeUnitLimit({ units: 200_000 });
  const cuPriceIx = ComputeBudgetProgram.setComputeUnitPrice({ microLamports: 5_000 });
  const tipAccount = await getJitoTipAccount(jitoUrl);
  const tipIx = buildTipIx(signer.publicKey, tipAccount, tipLamports);

  const tx = await driftClient.buildTransaction(
    [cuLimitIx, cuPriceIx, orderIx, tipIx],
    undefined,
    0
  );

  if (!(tx instanceof VersionedTransaction)) throw new Error("Expected VersionedTransaction");

  tx.sign([signer]);

  if (isDryRun()) {
    const b64 = Buffer.from(tx.serialize()).toString("base64");
    console.log("[ioc] DRY_RUN=1; not sending bundle. tx_base64=", b64);
    return "dry_run";
  }

  const bundleId = await sendJitoBundle(jitoUrl, [tx]);
  console.log("[ioc] bundle_id =", bundleId);
  return bundleId;
}

// ─── MAIN: pick a strategy and run it ─────────────────────────────────────────

async function main() {
  const rpcUrl = process.env.RPC_URL;
  if (!rpcUrl) throw new Error("Missing RPC_URL");

  const jitoUrl =
    process.env.JITO_BLOCK_ENGINE_URL ||
    "https://mainnet.block-engine.jito.wtf/api/v1/bundles";

  const signer = loadKeypair();
  const wallet = new Wallet(signer);
  const connection = new Connection(rpcUrl, "confirmed");

  const driftClient = new DriftClient({
    connection,
    wallet,
    env: "mainnet-beta",
  });

  await driftClient.subscribe();

  // ── Example A: Bracket entry on SOL-PERP (marketIndex 0)
  // Long 0.1 SOL-PERP at $180, TP at $186, SL below $176 with $175.50 limit.
  // ALPHA: risk:reward here is 6:4 → 1.5R. Adjust to your model's edge estimate.
  await placeBracketEntry(driftClient, signer, jitoUrl, {
    marketIndex: 0,
    subAccountId: 0,
    entryPrice: 180.00,
    takeProfitPrice: 186.00,
    stopLossPrice: 176.00,
    stopLossLimitPrice: 175.50,
    size: 0.1,
    tipLamports: 20_000,  // ~0.00002 SOL — raise in congested slots
  });

  // ── Example B: Oracle-pegged passive bid on SOL-PERP
  // Sit $0.05 below oracle price. Adjusts automatically with mark.
  // ALPHA: use this pattern for entries during calm markets. Collect the
  // ~2bps maker rebate; your breakeven improves before you even get filled.
  // await placeOraclePegMaker(driftClient, signer, jitoUrl, {
  //   marketIndex: 0,
  //   subAccountId: 0,
  //   direction: PositionDirection.LONG,
  //   size: 0.1,
  //   oracleOffsetDollar: -0.05,
  //   tipLamports: 10_000,
  // });

  // ── Example C: Aggressive IOC if you need immediate directional exposure
  // ALPHA: run this on high-conviction signals where delay costs more than
  // the ~1-2 bps taker fee differential vs a resting limit.
  // await placeIocAggressive(driftClient, signer, jitoUrl, {
  //   marketIndex: 0,
  //   subAccountId: 0,
  //   direction: PositionDirection.LONG,
  //   size: 0.1,
  //   maxPrice: 181.00,  // won't fill above $181
  //   tipLamports: 30_000,
  // });

  await driftClient.unsubscribe();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
