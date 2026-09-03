import { useEffect, useState } from 'react'
import RiskGauge from './RiskGauge'
import { api, ApiError, API_BASE } from './api'

const NAV = [
  { id: 'predict', label: 'Predict', hint: 'Score a customer' },
  { id: 'explain', label: 'Explain', hint: 'Why this score? (RAG)' },
  { id: 'features', label: 'Features', hint: 'Lookup raw signals' },
  { id: 'similar', label: 'Similar', hint: 'Nearest neighbors' },
  { id: 'abstats', label: 'A/B Stats', hint: 'Model comparison' },
  { id: 'recent', label: 'Activity', hint: 'Recent predictions' },
]

function useAuth() {
  const [mode, setMode] = useState('apikey')
  const [apiKey, setApiKey] = useState('demo-api-key-tenant1')
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('admin123')
  const [token, setToken] = useState('')
  const [loginError, setLoginError] = useState('')
  const [loggingIn, setLoggingIn] = useState(false)

  const headers = mode === 'apikey' ? { 'X-API-Key': apiKey } : token ? { Authorization: `Bearer ${token}` } : {}
  const isReady = mode === 'apikey' ? Boolean(apiKey) : Boolean(token)

  async function login() {
    setLoggingIn(true)
    setLoginError('')
    try {
      const res = await api.login(username, password)
      setToken(res.access_token)
    } catch (e) {
      setLoginError(e instanceof ApiError ? e.message : 'Could not reach the API')
    } finally {
      setLoggingIn(false)
    }
  }

  return { mode, setMode, apiKey, setApiKey, username, setUsername, password, setPassword, token, login, loginError, loggingIn, headers, isReady }
}

function Field({ label, children }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <label>{label}</label>
      {children}
    </div>
  )
}

function ErrorNote({ error }) {
  if (!error) return null
  return (
    <div
      className="mono"
      style={{ marginTop: 12, padding: '10px 12px', borderRadius: 8, background: 'var(--risk-high-soft)', color: 'var(--risk-high)', fontSize: 12 }}
    >
      {error}
    </div>
  )
}

function PredictView({ headers }) {
  const [userId, setUserId] = useState(5)
  const [useCustom, setUseCustom] = useState(false)
  const [features, setFeatures] = useState({ recency: 10, frequency: 5, monetary: 1000, credit_score: 700 })
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function run() {
    setLoading(true)
    setError('')
    try {
      const res = await api.predict(Number(userId), useCustom ? features : null, headers)
      setResult(res)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Request failed')
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 260px', gap: 20 }}>
      <div className="card">
        <h2 style={{ marginTop: 0, fontSize: 16 }}>Score a customer</h2>
        <Field label="Customer ID">
          <input type="number" min={1} value={userId} onChange={(e) => setUserId(e.target.value)} style={{ width: 140 }} />
        </Field>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', marginBottom: 12 }}>
          <input type="checkbox" checked={useCustom} onChange={(e) => setUseCustom(e.target.checked)} style={{ width: 'auto' }} />
          <span style={{ textTransform: 'none', letterSpacing: 0, fontSize: 13, color: 'var(--text-secondary)' }}>
            Override with custom features
          </span>
        </label>
        {useCustom && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
            {Object.entries(features).map(([key, value]) => (
              <Field key={key} label={key.replace('_', ' ')}>
                <input
                  type="number"
                  value={value}
                  onChange={(e) => setFeatures((f) => ({ ...f, [key]: Number(e.target.value) }))}
                />
              </Field>
            ))}
          </div>
        )}
        <button className="btn btn-primary" onClick={run} disabled={loading}>
          {loading ? 'Scoring…' : 'Run prediction'}
        </button>
        <ErrorNote error={error} />

        {result && (
          <div className="mono" style={{ marginTop: 18, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.9 }}>
            <div>tenant &nbsp;&nbsp;{result.tenant}</div>
            <div>model &nbsp;&nbsp;{result.data.model_version}</div>
            <div>latency &nbsp;{result.data.latency_ms}ms</div>
          </div>
        )}
      </div>

      <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <RiskGauge score={result?.data.risk_score ?? null} loading={loading} />
      </div>
    </div>
  )
}

