import { useState } from 'react'
import WalletConnect from './components/WalletConnect'
import DeploymentPanel from './components/DeploymentPanel'
import TradingSignals from './components/TradingSignals'
import PortfolioDashboard from './components/PortfolioDashboard'

type Tab = 'wallet' | 'deploy' | 'signals' | 'portfolio'

function App() {
  const [activeTab, setActiveTab] = useState<Tab>('wallet')
  const [isConnected, setIsConnected] = useState(false)
  const [walletAddress, setWalletAddress] = useState<string>('')

  const handleWalletConnect = (address: string) => {
    setWalletAddress(address)
    setIsConnected(true)
  }

  const handleWalletDisconnect = () => {
    setWalletAddress('')
    setIsConnected(false)
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-600 to-blue-500">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <header className="mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">
            MetaMask Python Bridge
          </h1>
          <p className="text-white/80">
            Python intelligence backend with MetaMask-powered execution
          </p>
        </header>

        {/* Navigation */}
        <nav className="mb-8">
          <div className="flex space-x-2 bg-white/10 rounded-lg p-2 backdrop-blur-sm">
            {[
              { id: 'wallet' as Tab, label: 'Wallet Connect' },
              { id: 'deploy' as Tab, label: 'Deploy' },
              { id: 'signals' as Tab, label: 'Trading Signals' },
              { id: 'portfolio' as Tab, label: 'Portfolio' },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-2 rounded-lg transition-all ${
                  activeTab === tab.id
                    ? 'bg-white text-purple-600 font-semibold'
                    : 'text-white hover:bg-white/20'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </nav>

        {/* Content */}
        <div className="bg-white/10 backdrop-blur-sm rounded-lg p-6">
          {!isConnected && activeTab !== 'wallet' && (
            <div className="text-center py-12">
              <p className="text-white text-lg mb-4">
                Please connect your wallet to continue
              </p>
              <button
                onClick={() => setActiveTab('wallet')}
                className="bg-white text-purple-600 px-6 py-2 rounded-lg font-semibold hover:bg-white/90"
              >
                Connect Wallet
              </button>
            </div>
          )}

          {activeTab === 'wallet' && (
            <WalletConnect
              isConnected={isConnected}
              walletAddress={walletAddress}
              onConnect={handleWalletConnect}
              onDisconnect={handleWalletDisconnect}
            />
          )}

          {isConnected && activeTab === 'deploy' && (
            <DeploymentPanel walletAddress={walletAddress} />
          )}

          {isConnected && activeTab === 'signals' && (
            <TradingSignals walletAddress={walletAddress} />
          )}

          {isConnected && activeTab === 'portfolio' && (
            <PortfolioDashboard walletAddress={walletAddress} />
          )}
        </div>

        {/* Footer */}
        <footer className="mt-8 text-center text-white/60 text-sm">
          <p>MetaMask Python Bridge v1.0.0</p>
        </footer>
      </div>
    </div>
  )
}

export default App
