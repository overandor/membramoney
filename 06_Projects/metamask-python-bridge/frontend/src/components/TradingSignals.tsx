import { useState, useEffect } from 'react'

interface TradingSignalsProps {
  walletAddress: string
}

interface TradeSignal {
  action: string
  target_contract: string
  calldata_params: Record<string, unknown>
  rationale: string
  estimated_gas: number
  expected_profit: number
  risk_level: string
}

export default function TradingSignals({ walletAddress }: TradingSignalsProps) {
  const [signals, setSignals] = useState<TradeSignal[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')

  const fetchSignals = async () => {
    setIsLoading(true)
    setError('')

    try {
      const response = await fetch('http://localhost:8000/api/strategy/signals')
      const data = await response.json()

      if (response.ok) {
        setSignals(data.signals || [])
      } else {
        setError(data.message || 'Failed to fetch trading signals')
      }
    } catch (err) {
      setError('Failed to connect to backend. Is the server running?')
      console.error(err)
    } finally {
      setIsLoading(false)
    }
  }

  const handleExecuteSignal = async (signal: TradeSignal) => {
    // TODO: Use MetaMask to sign and broadcast the transaction
    alert(`Executing ${signal.action} on ${signal.target_contract}. MetaMask signing will be implemented.`)
  }

  useEffect(() => {
    fetchSignals()
  }, [])

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-white mb-2">Trading Signals</h2>
          <p className="text-white/80">
            Python-generated trading strategies with user approval
          </p>
        </div>
        <button
          onClick={fetchSignals}
          disabled={isLoading}
          className="bg-white/20 text-white px-4 py-2 rounded-lg hover:bg-white/30 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
        >
          {isLoading ? 'Loading...' : 'Refresh'}
        </button>
      </div>

      {error && (
        <div className="bg-red-500/20 border border-red-500 text-red-200 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      {signals.length === 0 && !isLoading && !error && (
        <div className="bg-white/10 rounded-lg p-8 text-center">
          <p className="text-white/60">No trading signals available</p>
        </div>
      )}

      <div className="space-y-4">
        {signals.map((signal, index) => (
          <div
            key={index}
            className="bg-white/10 rounded-lg p-4 space-y-4 border border-white/10"
          >
            <div className="flex justify-between items-start">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <span
                    className={`px-2 py-1 rounded text-xs font-semibold ${
                      signal.action === 'buy'
                        ? 'bg-green-500/20 text-green-200'
                        : signal.action === 'sell'
                        ? 'bg-red-500/20 text-red-200'
                        : 'bg-gray-500/20 text-gray-200'
                    }`}
                  >
                    {signal.action.toUpperCase()}
                  </span>
                  <span
                    className={`px-2 py-1 rounded text-xs font-semibold ${
                      signal.risk_level === 'low'
                        ? 'bg-blue-500/20 text-blue-200'
                        : signal.risk_level === 'medium'
                        ? 'bg-yellow-500/20 text-yellow-200'
                        : 'bg-red-500/20 text-red-200'
                    }`}
                  >
                    {signal.risk_level.toUpperCase()} RISK
                  </span>
                </div>

                <div className="space-y-2">
                  <div>
                    <span className="text-white/60 text-sm">Target Contract:</span>
                    <p className="text-white font-mono text-sm break-all">
                      {signal.target_contract}
                    </p>
                  </div>

                  <div>
                    <span className="text-white/60 text-sm">Rationale:</span>
                    <p className="text-white text-sm">{signal.rationale}</p>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <span className="text-white/60 text-sm">Expected Profit:</span>
                      <p className="text-white font-semibold">
                        {(signal.expected_profit * 100).toFixed(2)}%
                      </p>
                    </div>
                    <div>
                      <span className="text-white/60 text-sm">Estimated Gas:</span>
                      <p className="text-white font-semibold">
                        {signal.estimated_gas.toLocaleString()}
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              <button
                onClick={() => handleExecuteSignal(signal)}
                className="bg-white text-purple-600 px-4 py-2 rounded-lg font-semibold hover:bg-white/90 transition-all ml-4"
              >
                Execute
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
