import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { BookOpen, Hash, CheckCircle, XCircle } from 'lucide-react'

export default function ProofBookView() {
  const [records, setRecords] = useState([])
  const [loading, setLoading] = useState(true)

  async function load() {
    try {
      const data = await api.getProofRecords()
      setRecords(data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  if (loading) return <div className="text-slate-500 text-sm">Loading ProofBook...</div>

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-amber-100">ProofBook</h2>
        <p className="text-xs text-slate-500">Immutable SHA-256 audit ledger</p>
      </div>

      <div className="bg-[#0f1525] border border-[#1a2035] rounded-xl overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-[#1a2035] text-slate-500">
              <th className="text-left p-3">Type</th>
              <th className="text-left p-3">Record ID</th>
              <th className="text-left p-3">Hash</th>
              <th className="text-left p-3">Status</th>
              <th className="text-left p-3">Created</th>
            </tr>
          </thead>
          <tbody>
            {records.length === 0 && (
              <tr><td colSpan={5} className="p-6 text-center text-slate-500">No proof records yet.</td></tr>
            )}
            {records.map((r) => (
              <tr key={r.proof_id} className="border-b border-[#1a2035] hover:bg-[#1a2035]/30">
                <td className="p-3">
                  <span className="px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400">{r.record_type}</span>
                </td>
                <td className="p-3 text-slate-300 font-mono">{r.record_id}</td>
                <td className="p-3 text-slate-400 font-mono text-[10px]">{r.hash}</td>
                <td className="p-3">
                  {r.verified ? (
                    <span className="flex items-center gap-1 text-emerald-400"><CheckCircle className="w-3 h-3" /> Verified</span>
                  ) : (
                    <span className="flex items-center gap-1 text-slate-500"><XCircle className="w-3 h-3" /> Pending</span>
                  )}
                </td>
                <td className="p-3 text-slate-500">{new Date(r.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
