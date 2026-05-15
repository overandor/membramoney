import "dotenv/config";
import crypto from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { createInterface } from "node:readline/promises";
import { stdin as input, stdout as output } from "node:process";
import { request } from "undici";
import { z } from "zod";

import {
  AddressLookupTableAccount,
  ComputeBudgetProgram,
  Connection,
  Keypair,
  PublicKey,
  TransactionInstruction,
  TransactionMessage,
  VersionedTransaction
} from "@solana/web3.js";

import {
  AccountLayout,
  ASSOCIATED_TOKEN_PROGRAM_ID,
  TOKEN_PROGRAM_ID,
  createAssociatedTokenAccountInstruction,
  getAssociatedTokenAddressSync
} from "@solana/spl-token";

import {
  KaminoMarket,
  getFlashLoanInstructions,
  PROGRAM_ID as KAMINO_PROGRAM_ID
} from "@kamino-finance/klend-sdk";

const USDC_MINT = new PublicKey("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v");

const Env = z.object({
  SOLANA_RPC_URL: z.string().url().default("https://api.mainnet-beta.solana.com"),
  WALLET_KEYPAIR_PATH: z.string().min(1),

  KAMINO_MARKET_ADDRESS: z.string().min(32),
  KAMINO_USDC_RESERVE_ADDRESS: z.string().min(32),

  JUPITER_QUOTE_URL: z.string().url().default("https://api.jup.ag/swap/v1/quote"),
  JUPITER_SWAP_INSTRUCTIONS_URL: z.string().url().default("https://api.jup.ag/swap/v1/swap-instructions"),
  JUPITER_API_KEY: z.string().optional().default(""),

  TARGET_MINTS: z.string().min(32),
  BORROW_SIZES_USDC_ATOMS: z.string().min(1),

  SLIPPAGE_BPS: z.coerce.number().int().min(1).max(1000).default(15),
  MAX_PRICE_IMPACT_BPS: z.coerce.number().int().min(0).max(5000).default(80),
  FLASH_LOAN_FEE_BPS: z.coerce.bigint().default(5n),
  PRIORITY_FEE_USDC_ATOMS: z.coerce.bigint().default(100000n),
  MIN_NET_PROFIT_USDC_ATOMS: z.coerce.bigint().default(300000n),
  MIN_SIMULATED_PROFIT_USDC_ATOMS: z.coerce.bigint().default(200000n),

  COMPUTE_UNIT_LIMIT: z.coerce.number().int().min(10000).max(1400000).default(1350000),
  COMPUTE_UNIT_PRICE_MICRO_LAMPORTS: z.coerce.number().int().min(0).default(20000),

  MAX_QUOTE_AGE_MS: z.coerce.number().int().min(100).default(1500),
  SCAN_INTERVAL_MS: z.coerce.number().int().min(250).default(3000),
  MAX_TX_BYTES: z.coerce.number().int().default(1232),

  LIVE_SEND_ENABLED: z.coerce.boolean().default(false),
  REQUIRE_MANUAL_APPROVAL: z.coerce.boolean().default(true),
  MAX_SEND_RETRIES: z.coerce.number().int().min(0).max(10).default(3),
  CONFIRMATION_COMMITMENT: z.enum(["confirmed", "finalized"]).default("confirmed"),

  PROOF_DIR: z.string().default("./proofs")
});

const env = Env.parse(process.env);

const connection = new Connection(env.SOLANA_RPC_URL, "confirmed");
const payer = loadKeypair(env.WALLET_KEYPAIR_PATH);
const user = payer.publicKey;

const marketPk = new PublicKey(env.KAMINO_MARKET_ADDRESS);
const reservePk = new PublicKey(env.KAMINO_USDC_RESERVE_ADDRESS);

const targets = env.TARGET_MINTS
  .split(",")
  .map((x) => x.trim())
  .filter(Boolean)
  .map((x) => new PublicKey(x));

