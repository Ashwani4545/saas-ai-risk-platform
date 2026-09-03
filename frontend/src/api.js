const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `Request failed (${status})`)
    this.status = status
  }
}

async function request(path, { method = 'GET', body, authHeaders = {} } = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders,
    },
    body: body ? JSON.stringify(body) : undefined,
  })

  const isJson = res.headers.get('content-type')?.includes('application/json')
  const data = isJson ? await res.json() : await res.text()

  if (!res.ok) {
    throw new ApiError(res.status, isJson ? data.detail : data)
  }
  return data
}

export const api = {
  health: () => request('/health'),
  login: (username, password) => request('/auth/login', { method: 'POST', body: { username, password } }),
  predict: (userId, features, authHeaders) =>
    request('/predict', { method: 'POST', body: { user_id: userId, features: features || undefined }, authHeaders }),
  features: (customerId, authHeaders) => request(`/features/${customerId}`, { authHeaders }),
  similarCustomers: (customerId, k, authHeaders) =>
    request('/similar-customers', { method: 'POST', body: { customer_id: customerId, k }, authHeaders }),
  abStats: (authHeaders) => request('/ab/stats', { authHeaders }),
  abOutcome: (userId, modelVersion, outcome, authHeaders) =>
    request('/ab/outcome', { method: 'POST', body: { user_id: userId, model_version: modelVersion, outcome }, authHeaders }),
  recentPredictions: (authHeaders) => request('/predictions/recent', { authHeaders }),
  explain: (customerId, authHeaders) => request('/explain', { method: 'POST', body: { customer_id: customerId }, authHeaders }),
  askPolicy: (question, authHeaders) => request('/policy/ask', { method: 'POST', body: { question }, authHeaders }),
}

export { ApiError, API_BASE }
