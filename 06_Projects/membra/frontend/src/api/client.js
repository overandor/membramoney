const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/v1'

async function get(path) {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`HTTP ${res.status}: ${text}`)
  }
  return res.json()
}

async function post(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`HTTP ${res.status}: ${text}`)
  }
  return res.json()
}

async function patch(path, body = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`HTTP ${res.status}: ${text}`)
  }
  return res.json()
}

export const api = {
  // KPI
  getSummary: () => get('/kpi/summary'),
  getTimeseries: (days = 30) => get(`/kpi/timeseries?days=${days}`),
  getTopAssets: (limit = 10) => get(`/kpi/top-assets?limit=${limit}`),
  getTopHosts: (limit = 10) => get(`/kpi/top-hosts?limit=${limit}`),

  // OrchestrationOS
  getObjectives: (params = '') => get(`/objectives${params}`),
  getTasks: (params = '') => get(`/tasks${params}`),
  createObjective: (body) => post('/objectives', body),
  createTask: (body) => post('/tasks', body),

  // AgentOS
  getAgents: (params = '') => get(`/agents${params}`),
  createAgent: (body) => post('/agents', body),

  // JobOS
  getJobs: (params = '') => get(`/jobs${params}`),
  createJob: (body) => post('/jobs', body),

  // CompanyOS
  getDepartments: () => get('/departments'),
  getSOPs: (params = '') => get(`/sops${params}`),
  getOperatingUnits: (params = '') => get(`/operating-units${params}`),

  // GovernanceOS
  getPolicies: (params = '') => get(`/policies${params}`),
  getApprovals: (params = '') => get(`/approvals${params}`),
  getAuditEvents: (params = '') => get(`/audit-events${params}`),

  // ProofBook
  getProofRecords: (params = '') => get(`/proof-records${params}`),

  // SettlementOS
  getSettlementEligibility: (params = '') => get(`/settlement-eligibility${params}`),

  // WorldBridge
  getWorldAssets: (params = '') => get(`/world-assets${params}`),

  // IntentOS / Concierge
  postIntent: (body) => post('/intent', body),

  // Production Boundaries
  getProductionBoundaries: () => get('/system/production-boundaries'),
}