const sizes = env.BORROW_SIZES_USDC_ATOMS
  .split(",")
  .map((x) => x.trim())
  .filter(Boolean)
  .map((x) => BigInt(x));

function loadKeypair(path: string): Keypair {
  const raw = JSON.parse(readFileSync(path, "utf8"));
  if (!Array.isArray(raw)) throw new Error("Wallet keypair must be Solana JSON byte array");
  return Keypair.fromSecretKey(Uint8Array.from(raw));
}

function json(x: unknown): string {
  return JSON.stringify(x, (_, v) => {
    if (typeof v === "bigint") return v.toString();
    if (v instanceof PublicKey) return v.toBase58();
    return v;
  }, 2);
}

function sha256(x: unknown): string {
  return crypto.createHash("sha256").update(json(x)).digest("hex");
}

function fmtUsdc(n: bigint): string {
  const neg = n < 0n;
  const a = neg ? -n : n;
  return `${neg ? "-" : ""}${a / 1000000n}.${(a % 1000000n).toString().padStart(6, "0")}`;
}

function priceImpactBps(v: unknown): number {
  const n = Number(v ?? 0);
  if (!Number.isFinite(n) || n < 0) return 999999;
  return Math.round(n * 10000);
}

function headers(): Record<string, string> {
  return {
    accept: "application/json",
    "content-type": "application/json",
    ...(env.JUPITER_API_KEY ? { "x-api-key": env.JUPITER_API_KEY } : {})
  };
}

async function askExecute(summary: unknown): Promise<boolean> {
  if (!env.REQUIRE_MANUAL_APPROVAL) return true;
  const rl = createInterface({ input, output });
  try {
    const ans = await rl.question(
      `${json(summary)}\n\nREAL MAINNET FLASH-ARB SEND. Type EXECUTE to broadcast:\n> ` 
    );
    return ans.trim() === "EXECUTE";
  } finally {
    rl.close();
  }
}

async function quote(inputMint: PublicKey, outputMint: PublicKey, amount: bigint): Promise<any> {
  const url = new URL(env.JUPITER_QUOTE_URL);
  url.searchParams.set("inputMint", inputMint.toBase58());
  url.searchParams.set("outputMint", outputMint.toBase58());
  url.searchParams.set("amount", amount.toString());
  url.searchParams.set("slippageBps", String(env.SLIPPAGE_BPS));
  url.searchParams.set("restrictIntermediateTokens", "true");

  const res = await request(url.toString(), {
    method: "GET",
    headers: headers(),
    headersTimeout: 5000,
    bodyTimeout: 5000
  });

  const body = await res.body.text();
  if (res.statusCode < 200 || res.statusCode >= 300) {
    throw new Error(`Jupiter quote HTTP ${res.statusCode}: ${body.slice(0, 300)}`);
  }

  const q = JSON.parse(body);
  if (!q.outAmount || !/^\d+$/.test(q.outAmount)) throw new Error("Bad Jupiter outAmount");

  const impact = priceImpactBps(q.priceImpactPct);
  if (impact > env.MAX_PRICE_IMPACT_BPS) {
    throw new Error(`Price impact too high: ${impact} bps`);
  }

  return q;
}

function deserializeJupIx(ix: any): TransactionInstruction {
  return new TransactionInstruction({
    programId: new PublicKey(ix.programId),
    keys: ix.accounts.map((a: any) => ({
      pubkey: new PublicKey(a.pubkey),
      isSigner: !!a.isSigner,
      isWritable: !!a.isWritable
    })),
    data: Buffer.from(ix.data, "base64")
  });
}

