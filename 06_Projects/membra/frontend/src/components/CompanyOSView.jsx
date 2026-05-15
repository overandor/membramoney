import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { Boxes, Users, FileText, Building2, AlertCircle } from 'lucide-react'

export default function CompanyOSView() {
  const [data, setData] = useState({ departments: [], agents: [], tasks: [], jobs: [] })
  const [loading, setLoading] = useState(true)

  async function load() {
    try {
      const [departments, agents, tasks, jobs] = await Promise.all([
        api.getDepartments(),
        api.getAgents(),
        api.getTasks(),
        api.getJobs(),
      ])
      setData({ departments, agents, tasks, jobs })
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  if (loading) return <div className="text-slate-500 text-sm">Loading CompanyOS…</div>

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-amber-100">CompanyOS</h2>
        <p className="text-xs text-slate-500">AI → roles → tasks → proof → governance → execution</p>
      </div>

      {/* Agent Registry */}
      <section className="bg-[#0f1525] border border-[#1a2035] rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Users className="w-4 h-4 text-amber-400" />
          <h3 className="text-sm font-medium text-amber-200">Agent Registry</h3>
          <span className="text-[10px] text-slate-500 ml-auto">{data.agents.length} registered</span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {data.agents.length === 0 && (
            <p className="text-xs text-slate-500 col-span-full">No agents registered yet. POST /v1/agents to register.</p>
          )}
          {data.agents.map((a) => (
            <div key={a.agent_id} className="bg-[#060914] border border-[#1a2035] rounded-lg p-3">
              <div className="text-xs font-medium text-amber-100">{a.name}</div>
              <div className="text-[10px] text-slate-500">{a.role}</div>
              <div className="text-[10px] text-emerald-400 mt-1 capitalize">{a.status}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Tasks */}
      <section className="bg-[#0f1525] border border-[#1a2035] rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Boxes className="w-4 h-4 text-amber-400" />
          <h3 className="text-sm font-medium text-amber-200">Orchestration</h3>
          <span className="text-[10px] text-slate-500 ml-auto">{data.tasks.length} tasks</span>
        </div>
        <div className="space-y-2">
          {data.tasks.length === 0 && (
            <p className="text-xs text-slate-500">No tasks yet. POST /v1/tasks to create.</p>
          )}
          {data.tasks.slice(0, 8).map((t) => (
            <div key={t.task_id} className="flex items-center justify-between bg-[#060914] border border-[#1a2035] rounded-lg p-3">
              <div>
                <div className="text-xs text-amber-100">{t.title}</div>
                <div className="text-[10px] text-slate-500">{t.assignee_type} • {t.priority}</div>
              </div>
              <span className={`text-[10px] px-2 py-0.5 rounded-full ${
                t.status === 'completed' ? 'bg-emerald-500/10 text-emerald-400' :
                t.status === 'in_progress' ? 'bg-amber-500/10 text-amber-400' :
                'bg-slate-700/30 text-slate-400'
              }`}>{t.status}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Jobs */}
      <section className="bg-[#0f1525] border border-[#1a2035] rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <FileText className="w-4 h-4 text-amber-400" />
          <h3 className="text-sm font-medium text-amber-200">JobOS</h3>
          <span className="text-[10px] text-slate-500 ml-auto">{data.jobs.length} jobs</span>
        </div>
        <div className="space-y-2">
          {data.jobs.length === 0 && (
            <p className="text-xs text-slate-500">No jobs yet. POST /v1/jobs to create.</p>
          )}
          {data.jobs.slice(0, 6).map((j) => (
            <div key={j.job_id} className="flex items-center justify-between bg-[#060914] border border-[#1a2035] rounded-lg p-3">
              <div>
                <div className="text-xs text-amber-100">{j.title}</div>
                <div className="text-[10px] text-slate-500">{j.job_type}</div>
              </div>
              <div className="text-right">
                <div className="text-xs text-emerald-400">${(j.reward_cents / 100).toFixed(2)}</div>
                <div className="text-[10px] text-slate-500">{j.status}</div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Departments */}
      <section className="bg-[#0f1525] border border-[#1a2035] rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Building2 className="w-4 h-4 text-amber-400" />
          <h3 className="text-sm font-medium text-amber-200">Departments</h3>
          <span className="text-[10px] text-slate-500 ml-auto">{data.departments.length} departments</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {data.departments.length === 0 && (
            <p className="text-xs text-slate-500 col-span-full">No departments yet. POST /v1/departments to create.</p>
          )}
          {data.departments.map((d) => (
            <div key={d.department_id} className="bg-[#060914] border border-[#1a2035] rounded-lg p-3">
              <div className="text-xs font-medium text-amber-100">{d.name}</div>
              <div className="text-[10px] text-slate-500">{d.description || 'No description'}</div>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
