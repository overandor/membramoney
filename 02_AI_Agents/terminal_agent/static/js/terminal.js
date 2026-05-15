let authToken = null;
let currentUsername = 'admin';
let currentSession = 'default';
let aiConnected = false;
let connectedWallet = null;
let currentOrderSide = 'buy';

async function api(url, options = {}) {
    const headers = { 'Content-Type': 'application/json' };
    if (authToken) headers['Authorization'] = authToken;
    const response = await fetch(url, { ...options, headers });
    if (response.status === 401) return null;
    return response.json();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function addMessage(role, text) {
    const container = document.getElementById('messages');
    const welcome = container.querySelector('.welcome');
    if (welcome) welcome.remove();

    const msg = document.createElement('div');
    msg.className = `message ${role}`;
    msg.innerHTML = `
        <div class="message-avatar">${role === 'user' ? 'U' : 'PC'}</div>
        <div class="message-content">${escapeHtml(text)}</div>
    `;
    container.appendChild(msg);
    container.scrollTop = container.scrollHeight;
}

function setLoading(loading) {
    const btn = document.getElementById('send-btn');
    btn.disabled = loading;
    btn.innerHTML = loading
        ? '<svg width="16" height="16" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2" fill="none" stroke-dasharray="40" stroke-dashoffset="10"><animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur="1s" repeatCount="indefinite"/></circle></svg>'
        : '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>';
}

async function sendMessage() {
    const input = document.getElementById('chat-input');
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    addMessage('user', text);
    setLoading(true);

    const result = await api('/api/ollama/chat', {
        method: 'POST',
        body: JSON.stringify({ message: text, session_id: currentSession })
    });
    setLoading(false);
    if (result && result.response) {
        addMessage('assistant', result.response);
    } else {
        addMessage('assistant', 'Sorry, I could not process that request. The AI service may be unavailable.');
    }
}

// Event listeners
document.getElementById('send-btn').addEventListener('click', sendMessage);
document.getElementById('chat-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

document.getElementById('chat-input').addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 200) + 'px';
});

// Suggestion cards
document.querySelectorAll('.suggestion-card').forEach(card => {
    card.addEventListener('click', () => {
        document.getElementById('chat-input').value = card.dataset.prompt;
        sendMessage();
    });
});

// Sidebar toggle
document.getElementById('menu-toggle').addEventListener('click', () => {
    document.getElementById('sidebar').classList.toggle('open');
});

// New chat
document.getElementById('new-chat-btn').addEventListener('click', () => {
    document.getElementById('messages').innerHTML = `
        <div class="welcome">
            <div class="welcome-icon">PC</div>
            <h1>Profit Concierge</h1>
            <p class="welcome-subtitle">Your AI-powered trading and profit opportunity assistant</p>
            <div class="suggestion-grid">
                <button class="suggestion-card" data-prompt="Scan Solana for arbitrage opportunities today">
                    <div class="suggestion-title">Solana Arbitrage</div>
                    <div class="suggestion-desc">Find DEX price discrepancies</div>
                </button>
                <button class="suggestion-card" data-prompt="What are the best DeFi yield opportunities right now?">
                    <div class="suggestion-title">DeFi Yields</div>
                    <div class="suggestion-desc">Compare staking and lending rates</div>
                </button>
                <button class="suggestion-card" data-prompt="Analyze BTC and ETH market momentum">
                    <div class="suggestion-title">Market Analysis</div>
                    <div class="suggestion-desc">Technical overview of major assets</div>
                </button>
                <button class="suggestion-card" data-prompt="Scan for new token launches and memecoin trends">
                    <div class="suggestion-title">New Launches</div>
                    <div class="suggestion-desc">Early opportunity detection</div>
                </button>
            </div>
        </div>
    `;
    document.querySelectorAll('.suggestion-card').forEach(card => {
        card.addEventListener('click', () => {
            document.getElementById('chat-input').value = card.dataset.prompt;
            sendMessage();
        });
    });
});

// Trading panel toggle
document.getElementById('trading-toggle').addEventListener('click', () => {
    document.getElementById('right-panel').classList.toggle('hidden');
});

// Right panel tabs
document.querySelectorAll('.panel-tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.panel-tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.panel-body').forEach(b => b.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById(`${tab.dataset.tab}-tab`).classList.add('active');
    });
});

