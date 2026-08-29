import { useState } from 'react'

const API = 'http://10.118.155.218:8081'

export default function App() {
  const [form, setForm] = useState({ company: '', email: '', niche: 'hvac', fleet_size: 10 })
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  const niches = ['hvac', 'plumbing', 'electrical', 'roofing', 'landscaping', 'pest_control', 'appliance_repair', 'cleaning', 'moving', 'security']

  async function submit(e) {
    e.preventDefault()
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const res = await fetch(`${API}/v1/leads/capture`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form)
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`)
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center py-10 px-4">
      <div className="w-full max-w-2xl">
        <span className="inline-flex items-center gap-2 bg-badge-bg border border-badge-border rounded px-3 py-1 text-xs text-badge-text mb-6">
          Empire AI Revenue Intelligence
        </span>
        <h1 className="text-4xl md:text-5xl font-bold leading-tight tracking-tight mb-4">
          Find Your <span className="text-accent">Revenue Leak</span>
        </h1>
        <p className="text-muted text-lg mb-8 max-w-xl">
          Enter your business details. We calculate the annual revenue you are losing
          from dispatch gaps, lead scoring, mobile UX, and website conversion — then
          generate a private audit portal with the exact dollar amount.
        </p>

        <div className="bg-card border border-border rounded-2xl p-6 md:p-8">
          <form onSubmit={submit} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-muted mb-2">Company Name</label>
              <input
                type="text"
                required
                placeholder="Acme HVAC Services"
                value={form.company}
                onChange={e => setForm({ ...form, company: e.target.value })}
                className="w-full px-4 py-3 bg-bg border border-border rounded-lg text-white placeholder:text-gray-500 focus:border-accent focus:outline-none transition-colors"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-muted mb-2">Email (audit portal link sent here)</label>
              <input
                type="email"
                required
                placeholder="owner@acmehvac.com"
                value={form.email}
                onChange={e => setForm({ ...form, email: e.target.value })}
                className="w-full px-4 py-3 bg-bg border border-border rounded-lg text-white placeholder:text-gray-500 focus:border-accent focus:outline-none transition-colors"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-muted mb-2">Niche</label>
              <select
                value={form.niche}
                onChange={e => setForm({ ...form, niche: e.target.value })}
                className="w-full px-4 py-3 bg-bg border border-border rounded-lg text-white focus:border-accent focus:outline-none transition-colors"
              >
                {niches.map(n => (
                  <option key={n} value={n}>{n.charAt(0).toUpperCase() + n.slice(1).replace('_', ' ')}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-muted mb-2">Fleet Size (trucks/technicians)</label>
              <input
                type="number"
                min="1"
                max="500"
                required
                value={form.fleet_size}
                onChange={e => setForm({ ...form, fleet_size: parseInt(e.target.value) || 1 })}
                className="w-full px-4 py-3 bg-bg border border-border rounded-lg text-white focus:border-accent focus:outline-none transition-colors"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-accent hover:bg-accent-hover text-bg font-semibold rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Calculating Leak...' : 'Get My Free Audit'}
            </button>
            <p className="text-center text-xs text-gray-500">
              No spam. Audit portal expires in 30 days. Unsubscribe anytime.
            </p>
          </form>

          {error && (
            <div className="mt-4 p-4 bg-error-bg border border-error-border rounded-lg text-error-text text-sm">
              {error}
            </div>
          )}

          {result && (
            <div className="mt-6 p-5 bg-result-bg border border-result-border rounded-lg animate-fade-in">
              <h3 className="text-accent font-semibold mb-4">Your Revenue Leak Audit</h3>
              <div className="space-y-3">
                <div className="flex justify-between border-b border-green-900/30 pb-2">
                  <span className="text-muted">Annual Leak Range</span>
                  <span className="font-semibold text-white">{result.leak_range}</span>
                </div>
                <div className="flex justify-between border-b border-green-900/30 pb-2">
                  <span className="text-muted">Primary Leak Vectors</span>
                  <span className="font-semibold text-white">{result.leaks?.join(', ') || 'N/A'}</span>
                </div>
                <div className="flex justify-between pt-2">
                  <span className="text-muted">Private Portal</span>
                  <a href={result.portal_url} target="_blank" rel="noopener noreferrer" className="text-accent hover:underline font-medium">
                    View Audit Portal →
                  </a>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}