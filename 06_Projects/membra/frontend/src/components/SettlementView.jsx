import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { DollarSign, CreditCard, Clock, CheckCircle } from 'lucide-react'

export default function SettlementView() {
  const [eligibilities, setEligibilities] = useState([])
  const [loading, setLoading] = useState(true)

  async function load() {
    try {
      const data = await api.getSettlementEligibility()
      setEligibilities(data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  if (loading) return <div className="text-slate-500 text-sm">Loading SettlementOS...</div>

  const totalPending = eligibilities
    .filter((e) => e.status === 'pending')
    .reduce((sum, e) => sum + e.amount_cents, 0)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-amber-100">SettlementOS</h2>
        <p className="text-xs text-slate-500">Payout eligibility & external rails</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-[#0f1525] border border-[#1a2035] rounded-xl p-5">
          <div className="text-[10px] text-slate-500 uppercase">Total Pending</div>
          <div className="text-2xl font-semibold text-amber-100 mt-1">${(totalPending / 100).toFixed(2)}</div>
        </div>
        <div className="bg-[#0f1525] border border-[#1a2035] rounded-xl p-5">
          <div className="text-[10px] text-slate-500 uppercase">Records</div>
          <div className="text-2xl font-semibold text-amber-100 mt-1">{eligibilities.length}</div>
        </div>
        <div className="bg-[#0f1525] border border-[#1a2035] rounded-xl p-5">
          <div className="text-[10px] text-slate-500 uppercase">External Rails</div>
          <div className="text-2xl font-semibold text-amber-100 mt-1">
            {new Set(eligibilities.map((e) => e.settlement_rail).filter(Boolean)).size}
          </div>
        </div>
      </div>

      <div className="bg-[#0f1525] border border-[#1a2035] rounded-xl overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-[#1a2035] text-slate-500">
              <th className="text-left p-3">Party</th>
              <th className="text-left p-3">Type</th>
              <th className="text-left p-3">Amount</th>
              <th className="text-left p-3">Status</th>
              <th className="text-left p-3">Rail</th>
            </tr>
          </thead>
          <tbody>
            {eligibilities.length === 0 && (
              <tr><td colSpan={5} className="p-6 text-center text-slate-500">No settlement records yet.</td></tr>
            )}
            {eligibilities.map((e) => (
              <tr key={e.eligibility_id} className="border-b border-[#1a2035] hover:bg-[#1a2035]/30">
                <td className="p-3 text-slate-300 font-mono">{e.party_id}</td>
                <td className="p-3 text-slate-400">{e.party_type}</td>
                <td className="p-3 text-emerald-400">${(e.amount_cents / 100).toFixed(2)}</td>
                <td className="p-3">
                  <span className={`px-2 py-0.5 rounded-full ${
                    e.status === 'paid' ? 'bg-emerald-500/10 text-emerald-400' :
                    e.status === 'pending' ? 'bg-amber-500/10 text-amber-400' :
                    'bg-slate-700/30 text-slate-400'
                  }`}>{e.status}</span>
                </td>
                <td className="p-3 text-slate-500">{e.settlement_rail || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
