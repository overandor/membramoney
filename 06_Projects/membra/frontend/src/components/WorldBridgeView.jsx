import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { Globe, MapPin, Home, Car, Shirt, Wrench, Store } from 'lucide-react'

const assetIcons = {
  apartment: Home,
  vehicle: Car,
  window: Store,
  tool: Wrench,
  wearable: Shirt,
}

export default function WorldBridgeView() {
  const [assets, setAssets] = useState([])
  const [loading, setLoading] = useState(true)

  async function load() {
    try {
      const data = await api.getWorldAssets()
      setAssets(data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  if (loading) return <div className="text-slate-500 text-sm">Loading WorldBridge...</div>

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-amber-100">WorldBridge</h2>
        <p className="text-xs text-slate-500">Real-world assets → inventory → revenue</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {assets.length === 0 && (
          <p className="text-xs text-slate-500 col-span-full">No world assets registered. POST /v1/world-assets to register.</p>
        )}
        {assets.map((a) => {
          const Icon = assetIcons[a.asset_type] || Globe
          return (
            <div key={a.world_asset_id} className="bg-[#0f1525] border border-[#1a2035] rounded-xl p-4 hover:border-amber-500/20 transition-colors">
              <div className="flex items-center gap-2 mb-2">
                <Icon className="w-4 h-4 text-amber-400" />
                <span className="text-[10px] text-slate-500 uppercase">{a.asset_type}</span>
              </div>
              <div className="text-sm font-medium text-amber-100">{a.title}</div>
              <div className="text-[10px] text-slate-500 mt-1">{a.description}</div>
              {a.capabilities && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {a.capabilities.map((cap) => (
                    <span key={cap} className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400">{cap}</span>
                  ))}
                </div>
              )}
              <div className="flex items-center gap-1 mt-2 text-[10px] text-slate-500">
                <MapPin className="w-3 h-3" />
                {a.latitude?.toFixed(2)}, {a.longitude?.toFixed(2)}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
