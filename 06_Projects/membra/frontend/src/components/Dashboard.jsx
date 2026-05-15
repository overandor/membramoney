import { useEffect, useState } from 'react'
import { api } from '../api/client'
import KpiCards from './KpiCards'
import TimeSeriesChart from './TimeSeriesChart'
import TopAssetsTable from './TopAssetsTable'
import TopHostsTable from './TopHostsTable'
import { RefreshCw, AlertCircle } from 'lucide-react'

export default function Dashboard() {
  const [summary, setSummary] = useState(null)
  const [timeseries, setTimeseries] = useState([])
  const [topAssets, setTopAssets] = useState([])
  const [topHosts, setTopHosts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  async function loadAll() {
    setLoading(true)
    setError(null)
    try {
      const [s, ts, ta, th] = await Promise.all([
        api.getSummary(),
        api.getTimeseries(30),
        api.getTopAssets(10),
        api.getTopHosts(10),
      ])
      setSummary(s)
      setTimeseries(ts)
      setTopAssets(ta)
      setTopHosts(th)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadAll()
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <RefreshCw className="w-8 h-8 animate-spin text-amber-400" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-96 gap-3">
        <AlertCircle className="w-10 h-10 text-red-400" />
        <p className="text-red-300 text-sm">{error}</p>
        <button
          onClick={loadAll}
          className="px-4 py-2 rounded-lg bg-amber-500/10 text-amber-400 text-sm hover:bg-amber-500/20 transition-colors"
        >
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-amber-100">MEMBRA Dashboard</h2>
        <button
          onClick={loadAll}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#0f1525] border border-[#1a2035] text-slate-300 text-sm hover:bg-[#1a2035] transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      <KpiCards summary={summary} />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-[#0f1525] border border-[#1a2035] rounded-xl p-5">
          <h3 className="text-sm font-medium text-amber-200 mb-4">Activity (30 days)</h3>
          <TimeSeriesChart data={timeseries} />
        </div>
        <div className="space-y-6">
          <div className="bg-[#0f1525] border border-[#1a2035] rounded-xl p-5">
            <h3 className="text-sm font-medium text-amber-200 mb-4">Top Assets by Revenue</h3>
            <TopAssetsTable data={topAssets} />
          </div>
          <div className="bg-[#0f1525] border border-[#1a2035] rounded-xl p-5">
            <h3 className="text-sm font-medium text-amber-200 mb-4">Top Hosts by Revenue</h3>
            <TopHostsTable data={topHosts} />
          </div>
        </div>
      </div>
    </div>
  )
}
