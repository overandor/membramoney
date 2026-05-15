// Decentralized Trader - Frontend JavaScript
// No registration required - wallet based trading

class DecentralizedTrader {
    constructor() {
        this.selectedProtocol = null;
        this.walletConnected = false;
        this.ethereumAddress = null;
        this.solanaAddress = null;
        this.apiKeys = {};
        this.transactions = [];
        
        this.initializeEventListeners();
        this.checkLocation();
    }

    initializeEventListeners() {
        // Wallet connection buttons
        document.getElementById('connect-eth').addEventListener('click', () => this.connectEthereumWallet());
        document.getElementById('connect-sol').addEventListener('click', () => this.connectSolanaWallet());
        
        // API key saving
        document.querySelectorAll('input[type="password"]').forEach(input => {
            input.addEventListener('change', () => this.saveApiKeys());
        });
        
        // Trade form
        document.getElementById('trade-form').addEventListener('submit', (e) => this.executeTrade(e));
        
        // Amount input for live calculation
        document.getElementById('trade-amount').addEventListener('input', (e) => this.calculateEstimatedReturn(e.target.value));
    }

    async checkLocation() {
        const geoStatus = document.getElementById('geo-status');
        const geoDetails = document.getElementById('geo-details');
        const geoLoading = document.getElementById('geo-loading');
        
        try {
            const response = await fetch('/api/validate_location');
            const data = await response.json();
            
            geoLoading.style.display = 'none';
            
            if (data.valid) {
                geoStatus.innerHTML = `
                    <span class="text-green-400">
                        <i class="fas fa-check-circle mr-2"></i>${data.message}
                    </span>
                `;
                geoDetails.innerHTML = `
                    <div class="text-green-300">
                        <i class="fas fa-shield-alt mr-2"></i>
                        Your location is compliant for trading
                    </div>
                `;
            } else {
                geoStatus.innerHTML = `
                    <span class="text-red-400">
                        <i class="fas fa-exclamation-triangle mr-2"></i>${data.message}
                    </span>
                `;
                geoDetails.innerHTML = `
                    <div class="text-yellow-300">
                        <i class="fas fa-info-circle mr-2"></i>
                        Consider using a VPN if you believe this is an error
                    </div>
                `;
            }
        } catch (error) {
            geoLoading.style.display = 'none';
            geoStatus.innerHTML = `
                <span class="text-yellow-400">
                    <i class="fas fa-question-circle mr-2"></i>Unable to verify location
                </span>
            `;
        }
    }

    async connectEthereumWallet() {
        const button = document.getElementById('connect-eth');
        const status = document.getElementById('eth-status');
        const walletCard = document.getElementById('eth-wallet-card');
        
        button.disabled = true;
        button.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Connecting...';
        
        try {
            // Check if MetaMask is installed
            if (typeof window.ethereum === 'undefined') {
                throw new Error('MetaMask not installed. Please install MetaMask first.');
            }
            
            // Request account access
            const accounts = await window.ethereum.request({
                method: 'eth_requestAccounts'
            });
            
            if (accounts.length > 0) {
                this.ethereumAddress = accounts[0];
                this.walletConnected = true;
                
                // Update UI
                status.innerHTML = `
                    <div class="text-green-400">
                        <i class="fas fa-check-circle mr-2"></i>
                        Connected: ${this.ethereumAddress.slice(0, 6)}...${this.ethereumAddress.slice(-4)}
                    </div>
                `;
                
                button.innerHTML = '<i class="fas fa-check mr-2"></i>Connected';
                button.className = 'w-full bg-green-600 px-4 py-2 rounded-lg';
                walletCard.classList.add('connected');
                
                this.showNotification('Ethereum wallet connected successfully!', 'success');
            }
        } catch (error) {
            status.innerHTML = `
                <div class="text-red-400">
                    <i class="fas fa-exclamation-circle mr-2"></i>${error.message}
                </div>
            `;
            button.disabled = false;
            button.innerHTML = 'Connect MetaMask';
            this.showNotification(error.message, 'error');
        }
    }