// Wallet
document.getElementById('connect-metamask').addEventListener('click', async () => {
    if (typeof window.ethereum !== 'undefined') {
        try {
            const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
            if (accounts.length > 0) await connectWallet(accounts[0]);
        } catch (e) { alert('MetaMask connection failed: ' + e.message); }
    } else { alert('MetaMask not installed.'); }
});

document.getElementById('connect-manual').addEventListener('click', async () => {
    const addr = document.getElementById('manual-address').value.trim();
    if (addr.startsWith('0x') && addr.length === 42) await connectWallet(addr);
    else alert('Invalid address');
});

async function connectWallet(address) {
    const result = await api('/api/web3/wallet/connect', {
        method: 'POST', body: JSON.stringify({ address, chain: 'ethereum' })
    });
    if (result) {
        connectedWallet = result;
        document.getElementById('wallet-connect-view').classList.add('hidden');
        document.getElementById('wallet-info-view').classList.remove('hidden');
        document.getElementById('wallet-address').textContent = address;
        document.getElementById('wallet-chain').textContent = result.chain;
        await refreshBalance();
        await loadGasPrice();
    }
}

document.getElementById('refresh-balance').addEventListener('click', refreshBalance);
document.getElementById('disconnect-wallet').addEventListener('click', () => {
    connectedWallet = null;
    document.getElementById('wallet-connect-view').classList.remove('hidden');
    document.getElementById('wallet-info-view').classList.add('hidden');
});

async function refreshBalance() {
    if (!connectedWallet) return;
    const result = await api('/api/web3/balance', {
        method: 'POST',
        body: JSON.stringify({ address: connectedWallet.address, chain: connectedWallet.chain })
    });
    if (result && !result.error) document.getElementById('wallet-balance').textContent = result.formatted;
}

async function loadGasPrice() {
    const result = await api('/api/web3/gas-price?chain=ethereum');
    if (result && !result.error) document.getElementById('gas-price').textContent = result.formatted;
}

// Trading
document.getElementById('buy-btn').addEventListener('click', () => { currentOrderSide = 'buy'; });
document.getElementById('sell-btn').addEventListener('click', () => { currentOrderSide = 'sell'; });

document.getElementById('analyze-market').addEventListener('click', async () => {
    const symbol = document.getElementById('market-symbol').value || 'BTC/USDT';
    const result = await api(`/api/trading/analyze/${encodeURIComponent(symbol)}`);
    if (result) {
        document.getElementById('market-result').innerHTML = `
            <strong>${result.symbol}</strong><br>
            Trend: ${result.trend} | Rec: ${result.recommendation}<br>
            Confidence: ${(result.confidence * 100).toFixed(0)}%<br>
            Price: $${result.data.price?.toFixed(2) || 'N/A'}
        `;
    }
});

document.getElementById('place-order').addEventListener('click', async () => {
    const symbol = document.getElementById('order-symbol').value;
    const amount = parseFloat(document.getElementById('order-amount').value);
    if (!symbol || !amount) return alert('Enter symbol and amount');
    const result = await api('/api/trading/order', {
        method: 'POST',
        body: JSON.stringify({ symbol, side: currentOrderSide, amount, type: 'market' })
    });
    if (result) alert(`Order: ${result.order_id} (${result.status})`);
});

document.getElementById('run-strategy').addEventListener('click', async () => {
    const result = await api('/api/trading/strategy', {
        method: 'POST',
        body: JSON.stringify({ strategy_name: 'default', symbols: ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'] })
    });
    if (result) {
        const html = result.results.map(r => `${r.symbol}: ${r.action} (${(r.confidence * 100).toFixed(0)}%)`).join('<br>');
        document.getElementById('strategy-result').innerHTML = html || 'No signals';
    }
});

async function loadPortfolio() {
    const result = await api('/api/trading/portfolio');
    if (result) {
        document.getElementById('portfolio-value').textContent = `$${result.total_value?.toFixed(2) || '0.00'}`;
        document.getElementById('positions-count').textContent = `${result.positions_count || 0}`;
    }
}

setInterval(loadPortfolio, 30000);
loadPortfolio();

// Init
loadPortfolio();

