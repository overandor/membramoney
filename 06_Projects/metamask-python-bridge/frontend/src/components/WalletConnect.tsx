import { useState } from 'react'

interface WalletConnectProps {
  isConnected: boolean
  walletAddress: string
  onConnect: (address: string) => void
  onDisconnect: () => void
}

export default function WalletConnect({
  isConnected,
  walletAddress,
  onConnect,
  onDisconnect,
}: WalletConnectProps) {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string>('')

  const handleConnect = async () => {
    setIsLoading(true)
    setError('')

    try {
      // Check if MetaMask is installed
      if (!(window as any).ethereum) {
        setError('MetaMask is not installed. Please install MetaMask to continue.')
        setIsLoading(false)
        return
      }

      // Request account access
      const accounts = await (window as any).ethereum.request({
        method: 'eth_requestAccounts',
      })

      if (accounts && accounts.length > 0) {
        onConnect(accounts[0])
      }
    } catch (err) {
      setError('Failed to connect wallet. Please try again.')
      console.error(err)
    } finally {
      setIsLoading(false)
    }
  }

  const handleDisconnect = () => {
    onDisconnect()
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-white mb-4">Wallet Connection</h2>
        <p className="text-white/80 mb-6">
          Connect your MetaMask wallet to interact with the Python backend
        </p>
      </div>

      {!isConnected ? (
        <div className="space-y-4">
          <button
            onClick={handleConnect}
            disabled={isLoading}
            className="w-full bg-white text-purple-600 px-6 py-3 rounded-lg font-semibold hover:bg-white/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            {isLoading ? 'Connecting...' : 'Connect MetaMask'}
          </button>

          {error && (
            <div className="bg-red-500/20 border border-red-500 text-red-200 px-4 py-3 rounded-lg">
              {error}
            </div>
          )}

          <div className="bg-white/10 rounded-lg p-4 space-y-2">
            <h3 className="font-semibold text-white">Why connect your wallet?</h3>
            <ul className="text-white/80 text-sm space-y-1 list-disc list-inside">
              <li>Sign transactions securely with MetaMask</li>
              <li>Deploy smart contracts</li>
              <li>Execute trading strategies</li>
              <li>View portfolio analytics</li>
            </ul>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="bg-green-500/20 border border-green-500 text-green-200 px-4 py-3 rounded-lg">
            ✓ Wallet connected successfully
          </div>

          <div className="bg-white/10 rounded-lg p-4 space-y-2">
            <div>
              <span className="text-white/60 text-sm">Connected Address:</span>
              <p className="text-white font-mono text-sm break-all">
                {walletAddress}
              </p>
            </div>
          </div>

          <button
            onClick={handleDisconnect}
            className="w-full bg-red-500/20 border border-red-500 text-red-200 px-6 py-3 rounded-lg font-semibold hover:bg-red-500/30 transition-all"
          >
            Disconnect Wallet
          </button>
        </div>
      )}
    </div>
  )
}
