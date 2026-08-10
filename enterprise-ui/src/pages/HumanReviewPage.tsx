import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../App'
import { apiFetch } from '../lib/api'

interface ReviewItem {
  finding_id: string
  db_id: string
  repository_id: string
  repository_name: string
  severity: string
  category: string
  title: string
  description: string
  module: string
  file_context: string
  line_count: number | null
  exceedance_ratio: number | null
  exceedance_tier: string | null
  evidence_references: Array<{ source: string; reference_path: string; detail: string }>
  governance_decision: string
  governance_rationale: string
  observation_status: string
  concern_status: string
  actionability_status: string
  mission_linkage: string[] | string
  current_adjudication: string | null
  operator: string | null
  operator_notes: string | null
  reviewed_at: string | null
}

interface ReviewSummary {
  total_reviewed: number
  useful: number
  false_positive: number
  not_actionable: number
  needs_more_evidence: number
  duplicate: number
  unknown: number
  finding_precision: number | null
  actionability_rate: number | null
  pending_review: number
}

const CLASSIFICATIONS = [
  'USEFUL', 'FALSE_POSITIVE', 'NOT_ACTIONABLE', 'NEEDS_MORE_EVIDENCE', 'DUPLICATE', 'UNKNOWN'
] as const

const SEVERITY_COLORS: Record<string, string> = {
  critical: '#dc2626',
  high: '#ea580c',
  medium: '#ca8a04',
  low: '#65a30d',
  info: '#0284c7',
}

const CLASSIFICATION_COLORS: Record<string, string> = {
  USEFUL: '#16a34a',
  FALSE_POSITIVE: '#dc2626',
  NOT_ACTIONABLE: '#6b7280',
  NEEDS_MORE_EVIDENCE: '#ca8a04',
  DUPLICATE: '#9333ea',
  UNKNOWN: '#9ca3af',
}