function FeaturesView({ headers }) {
  const [customerId, setCustomerId] = useState(1)
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function run() {
    setLoading(true)
    setError('')
    try {
      setData(await api.features(Number(customerId), headers))
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Request failed')
      setData(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card">
      <h2 style={{ marginTop: 0, fontSize: 16 }}>Customer feature lookup</h2>
      <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end', marginBottom: 16 }}>
        <Field label="Customer ID">
          <input type="number" min={1} value={customerId} onChange={(e) => setCustomerId(e.target.value)} style={{ width: 140 }} />
        </Field>
        <button className="btn" onClick={run} disabled={loading} style={{ marginBottom: 12 }}>
          {loading ? 'Loading…' : 'Fetch'}
        </button>
      </div>
      <ErrorNote error={error} />
      {data && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
          {Object.entries(data.features).map(([key, value]) => (
            <div key={key} style={{ background: 'var(--bg-raised)', border: '1px solid var(--panel-border-soft)', borderRadius: 8, padding: 12 }}>
              <div style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: 0.06, color: 'var(--text-muted)' }}>{key.replace('_', ' ')}</div>
              <div className="mono" style={{ fontSize: 18, marginTop: 4 }}>
                {typeof value === 'number' ? value.toFixed(2) : value}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function SimilarView({ headers }) {
  const [customerId, setCustomerId] = useState(1)
  const [k, setK] = useState(5)
  const [results, setResults] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function run() {
    setLoading(true)
    setError('')
    try {
      const res = await api.similarCustomers(Number(customerId), Number(k), headers)
      setResults(res.similar_customers)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Request failed')
      setResults(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card">
      <h2 style={{ marginTop: 0, fontSize: 16 }}>Nearest-neighbor customers</h2>
      <p style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: -6 }}>
        Tip: run a few predictions first so there's something in this tenant's vector index to compare against.
      </p>
      <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end', marginBottom: 16 }}>
        <Field label="Customer ID">
          <input type="number" min={1} value={customerId} onChange={(e) => setCustomerId(e.target.value)} style={{ width: 120 }} />
        </Field>
        <Field label="k">
          <input type="number" min={1} max={20} value={k} onChange={(e) => setK(e.target.value)} style={{ width: 80 }} />
        </Field>
        <button className="btn" onClick={run} disabled={loading} style={{ marginBottom: 12 }}>
          {loading ? 'Searching…' : 'Search'}
        </button>
      </div>
      <ErrorNote error={error} />
      {results && results.length === 0 && <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>No neighbors yet in this tenant's index.</p>}
      {results && results.length > 0 && (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ textAlign: 'left', color: 'var(--text-muted)', fontSize: 11, textTransform: 'uppercase' }}>
              <th style={{ padding: '6px 8px' }}>Customer</th>
              <th style={{ padding: '6px 8px' }}>Similarity</th>
              <th style={{ padding: '6px 8px' }}>Distance</th>
            </tr>
          </thead>
          <tbody>
            {results.map((r) => (
              <tr key={r.customer_id} style={{ borderTop: '1px solid var(--panel-border-soft)' }}>
                <td className="mono" style={{ padding: '8px' }}>#{r.customer_id}</td>
                <td className="mono" style={{ padding: '8px' }}>{(r.similarity_score * 100).toFixed(1)}%</td>
                <td className="mono" style={{ padding: '8px', color: 'var(--text-muted)' }}>{r.distance.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

function SourceChunks({ sources }) {
  if (!sources || sources.length === 0) return null
  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.06, color: 'var(--text-muted)', marginBottom: 8 }}>
        Grounded in
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {sources.map((s, i) => (
          <div key={i} style={{ background: 'var(--bg-raised)', border: '1px solid var(--panel-border-soft)', borderRadius: 8, padding: '10px 12px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
              <span className="mono" style={{ fontSize: 11, color: 'var(--accent)' }}>{s.doc}</span>
              <span className="mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>match {(s.score * 100).toFixed(0)}%</span>
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{s.text}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

function ExplainView({ headers }) {
  const [customerId, setCustomerId] = useState(3)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const [question, setQuestion] = useState('')
  const [qaResult, setQaResult] = useState(null)
  const [qaError, setQaError] = useState('')
  const [qaLoading, setQaLoading] = useState(false)

  async function runExplain() {
    setLoading(true)
    setError('')
    try {
      setResult(await api.explain(Number(customerId), headers))
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Request failed')
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  async function runAsk() {
    if (!question.trim()) return
    setQaLoading(true)
    setQaError('')
    try {
      setQaResult(await api.askPolicy(question, headers))
    } catch (e) {
      setQaError(e instanceof ApiError ? e.message : 'Request failed')
      setQaResult(null)
    } finally {
      setQaLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div className="card">
        <h2 style={{ marginTop: 0, fontSize: 16 }}>Explain a risk decision</h2>
        <p style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: -6 }}>
          Retrieval-augmented: pulls the relevant underwriting policy for this customer's features, then explains
          the score against it. Works without an LLM key configured (template fallback) - grounding is real either way.
        </p>
        <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end', marginBottom: 4 }}>
          <Field label="Customer ID">
            <input type="number" min={1} value={customerId} onChange={(e) => setCustomerId(e.target.value)} style={{ width: 140 }} />
          </Field>
          <button className="btn btn-primary" onClick={runExplain} disabled={loading} style={{ marginBottom: 12 }}>
            {loading ? 'Explaining…' : 'Explain'}
          </button>
        </div>
        <ErrorNote error={error} />
        {result && (
          <div style={{ marginTop: 12 }}>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 10 }}>
              <span className={`pill ${result.risk_class ? 'pill-high' : 'pill-low'}`}>
                {result.risk_class ? 'high' : 'low'} risk · {result.risk_score.toFixed(2)}
              </span>
              <span className="mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                {result.generated_by === 'llm' ? 'LLM-generated' : 'template fallback'}
              </span>
            </div>
            <p style={{ fontSize: 14, lineHeight: 1.6, color: 'var(--text-primary)' }}>{result.explanation}</p>
            <SourceChunks sources={result.sources} />
          </div>
        )}
      </div>

      <div className="card">
        <h2 style={{ marginTop: 0, fontSize: 16 }}>Ask the policy assistant</h2>
        <p style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: -6 }}>
          General Q&A over the underwriting policy knowledge base - not tied to a specific customer.
        </p>
        <div style={{ display: 'flex', gap: 10, marginBottom: 4 }}>
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && runAsk()}
            placeholder="e.g. what happens with two disputes and a low credit score?"
            style={{ flex: 1 }}
          />
          <button className="btn btn-primary" onClick={runAsk} disabled={qaLoading}>
            {qaLoading ? 'Asking…' : 'Ask'}
          </button>
        </div>
        <ErrorNote error={qaError} />
        {qaResult && (
          <div style={{ marginTop: 12 }}>
            <p style={{ fontSize: 14, lineHeight: 1.6, whiteSpace: 'pre-line' }}>{qaResult.answer}</p>
            <SourceChunks sources={qaResult.sources} />
          </div>
        )}
      </div>
    </div>
  )
}

function ABStatsView({ headers }) {
  const [stats, setStats] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function run() {
    setLoading(true)
    setError('')
    try {
      const res = await api.abStats(headers)
      if (res.error) {
        setError(res.message || res.error)
        setStats(null)
      } else {
        setStats(res)
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Request failed')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    run()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ marginTop: 0, fontSize: 16 }}>Model A/B comparison</h2>
        <button className="btn" onClick={run} disabled={loading}>
          {loading ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>
      <ErrorNote error={error} />
      {stats && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginTop: 16 }}>
          {Object.entries(stats).map(([model, s]) => (
            <div key={model} style={{ background: 'var(--bg-raised)', border: '1px solid var(--panel-border-soft)', borderRadius: 8, padding: 16 }}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>{model}</div>
              <div className="mono" style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
                <div>total &nbsp;&nbsp;&nbsp;{s.total}</div>
                <div>conversions &nbsp;{s.conversions}</div>
                <div>rate &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{(s.conversion_rate * 100).toFixed(1)}%</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function RecentView({ headers }) {
  const [rows, setRows] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function run() {
    setLoading(true)
    setError('')
    try {
      const res = await api.recentPredictions(headers)
      setRows(res.predictions)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Request failed')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    run()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ marginTop: 0, fontSize: 16 }}>Recent predictions (this tenant)</h2>
        <button className="btn" onClick={run} disabled={loading}>
          {loading ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>
      <ErrorNote error={error} />
      {rows && rows.length === 0 && <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>No predictions recorded yet.</p>}
      {rows && rows.length > 0 && (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, marginTop: 12 }}>
          <thead>
            <tr style={{ textAlign: 'left', color: 'var(--text-muted)', fontSize: 11, textTransform: 'uppercase' }}>
              <th style={{ padding: '6px 8px' }}>Customer</th>
              <th style={{ padding: '6px 8px' }}>Model</th>
              <th style={{ padding: '6px 8px' }}>Score</th>
              <th style={{ padding: '6px 8px' }}>Class</th>
              <th style={{ padding: '6px 8px' }}>When</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} style={{ borderTop: '1px solid var(--panel-border-soft)' }}>
                <td className="mono" style={{ padding: '8px' }}>#{r.customer_id}</td>
                <td className="mono" style={{ padding: '8px' }}>{r.model_version}</td>
                <td className="mono" style={{ padding: '8px' }}>{r.risk_score.toFixed(3)}</td>
                <td style={{ padding: '8px' }}>
                  <span className={`pill ${r.risk_class ? 'pill-high' : 'pill-low'}`}>{r.risk_class ? 'high' : 'low'}</span>
                </td>
                <td className="mono" style={{ padding: '8px', color: 'var(--text-muted)', fontSize: 11 }}>
                  {new Date(r.created_at).toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

export default function App() {
  const auth = useAuth()
  const [tab, setTab] = useState('predict')
  const [apiOnline, setApiOnline] = useState(null)

  useEffect(() => {
    api
      .health()
      .then(() => setApiOnline(true))
      .catch(() => setApiOnline(false))
  }, [])

  const views = {
    predict: <PredictView headers={auth.headers} />,
    explain: <ExplainView headers={auth.headers} />,
    features: <FeaturesView headers={auth.headers} />,
    similar: <SimilarView headers={auth.headers} />,
    abstats: <ABStatsView headers={auth.headers} />,
    recent: <RecentView headers={auth.headers} />,
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', minHeight: '100vh' }}>
      <aside style={{ borderRight: '1px solid var(--panel-border-soft)', padding: '22px 16px', background: 'var(--bg-raised)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 28, padding: '0 6px' }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: apiOnline ? 'var(--risk-low)' : 'var(--risk-high)' }} />
          <div>
            <div style={{ fontWeight: 700, fontSize: 14, letterSpacing: '0.01em' }}>Risk Ops Console</div>
            <div className="mono" style={{ fontSize: 10, color: 'var(--text-muted)' }}>{API_BASE.replace(/^https?:\/\//, '')}</div>
          </div>
        </div>

        <nav style={{ display: 'flex', flexDirection: 'column', gap: 2, marginBottom: 28 }}>
          {NAV.map((item) => (
            <button
              key={item.id}
              onClick={() => setTab(item.id)}
              className="btn"
              style={{
                textAlign: 'left',
                border: 'none',
                background: tab === item.id ? 'var(--accent-soft)' : 'transparent',
                color: tab === item.id ? 'var(--accent)' : 'var(--text-secondary)',
                fontWeight: tab === item.id ? 600 : 500,
              }}
            >
              {item.label}
              <div style={{ fontSize: 10, fontWeight: 400, color: 'var(--text-muted)', marginTop: 2 }}>{item.hint}</div>
            </button>
          ))}
        </nav>

        <div style={{ borderTop: '1px solid var(--panel-border-soft)', paddingTop: 16 }}>
          <label>Auth</label>
          <div style={{ display: 'flex', gap: 6, marginBottom: 10 }}>
            <button
              className="btn"
              style={{ flex: 1, fontSize: 12, background: auth.mode === 'apikey' ? 'var(--accent-soft)' : undefined, color: auth.mode === 'apikey' ? 'var(--accent)' : undefined }}
              onClick={() => auth.setMode('apikey')}
            >
              API Key
            </button>
            <button
              className="btn"
              style={{ flex: 1, fontSize: 12, background: auth.mode === 'jwt' ? 'var(--accent-soft)' : undefined, color: auth.mode === 'jwt' ? 'var(--accent)' : undefined }}
              onClick={() => auth.setMode('jwt')}
            >
              Login
            </button>
          </div>

          {auth.mode === 'apikey' ? (
            <input type="password" value={auth.apiKey} onChange={(e) => auth.setApiKey(e.target.value)} placeholder="X-API-Key" />
          ) : auth.token ? (
            <div className="mono" style={{ fontSize: 11, color: 'var(--risk-low)' }}>✓ signed in</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <input value={auth.username} onChange={(e) => auth.setUsername(e.target.value)} placeholder="username" />
              <input type="password" value={auth.password} onChange={(e) => auth.setPassword(e.target.value)} placeholder="password" />
              <button className="btn btn-primary" onClick={auth.login} disabled={auth.loggingIn}>
                {auth.loggingIn ? 'Signing in…' : 'Sign in'}
              </button>
              {auth.loginError && <span style={{ fontSize: 11, color: 'var(--risk-high)' }}>{auth.loginError}</span>}
            </div>
          )}
        </div>
      </aside>

      <main style={{ padding: '28px 32px' }}>
        <div style={{ maxWidth: 900 }}>{views[tab]}</div>
      </main>
    </div>
  )
}
