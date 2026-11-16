import { useState, useEffect, useRef } from 'react'
import { apiFetch } from './api'

export interface AgentSidePanelProps {
  agent: {
    id: string
    name: string
    tagline: string
    desc: string
    gate: string
    action: string
    actionQuery: string
  }
  isOpen: boolean
  onClose: () => void
  selectedRecord: string | null
  onClearSelectedRecord: () => void
  onRunWorkflow: (query: string, method?: string) => void
}

interface ChatMsg {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: string[]
  timestamp?: string
}

interface MetricItem {
  label: string
  value: string
  delta: string
  trend: string
  is_warning?: boolean
}

interface ProcessMilestone {
  name: string
  status: 'completed' | 'in_progress' | 'pending'
  details: string
}

interface ModuleAnalysisData {
  product_id: string
  product_name: string
  timestamp: string
  performance_score: number
  performance_status: string
  process_progress?: number
  process_status_label?: string
  process_milestones?: ProcessMilestone[]
  executive_summary: string
  statistics: MetricItem[]
  trends: string[]
  problems_detected: string[]
  pending_tasks: string[]
  risks_and_bottlenecks: string[]
  recommendations: string[]
  detailed_report_markdown: string
}

export function AgentSidePanel({
  agent,
  isOpen,
  onClose,
  selectedRecord,
  onClearSelectedRecord,
  onRunWorkflow,
}: AgentSidePanelProps) {
  const [tab, setTab] = useState<'analysis' | 'chat' | 'guardrails'>('analysis')
  const [messages, setMessages] = useState<ChatMsg[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [analysis, setAnalysis] = useState<ModuleAnalysisData | null>(null)
  const [loadingAnalysis, setLoadingAnalysis] = useState(false)
  const [expandedReport, setExpandedReport] = useState(false)
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (isOpen) {
      loadAnalysis()
    }
  }, [agent.id, isOpen])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const loadAnalysis = async () => {
    setLoadingAnalysis(true)
    try {
      const res = await apiFetch(`/agents/${agent.id}/analyze`)
      if (res.ok) {
        const data = await res.json()
        setAnalysis(data)
      }
    } catch (err) {
      console.error('Failed to load module analysis', err)
    } finally {
      setLoadingAnalysis(false)
    }
  }

  const sendMessage = async (overrideText?: string) => {
    const text = (overrideText || input).trim()
    if (!text || loading) return

    const nowStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    const userMsg: ChatMsg = {
      id: Date.now().toString(),
      role: 'user',
      content: text,
      timestamp: nowStr,
    }
    const assistantId = (Date.now() + 1).toString()
    const assistantMsg: ChatMsg = {
      id: assistantId,
      role: 'assistant',
      content: '',
      sources: [],
      timestamp: nowStr,
    }

    setMessages(prev => [...prev, userMsg, assistantMsg])
    setInput('')
    setLoading(true)

    try {
      const historyPayload = messages.slice(-4).map(m => ({ role: m.role, content: m.content }))
      const res = await apiFetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: text,
          history: historyPayload,
          agent: agent.id,
          page_context: {
            module_id: agent.id,
            selected_record: selectedRecord,
            filters: 'All records',
          },
        }),
      })

      if (!res.body) throw new Error('Streaming not supported')
      const reader = res.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let buffer = ''

      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.trim()) continue
          try {
            const chunk = JSON.parse(line)
            setMessages(prev =>
              prev.map(m => {
                if (m.id !== assistantId) return m
                const nextContent = chunk.token ? m.content + chunk.token : (chunk.answer || m.content)
                const nextSources = chunk.sources && chunk.sources.length > 0 ? chunk.sources : m.sources
                return { ...m, content: nextContent, sources: nextSources }
              })
            )
          } catch {
            // ignore partial line parse
          }
        }
      }
    } catch (err: any) {
      setMessages(prev =>
        prev.map(m => {
          if (m.id !== assistantId) return m
          return { ...m, content: `⚠️ Assistant connection error: ${err.message}` }
        })
      )
    } finally {
      setLoading(false)
    }
  }

  const copyToClipboard = (text: string, idx: number) => {
    navigator.clipboard.writeText(text)
    setCopiedIndex(idx)
    setTimeout(() => setCopiedIndex(null), 2000)
  }

  const PRODUCT_PROMPT_CHIPS: Record<string, string[]> = {
    recruitment: [
      'Who are the top matched candidates for Senior Developer?',
      'Review candidate qualification scores and initial screening status',
      'Which candidates are ready for technical round 1 interviews?',
      'Prepare and verify compensation package for Marcus Chen',
    ],
    payroll: [
      'Reconcile biometric attendance for all 10 Timely Health employees',
      'Calculate draft October payroll and total salary disbursement amount',
      'Detect attendance anomalies, overtime hours, and weekend shift variances',
      'Generate verified payslips for employees awaiting disbursement sign-off',
    ],
    task_management: [
      'Decompose the Sprint Planning epic into tracked subtasks and dependencies',
      'Detect sprint blockers and overdue work across active projects',
      'Analyze team velocity and workload distribution across developers',
      'What is the current burndown projection for the active sprint?',
    ],
    medical_camps: [
      'Show upcoming medical camp schedules and rostered volunteer coverage',
      'Review patient triage vitals screening alerts and critical hospital referrals',
      'Check pharmacy and diagnostic medical inventory dispatched to sites',
      'Generate clinical summary report for Rural Camp #4',
    ],
    op_management: [
      'What is the live outpatient queue status and estimated patient wait times?',
      'Check doctor chamber schedules and slot availability for today',
      'Call next token for Dr. Priya Mehta and route urgent cases',
      'Summarize today clinic appointments, e-Prescriptions, and revenue',
    ],
    coworking: [
      'Check hot desk and private cabin occupancy across 3rd and 4th floors',
      'Show pending meeting room reservations requiring administrator review',
      'Generate monthly pro-rata billing invoices for tenant members',
      'Analyze workplace utilization trends and member badge access logs',
    ],
    lab_management: [
      'Track diagnostic specimen accessioning and turnaround testing times',
      'Review abnormal pathology flags and critical alerts requiring sign-off',
      'Check laboratory reagent chemical stock levels and calibration status',
      'Release verified diagnostic pathology reports to the patient portal',
    ],
  }

  const promptChips = PRODUCT_PROMPT_CHIPS[agent.id] || [
    `Analyze operational performance and metrics for ${agent.name}`,
    `Detect bottlenecks and pending risks in ${agent.name}`,
    `Show pending tasks awaiting review in ${agent.name}`,
    agent.actionQuery,
  ]

  if (!isOpen) return null

  return (
    <aside className="agent-side-panel">
      {/* Panel Header */}
      <div className="side-panel-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div
            style={{
              width: '32px',
              height: '32px',
              borderRadius: '9px',
              background: 'rgba(37, 99, 235, 0.12)',
              border: '1px solid rgba(37, 99, 235, 0.3)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--primary)',
              fontSize: '15px',
            }}
          >
            ✦
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <strong style={{ fontSize: '13.5px', color: 'var(--text)', fontWeight: 700 }}>
                {agent.name}
              </strong>
              <span className="status-dot" style={{ width: 6, height: 6 }} />
            </div>
            <small style={{ fontSize: '11px', color: 'var(--primary)', fontWeight: 500 }}>
              Grounded in {agent.name} Context
            </small>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <button
            onClick={loadAnalysis}
            disabled={loadingAnalysis}
            className="icon-btn"
            style={{ width: '28px', height: '28px', borderRadius: '6px' }}
            title="Refresh module analytics"
          >
            <span style={{ display: 'inline-block', transform: loadingAnalysis ? 'rotate(180deg)' : 'none', transition: 'transform 0.4s' }}>
              ↻
            </span>
          </button>
          <button
            onClick={onClose}
            className="icon-btn"
            style={{ width: '28px', height: '28px', borderRadius: '6px' }}
            title="Close assistant panel"
          >
            ✕
          </button>
        </div>
      </div>

      {/* Selected Record Pill Banner */}
      {selectedRecord && (
        <div
          style={{
            background: 'linear-gradient(90deg, rgba(56, 189, 248, 0.14), rgba(2, 132, 199, 0.05))',
            borderBottom: '1px solid rgba(56, 189, 248, 0.25)',
            padding: '7px 14px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: '11px',
            gap: '8px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', overflow: 'hidden' }}>
            <span style={{ color: 'var(--primary)', fontSize: '12px' }}>📌</span>
            <span style={{ color: 'var(--muted)', whiteSpace: 'nowrap' }}>Active Context:</span>
            <strong
              style={{
                color: 'var(--text)',
                textOverflow: 'ellipsis',
                overflow: 'hidden',
                whiteSpace: 'nowrap',
              }}
              title={selectedRecord}
            >
              {selectedRecord}
            </strong>
          </div>
          <button
            onClick={onClearSelectedRecord}
            style={{
              background: 'rgba(255, 255, 255, 0.06)',
              border: '1px solid rgba(255, 255, 255, 0.12)',
              borderRadius: '4px',
              color: 'var(--muted)',
              cursor: 'pointer',
              fontSize: '10px',
              padding: '2px 6px',
              whiteSpace: 'nowrap',
            }}
            title="Clear selected record filter"
          >
            Clear ✕
          </button>
        </div>
      )}

      {/* Modern Segmented Navigation Tabs */}
      <div className="side-panel-tabs">
        <button
          className={`side-panel-tab ${tab === 'analysis' ? 'active' : ''}`}
          onClick={() => setTab('analysis')}
        >
          <span>📊</span>
          <span>Intelligence</span>
          {analysis && (
            <span
              style={{
                fontSize: '9.5px',
                padding: '1px 5px',
                borderRadius: '8px',
                background: analysis.performance_score >= 90 ? 'rgba(16, 185, 129, 0.25)' : 'rgba(245, 158, 11, 0.25)',
                color: analysis.performance_score >= 90 ? '#34d399' : '#fbbf24',
                fontWeight: 700,
              }}
            >
              {analysis.performance_score}%
            </span>
          )}
        </button>
        <button
          className={`side-panel-tab ${tab === 'chat' ? 'active' : ''}`}
          onClick={() => setTab('chat')}
        >
          <span>💬</span>
          <span>Ask Agent</span>
          {messages.length > 0 && (
            <span
              style={{
                fontSize: '9.5px',
                padding: '1px 5px',
                borderRadius: '8px',
                background: 'rgba(56, 189, 248, 0.2)',
                color: 'var(--primary)',
                fontWeight: 700,
              }}
            >
              {messages.length}
            </span>
          )}
        </button>
        <button
          className={`side-panel-tab ${tab === 'guardrails' ? 'active' : ''}`}
          onClick={() => setTab('guardrails')}
        >
          <span>🛡️</span>
          <span>Guardrails</span>
          <span
            style={{
              fontSize: '9px',
              padding: '1px 5px',
              borderRadius: '8px',
              background: 'rgba(16, 185, 129, 0.2)',
              color: '#10b981',
              fontWeight: 700,
            }}
          >
            ACTIVE
          </span>
        </button>
      </div>

      {/* Main Panel Content Body */}
      <div className="side-panel-body">
        {/* TAB 1: INTELLIGENCE & ANALYSIS */}
        {tab === 'analysis' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {loadingAnalysis && (
              <div
                style={{
                  padding: '30px 16px',
                  textAlign: 'center',
                  background: 'var(--surface2)',
                  borderRadius: '10px',
                  border: '1px solid var(--border)',
                }}
              >
                <div
                  className="status-dot"
                  style={{
                    width: 12,
                    height: 12,
                    display: 'inline-block',
                    marginBottom: '8px',
                    boxShadow: '0 0 12px #38bdf8',
                  }}
                />
                <strong style={{ display: 'block', fontSize: '13px', color: 'var(--text)' }}>
                  Synthesizing Module Intelligence…
                </strong>
                <small style={{ color: 'var(--muted)', fontSize: '11px', marginTop: '4px', display: 'block' }}>
                  Querying database, calculating KPIs & detecting operational bottlenecks…
                </small>
              </div>
            )}

            {analysis && (
              <>
                {/* Workflow Process Progress Card */}
                <div
                  style={{
                    background: 'var(--surface2)',
                    border: '1px solid var(--border)',
                    borderRadius: '12px',
                    padding: '16px',
                    boxShadow: 'var(--shadow-sm)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ fontSize: '14px' }}>⚡</span>
                      <strong style={{ fontSize: '13px', color: 'var(--text)' }}>Workflow Process Completion</strong>
                    </div>
                    <span
                      style={{
                        fontSize: '13px',
                        fontWeight: 700,
                        color: (analysis.process_progress || 85) >= 90 ? '#16A34A' : '#2563EB',
                      }}
                    >
                      {analysis.process_progress || 85}% Done
                    </span>
                  </div>
                  <div style={{ fontSize: '11.5px', color: 'var(--text-secondary)', marginBottom: '10px' }}>
                    {analysis.process_status_label || 'Process actively progressing'}
                  </div>
                  {/* Progress Bar */}
                  <div
                    style={{
                      height: '8px',
                      background: 'var(--bg)',
                      borderRadius: '999px',
                      overflow: 'hidden',
                      border: '1px solid var(--border)',
                      marginBottom: '14px',
                    }}
                  >
                    <div
                      style={{
                        width: `${analysis.process_progress || 85}%`,
                        height: '100%',
                        background: (analysis.process_progress || 85) >= 90 ? '#16A34A' : '#2563EB',
                        borderRadius: '999px',
                        transition: 'width 0.5s ease',
                      }}
                    />
                  </div>

                  {/* Process Milestones */}
                  {analysis.process_milestones && analysis.process_milestones.length > 0 && (
                    <div>
                      <small style={{ fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 700, color: 'var(--muted)', display: 'block', marginBottom: '8px' }}>
                        Operational Milestones ({analysis.process_milestones.filter(m => m.status === 'completed').length}/{analysis.process_milestones.length} Completed)
                      </small>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        {analysis.process_milestones.map((m, idx) => (
                          <div
                            key={idx}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              padding: '8px 10px',
                              background: 'var(--bg)',
                              border: '1px solid var(--border)',
                              borderRadius: '8px',
                              gap: '10px',
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1, minWidth: 0 }}>
                              <span
                                style={{
                                  width: '18px',
                                  height: '18px',
                                  borderRadius: '50%',
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'center',
                                  fontSize: '10px',
                                  fontWeight: 700,
                                  flexShrink: 0,
                                  background: m.status === 'completed' ? 'rgba(22, 163, 74, 0.15)' : m.status === 'in_progress' ? 'rgba(37, 99, 235, 0.15)' : 'var(--surface2)',
                                  color: m.status === 'completed' ? '#16A34A' : m.status === 'in_progress' ? '#2563EB' : 'var(--text-tertiary)',
                                  border: `1px solid ${m.status === 'completed' ? 'rgba(22, 163, 74, 0.4)' : m.status === 'in_progress' ? 'rgba(37, 99, 235, 0.4)' : 'var(--border)'}`,
                                }}
                              >
                                {m.status === 'completed' ? '✓' : m.status === 'in_progress' ? '⚡' : '○'}
                              </span>
                              <div style={{ minWidth: 0 }}>
                                <strong style={{ color: 'var(--text)', display: 'block', fontSize: '11.5px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                  {m.name}
                                </strong>
                                <small style={{ color: 'var(--text-secondary)', fontSize: '10.5px', display: 'block', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                  {m.details}
                                </small>
                              </div>
                            </div>
                            <span
                              style={{
                                fontSize: '9px',
                                textTransform: 'uppercase',
                                fontWeight: 700,
                                padding: '2px 6px',
                                borderRadius: '4px',
                                whiteSpace: 'nowrap',
                                flexShrink: 0,
                                background: m.status === 'completed' ? 'rgba(22, 163, 74, 0.12)' : m.status === 'in_progress' ? 'rgba(37, 99, 235, 0.12)' : 'var(--surface2)',
                                color: m.status === 'completed' ? '#16A34A' : m.status === 'in_progress' ? '#2563EB' : 'var(--text-tertiary)',
                              }}
                            >
                              {m.status === 'completed' ? 'Done' : m.status === 'in_progress' ? 'Active' : 'Pending'}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <small style={{ fontSize: '10.5px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--muted)' }}>
                  Questions to Ask {agent.name}
                </small>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {promptChips.slice(0, 4).map((q, idx) => (
                    <button
                      key={idx}
                      onClick={() => {
                        setTab('chat')
                        sendMessage(q)
                      }}
                      style={{
                        background: 'var(--surface2)',
                        border: '1px solid var(--border)',
                        borderRadius: '6px',
                        padding: '6px 10px',
                        fontSize: '11px',
                        color: 'var(--primary)',
                        cursor: 'pointer',
                        textAlign: 'left',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        width: '100%',
                        transition: 'all 0.15s ease',
                      }}
                      onMouseEnter={e => {
                        e.currentTarget.style.borderColor = 'var(--primary)'
                        e.currentTarget.style.background = 'var(--primary-bg)'
                      }}
                      onMouseLeave={e => {
                        e.currentTarget.style.borderColor = 'var(--border)'
                        e.currentTarget.style.background = 'var(--surface2)'
                      }}
                    >
                      <span style={{ color: 'var(--primary)', fontWeight: 'bold' }}>?</span>
                      <span style={{ flex: 1 }}>{q}</span>
                      <span style={{ fontSize: '10px', opacity: 0.7 }}>Ask ↗</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Performance Gauge Card */}
                <div
                  style={{
                    background: 'var(--surface2)',
                    border: '1px solid var(--border)',
                    borderRadius: '12px',
                    padding: '16px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '14px',
                    boxShadow: '0 4px 16px rgba(0, 0, 0, 0.25)',
                  }}
                >
                  <div
                    style={{
                      width: '64px',
                      height: '64px',
                      borderRadius: '50%',
                      background:
                        analysis.performance_score >= 90
                          ? 'radial-gradient(circle, rgba(16, 185, 129, 0.25) 0%, rgba(16, 185, 129, 0.05) 70%)'
                          : 'radial-gradient(circle, rgba(245, 158, 11, 0.25) 0%, rgba(245, 158, 11, 0.05) 70%)',
                      border: `2.5px solid ${analysis.performance_score >= 90 ? '#10b981' : '#f59e0b'}`,
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                      boxShadow: analysis.performance_score >= 90 ? '0 0 14px rgba(16, 185, 129, 0.3)' : '0 0 14px rgba(245, 158, 11, 0.3)',
                    }}
                  >
                    <strong
                      style={{
                        fontSize: '18px',
                        color: analysis.performance_score >= 90 ? '#34d399' : '#fbbf24',
                        fontWeight: 800,
                        lineHeight: 1,
                      }}
                    >
                      {analysis.performance_score}%
                    </strong>
                    <small
                      style={{
                        fontSize: '8.5px',
                        color: 'var(--muted)',
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em',
                        marginTop: '3px',
                        fontWeight: 600,
                      }}
                    >
                      Health
                    </small>
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                      <span
                        style={{
                          fontSize: '10px',
                          padding: '2px 7px',
                          borderRadius: '4px',
                          fontWeight: 700,
                          textTransform: 'uppercase',
                          background:
                            analysis.performance_score >= 90
                              ? 'rgba(16, 185, 129, 0.2)'
                              : 'rgba(245, 158, 11, 0.2)',
                          color: analysis.performance_score >= 90 ? '#34d399' : '#fbbf24',
                          border: `1px solid ${analysis.performance_score >= 90 ? 'rgba(16, 185, 129, 0.4)' : 'rgba(245, 158, 11, 0.4)'}`,
                        }}
                      >
                        {analysis.performance_status}
                      </span>
                      <small style={{ color: 'var(--muted)', fontSize: '10.5px' }}>
                        Live Audit
                      </small>
                    </div>
                    <p style={{ margin: 0, fontSize: '11.5px', color: 'var(--text-secondary)', lineHeight: '1.45' }}>
                      {analysis.executive_summary}
                    </p>
                  </div>
                </div>

                {/* Key Statistics Grid */}
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                    <small style={{ fontSize: '10.5px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--muted)' }}>
                      Core Performance Indicators
                    </small>
                    <small style={{ fontSize: '10px', color: 'var(--primary)' }}>
                      {analysis.statistics.length} metrics verified
                    </small>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                    {analysis.statistics.map(stat => (
                      <div
                        key={stat.label}
                        style={{
                          background: 'var(--surface2)',
                          border: `1px solid ${stat.is_warning ? 'rgba(245,158,11,0.4)' : 'var(--border)'}`,
                          borderRadius: '9px',
                          padding: '10px 12px',
                          transition: 'transform 0.15s ease',
                        }}
                      >
                        <small style={{ color: 'var(--muted)', fontSize: '10.5px', display: 'block' }}>
                          {stat.label}
                        </small>
                        <strong
                          style={{
                            fontSize: '16px',
                            color: 'var(--text)',
                            display: 'block',
                            margin: '3px 0 1px',
                            fontWeight: 700,
                          }}
                        >
                          {stat.value}
                        </strong>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <span
                            style={{
                              fontSize: '10px',
                              color: stat.is_warning ? '#fbbf24' : '#38bdf8',
                              fontWeight: 600,
                            }}
                          >
                            {stat.is_warning ? '⚠️ ' : '↗ '}
                            {stat.delta}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Operational Trends */}
                {analysis.trends && analysis.trends.length > 0 && (
                  <div
                    style={{
                      background: 'var(--surface2)',
                      border: '1px solid var(--border)',
                      borderRadius: '10px',
                      padding: '12px 14px',
                    }}
                  >
                    <strong style={{ fontSize: '12px', color: 'var(--primary)', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                      📈 Identified Operational Trends
                    </strong>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                      {analysis.trends.map((trend, i) => (
                        <div key={i} style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'flex', alignItems: 'flex-start', gap: '6px' }}>
                          <span style={{ color: 'var(--primary)', fontSize: '12px' }}>•</span>
                          <span style={{ lineHeight: '1.45' }}>{trend}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Risks & Bottlenecks Warning Card */}
                {analysis.risks_and_bottlenecks && analysis.risks_and_bottlenecks.length > 0 && (
                  <div
                    style={{
                      background: 'linear-gradient(135deg, rgba(239, 68, 68, 0.12), rgba(239, 68, 68, 0.04))',
                      border: '1px solid rgba(239, 68, 68, 0.35)',
                      borderRadius: '10px',
                      padding: '12px 14px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                      <strong style={{ fontSize: '12px', color: '#f87171', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        ⚠️ Bottlenecks & Operational Risks
                      </strong>
                      <span
                        style={{
                          fontSize: '9.5px',
                          padding: '1px 6px',
                          borderRadius: '4px',
                          background: 'rgba(239, 68, 68, 0.25)',
                          color: '#fca5a5',
                          fontWeight: 700,
                        }}
                      >
                        {analysis.risks_and_bottlenecks.length} DETECTED
                      </span>
                    </div>
                    <ul style={{ margin: '4px 0 0', paddingLeft: '16px', fontSize: '11px', color: '#fca5a5', lineHeight: '1.5' }}>
                      {analysis.risks_and_bottlenecks.map((risk, i) => (
                        <li key={i}>{risk}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Pending Tasks Section */}
                {analysis.pending_tasks && analysis.pending_tasks.length > 0 && (
                  <div
                    style={{
                      background: 'var(--surface2)',
                      border: '1px solid var(--border)',
                      borderRadius: '10px',
                      padding: '12px 14px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                      <strong style={{ fontSize: '12px', color: 'var(--text)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        📋 Action Items Requiring Attention
                      </strong>
                      <span style={{ fontSize: '10px', color: 'var(--muted)' }}>
                        {analysis.pending_tasks.length} tasks
                      </span>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      {analysis.pending_tasks.map((task, i) => (
                        <div
                          key={i}
                          style={{
                            fontSize: '11px',
                            color: 'var(--text-secondary)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '6px 8px',
                            background: 'rgba(0, 0, 0, 0.2)',
                            borderRadius: '6px',
                            border: '1px solid rgba(255, 255, 255, 0.04)',
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
                            <span style={{ color: 'var(--primary)', fontSize: '11px' }}>◻</span>
                            <span>{task}</span>
                          </div>
                          <button
                            onClick={() => {
                              setTab('chat')
                              sendMessage(`Review and resolve pending task: "${task}"`)
                            }}
                            style={{
                              background: 'transparent',
                              border: '1px solid #1d345b',
                              borderRadius: '4px',
                              color: 'var(--primary)',
                              fontSize: '10px',
                              padding: '2px 6px',
                              cursor: 'pointer',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            Resolve →
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* AI Recommendations with One-Click Execution */}
                {analysis.recommendations && analysis.recommendations.length > 0 && (
                  <div
                    style={{
                      background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.1), rgba(6, 78, 59, 0.05))',
                      border: '1px solid rgba(16, 185, 129, 0.35)',
                      borderRadius: '10px',
                      padding: '12px 14px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                      <strong style={{ fontSize: '12px', color: '#34d399', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        💡 AI Strategic Recommendations
                      </strong>
                      <span
                        style={{
                          fontSize: '9.5px',
                          padding: '1px 6px',
                          borderRadius: '4px',
                          background: 'rgba(16, 185, 129, 0.25)',
                          color: '#6ee7b7',
                          fontWeight: 700,
                        }}
                      >
                        ACTIONABLE
                      </span>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {analysis.recommendations.map((rec, i) => (
                        <div
                          key={i}
                          style={{
                            fontSize: '11px',
                            color: '#e2e8f0',
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            gap: '10px',
                            padding: '6px 8px',
                            background: 'rgba(0, 0, 0, 0.2)',
                            borderRadius: '6px',
                          }}
                        >
                          <span style={{ lineHeight: '1.4' }}>• {rec}</span>
                          <button
                            onClick={() => {
                              setTab('chat')
                              sendMessage(`Execute recommendation: "${rec}"`)
                            }}
                            className="btn"
                            style={{
                              padding: '3px 8px',
                              fontSize: '10.5px',
                              whiteSpace: 'nowrap',
                              boxShadow: 'none',
                              borderRadius: '5px',
                              background: '#0284c7',
                            }}
                          >
                            Execute ⚡
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Expandable Comprehensive Analytical Report */}
                <div style={{ marginTop: '2px' }}>
                  <button
                    onClick={() => setExpandedReport(!expandedReport)}
                    style={{
                      width: '100%',
                      background: 'var(--surface2)',
                      border: '1px solid var(--border)',
                      borderRadius: '8px',
                      padding: '9px 12px',
                      color: 'var(--primary)',
                      fontSize: '11.5px',
                      fontWeight: 600,
                      cursor: 'pointer',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      transition: 'background 0.15s ease',
                    }}
                  >
                    <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span>📄</span>
                      <span>{expandedReport ? 'Hide Complete Markdown Report' : 'View Full Analytical Report'}</span>
                    </span>
                    <span>{expandedReport ? '▲' : '▼'}</span>
                  </button>

                  {expandedReport && (
                    <div
                      style={{
                        marginTop: '8px',
                        background: 'var(--surface2)',
                        border: '1px solid var(--border)',
                        borderRadius: '8px',
                        padding: '12px 14px',
                        fontSize: '11px',
                        color: 'var(--text-secondary)',
                        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, monospace',
                        whiteSpace: 'pre-wrap',
                        maxHeight: '340px',
                        overflowY: 'auto',
                        lineHeight: '1.6',
                      }}
                    >
                      {analysis.detailed_report_markdown}
                    </div>
                  )}
                </div>
              </>
            )}

            {!loadingAnalysis && !analysis && (
              <div
                style={{
                  padding: '32px 16px',
                  textAlign: 'center',
                  background: 'var(--surface2)',
                  borderRadius: '10px',
                  border: '1px solid var(--border)',
                }}
              >
                <span style={{ fontSize: '24px', display: 'block', marginBottom: '8px' }}>📊</span>
                <strong style={{ display: 'block', fontSize: '13px', color: 'var(--text)' }}>
                  Intelligence Report Awaiting Generation
                </strong>
                <p style={{ color: 'var(--muted)', fontSize: '11.5px', margin: '6px 0 14px' }}>
                  Synthesize real-time operational metrics, trends, and risk analysis for {agent.name}.
                </p>
                <button
                  onClick={loadAnalysis}
                  className="btn"
                  style={{
                    padding: '6px 14px',
                    fontSize: '12px',
                    background: 'var(--primary)',
                    color: '#ffffff',
                    borderRadius: '6px',
                    border: 0,
                    cursor: 'pointer',
                  }}
                >
                  Generate Intelligence Report
                </button>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: INTERACTIVE AI CHAT */}
        {tab === 'chat' && (
          <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            {/* Context Awareness & Quick Chips */}
            <div style={{ marginBottom: '12px' }}>
              <small
                style={{
                  display: 'block',
                  color: 'var(--muted)',
                  fontSize: '10.5px',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  marginBottom: '6px',
                }}
              >
                Suggested Direct Queries
              </small>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {promptChips.map((chip, idx) => (
                  <button
                    key={idx}
                    onClick={() => sendMessage(chip)}
                    disabled={loading}
                    style={{
                      background: 'var(--surface2)',
                      border: '1px solid var(--border)',
                      borderRadius: '16px',
                      padding: '4px 10px',
                      fontSize: '10.5px',
                      color: 'var(--primary)',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                      textAlign: 'left',
                    }}
                    onMouseEnter={e => {
                      e.currentTarget.style.borderColor = '#38bdf8'
                      e.currentTarget.style.background = 'rgba(2, 132, 199, 0.2)'
                    }}
                    onMouseLeave={e => {
                      e.currentTarget.style.borderColor = 'var(--border)'
                      e.currentTarget.style.background = 'var(--surface2)'
                    }}
                  >
                    + {chip}
                  </button>
                ))}
              </div>
            </div>

            {/* Conversation Feed */}
            <div
              style={{
                flex: 1,
                overflowY: 'auto',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
                paddingBottom: '12px',
                paddingRight: '2px',
              }}
            >
              {messages.length === 0 && (
                <div
                  style={{
                    padding: '32px 16px',
                    textAlign: 'center',
                    background: 'var(--surface2)',
                    borderRadius: '10px',
                    border: '1px solid var(--border)',
                    margin: 'auto 0',
                  }}
                >
                  <div
                    style={{
                      width: '42px',
                      height: '42px',
                      borderRadius: '50%',
                      background: 'rgba(56, 189, 248, 0.15)',
                      border: '1px solid rgba(56, 189, 248, 0.3)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      margin: '0 auto 10px',
                      color: 'var(--primary)',
                      fontSize: '18px',
                    }}
                  >
                    ✦
                  </div>
                  <strong style={{ display: 'block', fontSize: '13px', color: 'var(--text)' }}>
                    {agent.name} Copilot Active
                  </strong>
                  <p style={{ margin: '6px 0 0', fontSize: '11.5px', color: 'var(--muted)', lineHeight: '1.45' }}>
                    Ask questions directly about this module’s data, staff, workflows, or operational records. Answers are grounded in actual database values.
                  </p>
                </div>
              )}

              {messages.map((m, idx) => (
                <div
                  key={m.id}
                  style={{
                    alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
                    maxWidth: '92%',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px',
                  }}
                >
                  <div
                    style={{
                      background:
                        m.role === 'user'
                          ? 'var(--primary)'
                          : 'var(--surface2)',
                      border: m.role === 'user' ? '1px solid var(--primary)' : '1px solid var(--border)',
                      color: m.role === 'user' ? '#ffffff' : 'var(--text)',
                      borderRadius:
                        m.role === 'user'
                          ? '14px 14px 3px 14px'
                          : '14px 14px 14px 3px',
                      padding: '10px 14px',
                      fontSize: '12px',
                      lineHeight: '1.55',
                      boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
                    }}
                  >
                    <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                      {m.content || (loading && idx === messages.length - 1 ? (
                        <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--primary)' }}>
                          <span className="status-dot" /> Reasoning and invoking domain tools…
                        </span>
                      ) : null)}
                    </div>

                    {m.sources && m.sources.length > 0 && (
                      <div
                        style={{
                          marginTop: '8px',
                          paddingTop: '6px',
                          borderTop: '1px solid rgba(255, 255, 255, 0.08)',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px',
                          flexWrap: 'wrap',
                        }}
                      >
                        <small style={{ color: 'var(--muted)', fontSize: '9.5px', marginRight: '2px' }}>
                          Verified:
                        </small>
                        {m.sources.map((s, sIdx) => (
                          <span
                            key={sIdx}
                            style={{
                              fontSize: '9.5px',
                              padding: '1px 6px',
                              background: 'rgba(56, 189, 248, 0.2)',
                              color: 'var(--primary)',
                              borderRadius: '4px',
                              border: '1px solid rgba(56, 189, 248, 0.3)',
                            }}
                          >
                            {s}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
                      padding: '0 4px',
                    }}
                  >
                    {m.timestamp && (
                      <small style={{ fontSize: '9.5px', color: 'var(--muted)' }}>
                        {m.timestamp}
                      </small>
                    )}
                    {m.role === 'assistant' && m.content && (
                      <button
                        onClick={() => copyToClipboard(m.content, idx)}
                        style={{
                          background: 'transparent',
                          border: 0,
                          color: copiedIndex === idx ? '#10b981' : 'var(--muted)',
                          fontSize: '10px',
                          cursor: 'pointer',
                          padding: '1px 4px',
                        }}
                        title="Copy message"
                      >
                        {copiedIndex === idx ? '✓ Copied' : 'Copy'}
                      </button>
                    )}
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>

            {/* Input Composer */}
            <div
              style={{
                marginTop: 'auto',
                display: 'flex',
                gap: '8px',
                background: 'var(--surface2)',
                padding: '6px 8px',
                borderRadius: '10px',
                border: '1px solid var(--border)',
              }}
            >
              <input
                style={{
                  flex: 1,
                  background: 'transparent',
                  border: 0,
                  outline: 'none',
                  fontSize: '12px',
                  color: 'var(--text)',
                  padding: '6px 4px',
                }}
                placeholder={`Ask ${agent.name} about this module…`}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    sendMessage()
                  }
                }}
                disabled={loading}
              />
              <button
                onClick={() => sendMessage()}
                disabled={loading || !input.trim()}
                className="btn"
                style={{
                  padding: '6px 14px',
                  fontSize: '11.5px',
                  borderRadius: '7px',
                }}
              >
                Send
              </button>
            </div>
          </div>
        )}

        {/* TAB 3: ENTERPRISE GUARDRAILS & SAFETY */}
        {tab === 'guardrails' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div
              style={{
                background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.1), rgba(6, 78, 59, 0.05))',
                border: '1px solid rgba(16, 185, 129, 0.35)',
                borderRadius: '10px',
                padding: '14px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                <strong style={{ fontSize: '12.5px', color: '#34d399', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  🛡️ Input Guardrail & Injection Protection
                </strong>
                <span
                  style={{
                    fontSize: '9.5px',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    background: 'rgba(16, 185, 129, 0.25)',
                    color: '#6ee7b7',
                    fontWeight: 700,
                  }}
                >
                  ACTIVE
                </span>
              </div>
              <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '11px', lineHeight: '1.45' }}>
                Every prompt is evaluated against 10 regex adversarial patterns (jailbreaks, DAN mode overrides, system instruction leaks, and developer mode escalations) before execution.
              </p>
            </div>

            <div
              style={{
                background: 'var(--surface2)',
                border: '1px solid var(--border)',
                borderRadius: '10px',
                padding: '14px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                <strong style={{ fontSize: '12.5px', color: 'var(--primary)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  🎯 Output Groundedness & Anti-Hallucination
                </strong>
                <span
                  style={{
                    fontSize: '9.5px',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    background: 'rgba(56, 189, 248, 0.2)',
                    color: 'var(--primary)',
                    fontWeight: 700,
                  }}
                >
                  VERIFIED
                </span>
              </div>
              <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '11px', lineHeight: '1.45' }}>
                All generated responses are verified against the canonical {agent.name} data store. Unsubstantiated commitments and hallucinations are blocked.
              </p>
            </div>

            <div
              style={{
                background: 'var(--surface2)',
                border: '1px solid var(--border)',
                borderRadius: '10px',
                padding: '14px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                <strong style={{ fontSize: '12.5px', color: 'var(--text)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  🏢 Tenant Isolation & Cryptographic RBAC
                </strong>
                <span
                  style={{
                    fontSize: '9.5px',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    background: 'rgba(255, 255, 255, 0.1)',
                    color: 'var(--text)',
                    fontWeight: 700,
                  }}
                >
                  ISOLATED
                </span>
              </div>
              <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '11px', lineHeight: '1.45' }}>
                Enforces strict tenant boundary isolation (<code>tenant_iryax_global</code>). Unauthorized cross-tenant queries fail automatically with permission denial.
              </p>
            </div>

            <div
              style={{
                background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.1), rgba(180, 83, 9, 0.05))',
                border: '1px solid rgba(245, 158, 11, 0.35)',
                borderRadius: '10px',
                padding: '14px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                <strong style={{ fontSize: '12.5px', color: '#fbbf24', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  ⚖️ Human-In-The-Loop Governance Gate
                </strong>
                <span
                  style={{
                    fontSize: '9.5px',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    background: 'rgba(245, 158, 11, 0.25)',
                    color: '#fde68a',
                    fontWeight: 700,
                  }}
                >
                  MANDATORY
                </span>
              </div>
              <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '11px', lineHeight: '1.45' }}>
                Policy: <code style={{ color: '#fbbf24' }}>{agent.gate}</code>. Irreversible actions automatically pause for authorized administrator sign-off in the Approvals Center.
              </p>
            </div>

            <div
              style={{
                padding: '10px 14px',
                background: 'var(--surface2)',
                border: '1px solid var(--border)',
                borderRadius: '8px',
                fontSize: '10.5px',
                color: 'var(--muted)',
                lineHeight: '1.4',
              }}
            >
              🔒 Security Architecture: <strong>Argon2id</strong> password hashing · <strong>HS256</strong> JWT with jti replay defense · Automated PII masking.
            </div>
          </div>
        )}
      </div>
    </aside>
  )
}
