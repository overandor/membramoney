import { useMemo } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid
} from 'recharts'

export default function TimeSeriesChart({ data }) {
  const chartData = useMemo(() => {
    return data.map((d) => ({
      day: d.day?.slice(5) ?? '',
      Visits: d.visits ?? 0,
      Payments: d.payment_count ?? 0,
      Revenue: Math.round((d.authorized_cents ?? 0) / 100),
    }))
  }, [data])

  if (!data.length) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-500 text-sm">
        No data available
      </div>
    )
  }

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <defs>
            <linearGradient id="colorVisits" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="colorPayments" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis dataKey="day" stroke="#64748b" fontSize={11} tickLine={false} axisLine={false} />
          <YAxis stroke="#64748b" fontSize={11} tickLine={false} axisLine={false} />
          <Tooltip
            contentStyle={{
              backgroundColor: '#1e293b',
              border: '1px solid #334155',
              borderRadius: '8px',
              fontSize: '12px',
              color: '#e2e8f0',
            }}
            itemStyle={{ color: '#e2e8f0' }}
          />
          <Area type="monotone" dataKey="Visits" stroke="#f59e0b" fillOpacity={1} fill="url(#colorVisits)" strokeWidth={2} />
          <Area type="monotone" dataKey="Payments" stroke="#3b82f6" fillOpacity={1} fill="url(#colorPayments)" strokeWidth={2} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