async function buildJupiterInstructions(quoteResponse: any): Promise<{
  ixs: TransactionInstruction[];
  altAddresses: PublicKey[];
}> {
  const res = await request(env.JUPITER_SWAP_INSTRUCTIONS_URL, {
    method: "POST",
    headers: headers(),
    headersTimeout: 8000,
    bodyTimeout: 8000,
    body: JSON.stringify({
      userPublicKey: user.toBase58(),
      quoteResponse,
      dynamicComputeUnitLimit: false,
      useSharedAccounts: false,
      wrapAndUnwrapSol: false
    })
  });

  const body = await res.body.text();
  if (res.statusCode < 200 || res.statusCode >= 300) {
    throw new Error(`Jupiter swap-instructions HTTP ${res.statusCode}: ${body.slice(0, 300)}`);
  }

  const s = JSON.parse(body);
  const raw = [
    ...(s.setupInstructions ?? []),
    ...(s.otherInstructions ?? []),
    s.swapInstruction,
    ...(s.cleanupInstruction ? [s.cleanupInstruction] : [])
  ];

  const ixs = raw
    .map(deserializeJupIx)
    .filter((ix: TransactionInstruction) => !ix.programId.equals(ComputeBudgetProgram.programId));

  const altAddresses = (s.addressLookupTableAddresses ?? []).map((x: string) => new PublicKey(x));
  return { ixs, altAddresses };
}

async function loadAlts(addresses: PublicKey[]): Promise<AddressLookupTableAccount[]> {
  const unique = [...new Map(addresses.map((a) => [a.toBase58(), a])).values()];
  const rows = await Promise.all(unique.map((a) => connection.getAddressLookupTable(a)));
  return rows.map((r) => r.value).filter((x): x is AddressLookupTableAccount => !!x);
}

function normalizeIx(raw: any): TransactionInstruction {
  if (raw instanceof TransactionInstruction) return raw;
  return new TransactionInstruction({
    programId: raw.programId instanceof PublicKey ? raw.programId : new PublicKey(raw.programId),
    keys: raw.keys.map((k: any) => ({
      pubkey: k.pubkey instanceof PublicKey ? k.pubkey : new PublicKey(k.pubkey),
      isSigner: !!k.isSigner,
      isWritable: !!k.isWritable
    })),
    data: Buffer.from(raw.data)
  });
}

async function loadKamino(): Promise<{ market: any; reserve: any }> {
  const market = await KaminoMarket.load(connection, marketPk);
  await market.loadReserves();

  const reserves = (market as any).reserves ?? [];
  const reserve = reserves.find((r: any) => {
    const pk = r.address ?? r.publicKey ?? r.getAddress?.();
    return pk?.equals(reservePk);
  });

  if (!reserve) throw new Error("Kamino reserve not found in market. Fix KAMINO_USDC_RESERVE_ADDRESS.");
  return { market, reserve };
}

function decodeTokenAmountFromBase64(dataBase64: string): bigint {
  const raw = Buffer.from(dataBase64, "base64");
  const decoded = AccountLayout.decode(raw);
  return BigInt(decoded.amount.toString());
}

async function getTokenBalanceOrZero(ata: PublicKey): Promise<bigint> {
  try {
    const bal = await connection.getTokenAccountBalance(ata, "confirmed");
    return BigInt(bal.value.amount);
  } catch {
    return 0n;
  }
}

async function ensureAta(mint: PublicKey): Promise<PublicKey> {
  const ata = getAssociatedTokenAddressSync(mint, user);
  const info = await connection.getAccountInfo(ata, "confirmed");
  if (info) return ata;

  console.log(`Creating missing ATA ${ata.toBase58()} for mint ${mint.toBase58()}`);

  const ix = createAssociatedTokenAccountInstruction(
    user,
    ata,
    user,
    mint,
    TOKEN_PROGRAM_ID,
    ASSOCIATED_TOKEN_PROGRAM_ID
  );

  const latest = await connection.getLatestBlockhash("confirmed");
  const msg = new TransactionMessage({
    payerKey: user,
    recentBlockhash: latest.blockhash,
    instructions: [ix]
  }).compileToV0Message([]);

  const tx = new VersionedTransaction(msg);
  tx.sign([payer]);

  const sig = await connection.sendRawTransaction(tx.serialize(), {
    skipPreflight: false,
    maxRetries: env.MAX_SEND_RETRIES,
    preflightCommitment: env.CONFIRMATION_COMMITMENT
  });

  await connection.confirmTransaction({
    signature: sig,
    blockhash: latest.blockhash,
    lastValidBlockHeight: latest.lastValidBlockHeight
  }, env.CONFIRMATION_COMMITMENT);

  console.log(`ATA created: ${sig}`);
  return ata;
}

