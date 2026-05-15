import { TrendingUp } from 'lucide-react'

export default function TopHostsTable({ data }) {
  if (!data.length) {
    return <p className="text-slate-500 text-xs">No data</p>
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-xs">
        <thead>
          <tr className="border-b border-[#1a2035] text-slate-500">
            <th className="py-2 font-medium">Host</th>
            <th className="py-2 font-medium text-right">Assets</th>
            <th className="py-2 font-medium text-right">Revenue</th>
          </tr>
        </thead>
        <tbody>
          {data.map((h, i) => (
            <tr key={h.user_id} className="border-b border-[#1a2035]/50 hover:bg-[#1a2035]/30 transition-colors">
              <td className="py-2">
                <div className="flex items-center gap-2">
                  <span className="text-slate-500 w-4">{i + 1}</span>
                  <div>
                    <div className="text-slate-200 font-medium truncate max-w-[120px]">{h.name}</div>
                    <div className="text-slate-500">{h.email}</div>
                  </div>
                </div>
              </td>
              <td className="py-2 text-right text-slate-300 tabular-nums">{h.asset_count}</td>
              <td className="py-2 text-right">
                <div className="flex items-center justify-end gap-1 text-emerald-400">
                  <TrendingUp className="w-3 h-3" />
                  <span className="tabular-nums">${h.revenue_usd.toLocaleString()}</span>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
