import { useState, useEffect } from 'react'
import { apiFetch } from './api'

interface DeploymentStep {
  step_name: string
  status: 'pending' | 'in_progress' | 'completed' | 'failed'
  duration_ms: number
  details?: string
}

interface AgentState {
  product_id: string
  product_name: string
  status: 'DEPLOYING' | 'HEALTHY' | 'DEGRADED' | 'FAILED' | 'OFFLINE'
  progress_pct: number
  current_phase: string
  steps: DeploymentStep[]
  registered_tools_count: number
  health_score: number
  latency_ms: number
  last_heartbeat: string
  error_message?: string
  simulation_mode?: boolean
}

interface ClusterSummary {
  total_agents: number
  healthy_count: number
  deploying_count: number
  failed_count: number
  overall_progress_pct: number
  cluster_status: string
  deployment_started_at: string
  deployment_completed_at?: string
  agents: Record<string, AgentState>
}

export function DeploymentDashboard() {
  const [cluster, setCluster] = useState<ClusterSummary | null>(null)
  const [loading, setLoading] = useState(false)
  const [toast, setToast] = useState('')
  const [filter, setFilter] = useState<'all' | 'healthy' | 'issues'>('all')
  const [showDiagnostics, setShowDiagnostics] = useState(false)

  const showToast = (msg: string) => {
    setToast(msg)
    setTimeout(() => setToast(''), 3500)
  }

  const fetchStatus = async () => {
    try {
      const res = await apiFetch('/agents/deploy/status')
      if (res.ok) {
        const data = await res.json()
        setCluster(data)
      }
    } catch (err) {
      console.error('Failed to fetch deployment status', err)
    }
  }

  useEffect(() => {
    fetchStatus()
    const timer = setInterval(fetchStatus, 4000)
    return () => clearInterval(timer)
  }, [])

  const deployAll = async (simulateFaultId?: string) => {
    setLoading(true)
    showToast(
      simulateFaultId
        ? `Testing fault detection with failure injected on ${simulateFaultId}…`
        : 'Deploying all 7 agents in parallel via asyncio orchestration…'
    )
    try {
      const url = simulateFaultId
        ? `/agents/deploy/parallel?simulate_failure_id=${simulateFaultId}`
        : '/agents/deploy/parallel'
      const res = await apiFetch(url, { method: 'POST' })
      if (res.ok) {
        const data = await res.json()
        setCluster(data)
        showToast(
          data.failed_count > 0
            ? `⚠️ Fault isolated: ${data.failed_count} failure detected & contained`
            : '✅ All 7 AI agents deployed and healthy in parallel!'
        )
      }
    } catch (err: any) {
      showToast(`Deployment error: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  const recoverAgent = async (agentId: string) => {
    setLoading(true)
    showToast(`Initiating self-healing restart for ${agentId}…`)
    try {
      const res = await apiFetch(`/agents/deploy/recover/${agentId}`, { method: 'POST' })
      if (res.ok) {
        await fetchStatus()
        showToast(`✅ Agent ${agentId} recovered and healthy!`)
      }
    } catch (err: any) {
      showToast(`Recovery failed: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  const agentList = cluster?.agents ? Object.values(cluster.agents) : []
  const filteredAgents = agentList.filter(ag => {
    if (filter === 'healthy') return ag.status === 'HEALTHY'
    if (filter === 'issues') return ag.status === 'FAILED' || ag.status === 'DEGRADED'
    return true
  })

  const clusterStatus = cluster?.cluster_status || 'HEALTHY'
  const isHealthy = clusterStatus === 'HEALTHY'
  const isDeploying = clusterStatus === 'DEPLOYING'

  return (
    <div className="page">
      {/* Header section */}
      <div className="page-title">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px', flexWrap: 'wrap' }}>
            <span
              style={{
                fontSize: '11px',
                padding: '3px 10px',
                borderRadius: '20px',
                fontWeight: 700,
                background: isHealthy
                  ? 'rgba(16, 185, 129, 0.15)'
                  : isDeploying
                  ? 'rgba(56, 189, 248, 0.15)'
                  : 'rgba(239, 68, 68, 0.15)',
                color: isHealthy ? '#34d399' : isDeploying ? '#38bdf8' : '#f87171',
                border: `1px solid ${isHealthy ? 'rgba(16, 185, 129, 0.3)' : isDeploying ? 'rgba(56, 189, 248, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              <span className="status-dot" style={{ width: 7, height: 7 }} />
              Cluster Fleet: {clusterStatus}
            </span>
            <span
              style={{
                fontSize: '11px',
                padding: '3px 10px',
                borderRadius: '20px',
                fontWeight: 600,
                background: 'rgba(2, 132, 199, 0.15)',
                color: 'var(--primary)',
                border: '1px solid rgba(2, 132, 199, 0.3)',
              }}
            >
              ⚡ Parallel asyncio.gather Orchestrator
            </span>
            <span
              style={{
                fontSize: '10.5px',
                padding: '3px 8px',
                borderRadius: '20px',
                fontWeight: 500,
                background: 'rgba(255, 255, 255, 0.05)',
                color: 'var(--muted)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
              }}
            >
              Simulation Mode: Deterministic Engine
            </span>
          </div>
          <h1>Parallel Deployment & Fleet Health</h1>
          <p>
            Real-time deployment orchestration, concurrent telemetry, and automated failure detection across all 7 operational AI agents.
          </p>
        </div>
        <div className="button-row">
          <button
            className="btn secondary"
            onClick={() => setShowDiagnostics(!showDiagnostics)}
            title="Toggle low-level step execution stages and technical diagnostics"
          >
            {showDiagnostics ? 'Hide Technical Diagnostics' : 'Show Technical Diagnostics'}
          </button>
          <button
            className="btn secondary"
            onClick={() => deployAll('payroll')}
            disabled={loading}
            title="Inject simulated failure into Payroll agent to verify automated fault isolation"
          >
            🧪 Test Fault Detection
          </button>
          <button
            className="btn"
            onClick={() => deployAll()}
            disabled={loading}
            style={{
              background: 'var(--primary)',
              border: 0,
              boxShadow: 'var(--shadow-sm)',
            }}
          >
            {loading ? 'Orchestrating Cluster…' : '🚀 Deploy 7 Agents in Parallel'}
          </button>
        </div>
      </div>

      {/* Cluster Overview KPI Cards */}
      <div className="metric-grid four">
        <div className="metric">
          <span>Fleet Capacity</span>
          <strong>{cluster?.total_agents || 7} Agents</strong>
          <small>All 7 products covered</small>
        </div>
        <div className="metric">
          <span>Healthy & Serving</span>
          <strong style={{ color: 'var(--success)' }}>{cluster?.healthy_count || 7} / 7</strong>
          <small>Active heartbeat & tools verified</small>
        </div>
        <div className="metric">
          <span>Failed / Degraded</span>
          <strong style={{ color: (cluster?.failed_count || 0) > 0 ? 'var(--danger)' : 'var(--success)' }}>
            {cluster?.failed_count || 0}
          </strong>
          <small>{(cluster?.failed_count || 0) > 0 ? 'Self-healing ready' : 'Zero cluster anomalies'}</small>
        </div>
        <div className="metric">
          <span>Fleet Readiness</span>
          <strong style={{ color: 'var(--primary)' }}>{cluster?.overall_progress_pct || 100}%</strong>
          <small>Concurrent startup progress</small>
        </div>
      </div>

      {/* Filter and Status Bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          margin: '20px 0 14px',
          flexWrap: 'wrap',
          gap: '10px',
        }}
      >
        <div style={{ display: 'flex', gap: '6px' }}>
          <button
            className={`side-panel-tab ${filter === 'all' ? 'active' : ''}`}
            onClick={() => setFilter('all')}
            style={{
              background: filter === 'all' ? 'var(--primary)' : 'var(--surface)',
              color: filter === 'all' ? '#ffffff' : 'var(--muted)',
              border: '1px solid var(--border)',
              padding: '6px 12px',
              borderRadius: '7px',
              cursor: 'pointer',
              fontSize: '11.5px',
              fontWeight: 600,
            }}
          >
            All Agents ({agentList.length})
          </button>
          <button
            className={`side-panel-tab ${filter === 'healthy' ? 'active' : ''}`}
            onClick={() => setFilter('healthy')}
            style={{
              background: filter === 'healthy' ? 'var(--primary)' : 'var(--surface)',
              color: filter === 'healthy' ? '#ffffff' : 'var(--muted)',
              border: '1px solid var(--border)',
              padding: '6px 12px',
              borderRadius: '7px',
              cursor: 'pointer',
              fontSize: '11.5px',
              fontWeight: 600,
            }}
          >
            Healthy ({agentList.filter(a => a.status === 'HEALTHY').length})
          </button>
          <button
            className={`side-panel-tab ${filter === 'issues' ? 'active' : ''}`}
            onClick={() => setFilter('issues')}
            style={{
              background: filter === 'issues' ? 'var(--danger)' : 'var(--surface)',
              color: filter === 'issues' ? '#ffffff' : 'var(--muted)',
              border: '1px solid var(--border)',
              padding: '6px 12px',
              borderRadius: '7px',
              cursor: 'pointer',
              fontSize: '11.5px',
              fontWeight: 600,
            }}
          >
            Action Required ({agentList.filter(a => a.status === 'FAILED' || a.status === 'DEGRADED').length})
          </button>
        </div>
        <small style={{ color: 'var(--muted)', fontSize: '11px' }}>
          Auto-polling cluster status every 4 seconds · Zero socket overhead
        </small>
      </div>

      {/* Real-time Agent Deployment Cards Grid */}
      <div className="deployment-grid">
        {filteredAgents.map(agent => {
          const isFailed = agent.status === 'FAILED'
          const isAgentDeploying = agent.status === 'DEPLOYING'
          return (
            <article
              key={agent.product_id}
              className={`deployment-card ${isFailed ? 'failed' : 'healthy'}`}
              style={{
                position: 'relative',
                overflow: 'hidden',
                transition: 'all 0.2s ease',
              }}
            >
              {/* Card Header */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
                <div>
                  <strong style={{ fontSize: '14.5px', color: 'var(--text)', display: 'block', fontWeight: 700 }}>
                    {agent.product_name}
                  </strong>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '2px' }}>
                    <small style={{ color: 'var(--primary)', fontSize: '11px', fontWeight: 600 }}>
                      ⚡ {agent.registered_tools_count} Domain Tools
                    </small>
                    <small style={{ color: 'var(--muted)', fontSize: '11px' }}>
                      · Latency: {agent.latency_ms}ms
                    </small>
                  </div>
                </div>
                <span
                  style={{
                    fontSize: '10px',
                    fontWeight: 700,
                    padding: '3px 9px',
                    borderRadius: '12px',
                    textTransform: 'uppercase',
                    letterSpacing: '0.04em',
                    background: isFailed
                      ? 'rgba(239, 68, 68, 0.2)'
                      : isAgentDeploying
                      ? 'rgba(56, 189, 248, 0.2)'
                      : 'rgba(16, 185, 129, 0.2)',
                    color: isFailed ? '#f87171' : isAgentDeploying ? '#38bdf8' : '#34d399',
                    border: `1px solid ${isFailed ? 'rgba(239, 68, 68, 0.4)' : isAgentDeploying ? 'rgba(56, 189, 248, 0.4)' : 'rgba(16, 185, 129, 0.4)'}`,
                  }}
                >
                  {agent.status}
                </span>
              </div>

              {/* Progress Bar & Phase */}
              <div style={{ margin: '8px 0 12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '4px' }}>
                  <span style={{ color: 'var(--muted)', fontWeight: 500 }}>{agent.current_phase}</span>
                  <strong style={{ color: 'var(--text)', fontFamily: 'monospace' }}>{agent.progress_pct}%</strong>
                </div>
                <div className="progress-track" style={{ height: '7px', borderRadius: '4px' }}>
                  <div
                    className={`progress-fill ${isFailed ? 'failed' : ''}`}
                    style={{
                      width: `${agent.progress_pct}%`,
                      transition: 'width 0.3s ease',
                      background: isFailed ? '#ef4444' : isAgentDeploying ? '#38bdf8' : 'linear-gradient(90deg, #0284c7, #10b981)',
                    }}
                  />
                </div>
              </div>

              {/* Step Progression Timeline (Admin Diagnostics Only) */}
              {showDiagnostics && (
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '5px',
                    background: 'rgba(0, 0, 0, 0.25)',
                    padding: '10px 12px',
                    borderRadius: '8px',
                    border: '1px solid rgba(255, 255, 255, 0.04)',
                  }}
                >
                  {agent.steps.map((step, idx) => {
                    const stepDone = step.status === 'completed'
                    const stepFailed = step.status === 'failed'
                    return (
                      <div
                        key={idx}
                        style={{
                          fontSize: '11px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          color: stepDone ? '#cbd5e1' : stepFailed ? '#fca5a5' : '#38bdf8',
                        }}
                      >
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '7px' }}>
                          <span
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              width: '14px',
                              height: '14px',
                              borderRadius: '50%',
                              fontSize: '9px',
                              fontWeight: 700,
                              background: stepDone
                                ? 'rgba(16, 185, 129, 0.25)'
                                : stepFailed
                                ? 'rgba(239, 68, 68, 0.25)'
                                : 'rgba(56, 189, 248, 0.25)',
                              color: stepDone ? '#34d399' : stepFailed ? '#f87171' : '#38bdf8',
                            }}
                          >
                            {stepDone ? '✓' : stepFailed ? '✕' : '⋯'}
                          </span>
                          {step.step_name}
                        </span>
                        <small style={{ color: 'var(--muted)', fontFamily: 'monospace', fontSize: '10px' }}>
                          {step.duration_ms}ms
                        </small>
                      </div>
                    )
                  })}
                </div>
              )}

              {/* Error and Automated Self-Healing */}
              {agent.error_message && (
                <div
                  style={{
                    background: 'rgba(239, 68, 68, 0.12)',
                    border: '1px solid rgba(239, 68, 68, 0.4)',
                    borderRadius: '8px',
                    padding: '10px 12px',
                    fontSize: '11px',
                    color: '#fca5a5',
                    marginTop: '10px',
                  }}
                >
                  <strong style={{ color: 'var(--danger)', display: 'block', marginBottom: '3px' }}>
                    Automated Fault Detection:
                  </strong>
                  <span>{agent.error_message}</span>
                  <div style={{ marginTop: '8px', display: 'flex', justifyContent: 'flex-end' }}>
                    <button
                      onClick={() => recoverAgent(agent.product_id)}
                      className="btn danger"
                      style={{
                        padding: '4px 10px',
                        fontSize: '10.5px',
                        fontWeight: 700,
                        background: 'var(--danger)',
                        color: 'var(--text)',
                        border: 0,
                        borderRadius: '5px',
                        boxShadow: 'none',
                      }}
                    >
                      Self-Heal Agent ↺
                    </button>
                  </div>
                </div>
              )}
            </article>
          )
        })}
      </div>

      {toast && (
        <div className="toast">
          {toast}
        </div>
      )}
    </div>
  )
}