async function simulateWithUsdcReturn(tx: VersionedTransaction, usdcAta: PublicKey): Promise<{
  err: unknown;
  unitsConsumed?: number;
  postUsdcBalance: bigint | null;
  logsTail?: string[];
}> {
  const txBase64 = Buffer.from(tx.serialize()).toString("base64");

  const raw = await fetch(connection.rpcEndpoint, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: 1,
      method: "simulateTransaction",
      params: [
        txBase64,
        {
          encoding: "base64",
          sigVerify: true,
          replaceRecentBlockhash: false,
          commitment: "confirmed",
          accounts: {
            encoding: "base64",
            addresses: [usdcAta.toBase58()]
          }
        }
      ]
    })
  });

  const body = await raw.text();
  if (!raw.ok) throw new Error(`simulateTransaction HTTP ${raw.status}: ${body.slice(0, 300)}`);

  const parsed = JSON.parse(body);
  const value = parsed.result?.value;
  const account = value?.accounts?.[0];

  return {
    err: value?.err ?? parsed.error ?? null,
    unitsConsumed: value?.unitsConsumed,
    postUsdcBalance: account?.data?.[0] ? decodeTokenAmountFromBase64(account.data[0]) : null,
    logsTail: value?.logs?.slice(-40)
  };
}

async function scanOnce(): Promise<any[]> {
  const hits: any[] = [];

  for (const target of targets) {
    for (const amount of sizes) {
      try {
        const checkedAtMs = Date.now();

        const q1 = await quote(USDC_MINT, target, amount);
        const out1 = BigInt(q1.outAmount);

        const q2 = await quote(target, USDC_MINT, out1);
        const out2 = BigInt(q2.outAmount);

        const gross = out2 - amount;
        const flashFee = amount * env.FLASH_LOAN_FEE_BPS / 10000n;
        const net = gross - flashFee - env.PRIORITY_FEE_USDC_ATOMS;

        const hit = {
          target: target.toBase58(),
          amount,
          amountUsdc: fmtUsdc(amount),
          forwardOut: out1,
          reverseOut: out2,
          gross,
          grossUsdc: fmtUsdc(gross),
          flashFee,
          flashFeeUsdc: fmtUsdc(flashFee),
          priorityFeeUsdc: fmtUsdc(env.PRIORITY_FEE_USDC_ATOMS),
          net,
          netUsdc: fmtUsdc(net),
          q1,
          q2,
          checkedAtMs,
          checkedAt: new Date(checkedAtMs).toISOString()
        };

        const ok = net >= env.MIN_NET_PROFIT_USDC_ATOMS;
        console.log(`${ok ? "HIT" : "MISS"} target=${target.toBase58().slice(0, 6)} size=${fmtUsdc(amount)} net=${fmtUsdc(net)}`);

        if (ok) hits.push(hit);
      } catch (e: any) {
        console.log(`ERR target=${target.toBase58().slice(0, 6)} ${fmtUsdc(amount)} ${e.message}`);
      }
    }
  }

  hits.sort((a, b) => Number(b.net - a.net));
  return hits;
}