export default function HumanReviewPage() {
  const { user } = useAuth()
  const [items, setItems] = useState<ReviewItem[]>([])
  const [summary, setSummary] = useState<ReviewSummary | null>(null)
  const [total, setTotal] = useState(0)
  const [selected, setSelected] = useState<ReviewItem | null>(null)
  const [classifyNotes, setClassifyNotes] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filterSeverity, setFilterSeverity] = useState<string>('')
  const [filterContext, setFilterContext] = useState<string>('')
  const [showReviewed, setShowReviewed] = useState<boolean>(false)

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (filterSeverity) params.set('severity', filterSeverity)
      params.set('limit', '200')
      const queueRes = await apiFetch<{ items: ReviewItem[]; total: number }>(
        `/review/findings?${params}`, { token: localStorage.getItem('hermes_token') || '' }
      )
      let filtered = queueRes.items
      if (filterContext) filtered = filtered.filter(i => i.file_context === filterContext)
      if (!showReviewed) filtered = filtered.filter(i => !i.current_adjudication)
      setItems(filtered)
      setTotal(queueRes.total)

      const sumRes = await apiFetch<ReviewSummary>(
        '/review/summary', { token: localStorage.getItem('hermes_token') || '' }
      )
      setSummary(sumRes)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [filterSeverity, filterContext, showReviewed])

  useEffect(() => { fetchData() }, [fetchData])

  const handleClassify = async (findingId: string, classification: string) => {
    try {
      await apiFetch(`/review/findings/${findingId}/adjudications`, {
        method: 'POST',
        token: localStorage.getItem('hermes_token') || '',
        body: JSON.stringify({
          classification,
          operator: user?.name || 'unknown',
          notes: classifyNotes || null,
        }),
      })
      setClassifyNotes('')
      setSelected(null)
      fetchData()
    } catch (e: any) {
      setError(e.message)
    }
  }

  return (
    <div style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
      <h1 style={{ fontSize: '24px', fontWeight: 700, marginBottom: '8px' }}>Human Review</h1>
      <p style={{ color: '#6b7280', marginBottom: '24px' }}>Evidence-based finding adjudication — {total} total findings</p>

      {error && <div style={{ color: '#dc2626', marginBottom: '16px', padding: '12px', background: '#fef2f2', borderRadius: '6px' }}>{error}</div>}

      {summary && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '12px', marginBottom: '24px' }}>
          <SummaryCard label="Pending" value={summary.pending_review} color="#f59e0b" />
          <SummaryCard label="Useful" value={summary.useful} color="#16a34a" />
          <SummaryCard label="False Positive" value={summary.false_positive} color="#dc2626" />
          <SummaryCard label="Not Actionable" value={summary.not_actionable} color="#6b7280" />
          <SummaryCard label="Needs Evidence" value={summary.needs_more_evidence} color="#ca8a04" />
          <SummaryCard label="Duplicate" value={summary.duplicate} color="#9333ea" />
          <SummaryCard label="Precision" value={summary.finding_precision !== null ? `${(summary.finding_precision * 100).toFixed(1)}%` : 'N/A'} color="#0284c7" />
          <SummaryCard label="Actionability" value={summary.actionability_rate !== null ? `${(summary.actionability_rate * 100).toFixed(1)}%` : 'N/A'} color="#0284c7" />
        </div>
      )}

      <div style={{ display: 'flex', gap: '12px', marginBottom: '16px', flexWrap: 'wrap' }}>
        <select value={filterSeverity} onChange={e => setFilterSeverity(e.target.value)} style={selectStyle}>
          <option value="">All Severities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
        <select value={filterContext} onChange={e => setFilterContext(e.target.value)} style={selectStyle}>
          <option value="">All Contexts</option>
          <option value="PRODUCTION">Production</option>
          <option value="TEST">Test</option>
          <option value="CONFIGURATION">Configuration</option>
          <option value="UNKNOWN">Unknown</option>
        </select>
        <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '14px' }}>
          <input type="checkbox" checked={showReviewed} onChange={e => setShowReviewed(e.target.checked)} />
          Show reviewed
        </label>
      </div>

      {loading ? <p>Loading...</p> : (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
          <thead>
            <tr style={{ borderBottom: '2px solid #e5e7eb', textAlign: 'left' }}>
              <th style={thStyle}>#</th>
              <th style={thStyle}>Repository</th>
              <th style={thStyle}>Finding</th>
              <th style={thStyle}>Severity</th>
              <th style={thStyle}>Context</th>
              <th style={thStyle}>Obs</th>
              <th style={thStyle}>Concern</th>
              <th style={thStyle}>Action</th>
              <th style={thStyle}>Status</th>
              <th style={thStyle}>Classify</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item, idx) => (
              <tr key={item.db_id} style={{ borderBottom: '1px solid #f3f4f6', cursor: 'pointer' }}
                  onClick={() => setSelected(item)}>
                <td style={tdStyle}>{idx + 1}</td>
                <td style={tdStyle}>{item.repository_name}</td>
                <td style={tdStyle}>
                  <div style={{ fontWeight: 500 }}>{item.title}</div>
                  <div style={{ color: '#6b7280', fontSize: '12px' }}>{item.module}</div>
                </td>
                <td style={tdStyle}>
                  <span style={{ color: SEVERITY_COLORS[item.severity] || '#000', fontWeight: 600 }}>
                    {item.severity}
                  </span>
                </td>
                <td style={tdStyle}>
                  <span style={{ padding: '2px 6px', borderRadius: '4px', background: '#f3f4f6', fontSize: '12px' }}>
                    {item.file_context}
                  </span>
                </td>
                <td style={tdStyle}>{item.observation_status}</td>
                <td style={tdStyle}>{item.concern_status}</td>
                <td style={tdStyle}>{item.actionability_status}</td>
                <td style={tdStyle}>
                  {item.current_adjudication ? (
                    <span style={{ color: CLASSIFICATION_COLORS[item.current_adjudication] || '#000', fontWeight: 600 }}>
                      {item.current_adjudication}
                    </span>
                  ) : (
                    <span style={{ color: '#f59e0b' }}>PENDING</span>
                  )}
                </td>
                <td style={tdStyle} onClick={e => e.stopPropagation()}>
                  {!item.current_adjudication && (
                    <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                      {CLASSIFICATIONS.map(c => (
                        <button key={c} onClick={() => handleClassify(item.finding_id, c)}
                          style={{ padding: '2px 6px', fontSize: '11px', border: '1px solid #d1d5db',
                                   borderRadius: '4px', cursor: 'pointer', background: CLASSIFICATION_COLORS[c] + '22',
                                   color: CLASSIFICATION_COLORS[c] }}>
                          {c.replace('_', ' ')}
                        </button>
                      ))}
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {selected && (
        <div style={{ position: 'fixed', top: 0, right: 0, width: '480px', height: '100vh',
                      background: '#fff', boxShadow: '-4px 0 24px rgba(0,0,0,0.15)', padding: '24px',
                      overflowY: 'auto', zIndex: 1000 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h2 style={{ fontSize: '18px', fontWeight: 700 }}>{selected.finding_id}</h2>
            <button onClick={() => setSelected(null)} style={{ background: 'none', border: 'none', fontSize: '20px', cursor: 'pointer' }}>X</button>
          </div>

          <div style={{ fontSize: '13px', lineHeight: '1.8' }}>
            <Row label="Repository" value={selected.repository_name} />
            <Row label="Title" value={selected.title} />
            <Row label="Severity" value={selected.severity} />
            <Row label="Category" value={selected.category} />
            <Row label="Module" value={selected.module} />
            <Row label="File Context" value={selected.file_context} />
            <Row label="Line Count" value={String(selected.line_count || 'N/A')} />
            <Row label="Exceedance" value={selected.exceedance_tier || 'N/A'} />
            <Row label="Observation" value={selected.observation_status} />
            <Row label="Concern" value={selected.concern_status} />
            <Row label="Actionability" value={selected.actionability_status} />
            <Row label="Governance" value={selected.governance_decision} />
            <Row label="Governance Rationale" value={selected.governance_rationale} />

            {selected.evidence_references.length > 0 && (
              <div style={{ marginTop: '12px' }}>
                <strong>Evidence:</strong>
                {selected.evidence_references.map((e, i) => (
                  <div key={i} style={{ marginLeft: '12px', color: '#374151' }}>
                    [{e.source}] {e.reference_path} — {e.detail}
                  </div>
                ))}
              </div>
            )}

            <div style={{ marginTop: '16px' }}>
              <strong>Operator Notes:</strong>
              <textarea value={classifyNotes} onChange={e => setClassifyNotes(e.target.value)}
                placeholder="Optional notes..."
                style={{ width: '100%', minHeight: '60px', marginTop: '6px', padding: '8px',
                         border: '1px solid #d1d5db', borderRadius: '6px', fontSize: '13px' }} />
            </div>

            <div style={{ marginTop: '12px', display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
              {CLASSIFICATIONS.map(c => (
                <button key={c} onClick={() => handleClassify(selected.finding_id, c)}
                  style={{ padding: '6px 12px', border: '1px solid #d1d5db', borderRadius: '6px',
                           cursor: 'pointer', fontWeight: 600, fontSize: '13px',
                           background: CLASSIFICATION_COLORS[c] + '22', color: CLASSIFICATION_COLORS[c] }}>
                  {c.replace('_', ' ')}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function SummaryCard({ label, value, color }: { label: string; value: string | number; color: string }) {
  return (
    <div style={{ padding: '12px', border: `2px solid ${color}33`, borderRadius: '8px', textAlign: 'center' }}>
      <div style={{ fontSize: '24px', fontWeight: 700, color }}>{value}</div>
      <div style={{ fontSize: '12px', color: '#6b7280', marginTop: '4px' }}>{label}</div>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', gap: '8px', marginBottom: '4px' }}>
      <strong style={{ minWidth: '140px', color: '#374151' }}>{label}:</strong>
      <span style={{ color: '#111827' }}>{value || 'N/A'}</span>
    </div>
  )
}

const thStyle = { padding: '8px 12px', fontWeight: 600, fontSize: '12px', color: '#374151' }
const tdStyle = { padding: '8px 12px', verticalAlign: 'top' as const }
const selectStyle = { padding: '6px 10px', border: '1px solid #d1d5db', borderRadius: '6px', fontSize: '13px' }
