/**
 * Iryax Multi-Agent Platform – Central API & Authentication Client
 *
 * SECURITY NOTE: This module reads the JWT access token from localStorage only.
 * There are NO embedded credentials. The user must log in through the
 * application's login page; the token is stored on successful authentication.
 * Never embed credentials in frontend source code.
 */

export interface AuthTokens {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

let cachedToken: string | null = null

/** Returns the stored JWT access token, or an empty string if not authenticated. */
export function getAuthToken(): string {
  if (cachedToken) return cachedToken
  const stored = localStorage.getItem('iryax_access_token')
  if (stored) {
    cachedToken = stored
    return stored
  }
  return ''
}

/** Clears the cached token (call on logout or 401 responses). */
export function clearAuthToken(): void {
  cachedToken = null
  localStorage.removeItem('iryax_access_token')
}

/** Stores a fresh token after successful login. */
export function setAuthToken(token: string): void {
  cachedToken = token
  localStorage.setItem('iryax_access_token', token)
}

/**
 * Authenticates an administrator using credentials.
 * Production-ready: credentials must be supplied explicitly by the user or session.
 */
export async function loginAdmin(email: string, password: string): Promise<string> {
  const res = await fetch('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Authentication failed' }))
    throw new Error(err.detail || 'Login failed')
  }
  const data = await res.json()
  if (data.access_token) {
    setAuthToken(data.access_token)
    return data.access_token
  }
  throw new Error('No access token returned')
}

/**
 * Retrieves the active access token.
 * If no token is present, does not silently forge or auto-inject credentials.
 */
export async function ensureAuthToken(): Promise<string> {
  const existing = getAuthToken()
  if (existing) return existing
  return ''
}

export async function apiFetch(url: string, init?: RequestInit): Promise<Response> {
  let token = getAuthToken()

  const headers = new Headers(init?.headers || {})
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const res = await fetch(url, { ...init, headers })

  if (res.status === 401 && !url.includes('/auth/login')) {
    clearAuthToken()
  }

  return res
}

export interface DashboardKPI {
  id: string
  label: string
  value: string
  subtext: string
  trend: string
  status: 'normal' | 'positive' | 'warning' | 'critical'
  category: string
  target_module: string
}

export interface DashboardApproval {
  id: string
  title: string
  module: string
  module_id: string
  severity: 'high' | 'medium' | 'low' | 'critical'
  description: string
  requester: string
  time_ago: string
}

export interface DashboardIssue {
  id: string
  module: string
  module_id: string
  severity: 'critical' | 'warning' | 'info'
  title: string
  impact: string
  action: string
}

export interface DashboardModule {
  id: string
  name: string
  icon: string
  domain: string
  score: number
  status: string
  key_metric: string
  summary: string
}

export interface DashboardActivity {
  id: string
  time: string
  domain: string
  module_id: string
  title: string
  details: string
  badge: string
  badge_tone: 'neutral' | 'live' | 'warning' | 'danger'
}

export interface DashboardSummaryData {
  organization: {
    name: string
    tier: string
    user: {
      id: string
      tenant_id: string
      role: string
    }
    health_score: number
    status: string
    timestamp: string
  }
  kpis: DashboardKPI[]
  pending_approvals: DashboardApproval[]
  operational_issues: DashboardIssue[]
  module_overview: DashboardModule[]
  recent_activities: DashboardActivity[]
  performance_trends: {
    sla_adherence: string
    automation_rate: string
    avg_cycle_velocity: string
    compliance_status: string
  }
  executive_ai_insights: {
    headline: string
    summary: string
    recommended_actions: string[]
  }
}

export async function fetchDashboardSummary(): Promise<DashboardSummaryData> {
  const res = await apiFetch('/dashboard/summary')
  if (!res.ok) {
    throw new Error(`Failed to load dashboard summary: ${res.statusText}`)
  }
  return res.json()
}