async function buildSimSendHit(hit: any, liveSend: boolean): Promise<void> {
  const age = Date.now() - hit.checkedAtMs;
  if (age > env.MAX_QUOTE_AGE_MS) {
    throw new Error(`Quote too old before build: ${age}ms > ${env.MAX_QUOTE_AGE_MS}ms`);
  }

  const { market, reserve } = await loadKamino();

  const userUsdcAta = await ensureAta(USDC_MINT);
  await ensureAta(new PublicKey(hit.target));

  const preBalance = await getTokenBalanceOrZero(userUsdcAta);

  const computeIxs = [
    ComputeBudgetProgram.setComputeUnitLimit({ units: env.COMPUTE_UNIT_LIMIT }),
    ComputeBudgetProgram.setComputeUnitPrice({ microLamports: env.COMPUTE_UNIT_PRICE_MICRO_LAMPORTS })
  ];

  const borrowIxIndex = computeIxs.length;
  const authority = await market.getLendingMarketAuthority();

  const flash = getFlashLoanInstructions({
    borrowIxIndex,
    userTransferAuthority: user,
    lendingMarketAuthority: authority,
    lendingMarketAddress: market.getAddress(),
    reserve,
    amountLamports: hit.amount,
    destinationAta: userUsdcAta,
    referrerAccount: null,
    referrerTokenState: null,
    programId: KAMINO_PROGRAM_ID
  } as never) as any;

  const borrowIx = normalizeIx(flash.flashBorrowIx);
  const repayIx = normalizeIx(flash.flashRepayIx);

  const leg1 = await buildJupiterInstructions(hit.q1);
  const leg2 = await buildJupiterInstructions(hit.q2);

  const alts = await loadAlts([...leg1.altAddresses, ...leg2.altAddresses]);

  const instructions = [
    ...computeIxs,
    borrowIx,
    ...leg1.ixs,
    ...leg2.ixs,
    repayIx
  ];

  if (instructions[borrowIxIndex] !== borrowIx) {
    throw new Error("borrowIxIndex mismatch");
  }

  const latest = await connection.getLatestBlockhash("confirmed");

  const msg = new TransactionMessage({
    payerKey: user,
    recentBlockhash: latest.blockhash,
    instructions
  }).compileToV0Message(alts);

  const tx = new VersionedTransaction(msg);
  tx.sign([payer]);

  const txBytes = tx.serialize().length;
  if (txBytes > env.MAX_TX_BYTES) throw new Error(`Transaction too large: ${txBytes} > ${env.MAX_TX_BYTES}`);

  const sim = await simulateWithUsdcReturn(tx, userUsdcAta);
  const simulatedProfit = sim.postUsdcBalance === null ? null : sim.postUsdcBalance - preBalance;

  const routeHash = sha256({
    target: hit.target,
    amount: hit.amount,
    q1Route: hit.q1.routePlan,
    q2Route: hit.q2.routePlan,
    checkedAt: hit.checkedAt
  });

  const simOk =
    sim.err === null &&
    simulatedProfit !== null &&
    simulatedProfit >= env.MIN_SIMULATED_PROFIT_USDC_ATOMS;

  const proof = {
    proofKind: "live_kamino_jupiter_flash_arb_v1",
    createdAt: new Date().toISOString(),
    routeHash,
    liveSendRequested: liveSend,
    user: user.toBase58(),
    kaminoProgram: KAMINO_PROGRAM_ID.toBase58(),
    market: marketPk.toBase58(),
    reserve: reservePk.toBase58(),
    target: hit.target,
    quoteAgeMsAtSimulation: Date.now() - hit.checkedAtMs,
    quotedAmountUsdc: hit.amountUsdc,
    quotedGrossUsdc: hit.grossUsdc,
    quotedNetUsdc: hit.netUsdc,
    tx: {
      borrowIxIndex,
      instructionCount: instructions.length,
      txBytes,
      maxTxBytes: env.MAX_TX_BYTES,
      altCount: alts.length
    },
    simulation: {
      ok: simOk,
      err: sim.err,
      unitsConsumed: sim.unitsConsumed,
      preUsdcBalance: preBalance,
      postUsdcBalance: sim.postUsdcBalance,
      simulatedProfit,
      simulatedProfitUsdc: simulatedProfit === null ? null : fmtUsdc(simulatedProfit),
      logsTail: sim.logsTail
    }
  };

  mkdirSync(env.PROOF_DIR, { recursive: true });
  const proofFile = `${env.PROOF_DIR}/${proof.createdAt.replace(/[:.]/g, "-")}_${routeHash.slice(0, 12)}.json`;
  writeFileSync(proofFile, json(proof));

  console.log("SIM_PROOF", json({
    proofFile,
    ok: simOk,
    quotedNetUsdc: hit.netUsdc,
    simulatedProfitUsdc: proof.simulation.simulatedProfitUsdc,
    txBytes,
    unitsConsumed: sim.unitsConsumed,
    err: sim.err
  }));

  if (!liveSend) return;

  if (!env.LIVE_SEND_ENABLED) {
    throw new Error("LIVE_SEND_ENABLED=false. Set true only when you accept real mainnet risk.");
  }

  if (!simOk) {
    throw new Error("Simulation/profit gate failed. Refusing live send.");
  }

  const quoteAge = Date.now() - hit.checkedAtMs;
  if (quoteAge > env.MAX_QUOTE_AGE_MS) {
    throw new Error(`Quote too old before send: ${quoteAge}ms > ${env.MAX_QUOTE_AGE_MS}ms`);
  }

  const approved = await askExecute({
    warning: "REAL MAINNET FLASH ARB",
    routeHash,
    user: user.toBase58(),
    target: hit.target,
    borrowAmountUsdc: hit.amountUsdc,
    quotedNetUsdc: hit.netUsdc,
    simulatedProfitUsdc: proof.simulation.simulatedProfitUsdc,
    quoteAgeMs: quoteAge,
    risk: "You can lose network/priority fees. Profit is not guaranteed. No on-chain profit assertion is included."
  });

  if (!approved) {
    console.log("Cancelled.");
    return;
  }

  const sig = await connection.sendRawTransaction(tx.serialize(), {
    skipPreflight: false,
    maxRetries: env.MAX_SEND_RETRIES,
    preflightCommitment: env.CONFIRMATION_COMMITMENT
  });

  console.log("SENT", json({
    signature: sig,
    routeHash,
    explorer: `https://solscan.io/tx/${sig}` 
  }));

  const conf = await connection.confirmTransaction({
    signature: sig,
    blockhash: latest.blockhash,
    lastValidBlockHeight: latest.lastValidBlockHeight
  }, env.CONFIRMATION_COMMITMENT);

  if (conf.value.err) {
    throw new Error(`Transaction failed: ${JSON.stringify(conf.value.err)}`);
  }

  const finalBalance = await getTokenBalanceOrZero(userUsdcAta);

  console.log("CONFIRMED", json({
    signature: sig,
    routeHash,
    finalUsdcBalanceAtoms: finalBalance,
    finalUsdcBalanceUsdc: fmtUsdc(finalBalance),
    explorer: `https://solscan.io/tx/${sig}` 
  }));
}

