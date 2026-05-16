const { useState, useEffect, useRef, useMemo } = React;

// ============== CONSTANTS / UTILS ==============
const API_BASE = window.COINPACK_API_BASE || '';
const SATS_PER_BTC = 100_000_000;
const NOTE_DENOMS = [
  { label: '10 BTC', sats: 10 * SATS_PER_BTC, tone: 'Institutional' },
  { label: '50 BTC', sats: 50 * SATS_PER_BTC, tone: 'Treasury' },
  { label: '100 BTC', sats: 100 * SATS_PER_BTC, tone: 'Reserve' },
  { label: '500 BTC', sats: 500 * SATS_PER_BTC, tone: 'Vault' },
];

const shorten = (addr, n = 6) => addr ? `${addr.slice(0, n)}...${addr.slice(-n)}` : '';
const nowSeconds = () => Math.floor(Date.now() / 1000);
const randomHex = (bytes = 24) => {
  const arr = new Uint8Array(bytes);
  crypto.getRandomValues(arr);
  return Array.from(arr).map(b => b.toString(16).padStart(2, '0')).join('');
};
const generateClaimId = () => randomHex(32);
const formatDenom = sats => `${(Number(sats || 0) / SATS_PER_BTC).toLocaleString(undefined, { maximumFractionDigits: 8 })} BTC`;
const formatSats = sats => `${Number(sats || 0).toLocaleString()} sats`;
const formatDate = value => value ? new Date(value).toLocaleString() : '—';
const toBase64 = bytes => btoa(String.fromCharCode(...new Uint8Array(bytes)));
const readError = async res => {
  try {
    const data = await res.json();
    return data?.detail?.message || data?.detail || data?.message || data?.error || `HTTP ${res.status}`;
  } catch (_) {
    return `HTTP ${res.status}`;
  }
};

function buildWalletMessage({ method, path, nonce }) {
  return [
    'CoinPack signed API request',
    `method=${method.toUpperCase()}`,
    `path=${path}`,
    `timestamp=${nowSeconds()}`,
    `nonce=${nonce}`,
    `origin=${window.location.origin}`,
  ].join('\n');
}

async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

