import { useEffect, useState } from 'react'
import { CompensationSlider } from './CompensationSlider'
import type { FormEvent } from 'react'
import {
  ArrowLeft, ArrowRight, ChartBar, CheckCircle, ClockCounterClockwise, Files,
  MagnifyingGlass, Plus, ShieldCheck, WarningCircle, X, Sun, Moon, CaretDown,
} from '@phosphor-icons/react'
import { api, type Comparison, type EvaluationReport, type QualityReport, type Summary, type Timeline } from './api'

type InboxMode = 'unexplained_gap' | 'exception' | ''
type Surface = 'review' | 'evaluation' | 'quality'
type DetailTab = 'comparison' | 'history' | 'decisions'
type Action = 'submit' | 'approve' | 'reject' | 'apply'
type Proposal = NonNullable<Timeline['proposals']>[number]
type ThemePreference = 'system' | 'light' | 'dark'

function systemTheme(): 'light' | 'dark' {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

const exceptionOutcomes = ['missing_effective_band', 'expired_band_used', 'fte_ignored', 'missing_fx', 'incomparable_group', 'unapproved_adjustment', 'missing_fx_rate', 'invalid_band', 'incorrect_fx'] as const

const qualityInventory = [
  { title: 'People & job structure', entries: [
    ['employee', 'Employees'], ['role', 'Roles'], ['level', 'Levels'], ['location', 'Locations'],
    ['employee_assignment', 'Job assignments'], ['tenure', 'Tenure records'], ['promotion', 'Promotions'],
  ] },
  { title: 'Compensation & evidence', entries: [
    ['compensation_band', 'Pay bands'], ['salary_record', 'Salary records'],
    ['performance_evidence', 'Performance records'], ['fx_rate', 'Currency rates'],
  ] },
  { title: 'Review & audit', entries: [
    ['analysis_run', 'Analysis runs'], ['comparison_result', 'Comparisons'],
    ['analysis_issue', 'Analysis issues'], ['adjustment_proposal', 'Proposals'],
    ['proposal_event', 'Proposal events'], ['audit_event', 'Audit events'],
    ['source_decision', 'Source decisions'], ['id_counter', 'ID sequences'],
  ] },
] as const
const knownQualityKeys = new Set<string>(qualityInventory.flatMap(group => group.entries.map(([key]) => key)))

const issueNames: Record<string, string> = {
  unexplained_gap: 'Pay gap', pay_outside_band: 'Outside band',
  missing_effective_band: 'Missing band', expired_band_used: 'Expired band',
  fte_ignored: 'FTE mismatch', missing_fx: 'Missing FX rate',
  incomparable_group: 'Wrong peer group', unapproved_adjustment: 'Unapproved adjustment',
  insufficient_comparators: 'Few comparators', reviewed_no_action: 'Within expectation',
  missing_fx_rate: 'Missing FX rate', invalid_band: 'Invalid band', incorrect_fx: 'Incorrect FX conversion',
}

const money = (value: number | null | undefined, currency: string | null | undefined = 'USD') => {
  if (value == null) return 'Unavailable'
  if (!currency) return `${value.toLocaleString('en-US', { maximumFractionDigits: 0 })} (currency unavailable)`
  try { return new Intl.NumberFormat('en-US', { style: 'currency', currency, maximumFractionDigits: 0 }).format(value) }
  catch { return `${value.toLocaleString('en-US', { maximumFractionDigits: 0 })} (currency unavailable)` }
}
const percent = (value: number | null | undefined) =>
  value == null ? 'Unavailable' : `${value > 0 ? '+' : ''}${(value * 100).toFixed(1)}%`
const score = (value: number | null | undefined) => value == null ? '—' : `${(value * 100).toFixed(1)}%`
const dateLabel = (value?: string) => value ? new Date(value).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '—'

function App() {
  const [themePreference, setThemePreference] = useState<ThemePreference>(() => {
    try {
      const saved = window.localStorage.getItem('compass-theme')
      return saved === 'dark' || saved === 'light' ? saved : 'system'
    } catch { return 'system' }
  })
  const [themeMenuOpen, setThemeMenuOpen] = useState(false)
  const [effectiveTheme, setEffectiveTheme] = useState<'light' | 'dark'>(() => document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light')
  const [surface, setSurface] = useState<Surface>('review')
  const [mode, setMode] = useState<InboxMode>('unexplained_gap')
  const [query, setQuery] = useState('')
  const [search, setSearch] = useState('')
  const [listEdge, setListEdge] = useState<'top' | 'middle' | 'bottom'>('top')
  const [offset, setOffset] = useState(0)
  const [summary, setSummary] = useState<Summary | null>(null)
  const [evaluation, setEvaluation] = useState<EvaluationReport | null>(null)
  const [quality, setQuality] = useState<QualityReport | null>(null)
  const [reportLoading, setReportLoading] = useState(false)
  const [reportError, setReportError] = useState('')
  const [records, setRecords] = useState<Comparison[]>([])
  const [total, setTotal] = useState(0)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [timeline, setTimeline] = useState<Timeline | null>(null)
  const [tab, setTab] = useState<DetailTab>('comparison')
  const [mobileDetailOpen, setMobileDetailOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [reloadKey, setReloadKey] = useState(0)
  const [proposalOpen, setProposalOpen] = useState(false)
  const [proposedAmount, setProposedAmount] = useState('')
  const [proposalReason, setProposalReason] = useState('')
  const [pendingAction, setPendingAction] = useState<{ proposal: Proposal; action: Action } | null>(null)
  const [actionReason, setActionReason] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const sync = () => {
      if (themePreference !== 'system') return
      const next = media.matches ? 'dark' : 'light'
      document.documentElement.dataset.theme = next
      setEffectiveTheme(next)
    }
    media.addEventListener('change', sync)
    return () => media.removeEventListener('change', sync)
  }, [themePreference])

  function chooseTheme(nextPreference: ThemePreference, origin?: HTMLElement) {
    const next = nextPreference === 'system' ? systemTheme() : nextPreference
    const apply = () => {
      document.documentElement.dataset.theme = next
      try { window.localStorage.setItem('compass-theme', nextPreference) } catch { /* theme still works for this tab */ }
      setThemePreference(nextPreference)
      setEffectiveTheme(next)
      setThemeMenuOpen(false)
    }
    const motionAllowed = !window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const transitionDocument = document as Document & { startViewTransition?: (update: () => void) => { ready: Promise<void> } }
    if (!motionAllowed || !transitionDocument.startViewTransition || next === effectiveTheme) { apply(); return }
    const rect = origin?.getBoundingClientRect()
    const x = rect ? rect.left + rect.width / 2 : window.innerWidth - 55
    const y = rect ? rect.top + rect.height / 2 : 34
    const radius = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y))
    const transition = transitionDocument.startViewTransition(apply)
    transition.ready.then(() => {
      document.documentElement.animate(
        { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`] },
        { duration: 520, easing: 'cubic-bezier(.2,.75,.25,1)', pseudoElement: '::view-transition-new(root)' }
      )
    }).catch(() => undefined)
  }

  useEffect(() => {
    const timer = window.setTimeout(() => { setSearch(query.trim()); setOffset(0) }, 260)
    return () => window.clearTimeout(timer)
  }, [query])

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    Promise.all([api.summary(), api.comparisons(mode, search, offset, 15)])
      .then(([nextSummary, page]) => {
        if (!active) return
        setSummary(nextSummary)
        setRecords(page.items)
        setTotal(page.total)
        setSelectedId(current => page.items.some(item => item.id === current) ? current : page.items[0]?.id ?? null)
      })
      .catch(cause => { if (active) setError(cause instanceof Error ? cause.message : 'Could not load review records.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [mode, search, offset, reloadKey])

  useEffect(() => {
    if (surface === 'review') return
    let active = true
    setReportLoading(true)
    setReportError('')
    const load = surface === 'evaluation' ? api.evaluation() : api.quality()
    load.then(report => {
      if (!active) return
      if (surface === 'evaluation') setEvaluation(report as EvaluationReport)
      else setQuality(report as QualityReport)
    }).catch(cause => {
      if (active) setReportError(cause instanceof Error ? cause.message : 'Report could not be loaded.')
    }).finally(() => { if (active) setReportLoading(false) })
    return () => { active = false }
  }, [surface, reloadKey])

  const selected = records.find(item => item.id === selectedId) ?? null
  useEffect(() => {
    if (!selected) { setTimeline(null); return }
    let active = true
    setDetailLoading(true)
    setDetailError('')
    setTimeline(null)
    api.timeline(selected.employee_id)
      .then(result => { if (active) setTimeline(result) })
      .catch(cause => { if (active) setDetailError(cause instanceof Error ? cause.message : 'Could not load pay history and decisions.') })
      .finally(() => { if (active) setDetailLoading(false) })
    return () => { active = false }
  }, [selected?.employee_id, reloadKey])

  function changeMode(next: InboxMode) {
    setSurface('review'); setMode(next); setOffset(0); setMobileDetailOpen(false); setProposalOpen(false); setPendingAction(null); setTab('comparison')
  }
  function choose(item: Comparison) {
    setSelectedId(item.id); setMobileDetailOpen(true); setTab('comparison'); setProposalOpen(false); setPendingAction(null)
  }
  function beginProposal() {
    if (!selected || !selected.currency || !selected.band_id || selected.outcome !== 'unexplained_gap') return
    setProposedAmount(String(Math.max(selected.expected_annual ?? selected.annual_fte, selected.annual_fte)))
    setProposalReason('')
    setTab('decisions')
    setProposalOpen(true)
  }
  async function saveProposal(event: FormEvent) {
    event.preventDefault()
    if (!selected || !selected.currency || Number(proposedAmount) <= 0 || proposalReason.trim().length < 12) return
    setSaving(true)
    try {
      const result = await api.createProposal(selected.id, Number(proposedAmount), selected.currency, proposalReason.trim())
      setNotice(`${result.id} saved as a draft.`)
      setProposalOpen(false)
      setReloadKey(key => key + 1)
    } catch (cause) { setNotice(cause instanceof Error ? cause.message : 'Proposal could not be saved.') }
    finally { setSaving(false) }
  }
  function beginAction(proposal: Proposal, action: Action) {
    setPendingAction({ proposal, action }); setActionReason('')
  }
  async function saveAction(event: FormEvent) {
    event.preventDefault()
    if (!pendingAction || actionReason.trim().length < 5) return
    const { proposal, action } = pendingAction
    const endpoint = action === 'approve' || action === 'reject' ? 'decision' : action
    const role = endpoint === 'decision' ? 'manager' : 'hr'
    setSaving(true)
    try {
      const body = { version: proposal.version, reason: actionReason.trim(), ...(endpoint === 'decision' ? { decision: action === 'approve' ? 'approved' : 'rejected' } : {}) }
      const result = await api.transition(proposal.id, endpoint, body, role)
      setNotice(`${proposal.id} is now ${result.state}.`)
      setPendingAction(null)
      setReloadKey(key => key + 1)
    } catch (cause) { setNotice(cause instanceof Error ? cause.message : 'Decision could not be saved.') }
    finally { setSaving(false) }
  }

  const pageStart = total ? offset + 1 : 0
  const pageEnd = Math.min(offset + 15, total)
  const maxPay = selected ? Math.max(selected.annual_fte, selected.expected_annual ?? 0) * 1.1 : 1
  const payWidth = selected ? Math.max(3, selected.annual_fte / maxPay * 100) : 0
  const expectedWidth = selected?.expected_annual ? Math.max(3, selected.expected_annual / maxPay * 100) : 0

  return <div className={`workbench surface-${surface} ${mobileDetailOpen ? 'show-detail' : ''}`}>
    <nav className="rail" aria-label="Primary navigation">
      <div className="rail-brand" title="PayLens compensation review"><img src="/paylens-logo.svg" width="150" height="35" alt="PayLens" /></div>
      <div className="rail-links">
        <button aria-current={surface === 'review' && mode === 'unexplained_gap' ? 'page' : undefined} onClick={() => changeMode('unexplained_gap')} title="Pay gaps"><Files size={21} /><span>Inbox</span></button>
        <button aria-current={surface === 'review' && mode === 'exception' ? 'page' : undefined} onClick={() => changeMode('exception')} title="Exceptions"><WarningCircle size={21} /><span>Issues</span></button>
        <button aria-current={surface === 'review' && mode === '' ? 'page' : undefined} onClick={() => changeMode('')} title="All comparisons"><ClockCounterClockwise size={21} /><span>All</span></button>
        <button aria-current={surface === 'evaluation' ? 'page' : undefined} onClick={() => setSurface('evaluation')} title="Detection evaluation"><ChartBar size={21} /><span>Results</span></button>
        <button aria-current={surface === 'quality' ? 'page' : undefined} onClick={() => setSurface('quality')} title="Data quality"><ShieldCheck size={21} /><span>Quality</span></button>
      </div>
      <div className="rail-end">
        <div className="theme-control">
          <button className="theme-toggle" aria-label={`Switch to ${effectiveTheme === 'dark' ? 'light' : 'dark'} theme`} title={`Switch to ${effectiveTheme === 'dark' ? 'light' : 'dark'} theme`} onClick={event => chooseTheme(effectiveTheme === 'dark' ? 'light' : 'dark', event.currentTarget)}>{effectiveTheme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}</button>
          <button className="theme-options-trigger" aria-label="Choose appearance" aria-expanded={themeMenuOpen} aria-haspopup="true" onClick={() => setThemeMenuOpen(open => !open)}><CaretDown size={12} /></button>
          {themeMenuOpen && <div className="theme-menu" role="group" aria-label="Appearance">{(['system','light','dark'] as const).map(option => <button key={option} aria-pressed={themePreference === option} onClick={event => chooseTheme(option, event.currentTarget)}>{option === 'system' ? 'System' : option === 'light' ? 'Light' : 'Dark'}{themePreference === option && <CheckCircle size={14} />}</button>)}</div>}
        </div>
      </div>
    </nav>

    <header className="context-bar">
      <div className="context-heading"><h1>{surface === 'review' ? 'Review studio' : surface === 'evaluation' ? 'Evaluation' : 'Data quality'}</h1></div>
      <div className="context-metrics" aria-label="Current review counts"><button onClick={() => changeMode('unexplained_gap')} className={surface === 'review' && mode === 'unexplained_gap' ? 'is-active' : ''}><b>{summary ? (summary.by_outcome.unexplained_gap ?? 0) : '—'}</b><span>Pay gaps</span></button><button onClick={() => changeMode('exception')} className={surface === 'review' && mode === 'exception' ? 'is-active' : ''}><b>{summary ? exceptionOutcomes.reduce((count, outcome) => count + (summary.by_outcome[outcome] ?? 0), 0) : '—'}</b><span>Data issues</span></button><button onClick={() => changeMode('')} className={surface === 'review' && mode === '' ? 'is-active' : ''}><b>{summary?.total_employees ?? '—'}</b><span>Employees</span></button></div>
      <span className="context-provenance">SYNTHETIC DATA</span>
    </header>

    <section className="inbox" aria-label="Compensation review inbox">
      <div className="inbox-head">
        <div className="inbox-brandline"><span className="seed-tag">{loading && !records.length ? 'LOADING' : `${total} RECORDS`}</span></div>
        <h2>{mode === 'unexplained_gap' ? 'Pay gaps to review' : mode === 'exception' ? 'Issues to resolve' : 'All comparisons'}</h2>
        <p>Select a person to inspect their pay evidence.</p>
      </div>
      <div className="inbox-tools">
        <label className="search"><MagnifyingGlass size={18} aria-hidden="true" /><span className="sr-only">Search employee</span><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search employee or ID" /></label>
      </div>
      {error && <div className="fetch-error" role="alert"><WarningCircle size={18} /><p>{error}<br /><button onClick={() => setReloadKey(key => key + 1)}>Try again</button></p></div>}
      <div className={`employee-list edge-${listEdge}`} role="list" aria-busy={loading} onScroll={event => { const node = event.currentTarget; setListEdge(node.scrollTop <= 4 ? 'top' : node.scrollTop + node.clientHeight >= node.scrollHeight - 4 ? 'bottom' : 'middle') }}>
        {loading && !records.length ? Array.from({ length: 5 }, (_, i) => <div className="list-skeleton" key={i}><span /><span /><span /></div>) : records.map(item => <div role="listitem" key={item.id}><button className={`employee-row ${selectedId === item.id ? 'selected' : ''}`} aria-pressed={selectedId === item.id} onClick={() => choose(item)}><span className="row-top"><strong>{item.display_name}</strong><span className="row-gap">{percent(item.residual_pct)}</span></span><span className="row-meta">{item.role} · {item.level}</span><span className="row-bottom"><span>{item.location} <i>·</i> {item.peer_count} peers</span><span className={`issue-pill ${item.outcome === 'unexplained_gap' ? 'gap' : ''}`}>{issueNames[item.outcome] ?? item.outcome}</span></span></button></div>)}
        {!loading && !records.length && !error && <div className="list-empty"><CheckCircle size={25} /><strong>No records in this view</strong><p>Try another category or search for a different employee.</p></div>}
      </div>
      <div className="inbox-footer"><span>{loading && !records.length ? 'Loading records...' : <>{pageStart}–{pageEnd} of {total}</>}</span><div><button aria-label="Previous page" disabled={offset === 0} onClick={() => setOffset(value => Math.max(0, value - 15))}><ArrowLeft size={17} /></button><button aria-label="Next page" disabled={offset + 15 >= total} onClick={() => setOffset(value => value + 15)}><ArrowRight size={17} /></button></div></div>
    </section>

    <main className="detail" aria-label="Employee compensation evidence">
      {selected ? <>
        <div className="detail-header"><button className="mobile-back" onClick={() => setMobileDetailOpen(false)}><ArrowLeft size={18} /> Back to inbox</button><div className="detail-locator">Review record <span>/</span> {selected.employee_id}</div><div className="detail-header-main"><div><h2>{selected.display_name}</h2><p>{selected.role} · {selected.level} · {selected.location}</p><span className={`outcome-tag ${selected.outcome === 'unexplained_gap' ? 'gap' : ''}`}>{issueNames[selected.outcome] ?? selected.outcome}</span></div><div className="headline-gap"><strong>{percent(selected.residual_pct)}</strong><span>from expected pay</span></div></div></div>
        {notice && <div className="notice" role="status"><CheckCircle size={18} /><span>{notice}</span><button aria-label="Dismiss message" onClick={() => setNotice('')}><X size={16} /></button></div>}
        {detailError && <div className="notice detail-error" role="alert"><WarningCircle size={18} /><span>{detailError}</span><button onClick={() => setReloadKey(key => key + 1)}>Retry</button></div>}
        <div className="detail-body">
          <div className="assessment"><div className="assessment-heading"><div><h3>Pay comparison</h3></div><span className="as-of">Salary at analysis date</span></div><p className="assessment-explain">{selected.explanation}</p><div className="comparison-visual" aria-label="Annual full-time equivalent pay compared with expected pay"><div className="pay-line"><div><span>Annual pay (full-time equivalent)</span><strong>{money(selected.annual_fte, selected.currency)}</strong></div><div className="track"><span className="actual-bar" style={{ width: `${payWidth}%` }} /></div></div><div className="pay-line"><div><span>Expected after documented factors</span><strong>{money(selected.expected_annual, selected.currency)}</strong></div><div className="track"><span className="expected-bar" style={{ width: `${expectedWidth}%` }} /></div></div></div>{selected.expected_annual != null && <div className="pay-distance"><span>Annual difference to expected pay</span><strong>{money(Math.abs(selected.expected_annual - selected.annual_fte), selected.currency)} <small>{selected.annual_fte < selected.expected_annual ? "below expectation" : "above expectation"}</small></strong></div>}<div className="assessment-footer"><div><span>Difference from expectation</span><strong className={selected.residual_pct != null && selected.residual_pct < 0 ? 'negative' : ''}>{percent(selected.residual_pct)}</strong></div><div><span>Comparable employees</span><strong>{selected.peer_count}</strong></div><div><span>Pay vs band midpoint</span><strong>{selected.compa_ratio == null ? 'Unavailable' : `${Math.round(selected.compa_ratio * 100)}%`}</strong></div></div></div>

          <div className="detail-tabs" role="tablist" aria-label="Evidence sections"><button role="tab" aria-selected={tab === 'comparison'} onClick={() => setTab('comparison')}>Evidence</button><button role="tab" aria-selected={tab === 'history'} onClick={() => setTab('history')}>Pay history</button><button role="tab" aria-selected={tab === 'decisions'} onClick={() => setTab('decisions')}>Decisions <span>{timeline?.proposals?.length ?? 0}</span></button></div>

          {tab === 'comparison' && <section className="tab-content"><div className="section-title"><h3>Why this employee is comparable</h3><span>Analysis snapshot</span></div><div className="evidence-grid"><div><span>Role</span><strong>{selected.role}</strong></div><div><span>Level</span><strong>{selected.level}</strong></div><div><span>Location</span><strong>{selected.location}</strong></div><div><span>Peer group size</span><strong>{selected.peer_count} employees</strong></div></div><div className="evidence-note"><ShieldCheck size={21} /><p>{selected.outcome === 'unexplained_gap' ? 'Role, level, location, and the salary-date compensation band support this comparison. An adjustment requires a documented reason and approval.' : 'Review the flagged data issue and source records before using this comparison for a pay decision.'}</p></div><details className="technical"><summary>Technical calculation and source IDs</summary><dl><div><dt>Comparison ID</dt><dd>{selected.id}</dd></div><div><dt>Salary record</dt><dd>{selected.salary_id ?? 'Unavailable'}</dd></div><div><dt>Effective band</dt><dd>{selected.band_id ?? 'No valid band'}</dd></div><div><dt>Within-band position</dt><dd>{percent(selected.band_position)}</dd></div></dl></details></section>}

          {tab === 'history' && <section className="tab-content"><div className="section-title"><h3>Salary and assignment history</h3><span>Most recent first</span></div>{detailLoading ? <p className="muted">Loading history…</p> : <><div className="timeline-list">{(timeline?.salaries ?? []).slice(-7).reverse().map(item => <div className="timeline-row" key={item.id}><div><strong>{item.event_kind === 'adjustment' ? 'Adjustment applied' : 'Salary recorded'}</strong><span>{dateLabel(item.effective_month)}</span></div><b>{money(item.monthly_amount, item.currency)} / month</b></div>)}</div><details className="technical"><summary>Assignment changes</summary><div className="assignment-list">{(timeline?.assignments ?? []).slice().reverse().map(item => <div key={item.id}>{item.role_id} · {item.level_id} · {item.location_id} · {Math.round(Number(item.fte) * 100)}% FTE <span>from {dateLabel(item.effective_from)}</span></div>)}</div></details></>}</section>}

          {tab === 'decisions' && <section className="tab-content"><div className="section-title"><h3>Adjustment decisions</h3><span>Append-only trail</span></div><p className="section-intro">Each proposal starts as a draft. A manager approves it before HR applies a pay change.</p>{(timeline?.proposals ?? []).map(proposal => <div className="proposal-row" key={proposal.id}><div className="proposal-top"><strong>{proposal.id}</strong><span className="proposal-state">{proposal.state}</span></div><div className="proposal-amount">{money(proposal.proposed_annual, proposal.currency)} <small>annual full-time equivalent</small></div><p>{proposal.rationale}</p><div className="proposal-actions-inline">{proposal.state === 'draft' && <button className="subtle-button" onClick={() => beginAction(proposal, 'submit')}>Submit for approval <ArrowRight size={16} /></button>}{proposal.state === 'submitted' && <><button className="subtle-button" onClick={() => beginAction(proposal, 'approve')}>Approve <ArrowRight size={16} /></button><button className="text-button" onClick={() => beginAction(proposal, 'reject')}>Reject</button></>}{proposal.state === 'approved' && <button className="subtle-button" onClick={() => beginAction(proposal, 'apply')}>Apply adjustment <ArrowRight size={16} /></button>}</div>{pendingAction?.proposal.id === proposal.id && <form className="inline-form action-form" onSubmit={saveAction}><label>Reason for {pendingAction.action}<textarea required minLength={5} rows={3} value={actionReason} onChange={event => setActionReason(event.target.value)} placeholder="Summarize the evidence for this decision" /></label><div><button type="button" className="text-button" onClick={() => setPendingAction(null)}>Cancel</button><button className="primary-button" type="submit" disabled={saving}>{saving ? 'Saving…' : 'Confirm decision'}</button></div></form>}</div>)}{!detailLoading && !(timeline?.proposals?.length) && <p className="muted">No adjustment proposal has been recorded for this employee.</p>}{proposalOpen && selected.currency && <form className="inline-form proposal-form" onSubmit={saveProposal}><div className="form-header"><div><strong>New adjustment proposal</strong><p>Record the proposed amount and why the evidence supports it.</p></div><button type="button" aria-label="Close proposal" onClick={() => setProposalOpen(false)}><X size={18} /></button></div><CompensationSlider value={proposedAmount} onChange={setProposedAmount} currentAnnual={selected.annual_fte} expectedAnnual={selected.expected_annual} currency={selected.currency} /><label>Reason for adjustment<textarea required minLength={12} rows={4} value={proposalReason} onChange={event => setProposalReason(event.target.value)} placeholder="Cite the pay comparison and any documented factors" /></label><div><button type="button" className="text-button" onClick={() => setProposalOpen(false)}>Cancel</button><button className="primary-button" type="submit" disabled={saving}>{saving ? 'Saving…' : 'Save draft'}</button></div></form>}{(timeline?.events ?? []).length > 0 && <details className="technical audit-trail"><summary>View approval trail</summary><div className="timeline-list">{timeline?.events?.map(event => <div className="timeline-row" key={event.id}><div><strong>{event.next_state ?? event.action}</strong><span>{event.actor} · {dateLabel(event.occurred_at)}</span></div><p>{event.reason}</p></div>)}</div></details>}</section>}
        </div>
        <div className="detail-actionbar"><button className="primary-button" disabled={selected.outcome !== 'unexplained_gap' || !selected.currency || !selected.band_id} title={selected.outcome === 'unexplained_gap' ? undefined : 'Resolve this issue before proposing an adjustment'} onClick={beginProposal}><Plus size={17} /> Propose adjustment</button></div>
      </> : loading ? <div className="detail-skeleton" aria-label="Loading employee evidence"><span /><span /><span /><span /><span /></div> : <div className="detail-placeholder"><Files size={28} /><h2>Select a record</h2><p>Choose an employee from the inbox to review pay evidence and decisions.</p></div>}
    </main>
    <main className="report-page" aria-label={surface === 'evaluation' ? 'Evaluation results' : 'Data quality report'}>
      <div className="report-masthead"><span>PAYLENS / ASSURANCE</span><span>{surface === 'evaluation' ? evaluation?.run_id ?? '—' : quality?.run_id ?? '—'}</span></div>
      <div className="report-hero"><div><p className="report-kicker">{surface === 'evaluation' ? 'DETECTION EVALUATION' : 'DATA QUALITY'}</p><h1>{surface === 'evaluation' ? 'Detection against synthetic labels.' : 'Validation and coverage.'}</h1><p>{surface === 'evaluation' ? 'Compare review flags with separate synthetic labels. Labels are used only for evaluation.' : 'Review joins, coverage, validation checks, and exceptions for this analysis run.'}</p></div><button className="report-refresh" onClick={() => setReloadKey(key => key + 1)}>Refresh report <ArrowRight size={16} /></button></div>
      {reportLoading && <div className="report-skeleton" aria-label="Loading report"><span /><span /><span /><span /></div>}
      {reportError && !reportLoading && <div className="report-error" role="alert"><WarningCircle size={22} /><div><strong>Report unavailable</strong><p>{reportError}</p></div><button onClick={() => setReloadKey(key => key + 1)}>Try again</button></div>}
      {surface === 'evaluation' && !reportLoading && !reportError && evaluation && (evaluation.available ? <>
        <section className="report-scoreline" aria-label="Evaluation metrics"><div><span>Precision</span><strong>{score(evaluation.metrics?.precision)}</strong><small>Flagged cases that match a label</small></div><div><span>Recall</span><strong>{score(evaluation.metrics?.recall)}</strong><small>Labelled cases detected</small></div><div><span>F1 score</span><strong>{score(evaluation.metrics?.f1)}</strong><small>Balance of precision and recall</small></div></section>
        <div className="report-grid"><section className="report-section"><div className="report-section-head"><h2>By issue type</h2><span>{evaluation.labelled_cases ?? 0} labelled cases</span></div><div className="report-table-wrap"><table><thead><tr><th>Issue</th><th>Cases</th><th>Found</th><th>Precision</th><th>Recall</th></tr></thead><tbody>{(evaluation.by_issue ?? []).map(item => <tr key={item.issue_type}><td>{issueNames[item.issue_type] ?? item.issue_type.replace(/_/g,' ')}</td><td>{item.support}</td><td>{item.tp}</td><td>{score(item.precision)}</td><td>{score(item.recall)}</td></tr>)}</tbody></table></div></section><aside className="report-aside"><h2>Decision counts</h2><dl><div><dt>Matched flags</dt><dd>{evaluation.metrics?.tp ?? '—'}</dd></div><div><dt>Extra flags</dt><dd>{evaluation.metrics?.fp ?? '—'}</dd></div><div><dt>Missed cases</dt><dd>{evaluation.metrics?.fn ?? '—'}</dd></div><div><dt>Unflagged, unlabelled</dt><dd>{evaluation.metrics?.tn ?? '—'}</dd></div></dl><p>Evaluated against separate labels from synthetic injection rules.</p></aside></div>
        {(evaluation.limitations ?? []).length > 0 && <section className="report-notes"><h2>Interpretation notes</h2>{evaluation.limitations?.map((item,index) => <p key={index}>{item}</p>)}</section>}
      </> : <div className="report-empty"><WarningCircle size={25} /><h2>Evaluation is not available yet</h2><p>{evaluation.reason ?? 'Generate the labelled synthetic dataset and run an analysis first.'}</p>{(evaluation.limitations ?? []).map((item,index) => <p key={index}>{item}</p>)}</div>)}
      {surface === 'quality' && !reportLoading && !reportError && quality && <>
        <section className="quality-headline"><div><span>Analysis coverage</span><strong>{score(quality.coverage.percent / 100)}</strong><small>{quality.coverage.compared} of {quality.coverage.employees} employees compared</small></div><div><span>Validation</span><strong>{quality.status === 'passed' ? 'Passed' : 'Attention'}</strong><small>{quality.error_count} errors · {quality.coverage.excluded} excluded</small></div></section>
        <section className="quality-validation" aria-label="Validation checks">
          <div className="quality-section-heading"><div><span className="quality-kicker">01 / VALIDATION</span><h2>Checks completed</h2></div><p>{quality.checks.length} checks across keys, dates, amounts, workflow, and coverage.</p></div>
          <div className="quality-checks">{quality.checks.map(item => <div key={item.name}><span className={item.status === 'passed' ? 'check-ok' : 'check-failed'}>{item.status === 'passed' ? <CheckCircle size={20} /> : <WarningCircle size={20} />}</span><strong>{item.name.replace(/_/g,' ')}</strong><span>{item.status === 'passed' ? 'Passed' : `${item.count} failed`}</span></div>)}</div>
          {quality.errors.length > 0 && <div className="quality-errors" role="alert"><strong>{quality.error_count} validation errors</strong><ul>{quality.errors.slice(0, 8).map((item, index) => <li key={`${item.type}-${index}`}>{item.type.replace(/_/g,' ')}</li>)}</ul></div>}
        </section>
        <section className="quality-inventory-section" aria-label="Dataset inventory">
          <div className="quality-section-heading"><div><span className="quality-kicker">02 / DATASET INVENTORY</span><h2>Records in the database</h2></div><p>Current synthetic database counts include retained history across analysis runs.</p></div>
          <div className="quality-inventory">{qualityInventory.map(group => <section className="quality-inventory-group" key={group.title}><h3>{group.title}</h3><dl>{group.entries.filter(([key]) => Object.prototype.hasOwnProperty.call(quality.counts, key)).map(([key,label]) => <div key={key} data-dataset-key={key} data-count={quality.counts[key]}><dt>{label}</dt><dd>{quality.counts[key].toLocaleString()}</dd></div>)}</dl></section>)}
          {Object.entries(quality.counts).some(([key]) => !knownQualityKeys.has(key)) && <section className="quality-inventory-group"><h3>Other records</h3><dl>{Object.entries(quality.counts).filter(([key]) => !knownQualityKeys.has(key)).sort(([a],[b]) => a.localeCompare(b)).map(([key,count]) => <div key={key} data-dataset-key={key} data-count={count}><dt>{key.replace(/_/g,' ')}</dt><dd>{count.toLocaleString()}</dd></div>)}</dl></section>}</div>
        </section>
        {quality.analysis_issues.length > 0 && <section className="report-notes"><h2>Analysis issues</h2>{quality.analysis_issues.slice(0,12).map((item,index) => <p key={`${item.employee_id}-${index}`}><strong>{item.employee_id}</strong> · {item.issue_type.replace(/_/g,' ')} — {item.detail}</p>)}</section>}
      </>}
    </main>
  </div>
}

export default App
