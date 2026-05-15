import { useState, useEffect } from 'react'

interface PortfolioDashboardProps {
  walletAddress: string
}

interface Position {
  token: string
  amount: number
  value_usd: number
  pnl_usd: number
}

interface PortfolioSummary {
  total_value_usd: number
  positions: Position[]
  last_updated: string
}

interface PortfolioAnalytics {
  daily_pnl: number
  weekly_pnl: number
  monthly_pnl: number
  win_rate: number
  sharpe_ratio: number
  max_drawdown: number
}

export default function PortfolioDashboard({ walletAddress }: PortfolioDashboardProps) {
  const [summary, setSummary] = useState<PortfolioSummary | null>(null)
  const [analytics, setAnalytics] = useState<PortfolioAnalytics | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')

  const fetchPortfolioData = async () => {
    setIsLoading(true)
    setError('')

    try {
      const [summaryRes, analyticsRes] = await Promise.all([
        fetch('http://localhost:8000/api/portfolio/summary'),
        fetch('http://localhost:8000/api/portfolio/analytics'),
      ])

      const summaryData = await summaryRes.json()
      const analyticsData = await analyticsRes.json()

      if (summaryRes.ok && analyticsRes.ok) {
        setSummary(summaryData)
        setAnalytics(analyticsData)
      } else {
        setError('Failed to fetch portfolio data')
      }
    } catch (err) {
      setError('Failed to connect to backend. Is the server running?')
      console.error(err)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchPortfolioData()
  }, [])

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-white mb-2">Portfolio Dashboard</h2>
          <p className="text-white/80">
            Real-time portfolio analytics and performance metrics
          </p>
        </div>
        <button
          onClick={fetchPortfolioData}
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

      {summary && (
        <div className="space-y-4">
          {/* Total Value */}
          <div className="bg-white/10 rounded-lg p-6 border border-white/10">
            <div>
              <span className="text-white/60 text-sm">Total Portfolio Value</span>
              <p className="text-4xl font-bold text-white">
                ${summary.total_value_usd.toLocaleString()}
              </p>
              <p className="text-white/60 text-sm mt-1">
                Last updated: {new Date(summary.last_updated).toLocaleString()}
              </p>
            </div>
          </div>

          {/* Positions */}
          <div className="bg-white/10 rounded-lg p-6 border border-white/10">
            <h3 className="text-xl font-semibold text-white mb-4">Positions</h3>
            <div className="space-y-3">
              {summary.positions.map((position, index) => (
                <div
                  key={index}
                  className="bg-black/20 rounded-lg p-4 flex justify-between items-center"
                >
                  <div>
                    <p className="text-white font-semibold">{position.token}</p>
                    <p className="text-white/60 text-sm">
                      {position.amount.toLocaleString()} tokens
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-white font-semibold">
                      ${position.value_usd.toLocaleString()}
                    </p>
                    <p
                      className={`text-sm ${
                        position.pnl_usd >= 0 ? 'text-green-400' : 'text-red-400'
                      }`}
                    >
                      {position.pnl_usd >= 0 ? '+' : ''}
                      ${position.pnl_usd.toLocaleString()}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Analytics */}
          {analytics && (
            <div className="bg-white/10 rounded-lg p-6 border border-white/10">
              <h3 className="text-xl font-semibold text-white mb-4">Analytics</h3>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                <div className="bg-black/20 rounded-lg p-4">
                  <span className="text-white/60 text-sm">Daily P&L</span>
                  <p
                    className={`text-2xl font-bold ${
                      analytics.daily_pnl >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}
                  >
                    {analytics.daily_pnl >= 0 ? '+' : ''}
                    ${analytics.daily_pnl.toLocaleString()}
                  </p>
                </div>

                <div className="bg-black/20 rounded-lg p-4">
                  <span className="text-white/60 text-sm">Weekly P&L</span>
                  <p
                    className={`text-2xl font-bold ${
                      analytics.weekly_pnl >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}
                  >
                    {analytics.weekly_pnl >= 0 ? '+' : ''}
                    ${analytics.weekly_pnl.toLocaleString()}
                  </p>
                </div>

                <div className="bg-black/20 rounded-lg p-4">
                  <span className="text-white/60 text-sm">Monthly P&L</span>
                  <p
                    className={`text-2xl font-bold ${
                      analytics.monthly_pnl >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}
                  >
                    {analytics.monthly_pnl >= 0 ? '+' : ''}
                    ${analytics.monthly_pnl.toLocaleString()}
                  </p>
                </div>

                <div className="bg-black/20 rounded-lg p-4">
                  <span className="text-white/60 text-sm">Win Rate</span>
                  <p className="text-2xl font-bold text-white">
                    {(analytics.win_rate * 100).toFixed(1)}%
                  </p>
                </div>

                <div className="bg-black/20 rounded-lg p-4">
                  <span className="text-white/60 text-sm">Sharpe Ratio</span>
                  <p className="text-2xl font-bold text-white">
                    {analytics.sharpe_ratio.toFixed(2)}
                  </p>
                </div>

                <div className="bg-black/20 rounded-lg p-4">
                  <span className="text-white/60 text-sm">Max Drawdown</span>
                  <p
                    className={`text-2xl font-bold ${
                      analytics.max_drawdown >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}
                  >
                    {analytics.max_drawdown >= 0 ? '+' : ''}
                    {(analytics.max_drawdown * 100).toFixed(2)}%
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