async function signedApiFetch(wallet, path, { method = 'POST', body } = {}) {
  if (!wallet.connected || !wallet.publicKey || !wallet.provider?.signMessage) {
    throw new Error('Wallet must support signMessage. Use Phantom or Solflare.');
  }
  const nonce = randomHex(24);
  const message = buildWalletMessage({ method, path, nonce });
  const encoded = new TextEncoder().encode(message);
  const signed = await wallet.provider.signMessage(encoded, 'utf8');
  const signatureBytes = signed.signature || signed;

  return apiFetch(path, {
    method,
    headers: {
      'X-Wallet-Address': wallet.publicKey,
      'X-Wallet-Message': message,
      'X-Wallet-Signature': toBase64(signatureBytes),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
}

// ============== WALLET HOOK ==============
function useWallet() {
  const [connected, setConnected] = useState(false);
  const [publicKey, setPublicKey] = useState(null);
  const [provider, setProvider] = useState(null);

  useEffect(() => {
    const phantom = window.phantom?.solana;
    const solflare = window.solflare;
    setProvider(phantom?.isPhantom ? phantom : solflare?.isSolflare ? solflare : null);
  }, []);

  const connect = async () => {
    if (!provider) {
      alert('Install Phantom or Solflare wallet.');
      return;
    }
    const resp = await provider.connect();
    setPublicKey(resp.publicKey.toString());
    setConnected(true);
  };

  const disconnect = async () => {
    if (provider?.disconnect) await provider.disconnect();
    setPublicKey(null);
    setConnected(false);
  };

  useEffect(() => {
    if (!provider) return;
    const onConnect = pk => { setPublicKey(pk.toString()); setConnected(true); };
    const onDisconnect = () => { setPublicKey(null); setConnected(false); };
    provider.on?.('connect', onConnect);
    provider.on?.('disconnect', onDisconnect);
    if (provider.isConnected && provider.publicKey) onConnect(provider.publicKey);
  }, [provider]);

  return { connected, publicKey, connect, disconnect, provider };
}

// ============== SHARED UI ==============
function StatusPill({ children, tone = 'neutral' }) {
  const cls = tone === 'good' ? 'bg-green-500/20 text-green-400' : tone === 'bad' ? 'bg-red-500/20 text-red-400' : 'bg-white/10 text-gray-400';
  return <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${cls}`}>{children}</span>;
}

function EmptyState({ title, body, action }) {
  return (
    <div className="card rounded-xl p-10 text-center">
      <div className="w-14 h-14 rounded-2xl btn-primary mx-auto mb-4 flex items-center justify-center font-black text-black">₿</div>
      <h3 className="text-lg font-bold mb-1">{title}</h3>
      <p className="text-sm text-gray-400 max-w-md mx-auto">{body}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

function RiskBanner() {
  const [dismissed, setDismissed] = useState(() => localStorage.getItem('coinpack-risk-dismissed') === '1');
  if (dismissed) return null;
  return (
    <div className="fixed bottom-3 left-3 right-3 z-50 card rounded-xl px-4 py-3 max-w-4xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-center gap-3 justify-between">
        <p className="text-xs text-gray-300">
          <strong className="text-red-400">Risk warning:</strong> BTC-backed notes are custodial claims, not native Bitcoin. Verify reserves, signatures, and redemption status before use.
        </p>
        <button onClick={() => { localStorage.setItem('coinpack-risk-dismissed', '1'); setDismissed(true); }} className="px-3 py-2 bg-white/10 rounded-lg text-xs">Acknowledge</button>
      </div>
    </div>
  );
}

function Header({ wallet }) {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-black/80 backdrop-blur-md border-b border-white/10">
      <div className="max-w-7xl mx-auto px-4 min-h-16 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl btn-primary flex items-center justify-center"><span className="text-black font-black">₿</span></div>
          <div>
            <h1 className="font-black text-lg tracking-tight">CoinPack Protocol</h1>
            <p className="text-xs text-gray-400">Signed Bitcoin bearer-note console</p>
          </div>
        </div>
        {wallet.connected ? (
          <div className="flex items-center gap-3">
            <StatusPill tone="good">Signed wallet · {shorten(wallet.publicKey)}</StatusPill>
            <button onClick={wallet.disconnect} className="px-3 py-2 text-sm bg-white/10 rounded-lg">Disconnect</button>
          </div>
        ) : (
          <button onClick={wallet.connect} className="px-4 py-2 btn-primary text-black font-bold rounded-lg text-sm">Connect Wallet</button>
        )}
      </div>
    </header>
  );
}

function HeroStats({ stats, reserve }) {
  const reserveRatio = reserve?.reserve_ratio_bps ? reserve.reserve_ratio_bps / 100 : 0;
  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
      <div className="card rounded-xl p-5">
        <div className="text-xs text-gray-400 uppercase tracking-wider mb-1">Outstanding Liabilities</div>
        <div className="text-xl font-bold mono">{formatDenom(stats?.outstanding_liabilities_sats || 0)}</div>
        <div className="text-xs text-gray-500 mt-1">{formatSats(stats?.outstanding_liabilities_sats || 0)}</div>
      </div>
      <div className="card rounded-xl p-5">
        <div className="text-xs text-gray-400 uppercase tracking-wider mb-1">Reserve Ratio</div>
        <div className="text-xl font-bold mono">{reserveRatio ? reserveRatio.toFixed(2) : '—'}%</div>
        <div className="mt-3 h-2 bg-black/50 rounded-full overflow-hidden"><div className="h-full btn-primary" style={{ width: `${Math.min(reserveRatio || 0, 120)}%` }} /></div>
      </div>
      <div className="card rounded-xl p-5">
        <div className="text-xs text-gray-400 uppercase tracking-wider mb-1">Notes</div>
        <div className="text-xl font-bold mono">{Number(stats?.total_notes || 0).toLocaleString()}</div>
        <div className="text-xs text-gray-500 mt-1">Redeemed: {Number(stats?.redeemed_notes || 0).toLocaleString()}</div>
      </div>
      <div className="card rounded-xl p-5">
        <div className="text-xs text-gray-400 uppercase tracking-wider mb-1">Claims</div>
        <div className="text-xl font-bold mono">{Number(stats?.total_claims || 0).toLocaleString()}</div>
        <div className="text-xs text-gray-500 mt-1">Claimed: {Number(stats?.claimed_claims || 0).toLocaleString()}</div>
      </div>
    </div>
  );
}

function NoteCard({ note, onTransfer, onRedeem }) {
  const [showQR, setShowQR] = useState(false);
  const qrRef = useRef(null);
  const serial = note.serial_number ?? note.serial;
  const denom = note.denomination ?? note.denom;
  const holder = note.current_holder ?? note.holder;

  useEffect(() => {
    if (!showQR || !qrRef.current) return;
    qrRef.current.innerHTML = '';
    new QRCode(qrRef.current, {
      text: JSON.stringify({ type: 'coinpack-note', serial, holder }),
      width: 168,
      height: 168,
      colorDark: '#f59e0b',
      colorLight: '#0a0e1a',
      correctLevel: QRCode.CorrectLevel.M,
    });
  }, [showQR, serial, holder]);

  return (
    <div className="note-card rounded-xl p-5 slide-in">
      <div className="flex justify-between items-start gap-4 mb-4">
        <div>
          <div className="text-xs text-gray-400 uppercase tracking-wider mb-1">Serial #{serial}</div>
          <div className="text-2xl font-black gradient-text mono">{formatDenom(denom)}</div>
          <div className="text-xs text-gray-500">{formatSats(denom)}</div>
        </div>
        <StatusPill tone={note.redeemed ? 'bad' : 'good'}>{note.redeemed ? 'REDEEMED' : 'ACTIVE'}</StatusPill>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mb-4 text-xs">
        <div className="bg-black/50 rounded-lg p-3"><span className="text-gray-400">Holder</span><div className="mono text-gray-200">{shorten(holder, 10)}</div></div>
        <div className="bg-black/50 rounded-lg p-3"><span className="text-gray-400">Created</span><div className="mono text-gray-200">{formatDate(note.created_at)}</div></div>
      </div>
      {!note.redeemed && (
        <div className="flex flex-col md:flex-row gap-2">
          <button onClick={() => setShowQR(!showQR)} className="flex-1 px-3 py-2 bg-white/10 rounded-lg text-sm font-semibold">{showQR ? 'Hide QR' : 'Show QR'}</button>
          <button onClick={() => onTransfer(note)} className="flex-1 px-3 py-2 bg-white/10 rounded-lg text-sm font-semibold">Signed Transfer</button>
          <button onClick={() => onRedeem(note)} className="flex-1 px-3 py-2 btn-primary text-black font-bold rounded-lg text-sm">Redeem</button>
        </div>
      )}
      {showQR && <div className="mt-4 flex flex-col items-center p-4 bg-black/50 rounded-lg"><div ref={qrRef} className="mb-2"></div><p className="text-xs text-gray-500 mono">offline display only · verify before accepting</p></div>}
    </div>
  );
}

function NotesView({ wallet, notes, loading, error, onRefresh, onTransfer, onRedeem, setTab }) {
  if (!wallet.connected) return <EmptyState title="Connect wallet" body="Connect Phantom or Solflare to load notes and authorize signed transfers." action={<button onClick={wallet.connect} className="btn-primary px-4 py-2 rounded-lg font-bold text-black">Connect Wallet</button>} />;
  if (loading) return <div className="card rounded-xl p-6 text-center text-gray-400">Loading signed wallet portfolio...</div>;
  if (error) return <EmptyState title="Could not load notes" body={error} action={<button onClick={onRefresh} className="bg-white/10 px-4 py-2 rounded-lg">Retry</button>} />;
  if (!notes.length) return <EmptyState title="No bearer notes found" body="This wallet does not currently hold active notes in the backend registry." action={<button onClick={() => setTab('mint')} className="btn-primary px-4 py-2 rounded-lg font-bold text-black">Mint / issue note</button>} />;
  return <div className="space-y-4">{notes.map(note => <NoteCard key={note.serial_number ?? note.serial} note={note} onTransfer={onTransfer} onRedeem={onRedeem} />)}</div>;
}

function TransferModal({ wallet, note, onClose, onDone }) {
  const [newHolder, setNewHolder] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const serial = note?.serial_number ?? note?.serial;
  const holder = note?.current_holder ?? note?.holder;

  const submit = async () => {
    setError(null);
    setBusy(true);
    try {
      await signedApiFetch(wallet, `/api/v1/notes/${serial}/transfer`, {
        body: { serial_number: serial, holder, new_holder: newHolder },
      });
      onDone();
      onClose();
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="card rounded-2xl p-6 max-w-lg w-full">
        <h3 className="text-xl font-black mb-1">Signed Transfer</h3>
        <p className="text-sm text-gray-400 mb-4">Your wallet will sign an API intent bound to this route, timestamp, and nonce.</p>
        <div className="bg-black/50 rounded-lg p-4 mb-4 text-sm"><div className="flex justify-between"><span className="text-gray-400">Serial</span><span className="mono">#{serial}</span></div><div className="flex justify-between mt-1"><span className="text-gray-400">Current holder</span><span className="mono">{shorten(holder, 10)}</span></div></div>
        <label className="text-xs text-gray-400 block mb-1">New Solana holder</label>
        <input value={newHolder} onChange={e => setNewHolder(e.target.value)} placeholder="Base58 wallet address" className="w-full bg-black/50 border border-white/10 rounded-lg px-4 py-3 text-sm mb-3 mono" />
        {error && <div className="mb-3 text-sm text-red-400 bg-red-900/20 rounded-lg p-2">{error}</div>}
        <div className="flex gap-3"><button onClick={onClose} className="flex-1 py-3 bg-white/10 rounded-xl font-semibold">Cancel</button><button onClick={submit} disabled={busy || !newHolder} className="flex-1 py-3 btn-primary text-black rounded-xl font-bold disabled:opacity-50">{busy ? 'Signing...' : 'Sign & Transfer'}</button></div>
      </div>
    </div>
  );
}

function RedemptionModal({ wallet, note, onClose, onDone }) {
  const [btcAddress, setBtcAddress] = useState('');
  const [accepted, setAccepted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const serial = note?.serial_number ?? note?.serial;
  const holder = note?.current_holder ?? note?.holder;
  const denom = note?.denomination ?? note?.denom;

  const submit = async () => {
    setError(null);
    setBusy(true);
    try {
      await signedApiFetch(wallet, `/api/v1/notes/${serial}/burn-to-redeem`, {
        body: { serial_number: serial, holder, btc_address: btcAddress, accepted_risk_disclosure: accepted },
      });
      onDone();
      onClose();
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="card rounded-2xl p-6 max-w-lg w-full">
        <h3 className="text-xl font-black mb-1">Burn to Redeem</h3>
        <p className="text-sm text-gray-400 mb-4">This queues BTC redemption and marks the note redeemed. This action is irreversible.</p>
        <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-4 mb-4"><div className="text-xs text-gray-400">Amount</div><div className="text-2xl font-black gradient-text mono">{formatDenom(denom)}</div><div className="text-xs text-gray-500">{formatSats(denom)}</div></div>
        <label className="text-xs text-gray-400 block mb-1">BTC receiving address</label>
        <input value={btcAddress} onChange={e => setBtcAddress(e.target.value)} placeholder="bc1q..." className="w-full bg-black/50 border border-white/10 rounded-lg px-4 py-3 text-sm mb-3 mono" />
        <label className="flex items-start gap-2 text-xs text-gray-300 bg-red-900/20 rounded-lg p-3 mb-3"><input type="checkbox" checked={accepted} onChange={e => setAccepted(e.target.checked)} /><span>I understand reserve, custody, address, fee, and confirmation risks.</span></label>
        {error && <div className="mb-3 text-sm text-red-400 bg-red-900/20 rounded-lg p-2">{error}</div>}
        <div className="flex gap-3"><button onClick={onClose} className="flex-1 py-3 bg-white/10 rounded-xl font-semibold">Cancel</button><button onClick={submit} disabled={busy || !accepted || btcAddress.length < 26} className="flex-1 py-3 bg-red-500 text-white rounded-xl font-bold disabled:opacity-50">{busy ? 'Signing...' : 'Sign & Redeem'}</button></div>
      </div>
    </div>
  );
}

function MintNoteForm({ wallet }) {
  const [selected, setSelected] = useState(NOTE_DENOMS[0].sats);
  return (
    <div className="card rounded-xl p-6">
      <div className="flex items-start justify-between gap-4 mb-5"><div><h3 className="text-lg font-black">Issue Note</h3><p className="text-sm text-gray-400">UI prepared for Anchor RPC minting. Backend/on-chain authority must be configured before production issuance.</p></div><StatusPill>Anchor required</StatusPill></div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-6">
        {NOTE_DENOMS.map(d => <button key={d.sats} onClick={() => setSelected(d.sats)} className={`p-4 rounded-xl text-left border transition ${selected === d.sats ? 'border-amber-500 bg-amber-500/10' : 'border-white/10 bg-white/5'}`}><div className="text-lg font-black">{d.label}</div><div className="text-xs text-gray-400">{formatSats(d.sats)} · {d.tone}</div></button>)}
      </div>
      <button disabled={!wallet.connected} onClick={() => alert('Production minting requires Anchor RPC service + mint authority configuration.')} className="w-full py-3 btn-primary text-black font-bold rounded-xl disabled:opacity-50">{wallet.connected ? 'Prepare Anchor Mint' : 'Connect Wallet'}</button>
    </div>
  );
}

function CreateCoinPack({ wallet }) {
  const [assets, setAssets] = useState([{ type: 'BTC', amount: '' }]);
  const [pin, setPin] = useState('');
  const [expiresHours, setExpiresHours] = useState(24);
  const [deliveryMethod, setDeliveryMethod] = useState('link');
  const [deliveryAddress, setDeliveryAddress] = useState('');
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const qrRef = useRef(null);

  useEffect(() => {
    if (!result?.claim_url || !qrRef.current) return;
    qrRef.current.innerHTML = '';
    new QRCode(qrRef.current, { text: result.claim_url, width: 190, height: 190, colorDark: '#f59e0b', colorLight: '#0a0e1a' });
  }, [result]);

  const create = async () => {
    setError(null); setBusy(true);
    try {
      const validAssets = assets.filter(a => a.amount && Number(a.amount) > 0).map(a => ({ type: a.type, amount: Number(a.amount) }));
      const data = await apiFetch('/api/v1/claims', { method: 'POST', body: JSON.stringify({ creator: wallet.publicKey, assets: validAssets, pin, expires_hours: Number(expiresHours), delivery_method: deliveryMethod, delivery_address: deliveryAddress || null }) });
      setResult(data);
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  };

  if (result) return <div className="card rounded-xl p-6 text-center"><h3 className="text-xl font-black mb-2">CoinPack Created</h3><div className="flex justify-center mb-4"><div ref={qrRef}></div></div><p className="text-xs text-gray-400 mb-1">Claim URL</p><p className="mono text-amber-400 text-sm break-all bg-black/50 rounded-lg p-3 mb-4">{result.claim_url || result.claim_id}</p><button onClick={() => setResult(null)} className="bg-white/10 px-4 py-2 rounded-lg">Create another</button></div>;

  return (
    <div className="card rounded-xl p-6">
      <h3 className="text-lg font-black mb-1">Create CoinPack</h3><p className="text-sm text-gray-400 mb-4">Backend-backed claim bundle with PIN and expiry controls.</p>
      <div className="space-y-3 mb-4">{assets.map((a, i) => <div key={i} className="flex gap-2"><select value={a.type} onChange={e => setAssets(assets.map((x, idx) => idx === i ? { ...x, type: e.target.value } : x))} className="bg-black/50 border border-white/10 rounded-lg px-3 py-2 text-sm w-28"><option>BTC</option><option>USDC</option><option>SOL</option><option>ETH</option></select><input type="number" value={a.amount} onChange={e => setAssets(assets.map((x, idx) => idx === i ? { ...x, amount: e.target.value } : x))} placeholder="Amount" className="flex-1 bg-black/50 border border-white/10 rounded-lg px-3 py-2 text-sm" /><button onClick={() => setAssets(assets.filter((_, idx) => idx !== i))} className="px-3 text-red-400">×</button></div>)}</div>
      <button onClick={() => setAssets([...assets, { type: 'BTC', amount: '' }])} className="text-sm text-amber-400 mb-4">+ Add asset</button>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4"><input type="password" value={pin} onChange={e => setPin(e.target.value)} placeholder="PIN" maxLength={8} className="bg-black/50 border border-white/10 rounded-lg px-3 py-2 text-sm mono" /><select value={expiresHours} onChange={e => setExpiresHours(e.target.value)} className="bg-black/50 border border-white/10 rounded-lg px-3 py-2 text-sm"><option value="1">1 hour</option><option value="24">24 hours</option><option value="72">3 days</option><option value="168">7 days</option></select><select value={deliveryMethod} onChange={e => setDeliveryMethod(e.target.value)} className="bg-black/50 border border-white/10 rounded-lg px-3 py-2 text-sm"><option value="link">Link</option><option value="email">Email</option><option value="sms">SMS</option></select><input value={deliveryAddress} onChange={e => setDeliveryAddress(e.target.value)} placeholder="Delivery address optional" className="bg-black/50 border border-white/10 rounded-lg px-3 py-2 text-sm" /></div>
      {error && <div className="mb-3 text-sm text-red-400 bg-red-900/20 rounded-lg p-2">{error}</div>}
      <button onClick={create} disabled={!wallet.connected || busy || pin.length < 4} className="w-full py-3 btn-primary text-black font-bold rounded-xl disabled:opacity-50">{busy ? 'Creating...' : 'Create backend CoinPack'}</button>
    </div>
  );
}

function ClaimCoinPack() {
  const [claimId, setClaimId] = useState('');
  const [pin, setPin] = useState('');
  const [device] = useState(() => `web-${randomHex(8)}`);
  const [claimable, setClaimable] = useState(null);
  const [accepted, setAccepted] = useState(false);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const verify = async () => { setError(null); setBusy(true); try { setClaimable(await apiFetch(`/api/v1/coinpacks/${claimId}/verify`, { method: 'POST', body: JSON.stringify({ pin, device_fingerprint: device }) })); } catch (e) { setError(e.message); } finally { setBusy(false); } };
  const claim = async () => { setError(null); setBusy(true); try { setResult(await apiFetch(`/api/v1/coinpacks/${claimId}/claim`, { method: 'POST', body: JSON.stringify({ claim_id: claimId, pin, device_fingerprint: device, accepted_risk_disclosure: accepted }) })); } catch (e) { setError(e.message); } finally { setBusy(false); } };

  if (result) return <div className="card rounded-xl p-6 text-center"><h3 className="text-xl font-black mb-2">Claim Complete</h3><p className="text-sm text-gray-400 mb-4">Assets assigned according to backend claim result.</p><pre className="text-left text-xs bg-black/50 rounded-lg p-3 overflow-auto">{JSON.stringify(result, null, 2)}</pre></div>;
  return <div className="card rounded-xl p-6"><h3 className="text-lg font-black mb-1">Claim CoinPack</h3><p className="text-sm text-gray-400 mb-4">Verify PIN first, then accept risk disclosure before claiming.</p><input value={claimId} onChange={e => setClaimId(e.target.value)} placeholder="Claim ID" className="w-full bg-black/50 border border-white/10 rounded-lg px-4 py-3 text-sm mb-3 mono" /><input type="password" value={pin} onChange={e => setPin(e.target.value)} placeholder="PIN" className="w-full bg-black/50 border border-white/10 rounded-lg px-4 py-3 text-sm mb-3 mono" />{claimable && <div className="bg-amber-500/10 rounded-lg p-3 mb-3 text-sm"><p className="font-bold text-amber-300 mb-2">Claim verified</p>{claimable.assets?.map((a, i) => <div key={i} className="flex justify-between"><span>{a.type}</span><span className="mono">{a.amount}</span></div>)}<label className="flex gap-2 mt-3 text-xs"><input type="checkbox" checked={accepted} onChange={e => setAccepted(e.target.checked)} />I accept custody, link theft, expiry, and reserve risks.</label></div>}{error && <div className="mb-3 text-sm text-red-400 bg-red-900/20 rounded-lg p-2">{error}</div>}{!claimable ? <button onClick={verify} disabled={!claimId || !pin || busy} className="w-full py-3 btn-primary text-black font-bold rounded-xl disabled:opacity-50">{busy ? 'Verifying...' : 'Verify Claim'}</button> : <button onClick={claim} disabled={!accepted || busy} className="w-full py-3 btn-primary text-black font-bold rounded-xl disabled:opacity-50">{busy ? 'Claiming...' : 'Accept & Claim'}</button>}</div>;
}

function ReserveView({ reserve }) {
  return <div className="space-y-4"><div className="card rounded-xl p-6"><h3 className="text-lg font-black mb-4">Proof of Reserves</h3><pre className="text-xs bg-black/50 rounded-lg p-4 overflow-auto">{JSON.stringify(reserve || { status: 'unavailable' }, null, 2)}</pre></div></div>;
}

function AuditLogView() {
  const [events, setEvents] = useState([]); const [loading, setLoading] = useState(true);
  useEffect(() => { apiFetch('/api/v1/audit/events?limit=50').then(d => setEvents(d.events || [])).catch(() => setEvents([])).finally(() => setLoading(false)); }, []);
  if (loading) return <div className="card rounded-xl p-6 text-center text-gray-400">Loading audit logs...</div>;
  return <div className="card rounded-xl p-6"><h3 className="text-lg font-black mb-4">Audit Chain</h3><div className="space-y-2 max-h-96 overflow-y-auto">{events.map(e => <div key={e.id} className="bg-black/50 rounded-lg p-3 text-sm"><div className="flex justify-between gap-3"><span className="text-amber-400 font-bold">{e.event_type}</span><span className="text-gray-500 text-xs">{formatDate(e.created_at)}</span></div><div className="text-xs text-gray-400 mono">wallet {shorten(e.wallet_address)} · hash {shorten(e.event_hash || '', 8)}</div></div>)}</div></div>;
}

function App() {
  const wallet = useWallet();
  const [tab, setTab] = useState('notes');
  const [notes, setNotes] = useState([]);
  const [stats, setStats] = useState(null);
  const [reserve, setReserve] = useState(null);
  const [loadingNotes, setLoadingNotes] = useState(false);
  const [notesError, setNotesError] = useState(null);
  const [transferNote, setTransferNote] = useState(null);
  const [redeemNote, setRedeemNote] = useState(null);

  const loadStats = () => { apiFetch('/api/v1/stats').then(setStats).catch(() => {}); apiFetch('/api/v1/reserves/proof').then(setReserve).catch(() => setReserve({ degraded_source: true, disclaimer: 'Reserve API unavailable.' })); };
  const loadNotes = async () => {
    if (!wallet.publicKey) return;
    setLoadingNotes(true); setNotesError(null);
    try { const data = await apiFetch(`/api/v1/notes?holder=${encodeURIComponent(wallet.publicKey)}&redeemed=false`); setNotes(data.notes || []); }
    catch (e) { setNotesError(e.message); }
    finally { setLoadingNotes(false); }
  };

  useEffect(loadStats, []);
  useEffect(() => { loadNotes(); }, [wallet.publicKey]);

  const tabs = [ ['notes', 'My Notes'], ['mint', 'Issue'], ['create', 'Create CoinPack'], ['claim', 'Claim'], ['reserves', 'Reserves'], ['audit', 'Audit'] ];

  return (
    <div className="min-h-screen pb-28"><Header wallet={wallet} /><main className="max-w-7xl mx-auto px-4 pt-24"><HeroStats stats={stats} reserve={reserve} /><div className="flex gap-2 mb-6 overflow-x-auto">{tabs.map(([id, label]) => <button key={id} onClick={() => setTab(id)} className={`px-4 py-2 rounded-lg text-sm font-bold whitespace-nowrap transition ${tab === id ? 'btn-primary text-black' : 'bg-white/5'}`}>{label}</button>)}</div>{tab === 'notes' && <NotesView wallet={wallet} notes={notes} loading={loadingNotes} error={notesError} onRefresh={loadNotes} onTransfer={setTransferNote} onRedeem={setRedeemNote} setTab={setTab} />}{tab === 'mint' && <MintNoteForm wallet={wallet} />}{tab === 'create' && <CreateCoinPack wallet={wallet} />}{tab === 'claim' && <ClaimCoinPack />}{tab === 'reserves' && <ReserveView reserve={reserve} />}{tab === 'audit' && <AuditLogView />}</main>{transferNote && <TransferModal wallet={wallet} note={transferNote} onClose={() => setTransferNote(null)} onDone={loadNotes} />}{redeemNote && <RedemptionModal wallet={wallet} note={redeemNote} onClose={() => setRedeemNote(null)} onDone={() => { loadNotes(); loadStats(); }} />}<RiskBanner /><div className="fixed bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-amber-500 to-transparent opacity-30"></div></div>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
