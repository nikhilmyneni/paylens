export const API_BASE = (import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')

export type Outcome = 'unexplained_gap' | 'pay_outside_band' | 'missing_effective_band' | 'expired_band_used' | 'fte_ignored' | 'missing_fx' | 'incomparable_group' | 'unapproved_adjustment' | 'insufficient_comparators' | 'reviewed_no_action'

export interface Summary {
  total_employees: number
  flagged: number
  exceptions: number
  proposals: number
  by_outcome: Record<string, number>
  as_of?: string
  latest_run?: string
}

export interface Comparison {
  id: string
  employee_id: string
  display_name: string
  role: string
  level: string
  location: string
  annual_fte: number
  currency: string | null
  compa_ratio: number | null
  band_position?: number | null
  residual_pct: number | null
  expected_annual?: number | null
  peer_count: number
  outcome: Outcome
  explanation: string
  band_id?: string | null
  salary_id?: string
}

export interface ComparisonPage {
  items: Comparison[]
  total: number
}

export interface Timeline {
  employee: { id: string; display_name: string; hire_date?: string; status?: string }
  comparisons?: Comparison[]
  salaries?: Array<{ id: string; effective_month: string; monthly_amount: number; currency: string; event_kind?: string }>
  assignments?: Array<{ id: string; role_id: string; level_id: string; location_id: string; fte: number; effective_from: string; effective_to: string | null }>
  proposals?: Array<{ id: string; state: string; proposed_annual: number; currency: string; rationale: string; version: number }>
  events?: Array<{ id: string; next_state?: string; action?: string; actor: string; reason?: string; occurred_at: string }>
}

export interface EvaluationReport {
  available: boolean
  reason?: string
  run_id?: string
  as_of?: string
  basis?: 'synthetic_injection_labels'
  population?: number
  labelled_cases?: number
  metrics?: { tp: number; fp: number; fn: number; tn: number; precision: number | null; recall: number | null; f1: number | null }
  by_issue?: Array<{ issue_type: string; support: number; tp: number; fp: number; fn: number; precision: number | null; recall: number | null; f1: number | null }>
  missed_cases?: Array<{ employee_id: string; expected: string; actual: string }>
  extra_flags?: Array<{ employee_id: string; actual: string }>
  limitations?: string[]
}

export interface QualityReport {
  run_id: string
  as_of: string
  status: 'passed' | 'attention'
  counts: Record<string, number>
  error_count: number
  errors: Array<{ type: string; [key: string]: unknown }>
  coverage: { employees: number; compared: number; excluded: number; percent: number }
  analysis_issues: Array<{ employee_id: string; issue_type: string; detail: string }>
  checks: Array<{ name: string; status: 'passed' | 'failed'; count: number }>
  source: 'synthetic'
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  })
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`
    try { const body = await response.json(); detail = body.detail || detail } catch { /* response may not be JSON */ }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return response.json() as Promise<T>
}

export const api = {
  summary: () => request<Summary>('/api/v1/summary'),
  evaluation: () => request<EvaluationReport>('/api/v1/evaluation'),
  quality: () => request<QualityReport>('/api/v1/quality'),
  comparisons: (outcome: string, q: string, offset: number, limit = 12) => {
    const p = new URLSearchParams({ offset: String(offset), limit: String(limit) })
    if (outcome) p.set('outcome', outcome)
    if (q.trim()) p.set('q', q.trim())
    return request<ComparisonPage>(`/api/v1/comparisons?${p.toString()}`)
  },
  timeline: (employeeId: string) => request<Timeline>(`/api/v1/employees/${encodeURIComponent(employeeId)}/timeline`),
  createProposal: (comparisonId: string, proposedAnnual: number, currency: string, rationale: string) => request<{ id: string; state: string }>('/api/v1/proposals', {
    method: 'POST',
    body: JSON.stringify({ comparison_id: comparisonId, proposed_annual: proposedAnnual, currency, rationale }),
  }),
  transition: (proposalId: string, action: 'submit' | 'decision' | 'apply', body: object, role: 'hr' | 'manager') => request<{ id: string; state: string }>(`/api/v1/proposals/${encodeURIComponent(proposalId)}/${action}`, {
    method: 'POST', headers: { 'X-Role': role, 'X-Actor': `demo-${role}` }, body: JSON.stringify(body),
  }),
}