async function main(): Promise<void> {
  const mode = process.argv[2] ?? "once";

  console.log(json({
    mode,
    user: user.toBase58(),
    rpc: env.SOLANA_RPC_URL,
    kaminoProgram: KAMINO_PROGRAM_ID.toBase58(),
    market: marketPk.toBase58(),
    reserve: reservePk.toBase58(),
    liveSendEnabled: env.LIVE_SEND_ENABLED
  }));

  const solBalance = await connection.getBalance(user, "confirmed");
  console.log(json({ solLamports: solBalance, sol: solBalance / 1_000_000_000 }));

  if (mode === "once" || mode === "send") {
    const hits = await scanOnce();
    if (!hits.length) {
      console.log("No positive route found right now.");
      return;
    }
    await buildSimSendHit(hits[0], mode === "send");
    return;
  }

  if (mode === "scan") {
    while (true) {
      const hits = await scanOnce();
      if (hits[0]) {
        try {
          await buildSimSendHit(hits[0], false);
        } catch (e: any) {
          console.error("SIM_HIT_FAILED", e.message);
        }
      }
      await new Promise((r) => setTimeout(r, env.SCAN_INTERVAL_MS));
    }
  }

  throw new Error("Use: npm run once OR npm run scan OR npm run send");
}

main().catch((e) => {
  console.error("FATAL", e?.message ?? e);
  process.exit(1);
});
