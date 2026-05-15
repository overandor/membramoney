import os
// multi-dex-profitability-tracker.plug-and-play.ts
//
// Plug-and-play profitability tracker focused on VERIFIED public endpoints.
// Current live support:
//   - Orderly ecosystem (official public REST API)
//   - Builder-level filtering for Orderly-powered DEXs like Raydium/Kodiak via broker_id
//
// Why this version is safer:
//   - uses documented Orderly public endpoints only
//   - no fake endpoint assumptions
//   - no fake auth placeholders
//   - graceful retry / timeout / fallback behavior
//   - produces a report even if some builders fail
//
// Install:
//   npm i axios dotenv
//
// Run:
//   npx ts-node multi-dex-profitability-tracker.plug-and-play.ts
//
// Optional .env:
//   ORDERLY_BASE_URL=https://api.orderly.org
//   ORDERLY_BROKERS=raydium,kodiak
//   ORDERLY_BUILDER_LABELS=raydium:Raydium Perps,kodiak:Kodiak Perps
//   ORDERLY_TAKER_FEE_BPS=3
//   ORDERLY_MAKER_FEE_BPS=0
//   ORDERLY_AVG_TX_COST_USD=0.01
//   REQUEST_TIMEOUT_MS=12000
//   REQUEST_RETRIES=2
//   WRITE_JSON=true
//   WRITE_CSV=true
//
// Notes:
//   - Profitability here means "fee capture / market activity profile", not protocol net income.
//   - Builder-specific fees above Orderly base fees are not public on every venue, so we default
//     to the documented Orderly base fee unless you override via env.
//   - If ORDERLY_BROKERS is empty, the script aggregates the full Orderly ecosystem.
//
// TSConfig recommendation (if needed):
// {
//   "compilerOptions": {
//     "target": "ES2020",
//     "module": "commonjs",
//     "moduleResolution": "node",
//     "esModuleInterop": true,
//     "strict": true,
//     "skipLibCheck": true
//   }
// }

import 'dotenv/config';
import axios, { AxiosError, AxiosInstance } from 'axios';
import * as fs from 'fs';
import * as path from 'path';

type Chain = 'solana' | 'berachain' | 'ethereum-l2' | 'omnichain';

interface ProfitabilityMetrics {
  dexName: string;
  venueType: 'builder' | 'ecosystem';
  chain: Chain;
  timestamp: number;

  // Market metrics
  openInterest: number;        // USD
  tradingVolume24h: number;    // USD
  fundingRate: number;         // decimal (e.g. 0.0003 = 3 bps)
  marketCount: number;

  // Revenue metrics
  feeRevenue24h: number;       // USD
  makerFee: number;            // decimal
  takerFee: number;            // decimal

  // Position metrics
  longOpenInterest: number;    // USD
  shortOpenInterest: number;   // USD
  longShortRatio: number;

  // Protocol / venue metrics
  connectedUsers: number;
  tvl: number | null;
  annualizedRevenue: number;

  // Costs
  avgTxCost: number;           // USD

  // Metadata
  brokerId?: string;
  notes?: string[];
}

interface OrderlyFuturesMarketRow {
  symbol: string;
  index_price?: number;
  mark_price?: number;
  sum_unitary_funding?: number;
  est_funding_rate?: number;
  last_funding_rate?: number;
  next_funding_time?: number;
  open_interest?: number;
  '24h_open'?: number;
  '24h_close'?: number;
  '24h_high'?: number;
  '24h_low'?: number;
  '24h_amount'?: number;
  '24h_volume'?: number;
}

interface OrderlyOpenInterestRow {
  symbol: string;
  long_oi?: number;
  short_oi?: number;
}

interface OrderlyBrokerStatsRow {
  connected_user?: string | number;
}

interface OrderlyResponse<T> {
  success: boolean;
  data?: {
    rows?: T[];
    [key: string]: any;
  };
  timestamp?: number;
}

function envNum(name: string, fallback: number): number {
  const raw = process.env[name];
  if (raw == null || raw.trim() === '') return fallback;
  const n = Number(raw);
  return Number.isFinite(n) ? n : fallback;
}

function envBool(name: string, fallback: boolean): boolean {
  const raw = process.env[name];
  if (raw == null || raw.trim() === '') return fallback;
  return ['1', 'true', 'yes', 'y', 'on'].includes(raw.toLowerCase());
}

