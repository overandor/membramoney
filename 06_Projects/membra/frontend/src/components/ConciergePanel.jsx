import { useState } from 'react'
import { api } from '../api/client'
import { Send, Bot, User, Lightbulb } from 'lucide-react'

export default function ConciergePanel() {
  const [message, setMessage] = useState('')
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    if (!message.trim()) return
    const userMsg = message.trim()
    setHistory((h) => [...h, { role: 'user', text: userMsg }])
    setMessage('')
    setLoading(true)
    try {
      const res = await api.postIntent({ message: userMsg })
      setHistory((h) => [...h, {
        role: 'concierge',
        text: `Parsed objective: ${res.parsed_objective}`,
        actions: res.suggested_actions || [],
      }])
    } catch (err) {
      setHistory((h) => [...h, { role: 'concierge', text: `Error: ${err.message}`, actions: [] }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="h-full flex flex-col max-w-3xl mx-auto">
      <div className="mb-4">
        <h2 className="text-xl font-semibold text-amber-100">IntentOS Concierge</h2>
        <p className="text-xs text-slate-500 mt-1">Describe what you have or need. MEMBRA structures it into objectives, tasks, and marketplace actions.</p>
      </div>

      <div className="flex-1 bg-[#0f1525] border border-[#1a2035] rounded-xl p-4 overflow-y-auto space-y-4 min-h-[400px]">
        {history.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-slate-500 gap-3">
            <Bot className="w-10 h-10 text-amber-500/30" />
            <p className="text-sm">Say something like:</p>
            <div className="space-y-2 text-xs text-center">
              <p className="bg-[#060914] border border-[#1a2035] rounded-lg px-4 py-2">"I have a window and a car, how can I earn?"</p>
              <p className="bg-[#060914] border border-[#1a2035] rounded-lg px-4 py-2">"I need someone to help move boxes tomorrow"</p>
              <p className="bg-[#060914] border border-[#1a2035] rounded-lg px-4 py-2">"Show me my KPI dashboard"</p>
            </div>
          </div>
        )}
        {history.map((m, i) => (
          <div key={i} className={`flex gap-3 ${m.role === 'user' ? 'flex-row-reverse' : ''}`}>
            <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 ${
              m.role === 'user' ? 'bg-amber-500/10' : 'bg-emerald-500/10'
            }`}>
              {m.role === 'user' ? <User className="w-3.5 h-3.5 text-amber-400" /> : <Bot className="w-3.5 h-3.5 text-emerald-400" />}
            </div>
            <div className={`max-w-[80%] rounded-xl px-4 py-2.5 text-xs ${
              m.role === 'user'
                ? 'bg-amber-500/10 text-amber-100 border border-amber-500/20'
                : 'bg-[#060914] text-slate-300 border border-[#1a2035]'
            }`}>
              <p>{m.text}</p>
              {m.actions && m.actions.length > 0 && (
                <div className="mt-2 space-y-1">
                  <p className="text-[10px] text-slate-500 uppercase tracking-wider">Suggested Actions</p>
                  {m.actions.map((a, j) => (
                    <div key={j} className="flex items-center gap-2 text-[11px] text-emerald-400">
                      <Lightbulb className="w-3 h-3" />
                      <span>{a.action}: {a.description}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex gap-3">
            <div className="w-7 h-7 rounded-full bg-emerald-500/10 flex items-center justify-center">
              <Bot className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
            </div>
            <div className="bg-[#060914] border border-[#1a2035] rounded-xl px-4 py-2.5 text-xs text-slate-500">
              Parsing intent…
            </div>
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit} className="mt-4 flex gap-2">
        <input
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="What do you have or need?"
          className="flex-1 bg-[#0f1525] border border-[#1a2035] rounded-lg px-4 py-2.5 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-amber-500/30 transition-colors"
        />
        <button
          type="submit"
          disabled={loading}
          className="px-4 py-2.5 bg-amber-500/10 border border-amber-500/20 rounded-lg text-amber-400 hover:bg-amber-500/20 transition-colors disabled:opacity-50"
        >
          <Send className="w-4 h-4" />
        </button>
      </form>
    </div>
  )
}
