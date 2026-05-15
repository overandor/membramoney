import { useState } from 'react'
import { Routes, Route, Link, useLocation } from 'react-router-dom'
import Dashboard from './components/Dashboard'
import CompanyOSView from './components/CompanyOSView'
import ConciergePanel from './components/ConciergePanel'
import GovernanceView from './components/GovernanceView'
import WorldBridgeView from './components/WorldBridgeView'
import ProofBookView from './components/ProofBookView'
import SettlementView from './components/SettlementView'
import { LayoutDashboard, Boxes, MessageSquare, Shield, Globe, BookOpen, DollarSign } from 'lucide-react'

const navItems = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/company', label: 'CompanyOS', icon: Boxes },
  { path: '/worldbridge', label: 'WorldBridge', icon: Globe },
  { path: '/proofbook', label: 'ProofBook', icon: BookOpen },
  { path: '/settlement', label: 'Settlement', icon: DollarSign },
  { path: '/governance', label: 'Governance', icon: Shield },
  { path: '/concierge', label: 'Concierge', icon: MessageSquare },
]

function Sidebar() {
  const location = useLocation()
  return (
    <aside className="w-56 bg-[#0b0f1a] border-r border-[#1a2035] flex flex-col fixed h-full z-40">
      <div className="p-5 flex items-center gap-3 border-b border-[#1a2035]">
        <div className="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
          <span className="text-amber-400 font-bold text-sm">M</span>
        </div>
        <div>
          <h1 className="text-sm font-semibold text-amber-100">MEMBRA</h1>
          <p className="text-[10px] text-amber-500/60 uppercase tracking-wider">CompanyOS</p>
        </div>
      </div>
      <nav className="flex-1 p-3 space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon
          const active = location.pathname === item.path
          return (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-medium transition-all ${
                active
                  ? 'bg-amber-500/10 text-amber-300 border border-amber-500/20'
                  : 'text-slate-400 hover:bg-[#1a2035] hover:text-slate-200'
              }`}
            >
              <Icon className="w-4 h-4" />
              {item.label}
            </Link>
          )
        })}
      </nav>
      <div className="p-4 border-t border-[#1a2035]">
        <a
          href="http://localhost:8000/docs"
          target="_blank"
          rel="noreferrer"
          className="text-[10px] text-slate-500 hover:text-amber-400 transition-colors"
        >
          API Docs →
        </a>
      </div>
    </aside>
  )
}

function GovernanceView() {
  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-amber-100">GovernanceOS</h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          { title: 'Policies', desc: 'Active risk and consent policies' },
          { title: 'Approvals', desc: 'Pending and resolved approval gates' },
          { title: 'Audit Events', desc: 'Immutable decision trail' },
        ].map((card) => (
          <div key={card.title} className="bg-[#0f1525] border border-[#1a2035] rounded-xl p-5 hover:border-amber-500/20 transition-colors">
            <h3 className="text-sm font-medium text-amber-200">{card.title}</h3>
            <p className="text-xs text-slate-500 mt-1">{card.desc}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

function App() {
  return (
    <div className="min-h-screen bg-[#060914] text-slate-300 flex">
      <Sidebar />
      <main className="flex-1 ml-56 p-6 overflow-auto">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/company" element={<CompanyOSView />} />
          <Route path="/worldbridge" element={<WorldBridgeView />} />
          <Route path="/proofbook" element={<ProofBookView />} />
          <Route path="/settlement" element={<SettlementView />} />
          <Route path="/governance" element={<GovernanceView />} />
          <Route path="/concierge" element={<ConciergePanel />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