function safeNumber(value: unknown, fallback = 0): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function formatUsd(n: number): string {
  if (!Number.isFinite(n)) return '$0.00';
  if (Math.abs(n) >= 1_000_000_000) return `$${(n / 1_000_000_000).toFixed(2)}B`;
  if (Math.abs(n) >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  if (Math.abs(n) >= 1_000) return `$${(n / 1_000).toFixed(2)}K`;
  return `$${n.toFixed(2)}`;
}

function pct(decimalValue: number, digits = 3): string {
  return `${(decimalValue * 100).toFixed(digits)}%`;
}

function nowIso(): string {
  return new Date().toISOString();
}

function parseBrokerLabels(): Map<string, string> {
  const raw = process.env.ORDERLY_BUILDER_LABELS?.trim();
  const map = new Map<string, string>();
  if (!raw) return map;

  for (const pair of raw.split(',')) {
    const [k, v] = pair.split(':').map(s => s.trim());
    if (k && v) map.set(k, v);
  }
  return map;
}

function parseBrokerList(): string[] {
  const raw = process.env.ORDERLY_BROKERS?.trim();
  if (!raw) return [];
  return raw
    .split(',')
    .map(s => s.trim())
    .filter(Boolean);
}

class HttpClient {
  private readonly client: AxiosInstance;
  private readonly retries: number;
  private readonly timeoutMs: number;

  constructor(baseURL: string, timeoutMs: number, retries: number) {
    this.client = axios.create({
      baseURL,
      timeout: timeoutMs,
      headers: {
        'Content-Type': 'application/json',
        'User-Agent': 'multi-dex-profitability-tracker/plug-and-play'
      }
    });
    this.retries = retries;
    this.timeoutMs = timeoutMs;
  }

  async get<T>(url: string, params?: Record<string, any>): Promise<T> {
    let lastErr: unknown;

    for (let attempt = 0; attempt <= this.retries; attempt++) {
      try {
        const res = await this.client.get<T>(url, { params });
        return res.data;
      } catch (err) {
        lastErr = err;
        const isLast = attempt === this.retries;
        const status = (err as AxiosError)?.response?.status;
        const retryable =
          !status || status >= 500 || status === 408 || status === 429;

        if (isLast || !retryable) break;

        const backoffMs = 400 * Math.pow(2, attempt);
        await new Promise(r => setTimeout(r, backoffMs));
      }
    }

    throw lastErr;
  }
}

class OrderlyAdapter {
  private readonly http: HttpClient;
  private readonly makerFee: number;
  private readonly takerFee: number;
  private readonly avgTxCost: number;
  private readonly brokerLabels: Map<string, string>;

  constructor() {
    const baseURL = process.env.ORDERLY_BASE_URL || 'https://api.orderly.org';
    const timeoutMs = envNum('REQUEST_TIMEOUT_MS', 12_000);
    const retries = envNum('REQUEST_RETRIES', 2);

    this.http = new HttpClient(baseURL, timeoutMs, retries);

    // Orderly base fee model from official docs:
    // maker 0 bps, taker 3 bps by default unless builder customizes above that.
    this.makerFee = envNum('ORDERLY_MAKER_FEE_BPS', 0) / 10_000;
    this.takerFee = envNum('ORDERLY_TAKER_FEE_BPS', 3) / 10_000;
    this.avgTxCost = envNum('ORDERLY_AVG_TX_COST_USD', 0.01);
    this.brokerLabels = parseBrokerLabels();
  }

  async fetchAll(brokerIds: string[]): Promise<ProfitabilityMetrics[]> {
    if (brokerIds.length === 0) {
      const ecosystem = await this.fetchOne(undefined);
      return ecosystem ? [ecosystem] : [];
    }

    const results = await Promise.allSettled(
      brokerIds.map(brokerId => this.fetchOne(brokerId))
    );

    const metrics: ProfitabilityMetrics[] = [];
    for (const r of results) {
      if (r.status === 'fulfilled' && r.value) {
        metrics.push(r.value);
      }
    }
    return metrics;
  }

  private async fetchOne(brokerId?: string): Promise<ProfitabilityMetrics | null> {
    const futuresParams = brokerId ? { broker_id: brokerId } : undefined;
    const oiParams = brokerId ? { broker_id: brokerId } : undefined;
    const statsParams = brokerId ? { broker_id: brokerId } : undefined;

    const [futuresMarketRes, oiRes, brokerStatsRes] = await Promise.allSettled([
      this.http.get<OrderlyResponse<OrderlyFuturesMarketRow>>('/v1/public/futures_market', futuresParams),
      this.http.get<OrderlyResponse<OrderlyOpenInterestRow>>('/v1/public/market_info/traders_open_interests', oiParams),
      this.http.get<OrderlyResponse<OrderlyBrokerStatsRow>>('/v1/public/broker/stats', statsParams),
    ]);

    const notes: string[] = [];
    const futuresRows =
      futuresMarketRes.status === 'fulfilled'
        ? futuresMarketRes.value?.data?.rows || []
        : [];

    const oiRows =
      oiRes.status === 'fulfilled'
        ? oiRes.value?.data?.rows || []
        : [];

    const brokerRows =
      brokerStatsRes.status === 'fulfilled'
        ? brokerStatsRes.value?.data?.rows || []
        : [];

    if (futuresMarketRes.status === 'rejected') {
      notes.push(`futures_market fetch failed: ${stringifyErr(futuresMarketRes.reason)}`);
    }
    if (oiRes.status === 'rejected') {
      notes.push(`traders_open_interests fetch failed: ${stringifyErr(oiRes.reason)}`);
    }
    if (brokerStatsRes.status === 'rejected') {
      notes.push(`broker stats fetch failed: ${stringifyErr(brokerStatsRes.reason)}`);
    }

    if (futuresRows.length === 0 && oiRows.length === 0) {
      return null;
    }

    const oiMap = new Map<string, OrderlyOpenInterestRow>();
    for (const row of oiRows) {
      oiMap.set(row.symbol, row);
    }

    let tradingVolume24h = 0;
    let openInterest = 0;
    let fundingAccumulator = 0;
    let fundingCount = 0;
    let longOpenInterest = 0;
    let shortOpenInterest = 0;

    const seenSymbols = new Set<string>();

    for (const row of futuresRows) {
      const symbol = row.symbol;
      seenSymbols.add(symbol);

      tradingVolume24h += safeNumber(row['24h_volume']);
      openInterest += safeNumber(row.open_interest);

      const fundingRate = safeNumber(
        row.last_funding_rate ?? row.est_funding_rate,
        NaN
      );
      if (Number.isFinite(fundingRate)) {
        fundingAccumulator += fundingRate;
        fundingCount += 1;
      }

      const oi = oiMap.get(symbol);
      if (oi) {
        longOpenInterest += safeNumber(oi.long_oi);
        shortOpenInterest += safeNumber(oi.short_oi);
      }
    }

    // If futures endpoint had no rows but OI did, still count those symbols.
    if (futuresRows.length === 0 && oiRows.length > 0) {
      for (const row of oiRows) {
        seenSymbols.add(row.symbol);
        longOpenInterest += safeNumber(row.long_oi);
        shortOpenInterest += safeNumber(row.short_oi);
      }
      openInterest = longOpenInterest + shortOpenInterest;
    }

    const connectedUsers =
      brokerRows.length > 0 ? safeNumber(brokerRows[0]?.connected_user) : 0;

    const fundingRate = fundingCount > 0 ? fundingAccumulator / fundingCount : 0;
    const feeRevenue24h = tradingVolume24h * this.takerFee;
    const annualizedRevenue = feeRevenue24h * 365;
    const longShortRatio = longOpenInterest / Math.max(shortOpenInterest, 1);

    const dexName = brokerId
      ? this.brokerLabels.get(brokerId) || `Orderly Builder: ${brokerId}`
      : 'Orderly Ecosystem';

    return {
      dexName,
      venueType: brokerId ? 'builder' : 'ecosystem',
      chain: 'omnichain',
      timestamp: Date.now(),
      openInterest,
      tradingVolume24h,
      fundingRate,
      marketCount: seenSymbols.size,
      feeRevenue24h,
      makerFee: this.makerFee,
      takerFee: this.takerFee,
      longOpenInterest,
      shortOpenInterest,
      longShortRatio,
      connectedUsers,
      tvl: null,
      annualizedRevenue,
      avgTxCost: this.avgTxCost,
      brokerId,
      notes
    };
  }
}

function stringifyErr(err: unknown): string {
  if (err instanceof Error) return err.message;
  try {
    return JSON.stringify(err);
  } catch {
    return String(err);
  }
}

class MultiDEXProfitabilityTracker {
  private readonly orderlyAdapter: OrderlyAdapter;
  private readonly brokerIds: string[];

  constructor() {
    this.orderlyAdapter = new OrderlyAdapter();
    this.brokerIds = parseBrokerList();
  }

  async aggregateProfitabilityData(): Promise<ProfitabilityMetrics[]> {
    console.log('\n🚀 Starting plug-and-play profitability aggregation...\n');

    const metrics = await this.orderlyAdapter.fetchAll(this.brokerIds);

    if (metrics.length === 0) {
      throw new Error('No venue metrics could be fetched.');
    }

    return metrics;
  }

  calculateProfitabilityRankings(metrics: ProfitabilityMetrics[]) {
    return metrics
      .map(m => ({
        dex: m.dexName,
        brokerId: m.brokerId ?? '',
        dailyRevenue: m.feeRevenue24h,
        annualRevenue: m.annualizedRevenue,
        revenuePerOIRatio: m.feeRevenue24h / Math.max(m.openInterest, 1),
        volumeToOIRatio: m.tradingVolume24h / Math.max(m.openInterest, 1),
        feeRate: m.takerFee,
        avgTxCost: m.avgTxCost,
        efficiency: m.feeRevenue24h / Math.max(m.tradingVolume24h, 1),
        marketCount: m.marketCount,
        connectedUsers: m.connectedUsers,
        fundingRate: m.fundingRate,
        longShortRatio: m.longShortRatio,
      }))
      .sort((a, b) => b.dailyRevenue - a.dailyRevenue);
  }

  generateReport(metrics: ProfitabilityMetrics[]): string {
    const rankings = this.calculateProfitabilityRankings(metrics);

    let report = '\n' + '='.repeat(88) + '\n';
    report += '📈 PLUG-AND-PLAY PERP DEX PROFITABILITY REPORT\n';
    report += '='.repeat(88) + '\n\n';

    report += `TIMESTAMP: ${nowIso()}\n`;
    report += `DATA SOURCE: Official Orderly public REST API\n`;
    report += `BROKER FILTER: ${this.brokerIds.length ? this.brokerIds.join(', ') : 'none (ecosystem-wide)'}\n\n`;

    report += 'PROFITABILITY RANKINGS\n';
    report += '-'.repeat(88) + '\n';

    rankings.forEach((r, i) => {
      report += `${i + 1}. ${r.dex}${r.brokerId ? ` [${r.brokerId}]` : ''}\n`;
      report += `   ├─ Daily Revenue Estimate: ${formatUsd(r.dailyRevenue)}\n`;
      report += `   ├─ Annual Revenue Estimate: ${formatUsd(r.annualRevenue)}\n`;
      report += `   ├─ Revenue / OI Ratio: ${(r.revenuePerOIRatio * 100).toFixed(4)}%\n`;
      report += `   ├─ Volume / OI Ratio: ${r.volumeToOIRatio.toFixed(2)}x\n`;
      report += `   ├─ Taker Fee Assumption: ${pct(r.feeRate, 3)}\n`;
      report += `   ├─ Avg Funding Rate: ${pct(r.fundingRate, 4)}\n`;
      report += `   ├─ Long / Short OI Ratio: ${r.longShortRatio.toFixed(3)}x\n`;
      report += `   ├─ Markets: ${r.marketCount}\n`;
      report += `   ├─ Connected Users: ${Math.round(r.connectedUsers)}\n`;
      report += `   └─ Avg Tx Cost: ${formatUsd(r.avgTxCost)}\n\n`;
    });

    report += 'MARKET SUMMARY\n';
    report += '-'.repeat(88) + '\n';

    const totalDailyRev = metrics.reduce((sum, m) => sum + m.feeRevenue24h, 0);
    const totalAnnualRev = metrics.reduce((sum, m) => sum + m.annualizedRevenue, 0);
    const totalOI = metrics.reduce((sum, m) => sum + m.openInterest, 0);
    const totalVolume = metrics.reduce((sum, m) => sum + m.tradingVolume24h, 0);
    const totalLongOI = metrics.reduce((sum, m) => sum + m.longOpenInterest, 0);
    const totalShortOI = metrics.reduce((sum, m) => sum + m.shortOpenInterest, 0);
    const avgFeeRate =
      metrics.reduce((sum, m) => sum + m.takerFee, 0) / Math.max(metrics.length, 1);

    report += `Total Daily Revenue Estimate: ${formatUsd(totalDailyRev)}\n`;
    report += `Total Annual Revenue Estimate: ${formatUsd(totalAnnualRev)}\n`;
    report += `Total Open Interest: ${formatUsd(totalOI)}\n`;
    report += `Total 24h Volume: ${formatUsd(totalVolume)}\n`;
    report += `Total Long OI: ${formatUsd(totalLongOI)}\n`;
    report += `Total Short OI: ${formatUsd(totalShortOI)}\n`;
    report += `Aggregate Long/Short Ratio: ${(totalLongOI / Math.max(totalShortOI, 1)).toFixed(3)}x\n`;
    report += `Average Taker Fee Used: ${pct(avgFeeRate, 3)}\n`;

    report += '\nDETAILS / WARNINGS\n';
    report += '-'.repeat(88) + '\n';
    for (const m of metrics) {
      report += `${m.dexName}:\n`;
      if (!m.notes || m.notes.length === 0) {
        report += '  - no warnings\n';
      } else {
        for (const note of m.notes) {
          report += `  - ${note}\n`;
        }
      }
    }

    report += '\n' + '='.repeat(88) + '\n';
    return report;
  }

  writeOutputs(metrics: ProfitabilityMetrics[]) {
    const stamp = new Date().toISOString().replace(/[:.]/g, '-');
    const outDir = path.resolve(process.cwd(), 'out');
    fs.mkdirSync(outDir, { recursive: true });

    if (envBool('WRITE_JSON', true)) {
      const jsonPath = path.join(outDir, `profitability-report-${stamp}.json`);
      fs.writeFileSync(jsonPath, JSON.stringify(metrics, null, 2), 'utf8');
      console.log(`✅ JSON written: ${jsonPath}`);
    }

    if (envBool('WRITE_CSV', true)) {
      const csvPath = path.join(outDir, `profitability-report-${stamp}.csv`);
      const header = [
        'dexName',
        'venueType',
        'chain',
        'timestamp',
        'brokerId',
        'openInterest',
        'tradingVolume24h',
        'fundingRate',
        'marketCount',
        'feeRevenue24h',
        'makerFee',
        'takerFee',
        'longOpenInterest',
        'shortOpenInterest',
        'longShortRatio',
        'connectedUsers',
        'tvl',
        'annualizedRevenue',
        'avgTxCost',
        'notes',
      ];

      const rows = metrics.map(m => [
        escapeCsv(m.dexName),
        escapeCsv(m.venueType),
        escapeCsv(m.chain),
        String(m.timestamp),
        escapeCsv(m.brokerId ?? ''),
        String(m.openInterest),
        String(m.tradingVolume24h),
        String(m.fundingRate),
        String(m.marketCount),
        String(m.feeRevenue24h),
        String(m.makerFee),
        String(m.takerFee),
        String(m.longOpenInterest),
        String(m.shortOpenInterest),
        String(m.longShortRatio),
        String(m.connectedUsers),
        m.tvl == null ? '' : String(m.tvl),
        String(m.annualizedRevenue),
        String(m.avgTxCost),
        escapeCsv((m.notes ?? []).join(' | ')),
      ]);

      const csv = [header.join(','), ...rows.map(r => r.join(','))].join('\n');
      fs.writeFileSync(csvPath, csv, 'utf8');
      console.log(`✅ CSV written: ${csvPath}`);
    }
  }
}

function escapeCsv(value: string): string {
  if (value.includes('"') || value.includes(',') || value.includes('\n')) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}

async function main() {
  console.log('Multi-DEX Profitability Tracker');
  console.log('Plug-and-play version using verified public endpoints only\n');

  const tracker = new MultiDEXProfitabilityTracker();

  try {
    const metrics = await tracker.aggregateProfitabilityData();
    const report = tracker.generateReport(metrics);
    console.log(report);
    tracker.writeOutputs(metrics);
  } catch (error) {
    console.error('❌ Fatal error in main execution:', stringifyErr(error));
    process.exitCode = 1;
  }
}

if (require.main === module) {
  main().catch(err => {
    console.error('❌ Unhandled fatal error:', stringifyErr(err));
    process.exitCode = 1;
  });
}

export {
  MultiDEXProfitabilityTracker,
  OrderlyAdapter,
  ProfitabilityMetrics,
};