    async connectSolanaWallet() {
        const button = document.getElementById('connect-sol');
        const status = document.getElementById('sol-status');
        const walletCard = document.getElementById('sol-wallet-card');
        
        button.disabled = true;
        button.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Connecting...';
        
        try {
            // Try auto-creation first
            const response = await fetch('/api/connect_solana_auto', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ auto_create: true })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.solanaAddress = data.address;
                this.walletConnected = true;
                
                // Update UI
                status.innerHTML = `
                    <div class="text-green-400">
                        <i class="fas fa-check-circle mr-2"></i>
                        Connected: ${this.solanaAddress.slice(0, 6)}...${this.solanaAddress.slice(-4)}
                        ${data.auto_created ? '<span class="text-yellow-300 ml-2">(Auto-created)</span>' : ''}
                    </div>
                    <div class="text-sm mt-1 opacity-80">
                        Balance: ${data.balance.toFixed(6)} SOL
                    </div>
                `;
                
                button.innerHTML = '<i class="fas fa-check mr-2"></i>Connected';
                button.className = 'w-full bg-green-600 px-4 py-2 rounded-lg';
                walletCard.classList.add('connected');
                
                // Show auto-created notification
                if (data.auto_created) {
                    this.showNotification('New Solana wallet auto-created with 0 balance!', 'success');
                } else {
                    this.showNotification('Solana wallet connected successfully!', 'success');
                }
                
                // Store wallet info for transaction signing
                this.currentSolanaWallet = {
                    address: data.address,
                    balance: data.balance,
                    auto_created: data.auto_created
                };
            } else {
                throw new Error(data.error || 'Connection failed');
            }
        } catch (error) {
            // Fallback to Phantom wallet
            if (typeof window.solana !== 'undefined') {
                try {
                    const response = await window.solana.connect();
                    this.solanaAddress = response.publicKey.toString();
                    this.walletConnected = true;
                    
                    status.innerHTML = `
                        <div class="text-green-400">
                            <i class="fas fa-check-circle mr-2"></i>
                            Connected: ${this.solanaAddress.slice(0, 6)}...${this.solanaAddress.slice(-4)}
                            <span class="text-blue-300 ml-2">(Phantom)</span>
                        </div>
                    `;
                    
                    button.innerHTML = '<i class="fas fa-check mr-2"></i>Connected';
                    button.className = 'w-full bg-green-600 px-4 py-2 rounded-lg';
                    walletCard.classList.add('connected');
                    
                    this.showNotification('Phantom wallet connected successfully!', 'success');
                } catch (phantomError) {
                    throw new Error('Both auto-creation and Phantom wallet failed');
                }
            } else {
                throw new Error(error.message);
            }
        } finally {
            if (!this.walletConnected) {
                button.disabled = false;
                button.innerHTML = 'Connect Phantom';
                status.innerHTML = `
                    <div class="text-red-400">
                        <i class="fas fa-exclamation-circle mr-2"></i>${error.message}
                    </div>
                `;
                this.showNotification(error.message, 'error');
            }
        }
    }

    async signTransaction(transactionData) {
        if (!this.solanaAddress || !this.currentSolanaWallet?.auto_created) {
            // For Phantom wallet, let the user handle signing
            this.showNotification('Please sign the transaction in Phantom wallet', 'info');
            return { signed: true, signature: 'phantom_signed' };
        }
        
        try {
            const response = await fetch('/api/sign_transaction', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    public_key: this.solanaAddress,
                    transaction_data: transactionData
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showNotification('Transaction signed successfully!', 'success');
                return {
                    signed: data.signed,
                    signature: data.signature
                };
            } else {
                throw new Error(data.error);
            }
        } catch (error) {
            this.showNotification(`Transaction signing failed: ${error.message}`, 'error');
            return { signed: false, error: error.message };
        }
    }

    async checkWalletBalance() {
        if (!this.solanaAddress) return;
        
        try {
            const response = await fetch(`/api/wallet_balance/${this.solanaAddress}`);
            const data = await response.json();
            
            if (data.success) {
                const status = document.getElementById('sol-status');
                const balanceElement = status.querySelector('.text-sm');
                if (balanceElement) {
                    balanceElement.textContent = `Balance: ${data.balance.toFixed(6)} SOL`;
                }
            }
        } catch (error) {
            console.error('Balance check failed:', error);
        }
    }

    saveApiKeys() {
        const oneinchKey = document.getElementById('1inch-key').value;
        const hyperliquidKey = document.getElementById('hyperliquid-key').value;
        const driftKey = document.getElementById('drift-key').value;
        
        this.apiKeys = {
            oneinch: oneinchKey,
            hyperliquid: hyperliquidKey,
            drift: driftKey
        };
        
        // Save to backend
        fetch('/api/set_api_keys', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(this.apiKeys)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                this.showNotification('API keys saved successfully!', 'success');
            }
        })
        .catch(error => {
            console.error('Error saving API keys:', error);
            this.showNotification('Error saving API keys', 'error');
        });
    }

    selectProtocol(protocol) {
        if (!this.walletConnected) {
            this.showNotification('Please connect a wallet first', 'warning');
            return;
        }
        
        this.selectedProtocol = protocol;
        
        // Update UI
        document.getElementById('selected-protocol').textContent = protocol.charAt(0).toUpperCase() + protocol.slice(1);
        document.getElementById('trading-interface').classList.remove('hidden');
        
        // Show/hide leverage section based on protocol
        const leverageSection = document.getElementById('leverage-section');
        if (protocol === 'hyperliquid' || protocol === 'drift') {
            leverageSection.style.display = 'block';
        } else {
            leverageSection.style.display = 'none';
        }
        
        // Update token options based on protocol
        this.updateTokenOptions(protocol);
        
        // Scroll to trading interface
        document.getElementById('trading-interface').scrollIntoView({ behavior: 'smooth' });
        
        this.showNotification(`${protocol.toUpperCase()} selected`, 'info');
    }

    updateTokenOptions(protocol) {
        const fromToken = document.getElementById('from-token');
        const toToken = document.getElementById('to-token');
        
        // Clear existing options
        fromToken.innerHTML = '';
        toToken.innerHTML = '';
        
        const tokenOptions = {
            '1inch': [
                { value: 'ETH', text: 'ETH' },
                { value: 'USDC', text: 'USDC' },
                { value: 'USDT', text: 'USDT' },
                { value: 'WBTC', text: 'WBTC' },
                { value: 'DAI', text: 'DAI' }
            ],
            'hyperliquid': [
                { value: 'ETH', text: 'ETH' },
                { value: 'BTC', text: 'BTC' },
                { value: 'SOL', text: 'SOL' },
                { value: 'ARB', text: 'ARB' }
            ],
            'drift': [
                { value: 'SOL', text: 'SOL' },
                { value: 'BTC-PERP', text: 'BTC-PERP' },
                { value: 'ETH-PERP', text: 'ETH-PERP' },
                { value: 'SOL-PERP', text: 'SOL-PERP' }
            ]
        };
        
        const options = tokenOptions[protocol] || tokenOptions['1inch'];
        
        options.forEach((token, index) => {
            const fromOption = new Option(token.text, token.value);
            const toOption = new Option(token.text, token.value);
            
            if (index === 0) fromToken.add(fromOption);
            if (index === 1) toToken.add(toOption);
            else toToken.add(toOption);
        });
        
        this.updateMarketInfo();
    }

    async updateMarketInfo() {
        const marketInfo = document.getElementById('market-info');
        
        // Simulate market data (in real app, this would fetch from API)
        const mockData = {
            currentPrice: '$2,450.00',
            volume24h: '$125.4M',
            gasFee: '0.005 ETH'
        };
        
        document.getElementById('current-price').textContent = mockData.currentPrice;
        document.getElementById('volume-24h').textContent = mockData.volume24h;
        document.getElementById('gas-fee').textContent = mockData.gasFee;
    }

    updateLeverageDisplay(value) {
        document.getElementById('leverage-display').textContent = `${value}x`;
        this.calculateEstimatedReturn(document.getElementById('trade-amount').value);
    }

    async calculateEstimatedReturn(amount) {
        if (!amount || amount <= 0) {
            document.getElementById('estimated-return').textContent = '-';
            return;
        }
        
        // Simulate calculation (in real app, this would fetch from API)
        const leverage = document.getElementById('leverage').value;
        const estimatedReturn = amount * 1.02 * leverage; // 2% profit estimate
        
        document.getElementById('estimated-return').textContent = 
            `$${estimatedReturn.toFixed(4)} (${leverage}x leverage)`;
    }

    async executeTrade(event) {
        event.preventDefault();
        
        if (!this.walletConnected) {
            this.showNotification('Please connect a wallet first', 'warning');
            return;
        }
        
        if (!this.selectedProtocol) {
            this.showNotification('Please select a trading protocol', 'warning');
            return;
        }
        
        const formData = {
            protocol: this.selectedProtocol,
            from_token: document.getElementById('from-token').value,
            to_token: document.getElementById('to-token').value,
            amount: parseFloat(document.getElementById('trade-amount').value),
            wallet_address: this.ethereumAddress || this.solanaAddress,
            leverage: parseInt(document.getElementById('leverage').value)
        };
        
        const submitButton = event.target.querySelector('button[type="submit"]');
        submitButton.disabled = true;
        submitButton.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Executing...';
        
        try {
            // For Solana protocols, sign transaction first if using auto-created wallet
            if ((this.selectedProtocol === 'drift' || this.selectedProtocol === 'hyperliquid') && 
                this.currentSolanaWallet?.auto_created) {
                
                this.showNotification('Preparing transaction for auto-signed wallet...', 'info');
                
                // Create transaction data for signing
                const transactionData = {
                    protocol: this.selectedProtocol,
                    from_token: formData.from_token,
                    to_token: formData.to_token,
                    amount: formData.amount,
                    leverage: formData.leverage
                };
                
                // Sign the transaction
                const signResult = await this.signTransaction(transactionData);
                
                if (!signResult.signed) {
                    throw new Error('Transaction signing failed');
                }
                
                // Add signature to form data
                formData.signature = signResult.signature;
                formData.auto_signed = true;
            }
            
            const response = await fetch('/api/execute_trade', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });
            
            const result = await response.json();
            
            if (response.ok && !result.error) {
                this.addTransaction({
                    protocol: this.selectedProtocol,
                    from: formData.from_token,
                    to: formData.to_token,
                    amount: formData.amount,
                    status: 'success',
                    timestamp: new Date().toISOString(),
                    txHash: result.txHash || result.signature || 'pending',
                    autoSigned: formData.auto_signed || false
                });
                
                this.showNotification('Trade executed successfully!', 'success');
                
                // Update wallet balance if it's a Solana wallet
                if (this.solanaAddress) {
                    setTimeout(() => this.checkWalletBalance(), 2000);
                }
                
                // Reset form
                event.target.reset();
                document.getElementById('estimated-return').textContent = '-';
            } else {
                this.addTransaction({
                    protocol: this.selectedProtocol,
                    from: formData.from_token,
                    to: formData.to_token,
                    amount: formData.amount,
                    status: 'failed',
                    timestamp: new Date().toISOString(),
                    error: result.error
                });
                
                this.showNotification(`Trade failed: ${result.error}`, 'error');
            }
        } catch (error) {
            console.error('Trade execution error:', error);
            this.showNotification('Trade execution failed', 'error');
        } finally {
            submitButton.disabled = false;
            submitButton.innerHTML = '<i class="fas fa-exchange-alt mr-2"></i>Execute Trade';
        }
    }

    addTransaction(transaction) {
        this.transactions.unshift(transaction);
        this.updateTransactionHistory();
    }

    updateTransactionHistory() {
        const historyContainer = document.getElementById('transaction-history');
        
        if (this.transactions.length === 0) {
            historyContainer.innerHTML = '<p class="text-center opacity-60">No transactions yet</p>';
            return;
        }
        
        historyContainer.innerHTML = this.transactions.map(tx => `
            <div class="flex justify-between items-center p-3 bg-white/5 rounded-lg">
                <div class="flex items-center space-x-3">
                    <div class="w-2 h-2 rounded-full ${tx.status === 'success' ? 'bg-green-400' : 'bg-red-400'}"></div>
                    <div>
                        <div class="font-medium">
                            ${tx.protocol.toUpperCase()}
                            ${tx.autoSigned ? '<span class="text-yellow-300 text-xs ml-1">🔐 Auto-Signed</span>' : ''}
                        </div>
                        <div class="text-sm opacity-60">${tx.amount} ${tx.from} → ${tx.to}</div>
                        ${tx.txHash ? `<div class="text-xs opacity-50">Hash: ${tx.txHash.slice(0, 10)}...</div>` : ''}
                    </div>
                </div>
                <div class="text-right">
                    <div class="text-sm ${tx.status === 'success' ? 'text-green-400' : 'text-red-400'}">
                        ${tx.status === 'success' ? 'Success' : 'Failed'}
                    </div>
                    <div class="text-xs opacity-60">
                        ${new Date(tx.timestamp).toLocaleTimeString()}
                    </div>
                </div>
            </div>
        `).join('');
    }

    // Mining and stress testing functions
    async startMining() {
        const threads = parseInt(document.getElementById('mining-threads').value);
        
        try {
            const response = await fetch('/api/start_mining', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ threads })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showNotification(data.message, 'success');
                this.startMiningStatsUpdate();
            } else {
                this.showNotification(data.error, 'error');
            }
        } catch (error) {
            this.showNotification('Mining start failed', 'error');
        }
    }

    async stopMining() {
        try {
            const response = await fetch('/api/stop_mining', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showNotification(data.message, 'success');
                this.stopMiningStatsUpdate();
            } else {
                this.showNotification(data.error, 'error');
            }
        } catch (error) {
            this.showNotification('Mining stop failed', 'error');
        }
    }

    startMiningStatsUpdate() {
        this.miningUpdateInterval = setInterval(async () => {
            try {
                const response = await fetch('/api/mining_stats');
                const stats = await response.json();
                
                document.getElementById('generated-lamports').textContent = stats.generated_lamports.toLocaleString();
                document.getElementById('puzzles-solved').textContent = stats.puzzles_solved.toLocaleString();
                document.getElementById('active-threads').textContent = stats.active_threads;
                document.getElementById('mining-difficulty').textContent = stats.difficulty;
                
                // Update performance monitor
                document.getElementById('perf-lamports-per-sec').textContent = 
                    Math.round(stats.performance.lamports_per_second || 0).toLocaleString();
            } catch (error) {
                console.error('Failed to update mining stats:', error);
            }
        }, 1000);
    }

    stopMiningStatsUpdate() {
        if (this.miningUpdateInterval) {
            clearInterval(this.miningUpdateInterval);
            this.miningUpdateInterval = null;
        }
    }

    async startStressTest() {
        const duration = parseInt(document.getElementById('stress-duration').value);
        const concurrentTrades = parseInt(document.getElementById('concurrent-trades').value);
        
        const button = event.target;
        button.disabled = true;
        button.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Stress Testing...';
        
        try {
            this.showNotification(`Starting stress test: ${concurrentTrades} concurrent trades for ${duration}s`, 'info');
            
            const response = await fetch('/api/stress_test_drift', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    duration_seconds: duration,
                    concurrent_trades: concurrentTrades
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                const results = data.stress_test_results;
                
                // Update stress test results
                document.getElementById('stress-results').classList.remove('hidden');
                document.getElementById('trades-per-second').textContent = results.trades_per_second.toFixed(2);
                document.getElementById('success-rate').textContent = (results.success_rate * 100).toFixed(1) + '%';
                document.getElementById('total-trades').textContent = results.total_trades_attempted.toLocaleString();
                
                // Update performance monitor
                document.getElementById('perf-trades-per-sec').textContent = results.trades_per_second.toFixed(1);
                document.getElementById('perf-success-rate').textContent = (results.success_rate * 100).toFixed(1) + '%';
                document.getElementById('perf-avg-execution').textContent = 
                    (results.average_execution_time * 1000).toFixed(1) + 'ms';
                
                this.showNotification(
                    `Stress test completed: ${results.trades_per_second.toFixed(2)} trades/second!`, 
                    'success'
                );
                
                // Log detailed results
                console.log('Stress Test Results:', results);
            } else {
                this.showNotification(data.error, 'error');
            }
        } catch (error) {
            this.showNotification('Stress test failed', 'error');
        } finally {
            button.disabled = false;
            button.innerHTML = '<i class="fas fa-rocket mr-2"></i>Start Stress Test';
        }
    }

    async startProductionMM() {
        const button = event.target;
        button.disabled = true;
        button.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Starting...';
        
        try {
            const response = await fetch('/api/start_production_mm', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showNotification(`Production MM started: ${data.wallet_address.slice(0, 8)}...`, 'success');
                document.getElementById('production-mm-stats').classList.remove('hidden');
                this.startProductionMMStatsUpdate();
            } else {
                this.showNotification(data.error, 'error');
            }
        } catch (error) {
            this.showNotification('Failed to start Production MM', 'error');
        } finally {
            button.disabled = false;
            button.innerHTML = '<i class="fas fa-play mr-2"></i>Start Production MM';
        }
    }

    startProductionMMStatsUpdate() {
        this.productionMMUpdateInterval = setInterval(async () => {
            try {
                const response = await fetch('/api/production_mm_stats');
                const data = await response.json();
                
                if (data.success) {
                    const stats = data.stats.performance;
                    document.getElementById('bundles-sent').textContent = stats.bundles_sent.toLocaleString();
                    document.getElementById('bundle-success-rate').textContent = stats.success_rate.toFixed(1) + '%';
                    document.getElementById('realized-pnl').textContent = '$' + stats.realized_pnl.toFixed(4);
                    document.getElementById('mm-position').textContent = stats.position.toFixed(3) + ' SOL';
                }
            } catch (error) {
                console.error('Failed to update Production MM stats:', error);
            }
        }, 2000);
    }

    async startUltimateStressTest() {
        const duration = parseInt(document.getElementById('ultimate-duration').value);
        const concurrentTrades = parseInt(document.getElementById('ultimate-concurrent').value);
        const enableProductionMM = document.getElementById('enable-production-mm').value === 'true';
        
        const button = event.target;
        button.disabled = true;
        button.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Running Ultimate Test...';
        
        try {
            this.showNotification(
                `Starting ULTIMATE stress test: ${concurrentTrades} concurrent trades for ${duration}s`, 
                'info'
            );
            
            const response = await fetch('/api/ultimate_stress_test', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    duration_seconds: duration,
                    concurrent_trades: concurrentTrades,
                    enable_production_mm: enableProductionMM
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                const results = data.ultimate_results;
                
                // Update ultimate results display
                document.getElementById('ultimate-results').classList.remove('hidden');
                document.getElementById('ultimate-ops-per-sec').textContent = 
                    results.combined_performance.total_operations_per_second.toFixed(2);
                document.getElementById('net-lamports').textContent = 
                    results.combined_performance.net_lamports.toLocaleString();
                document.getElementById('ultimate-efficiency').textContent = 
                    results.combined_performance.efficiency.toFixed(1) + '%';
                
                // Show detailed breakdown
                console.log('ULTIMATE STRESS TEST RESULTS:', results);
                
                this.showNotification(
                    `ULTIMATE test completed: ${results.combined_performance.total_operations_per_second.toFixed(2)} ops/sec!`, 
                    'success'
                );
                
                // Update performance monitor with ultimate results
                document.getElementById('perf-trades-per-sec').textContent = 
                    results.combined_performance.total_operations_per_second.toFixed(1);
                document.getElementById('perf-success-rate').textContent = 
                    results.combined_performance.efficiency.toFixed(1) + '%';
            } else {
                this.showNotification(data.error, 'error');
            }
        } catch (error) {
            this.showNotification('Ultimate stress test failed', 'error');
        } finally {
            button.disabled = false;
            button.innerHTML = '<i class="fas fa-fire mr-2"></i>Start Ultimate Stress Test';
        }
    }

    async executeZeroBalanceTrade() {
        if (!this.selectedProtocol) {
            this.showNotification('Please select a trading protocol', 'warning');
            return;
        }
        
        const tradeData = {
            protocol: this.selectedProtocol,
            from_token: document.getElementById('from-token').value,
            to_token: document.getElementById('to-token').value,
            amount: parseFloat(document.getElementById('trade-amount').value),
            leverage: parseInt(document.getElementById('leverage').value)
        };
        
        try {
            this.showNotification('Executing zero-balance trade...', 'info');
            
            const response = await fetch('/api/zero_balance_trade', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(tradeData)
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.addTransaction({
                    protocol: this.selectedProtocol,
                    from: tradeData.from_token,
                    to: tradeData.to_token,
                    amount: tradeData.amount,
                    status: 'success',
                    timestamp: new Date().toISOString(),
                    txHash: result.trade_id,
                    autoSigned: true,
                    zeroBalance: true,
                    gasCost: result.gas_cost_lamports
                });
                
                this.showNotification(
                    `Zero-balance trade executed! Gas cost: ${result.gas_cost_lamports} lamports`, 
                    'success'
                );
            } else {
                this.showNotification(`Trade failed: ${result.error}`, 'error');
            }
        } catch (error) {
            this.showNotification('Zero-balance trade failed', 'error');
        }
    }

    async updatePerformanceMonitor() {
        try {
            const response = await fetch('/api/trade_performance');
            const data = await response.json();
            
            // Update performance metrics
            document.getElementById('perf-trades-per-sec').textContent = 
                data.trade_performance.trades_per_second.toFixed(2);
            document.getElementById('perf-success-rate').textContent = 
                (data.trade_performance.success_rate * 100).toFixed(1) + '%';
            document.getElementById('perf-avg-execution').textContent = 
                (data.trade_performance.average_execution_time * 1000).toFixed(1) + 'ms';
        } catch (error) {
            console.error('Failed to update performance monitor:', error);
        }
    }

    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `fixed top-4 right-4 px-6 py-3 rounded-lg shadow-lg z-50 ${
            type === 'success' ? 'bg-green-600' :
            type === 'error' ? 'bg-red-600' :
            type === 'warning' ? 'bg-yellow-600' :
            'bg-blue-600'
        } text-white`;
        notification.innerHTML = `
            <div class="flex items-center">
                <i class="fas ${
                    type === 'success' ? 'fa-check-circle' :
                    type === 'error' ? 'fa-exclamation-circle' :
                    type === 'warning' ? 'fa-exclamation-triangle' :
                    'fa-info-circle'
                } mr-2"></i>
                ${message}
            </div>
        `;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.style.opacity = '0';
            notification.style.transition = 'opacity 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }
}

// Global functions for onclick handlers
function selectProtocol(protocol) {
    window.trader.selectProtocol(protocol);
}

function connectEthereumWallet() {
    window.trader.connectEthereumWallet();
}

function connectSolanaWallet() {
    window.trader.connectSolanaWallet();
}

function saveApiKeys() {
    window.trader.saveApiKeys();
}

function updateLeverageDisplay(value) {
    window.trader.updateLeverageDisplay(value);
}

function executeTrade(event) {
    window.trader.executeTrade(event);
}

function startMining() {
    window.trader.startMining();
}

function stopMining() {
    window.trader.stopMining();
}

function startStressTest() {
    window.trader.startStressTest();
}

function executeZeroBalanceTrade() {
    window.trader.executeZeroBalanceTrade();
}

function startProductionMM() {
    window.trader.startProductionMM();
}

function startUltimateStressTest() {
    window.trader.startUltimateStressTest();
}

// Initialize the app
document.addEventListener('DOMContentLoaded', () => {
    window.trader = new DecentralizedTrader();
    
    // Start performance monitor updates
    setInterval(() => {
        window.trader.updatePerformanceMonitor();
    }, 2000);
});
