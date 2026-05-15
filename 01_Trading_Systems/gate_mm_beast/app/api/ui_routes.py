def unified_ui_html() -> str:
    return """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>Unified Exchange Balance</title>
  <style>
    :root {
      --bg: radial-gradient(1200px 700px at 10% 0%, #1a2242 0%, #0b0f1d 45%, #06070b 100%);
      --card: rgba(255,255,255,0.06);
      --stroke: rgba(255,255,255,0.12);
      --text: #eaf1ff;
      --muted: #9fb0d4;
      --good: #3fe08f;
      --bad: #ff6b7d;
      --accent: #66d2ff;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background: var(--bg);
      min-height: 100vh;
    }
    .wrap {
      max-width: 1100px;
      margin: 24px auto;
      padding: 0 16px 28px;
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: end;
      gap: 16px;
      margin-bottom: 18px;
    }
    .title { font-size: 1.5rem; font-weight: 700; letter-spacing: 0.4px; }
    .total {
      font-size: 1.15rem;
      color: var(--accent);
      font-weight: 700;
    }
    .meta { color: var(--muted); font-size: 0.92rem; margin-top: 4px; }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 14px;
    }
    .card {
      background: var(--card);
      border: 1px solid var(--stroke);
      border-radius: 14px;
      padding: 14px;
      backdrop-filter: blur(3px);
    }
    .name { font-size: 1rem; font-weight: 700; text-transform: capitalize; }
    .status { font-size: 0.86rem; margin-top: 4px; }
    .ok { color: var(--good); }
    .err { color: var(--bad); }
    .usd { margin-top: 8px; font-size: 1.05rem; font-weight: 700; }
    .assets { margin-top: 10px; max-height: 180px; overflow: auto; font-size: 0.86rem; color: var(--muted); }
    .asset-row { display: flex; justify-content: space-between; gap: 10px; padding: 2px 0; }
    .hint { margin-top: 14px; color: var(--muted); font-size: 0.85rem; }
  </style>
</head>
<body>
  <div class=\"wrap\">
    <div class=\"header\">
      <div>
        <div class=\"title\">Unified Exchange Balance</div>
        <div class=\"meta\" id=\"stamp\">loading...</div>
      </div>
      <div class=\"total\" id=\"total\">$0.00</div>
    </div>
    <div class=\"grid\" id=\"grid\"></div>
    <div class=\"hint\">Tip: this dashboard aggregates USD-like assets (USD/USDT/USDC/BUSD/FDUSD/TUSD).</div>
  </div>
<script>
async function loadBalances() {
  try {
    const res = await fetch('/unified-balance');
    const data = await res.json();
    const exchanges = data.exchanges || {};
    document.getElementById('total').textContent = '$' + Number(data.total_usd || 0).toFixed(2);
    document.getElementById('stamp').textContent = data.ts ? ('updated: ' + data.ts) : 'updated: n/a';

    const grid = document.getElementById('grid');
    grid.innerHTML = '';
    Object.entries(exchanges).forEach(([name, info]) => {
      const card = document.createElement('div');
      card.className = 'card';
      const statusClass = info.status === 'ok' ? 'ok' : 'err';
      const assets = Array.isArray(info.assets) ? info.assets : [];
      card.innerHTML = `
        <div class=\"name\">${name}</div>
        <div class=\"status ${statusClass}\">${info.status || 'unknown'}${info.error ? ' • ' + info.error : ''}</div>
        <div class=\"usd\">$${Number(info.total_usd || 0).toFixed(2)}</div>
        <div class=\"assets\">${assets.slice(0, 20).map(a => `<div class=\"asset-row\"><span>${a.asset || '-'}</span><span>${Number((a.free||0)+(a.locked||0)).toFixed(6)}</span></div>`).join('') || 'No assets'}</div>
      `;
      grid.appendChild(card);
    });
  } catch (err) {
    document.getElementById('stamp').textContent = 'fetch error: ' + String(err);
  }
}
loadBalances();
setInterval(loadBalances, 5000);
</script>
</body>
</html>"""
