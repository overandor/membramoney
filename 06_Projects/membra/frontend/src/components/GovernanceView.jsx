import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { Shield, FileText, CheckCircle, XCircle, AlertTriangle, Activity } from 'lucide-react'

export default function GovernanceView() {
  const [policies, setPolicies] = useState([])
  const [approvals, setApprovals] = useState([])
  const [auditEvents, setAuditEvents] = useState([])
  const [loading, setLoading] = useState(true)

  async function load() {
    try {
      const [p, a, ae] = await Promise.all([
        api.getPolicies(),
        api.getApprovals(),
        api.getAuditEvents(),
      ])
      setPolicies(p)
      setApprovals(a)
      setAuditEvents(ae)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  if (loading) return <div className="text-slate-500 text-sm">Loading GovernanceOS...</div>

  const pending = approvals.filter((a) => a.status === 'pending')
  const approved = approvals.filter((a) => a.status === 'approved')
  const rejected = approvals.filter((a) => a.status === 'rejected')

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-amber-100">GovernanceOS</h2>
        <p className="text-xs text-slate-500">Policies, approvals, and audit trails</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-[#0f1525] border border-[#1a2035] rounded-xl p-4">
          <div className="text-[10px] text-slate-500 uppercase">Policies</div>
          <div className="text-xl font-semibold text-amber-100 mt-1">{policies.length}</div>
        </div>
        <div className="bg-[#0f1525] border border-[#1a2035] rounded-xl p-4">
          <div className="text-[10px] text-slate-500 uppercase">Pending</div>
          <div className="text-xl font-semibold text-amber-400 mt-1">{pending.length}</div>
        </div>
        <div className="bg-[#0f1525] border border-[#1a2035] rounded-xl p-4">
          <div className="text-[10px] text-slate-500 uppercase">Approved</div>
          <div className="text-xl font-semibold text-emerald-400 mt-1">{approved.length}</div>
        </div>
        <div className="bg-[#0f1525] border border-[#1a2035] rounded-xl p-4">
          <div className="text-[10px] text-slate-500 uppercase">Rejected</div>
          <div className="text-xl font-semibold text-red-400 mt-1">{rejected.length}</div>
        </div>
      </div>

      <section className="bg-[#0f1525] border border-[#1a2035] rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Shield className="w-4 h-4 text-amber-400" />
          <h3 className="text-sm font-medium text-amber-200">Active Policies</h3>
        </div>
        <div className="space-y-2">
          {policies.length === 0 && <p className="text-xs text-slate-500">No policies yet.</p>}
          {policies.map((p) => (
            <div key={p.policy_id} className="flex items-start gap-3 bg-[#060914] border border-[#1a2035] rounded-lg p-3">
              <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              <div>
                <div className="text-xs font-medium text-amber-100">{p.name}</div>
                <div className="text-[10px] text-slate-500 mt-0.5">v{p.version} • {p.description || 'No description'}</div>
                {p.rules && (
                  <div className="mt-1 text-[10px] text-slate-400">
                    Rule: {p.rules.rule || JSON.stringify(p.rules)}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="bg-[#0f1525] border border-[#1a2035] rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <FileText className="w-4 h-4 text-amber-400" />
          <h3 className="text-sm font-medium text-amber-200">Approval Queue</h3>
        </div>
        <div className="space-y-2">
          {approvals.length === 0 && <p className="text-xs text-slate-500">No approvals yet.</p>}
          {approvals.slice(0, 10).map((a) => (
            <div key={a.approval_id} className="flex items-center justify-between bg-[#060914] border border-[#1a2035] rounded-lg p-3">
              <div>
                <div className="text-xs text-amber-100">{a.request_type}</div>
                <div className="text-[10px] text-slate-500">{a.reason}</div>
              </div>
              <div className="text-right">
                <span className={`text-[10px] px-2 py-0.5 rounded-full ${
                  a.status === 'approved' ? 'bg-emerald-500/10 text-emerald-400' :
                  a.status === 'rejected' ? 'bg-red-500/10 text-red-400' :
                  'bg-amber-500/10 text-amber-400'
                }`}>{a.status}</span>
                <div className="text-[10px] text-slate-500 mt-1">risk: {a.risk_score}</div>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="bg-[#0f1525] border border-[#1a2035] rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Activity className="w-4 h-4 text-amber-400" />
          <h3 className="text-sm font-medium text-amber-200">Recent Audit Events</h3>
        </div>
        <div className="space-y-2">
          {auditEvents.length === 0 && <p className="text-xs text-slate-500">No audit events yet.</p>}
          {auditEvents.slice(0, 10).map((e) => (
            <div key={e.event_id} className="flex items-center gap-3 bg-[#060914] border border-[#1a2035] rounded-lg p-3">
              <CheckCircle className="w-3 h-3 text-slate-500 shrink-0" />
              <div className="flex-1">
                <div className="text-[11px] text-slate-300"><span className="text-amber-400">{e.event_type}</span> by {e.actor_id}</div>
                <div className="text-[10px] text-slate-500">{e.target_type}/{e.target_id}</div>
              </div>
              <div className="text-[10px] text-slate-500">{new Date(e.created_at).toLocaleDateString()}</div>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
