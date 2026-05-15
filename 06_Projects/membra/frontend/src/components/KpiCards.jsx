import { Users, Building2, Calendar, DollarSign, Shield, AlertTriangle, Megaphone, Shirt } from 'lucide-react'

const cardDefs = [
  { key: 'identity', icon: Users, title: 'Users', fields: ['total_users', 'verified_users'] },
  { key: 'assets', icon: Building2, title: 'Assets', fields: ['total_assets', 'active_assets'] },
  { key: 'visits', icon: Calendar, title: 'Visits', fields: ['total_visits'] },
  { key: 'payments', icon: DollarSign, title: 'Revenue', fields: ['revenue_usd', 'platform_fees_usd'] },
  { key: 'insurance', icon: Shield, title: 'Insurance', fields: ['total_coverages', 'active_coverages'] },
  { key: 'incidents', icon: AlertTriangle, title: 'Incidents', fields: ['total_incidents', 'total_claims'] },
  { key: 'ads', icon: Megaphone, title: 'Campaigns', fields: ['total_campaigns', 'active_campaigns'] },
  { key: 'wear', icon: Shirt, title: 'Wear', fields: ['total_wearers', 'total_wearables'] },
]

export default function KpiCards({ summary }) {
  if (!summary) return null

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {cardDefs.map((def) => {
        const data = summary[def.key]
        if (!data) return null
        const Icon = def.icon
        return (
          <div key={def.key} className="bg-[#0f1525] border border-[#1a2035] rounded-xl p-4 hover:border-amber-500/20 transition-colors">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-7 h-7 rounded-lg bg-amber-500/10 flex items-center justify-center">
                <Icon className="w-4 h-4 text-amber-400" />
              </div>
              <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">{def.title}</span>
            </div>
            <div className="space-y-1">
              {def.fields.map((field) => {
                const value = data[field]
                const label = field.replace(/_/g, ' ')
                return (
                  <div key={field} className="flex items-baseline justify-between">
                    <span className="text-[10px] text-slate-500 capitalize">{label}</span>
                    <span className="text-sm font-semibold text-white tabular-nums">
                      {typeof value === 'number' && field.includes('usd') ? `$${value.toLocaleString()}` : value?.toLocaleString?.() ?? value}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>
        )
      })}
    </div>
  )
}
