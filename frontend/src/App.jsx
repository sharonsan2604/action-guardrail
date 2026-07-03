import { useState, useEffect } from 'react'
import { 
  Shield, 
  Activity, 
  Terminal, 
  FileText, 
  CheckCircle, 
  AlertOctagon, 
  Clock, 
  ArrowRight, 
  Lock, 
  Mail, 
  Database, 
  Eye, 
  RefreshCw, 
  User, 
  ChevronDown, 
  ChevronUp 
} from 'lucide-react'
import './App.css'

function App() {
  const [activeTab, setActiveTab] = useState('Overview')
  const [apiOnline, setApiOnline] = useState(false)
  const [healthData, setHealthData] = useState({})
  
  // App Data State
  const [auditLogs, setAuditLogs] = useState([])
  const [pendingReviews, setPendingReviews] = useState([])
  const [policyRules, setPolicyRules] = useState({ rules: [], default_action: 'log_and_allow' })
  const [patternAlerts, setPatternAlerts] = useState([])
  
  // Form States (Playground - Direct Action)
  const [selectedTool, setSelectedTool] = useState('delete_records')
  const [deleteParams, setDeleteParams] = useState({ table: 'customers', count: 5 })
  const [emailParams, setEmailParams] = useState({ to: 'alice', domain: 'gmail.com', body: 'Confidential update.' })
  const [fileParams, setFileParams] = useState({ path: '/data/confidential/financials.csv' })
  const [playgroundDryRun, setPlaygroundDryRun] = useState(false)
  const [playgroundResult, setPlaygroundResult] = useState(null)
  const [playgroundLoading, setPlaygroundLoading] = useState(false)
  const [playgroundError, setPlaygroundError] = useState(null)

  // Form States (Playground - Agent prompt)
  const [agentPrompt, setAgentPrompt] = useState('')
  const [agentDryRun, setAgentDryRun] = useState(false)
  const [agentResult, setAgentResult] = useState(null)
  const [agentLoading, setAgentLoading] = useState(false)
  const [agentError, setAgentError] = useState(null)

  // HITL Form States
  const [reviewerName, setReviewerName] = useState('')
  const [reviewerNotes, setReviewerNotes] = useState('')
  const [reviewLoading, setReviewLoading] = useState(null) // ID of current review processing

  // Expanded log state
  const [expandedLogId, setExpandedLogId] = useState(null)

  // Filter logs state
  const [logsFilter, setLogsFilter] = useState('All')

  // Fetch metrics and update core state
  const fetchData = async () => {
    try {
      // 1. Health status check
      const healthRes = await fetch('/health')
      if (healthRes.ok) {
        setApiOnline(true)
        const health = await healthRes.json()
        setHealthData(health)
      } else {
        setApiOnline(false)
      }
    } catch (e) {
      setApiOnline(false)
    }

    try {
      // 2. Audit logs query
      const auditRes = await fetch('/audit?limit=100')
      if (auditRes.ok) {
        const logs = await auditRes.json()
        setAuditLogs(logs)
      }
    } catch (e) {
      console.error("Failed to fetch audit logs", e)
    }

    try {
      // 3. Pending reviews query
      const reviewRes = await fetch('/review')
      if (reviewRes.ok) {
        const reviews = await reviewRes.json()
        setPendingReviews(reviews)
      }
    } catch (e) {
      console.error("Failed to fetch pending reviews", e)
    }

    try {
      // 4. Pattern alerts query
      const patternsRes = await fetch('/patterns/alerts')
      if (patternsRes.ok) {
        const alerts = await patternsRes.json()
        setPatternAlerts(alerts)
      }
    } catch (e) {
      console.error("Failed to fetch pattern alerts", e)
    }
  };

  // Fetch static metadata once
  const fetchMetadata = async () => {
    try {
      const rulesRes = await fetch('/rules')
      if (rulesRes.ok) {
        const rules = await rulesRes.json()
        setPolicyRules(rules)
      }
    } catch (e) {
      console.error("Failed to fetch policy rules", e)
    }
  };

  useEffect(() => {
    fetchData()
    fetchMetadata()

    // Setup polling intervals
    const interval = setInterval(fetchData, 4000)
    return () => clearInterval(interval)
  }, [])

  // Submitting Direct Action Playground
  const handlePlaygroundSubmit = async (e) => {
    e.preventDefault()
    setPlaygroundLoading(true)
    setPlaygroundError(null)
    setPlaygroundResult(null)

    let params = {}
    if (selectedTool === 'delete_records') params = deleteParams
    else if (selectedTool === 'send_email') params = emailParams
    else if (selectedTool === 'read_file') params = fileParams

    try {
      const payload = {
        tool: selectedTool,
        params,
        dry_run: playgroundDryRun
      }
      const response = await fetch('/act', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })

      if (response.ok) {
        const res = await response.json()
        setPlaygroundResult(res)
        fetchData() // Refresh logs
      } else {
        const errText = await response.text()
        try {
          const errObj = JSON.parse(errText)
          setPlaygroundError(errObj.detail || errObj.message || "Failed to evaluate action.")
        } catch {
          setPlaygroundError(errText || "Error communicating with server.")
        }
      }
    } catch (err) {
      setPlaygroundError(err.message || "Request failed.")
    } finally {
      setPlaygroundLoading(false)
    }
  }

  // Submitting LLM Agent Sandbox Request
  const handleAgentSubmit = async (e) => {
    e.preventDefault()
    if (!agentPrompt.trim()) return
    setAgentLoading(true)
    setAgentError(null)
    setAgentResult(null)

    try {
      const payload = {
        user_message: agentPrompt,
        dry_run: agentDryRun
      }
      const response = await fetch('/request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })

      if (response.ok) {
        const res = await response.json()
        setAgentResult(res)
        fetchData() // Refresh logs
      } else {
        const errText = await response.text()
        try {
          const errObj = JSON.parse(errText)
          setAgentError(errObj.detail || errObj.message || "Failed to run agent request.")
        } catch {
          setAgentError(errText || "Error communicating with server.")
        }
      }
    } catch (err) {
      setAgentError(err.message || "Request failed.")
    } finally {
      setAgentLoading(false)
    }
  }

  // Approving or Rejecting HITL actions
  const handleReviewAction = async (id, isApprove) => {
    if (!reviewerName.trim()) {
      alert("Please enter a Reviewer Name before making a decision.")
      return
    }
    if (!isApprove && !reviewerNotes.trim()) {
      alert("Please provide a reason in reviewer notes to reject this action.")
      return
    }

    setReviewLoading(id)
    const endpoint = isApprove ? `/review/${id}/approve` : `/review/${id}/reject`
    const payload = isApprove 
      ? { reviewer_name: reviewerName, notes: reviewerNotes }
      : { reviewer_name: reviewerName, reason: reviewerNotes }

    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })

      if (response.ok) {
        setReviewerNotes('')
        fetchData() // Refresh database list
      } else {
        const errText = await response.text()
        alert(`Failed to complete review: ${errText}`)
      }
    } catch (err) {
      alert(`Error submitting review decision: ${err.message}`)
    } finally {
      setReviewLoading(null)
    }
  }

  // Parse total stats from audit logs
  const getOverviewStats = () => {
    const allowed = auditLogs.filter(l => l.outcome === 'allowed').length
    const blocked = auditLogs.filter(l => l.outcome === 'blocked').length
    const pending = pendingReviews.length
    const total = auditLogs.length
    const blockRate = total > 0 ? ((blocked / total) * 100).toFixed(0) : 0

    return { total, allowed, blocked, pending, blockRate }
  }

  const stats = getOverviewStats()

  // Dynamic values for trend chart mapping
  const generateChartPoints = () => {
    // Return custom path based on logged requests
    if (auditLogs.length === 0) {
      return { path: "M 50,150 L 550,150", points: [] }
    }
    
    // Group logs into 6 intervals to generate dynamic peaks
    const logsCopy = [...auditLogs].reverse()
    const intervals = 6
    const chunk = Math.max(1, Math.ceil(logsCopy.length / intervals))
    const counts = []
    
    for (let i = 0; i < intervals; i++) {
      const slice = logsCopy.slice(i * chunk, (i + 1) * chunk)
      // Count blocked + allowed in this timeframe
      counts.push(slice.length)
    }
    
    // Normalize values to fit inside chart viewport (width 600, height 180)
    // padding bounds: x from 50 to 550, y from 30 to 150
    const xInterval = 500 / (intervals - 1)
    const maxVal = Math.max(2, ...counts)
    
    const pointsList = counts.map((count, index) => {
      const x = 50 + index * xInterval
      const y = 150 - (count / maxVal) * 100
      return { x, y, count }
    })
    
    let path = `M ${pointsList[0].x},${pointsList[0].y}`
    for (let i = 1; i < pointsList.length; i++) {
      // Smooth curve interpolation
      const prev = pointsList[i - 1]
      const curr = pointsList[i]
      const cpX1 = prev.x + xInterval / 2
      const cpY1 = prev.y
      const cpX2 = curr.x - xInterval / 2
      const cpY2 = curr.y
      path += ` C ${cpX1},${cpY1} ${cpX2},${cpY2} ${curr.x},${curr.y}`
    }
    
    return { path, points: pointsList }
  }

  const chartData = generateChartPoints()

  return (
    <div className="app-container">
      {/* Sidebar Navigation */}
      <aside className="sidebar">
        <div className="logo-container">
          <Shield className="logo-icon-glow" size={26} />
          <span className="logo-text">The Action Guardrail</span>
        </div>
        
        <nav className="nav-menu">
          <div 
            className={`nav-item ${activeTab === 'Overview' ? 'active' : ''}`}
            onClick={() => setActiveTab('Overview')}
          >
            <Activity className="nav-icon" size={18} />
            <span>Dashboard</span>
          </div>
          
          <div 
            className={`nav-item ${activeTab === 'Playground' ? 'active' : ''}`}
            onClick={() => setActiveTab('Playground')}
          >
            <Terminal className="nav-icon" size={18} />
            <span>Playground</span>
          </div>
          
          <div 
            className={`nav-item ${activeTab === 'Reviews' ? 'active' : ''}`}
            onClick={() => setActiveTab('Reviews')}
          >
            <Clock className="nav-icon" size={18} />
            <span>Review Queue {stats.pending > 0 && <span style={{ marginLeft: 'auto', backgroundColor: '#fbbf24', color: '#000', fontSize: '0.75rem', fontWeight: 'bold', padding: '2px 6px', borderRadius: '10px' }}>{stats.pending}</span>}</span>
          </div>

          <div 
            className={`nav-item ${activeTab === 'Patterns' ? 'active' : ''}`}
            onClick={() => setActiveTab('Patterns')}
          >
            <AlertOctagon className="nav-icon" size={18} />
            <span>Pattern Alerts {patternAlerts.length > 0 && <span style={{ marginLeft: 'auto', backgroundColor: '#ef4444', color: '#fff', fontSize: '0.75rem', fontWeight: 'bold', padding: '2px 6px', borderRadius: '10px' }}>{patternAlerts.length}</span>}</span>
          </div>
          
          <div 
            className={`nav-item ${activeTab === 'Logs' ? 'active' : ''}`}
            onClick={() => setActiveTab('Logs')}
          >
            <FileText className="nav-icon" size={18} />
            <span>Audit Logs</span>
          </div>

          <div 
            className={`nav-item ${activeTab === 'Rules' ? 'active' : ''}`}
            onClick={() => setActiveTab('Rules')}
          >
            <Lock className="nav-icon" size={18} />
            <span>Policy Rules</span>
          </div>
        </nav>
        
        <div className="sidebar-footer">
          <p>Action Guardrail Engine v1.0</p>
          <p style={{ fontSize: '0.7rem', opacity: 0.6, marginTop: '4px' }}>CIT AI Engineers task</p>
        </div>
      </aside>

      {/* Main Content Pane */}
      <main className="main-content">
        {/* Dynamic Header Panel */}
        <section className="header-panel">
          <div className="header-title">
            <h1>{activeTab}</h1>
            <p>
              {activeTab === 'Overview' && "Real-time activity overview and safety metrics."}
              {activeTab === 'Playground' && "Evaluate tool actions and prompt the LLM safety engine."}
              {activeTab === 'Reviews' && "Human review required to allow or block flagged actions."}
              {activeTab === 'Patterns' && "Cross-session compliance scans and security risk warnings."}
              {activeTab === 'Logs' && "Audit logs tracking decisions and operations."}
              {activeTab === 'Rules' && "Configured conditions and actions loaded from rules.yaml."}
            </p>
          </div>
          
          <div className="system-status-indicator">
            <div className={`status-dot ${apiOnline ? 'online' : 'offline'}`} />
            <span>API SERVER: {apiOnline ? 'ONLINE' : 'OFFLINE'}</span>
          </div>
        </section>

        {/* -------------------- VIEW 1: OVERVIEW -------------------- */}
        {activeTab === 'Overview' && (
          <>
            {/* Metrics cards grid */}
            <div className="metrics-grid">
              <div className="metric-card info">
                <div className="metric-icon-wrapper">
                  <Activity size={24} />
                </div>
                <div className="metric-info">
                  <span className="metric-label">System State</span>
                  <span className="metric-value" style={{ fontSize: '1.2rem', color: apiOnline ? '#34d399' : '#f87171' }}>
                    {apiOnline ? 'ACTIVE GATE' : 'OFFLINE'}
                  </span>
                </div>
              </div>

              <div className="metric-card allowed">
                <div className="metric-icon-wrapper">
                  <CheckCircle size={24} />
                </div>
                <div className="metric-info">
                  <span className="metric-label">Allowed Actions</span>
                  <span className="metric-value">{stats.allowed}</span>
                </div>
              </div>

              <div className="metric-card blocked">
                <div className="metric-icon-wrapper">
                  <AlertOctagon size={24} />
                </div>
                <div className="metric-info">
                  <span className="metric-label">Blocked Rate</span>
                  <span className="metric-value">{stats.blockRate}%</span>
                </div>
              </div>

              <div className="metric-card pending">
                <div className="metric-icon-wrapper">
                  <Clock size={24} />
                </div>
                <div className="metric-info">
                  <span className="metric-label">HITL Pending</span>
                  <span className="metric-value">{stats.pending}</span>
                </div>
              </div>
            </div>

            {/* Glowing Trend Line Chart */}
            <div className="panel-card">
              <div className="panel-header">
                <div>
                  <h2>Security Traffic & Block Rate</h2>
                  <p style={{ marginTop: '4px' }}>Load history demonstrating evaluated actions over current sessions.</p>
                </div>
                <div style={{ display: 'flex', gap: '16px', fontSize: '0.85rem' }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <div style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: 'var(--color-emerald)' }} />
                    Evaluated Actions
                  </span>
                </div>
              </div>

              <div className="svg-chart-container">
                <svg width="100%" height="100%" viewBox="0 0 600 180" preserveAspectRatio="none">
                  <defs>
                    <linearGradient id="chart-gradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="var(--color-emerald)" stopOpacity="0.25" />
                      <stop offset="100%" stopColor="var(--color-emerald)" stopOpacity="0.0" />
                    </linearGradient>
                  </defs>

                  {/* Horizontal grid lines */}
                  <line x1="50" y1="30" x2="550" y2="30" className="chart-grid-line" />
                  <line x1="50" y1="70" x2="550" y2="70" className="chart-grid-line" />
                  <line x1="50" y1="110" x2="550" y2="110" className="chart-grid-line" />
                  <line x1="50" y1="150" x2="550" y2="150" className="chart-grid-line" />

                  {/* SVG glowing trend path */}
                  <path d={chartData.path} className="svg-chart-line" />
                  
                  {/* Fill below trend path */}
                  {chartData.points.length > 0 && (
                    <path 
                      d={`${chartData.path} L ${chartData.points[chartData.points.length - 1].x},150 L ${chartData.points[0].x},150 Z`} 
                      className="svg-chart-fill" 
                    />
                  )}

                  {/* Render peak point indicators */}
                  {chartData.points.map((pt, i) => (
                    <g key={i}>
                      <circle 
                        cx={pt.x} 
                        cy={pt.y} 
                        r="5" 
                        fill="#0A0D0B" 
                        stroke="var(--color-emerald)" 
                        strokeWidth="2.5" 
                        style={{ filter: 'drop-shadow(0 0 4px var(--color-emerald-glow))' }}
                      />
                      <text x={pt.x} y={pt.y - 12} textAnchor="middle" className="chart-axis-label" fill="var(--text-primary)">
                        {pt.count}
                      </text>
                    </g>
                  ))}

                  {/* X Axis Labels */}
                  <text x="50" y="170" textAnchor="middle" className="chart-axis-label">Interval 1</text>
                  <text x="150" y="170" textAnchor="middle" className="chart-axis-label">Interval 2</text>
                  <text x="250" y="170" textAnchor="middle" className="chart-axis-label">Interval 3</text>
                  <text x="350" y="170" textAnchor="middle" className="chart-axis-label">Interval 4</text>
                  <text x="450" y="170" textAnchor="middle" className="chart-axis-label">Interval 5</text>
                  <text x="550" y="170" textAnchor="middle" className="chart-axis-label">Interval 6</text>
                </svg>
              </div>
            </div>
            
            {/* Split bottom cards */}
            <div className="split-layout">
              {/* Rules summary quick card */}
              <div className="panel-card" style={{ flexGrow: 1 }}>
                <div className="panel-header">
                  <h2>Active Policy Shield</h2>
                  <span style={{ fontSize: '0.85rem', color: 'var(--color-emerald)' }}>Rules Configured</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {policyRules.rules.slice(0, 3).map((rule, idx) => (
                    <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', backgroundColor: 'rgba(255,255,255,0.02)', padding: '12px 16px', borderRadius: '10px', border: '1px solid var(--card-border)' }}>
                      <div>
                        <span style={{ fontWeight: '600', fontSize: '0.9rem' }}>{rule.name}</span>
                        <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Tool: {rule.tool}</p>
                      </div>
                      <span className={`outcome-badge ${
                        rule.action === 'block' ? 'blocked' : rule.action === 'require_hitl' ? 'pending_review' : 'allowed'
                      }`}>
                        {rule.action === 'block' ? 'block' : rule.action === 'require_hitl' ? 'HITL' : 'allow'}
                      </span>
                    </div>
                  ))}
                  {policyRules.rules.length > 3 && (
                    <span 
                      style={{ fontSize: '0.85rem', color: 'var(--color-emerald)', cursor: 'pointer', textAlign: 'center' }}
                      onClick={() => setActiveTab('Rules')}
                    >
                      View all active rules &rarr;
                    </span>
                  )}
                </div>
              </div>

              {/* Review Queue Summary */}
              <div className="panel-card" style={{ flexGrow: 1 }}>
                <div className="panel-header">
                  <h2>Pending Security Approvals</h2>
                  <span style={{ fontSize: '0.85rem', color: 'var(--color-pending)' }}>HITL Waiting</span>
                </div>
                {pendingReviews.length === 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: '12px', color: 'var(--text-secondary)' }}>
                    <CheckCircle size={32} style={{ color: 'var(--color-allowed)' }} />
                    <p style={{ fontSize: '0.9rem' }}>No items pending review approval.</p>
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexData: 'column', flexDirection: 'column', gap: '12px' }}>
                    {pendingReviews.slice(0, 2).map((item, idx) => (
                      <div key={idx} style={{ padding: '12px 16px', backgroundColor: 'rgba(251, 191, 36, 0.03)', border: '1px solid rgba(251, 191, 36, 0.1)', borderRadius: '10px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                          <span style={{ fontWeight: '600', fontSize: '0.9rem' }}>{item.tool}</span>
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>ID #{item.id}</span>
                        </div>
                        <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{item.reason}</p>
                      </div>
                    ))}
                    <span 
                      style={{ fontSize: '0.85rem', color: 'var(--color-pending)', cursor: 'pointer', textAlign: 'center' }}
                      onClick={() => setActiveTab('Reviews')}
                    >
                      Open full review queue &rarr;
                    </span>
                  </div>
                )}
              </div>
            </div>
          </>
        )}

        {/* -------------------- VIEW 2: PLAYGROUND -------------------- */}
        {activeTab === 'Playground' && (
          <div className="split-layout">
            {/* Policy Playground Form */}
            <div className="panel-card">
              <div className="panel-header">
                <h2>Policy Playground</h2>
                <p>Simulate action requests against security filters.</p>
              </div>

              <form onSubmit={handlePlaygroundSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                <div className="form-group">
                  <label className="form-label">Select Tool Action</label>
                  <select 
                    className="form-select" 
                    value={selectedTool} 
                    onChange={(e) => setSelectedTool(e.target.value)}
                  >
                    <option value="delete_records">delete_records (Database Delete)</option>
                    <option value="send_email">send_email (Send Outbound Email)</option>
                    <option value="read_file">read_file (Read File System)</option>
                  </select>
                </div>

                {/* Render inputs dynamically */}
                {selectedTool === 'delete_records' && (
                  <>
                    <div className="form-group">
                      <label className="form-label">Target Table</label>
                      <input 
                        type="text" 
                        className="form-input" 
                        value={deleteParams.table}
                        onChange={(e) => setDeleteParams({ ...deleteParams, table: e.target.value })}
                        required
                      />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Delete Record Count</label>
                      <input 
                        type="number" 
                        className="form-input" 
                        value={deleteParams.count}
                        onChange={(e) => setDeleteParams({ ...deleteParams, count: parseInt(e.target.value) || 0 })}
                        min="1"
                        required
                      />
                    </div>
                  </>
                )}

                {selectedTool === 'send_email' && (
                  <>
                    <div className="form-group">
                      <label className="form-label">Recipient Username</label>
                      <input 
                        type="text" 
                        className="form-input" 
                        value={emailParams.to}
                        onChange={(e) => setEmailParams({ ...emailParams, to: e.target.value })}
                        required
                      />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Email Domain</label>
                      <input 
                        type="text" 
                        className="form-input" 
                        value={emailParams.domain}
                        onChange={(e) => setEmailParams({ ...emailParams, domain: e.target.value })}
                        required
                      />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Email Body Content</label>
                      <textarea 
                        className="form-textarea" 
                        value={emailParams.body}
                        onChange={(e) => setEmailParams({ ...emailParams, body: e.target.value })}
                        required
                      />
                    </div>
                  </>
                )}

                {selectedTool === 'read_file' && (
                  <div className="form-group">
                    <label className="form-label">Absolute File Path</label>
                    <input 
                      type="text" 
                      className="form-input" 
                      value={fileParams.path}
                      onChange={(e) => setFileParams({ ...fileParams, path: e.target.value })}
                      required
                    />
                  </div>
                )}

                <div className="form-group">
                  <label className="checkbox-label">
                    <input 
                      type="checkbox" 
                      className="checkbox-input" 
                      checked={playgroundDryRun}
                      onChange={(e) => setPlaygroundDryRun(e.target.checked)}
                    />
                    Dry Run Mode (Assess policy but do not execute tool)
                  </label>
                </div>

                <button 
                  type="submit" 
                  className="btn" 
                  disabled={playgroundLoading || !apiOnline}
                >
                  {playgroundLoading ? <RefreshCw className="nav-icon" style={{ animation: 'spin 2s linear infinite' }} size={16} /> : null}
                  Evaluate Action
                </button>
              </form>

              {/* Playground error output */}
              {playgroundError && (
                <div style={{ marginTop: '16px', color: 'var(--color-blocked)', fontSize: '0.9rem' }}>
                  <strong>Error:</strong> {playgroundError}
                </div>
              )}

              {/* Direct action result outcome */}
              {playgroundResult && (
                <div className={`outcome-container ${playgroundResult.outcome}`}>
                  <span className={`outcome-badge ${playgroundResult.outcome}`}>
                    {playgroundResult.outcome}
                  </span>
                  
                  <div className="outcome-detail-grid">
                    <span className="outcome-detail-label">Matched Rule:</span>
                    <span className="outcome-detail-value"><code>{playgroundResult.matched_rule}</code></span>

                    <span className="outcome-detail-label">Reasoning:</span>
                    <span className="outcome-detail-value">{playgroundResult.reason}</span>

                    <span className="outcome-detail-label">Executed:</span>
                    <span className="outcome-detail-value" style={{ color: playgroundResult.executed ? 'var(--color-allowed)' : 'var(--color-blocked)' }}>
                      {playgroundResult.executed ? 'Yes ✓' : 'No ✗'}
                    </span>
                  </div>

                  {playgroundResult.result && (
                    <pre className="audit-item-details" style={{ margin: '10px 0px 0px 0px' }}>
                      {JSON.stringify(playgroundResult.result, null, 2)}
                    </pre>
                  )}
                </div>
              )}
            </div>

            {/* AI Agent Sandbox */}
            <div className="panel-card">
              <div className="panel-header">
                <h2>AI Agent Sandbox</h2>
                <p>Submit a request in natural language. The AI Agent will decide on tool calls governed by security rules (Gemini API / Local Offline fallback).</p>
              </div>

              <form onSubmit={handleAgentSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                <div className="form-group">
                  <label className="form-label">Plain English Instruction</label>
                  <textarea 
                    className="form-textarea" 
                    placeholder="e.g. Delete 500 inactive users from the customer records table..."
                    value={agentPrompt}
                    onChange={(e) => setAgentPrompt(e.target.value)}
                    style={{ minHeight: '135px' }}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="checkbox-label">
                    <input 
                      type="checkbox" 
                      className="checkbox-input" 
                      checked={agentDryRun}
                      onChange={(e) => setAgentDryRun(e.target.checked)}
                    />
                    Dry Run Mode (Evaluate safety but do not execute selected tool)
                  </label>
                </div>

                <button 
                  type="submit" 
                  className="btn" 
                  disabled={agentLoading || !apiOnline}
                >
                  {agentLoading ? <RefreshCw className="nav-icon" style={{ animation: 'spin 2s linear infinite' }} size={16} /> : <ArrowRight size={16} />}
                  Send Instruction
                </button>
              </form>

              {/* Agent Error Output */}
              {agentError && (
                <div style={{ marginTop: '16px', color: 'var(--color-blocked)', fontSize: '0.9rem' }}>
                  <strong>Error:</strong> {agentError}
                </div>
              )}

              {/* Agent evaluation result */}
              {agentResult && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '12px' }}>
                  <div style={{ backgroundColor: 'rgba(255,255,255,0.02)', padding: '16px', borderRadius: '12px', border: '1px solid var(--card-border)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: '600', textTransform: 'uppercase' }}>Interpreted Tool Call:</span>
                      {agentResult.agent_mode && (
                        <span style={{ fontSize: '0.75rem', color: agentResult.agent_mode.includes('Offline') ? '#f39c12' : '#34d399', backgroundColor: 'rgba(255,255,255,0.05)', padding: '2px 8px', borderRadius: '12px', fontWeight: 'bold' }}>
                          {agentResult.agent_mode}
                        </span>
                      )}
                    </div>
                    {agentResult.action_decided ? (
                      <pre className="audit-item-details" style={{ marginTop: '8px' }}>
                        {JSON.stringify(agentResult.action_decided, null, 2)}
                      </pre>
                    ) : (
                      <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginTop: '8px' }}>None (Agent decided not to trigger any registered tool).</p>
                    )}
                  </div>

                  {agentResult.action_decided && (
                    <div className={`outcome-container ${agentResult.outcome}`}>
                      <span className={`outcome-badge ${agentResult.outcome}`}>
                        {agentResult.outcome}
                      </span>
                      
                      <div className="outcome-detail-grid">
                        <span className="outcome-detail-label">Matched Rule:</span>
                        <span className="outcome-detail-value"><code>{agentResult.matched_rule}</code></span>

                        <span className="outcome-detail-label">Reasoning:</span>
                        <span className="outcome-detail-value">{agentResult.reason}</span>

                        <span className="outcome-detail-label">Executed:</span>
                        <span className="outcome-detail-value" style={{ color: agentResult.executed ? 'var(--color-allowed)' : 'var(--color-blocked)' }}>
                          {agentResult.executed ? 'Yes ✓' : 'No ✗'}
                        </span>
                      </div>

                      {agentResult.result && (
                        <pre className="audit-item-details" style={{ margin: '10px 0px 0px 0px' }}>
                          {JSON.stringify(agentResult.result, null, 2)}
                        </pre>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* -------------------- VIEW 3: REVIEW QUEUE -------------------- */}
        {activeTab === 'Reviews' && (
          <div className="panel-card">
            <div className="panel-header">
              <h2>Human-In-The-Loop Reviews</h2>
              <p>Review items in the review queue. Approving runs the payload; rejecting drops it.</p>
            </div>

            {pendingReviews.length === 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '200px', gap: '16px', color: 'var(--text-secondary)' }}>
                <CheckCircle size={44} style={{ color: 'var(--color-allowed)' }} />
                <h3>No Actions Pending Review</h3>
                <p>Everything is currently evaluated and secure.</p>
              </div>
            ) : (
              <div>
                {pendingReviews.map((item) => (
                  <div key={item.id} className="review-item">
                    <div className="review-meta">
                      <span className="outcome-badge pending_review">Pending Review</span>
                      <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Logged at: {item.timestamp}</span>
                    </div>

                    <div>
                      <h3 style={{ fontSize: '1.25rem', marginBottom: '8px' }}>Action #{item.id}: <code>{item.tool}</code></h3>
                      <p style={{ color: 'var(--color-pending)', fontSize: '0.9rem', marginBottom: '12px' }}>
                        <strong>Trigger Reason:</strong> {item.reason}
                      </p>

                      {item.reviewer_context && (
                        <div style={{ backgroundColor: 'rgba(251,191,36,0.05)', border: '1px solid rgba(251,191,36,0.2)', padding: '14px', borderRadius: '8px', color: '#fbbf24', fontSize: '0.9rem', lineHeight: '1.4', marginBottom: '12px' }}>
                          <strong>Intelligent Safety Analysis Summary:</strong>
                          <p style={{ marginTop: '6px', color: 'var(--text-primary)' }}>{item.reviewer_context}</p>
                        </div>
                      )}
                      
                      <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: '600' }}>Parameters payload:</span>
                      <pre className="audit-item-details">
                        {JSON.stringify(item.params, null, 2)}
                      </pre>
                    </div>

                    {/* Resolution form */}
                    <div className="review-form">
                      <div className="review-form-row">
                        <div className="form-group">
                          <label className="form-label"><User size={12} style={{ marginRight: '6px' }} />Reviewer Name</label>
                          <input 
                            type="text" 
                            className="form-input" 
                            placeholder="e.g. Admin Guard"
                            value={reviewerName}
                            onChange={(e) => setReviewerName(e.target.value)}
                            required
                          />
                        </div>
                        <div className="form-group">
                          <label className="form-label">Reviewer Notes / Rejection Reason</label>
                          <input 
                            type="text" 
                            className="form-input" 
                            placeholder="Explain decision..."
                            value={reviewerNotes}
                            onChange={(e) => setReviewerNotes(e.target.value)}
                          />
                        </div>
                      </div>

                      <div className="review-buttons">
                        <button 
                          className="btn btn-approve"
                          onClick={() => handleReviewAction(item.id, true)}
                          disabled={reviewLoading !== null || !reviewerName.trim()}
                        >
                          {reviewLoading === item.id ? "Approving..." : "Approve Action"}
                        </button>
                        <button 
                          className="btn btn-reject"
                          onClick={() => handleReviewAction(item.id, false)}
                          disabled={reviewLoading !== null || !reviewerName.trim() || !reviewerNotes.trim()}
                        >
                          {reviewLoading === item.id ? "Rejecting..." : "Reject Action"}
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* -------------------- VIEW 4: AUDIT LOGS -------------------- */}
        {activeTab === 'Logs' && (
          <div className="panel-card">
            <div className="panel-header">
              <div>
                <h2>Real-time Audit Trail</h2>
                <p>Security trace of evaluated agent transactions.</p>
              </div>

              {/* Filter tools bar */}
              <div style={{ display: 'flex', gap: '16px' }}>
                <select 
                  className="form-select" 
                  style={{ width: '180px', padding: '6px 12px', fontSize: '0.85rem' }}
                  value={logsFilter}
                  onChange={(e) => setLogsFilter(e.target.value)}
                >
                  <option value="All">All Outcomes</option>
                  <option value="allowed">Allowed</option>
                  <option value="blocked">Blocked</option>
                  <option value="pending_review">Pending Review</option>
                </select>
              </div>
            </div>

            <div className="audit-list">
              {auditLogs
                .filter(log => logsFilter === 'All' || log.outcome === logsFilter)
                .map((log) => {
                  const isExpanded = expandedLogId === log.id
                  
                  return (
                    <div 
                      key={log.id} 
                      className="audit-item"
                      onClick={() => setExpandedLogId(isExpanded ? null : log.id)}
                    >
                      <div className="audit-item-top">
                        <div className="audit-item-meta">
                          <span className={`outcome-badge ${log.outcome}`}>
                            {log.outcome}
                          </span>
                          <span className="audit-item-id">
                            Transaction #{log.id} &mdash; <code>{log.tool}</code>
                          </span>
                        </div>
                        
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                          <span className="audit-item-time">{log.timestamp.split('.')[0].replace('T', ' ')}</span>
                          {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                        </div>
                      </div>

                      <div className="audit-item-body">
                        <span style={{ color: 'var(--text-primary)', fontWeight: '600' }}>Matched Rule:</span> <code>{log.matched_rule}</code> &mdash; {log.reason}
                        
                        {log.reviewer_name && (
                          <div style={{ marginTop: '8px', fontSize: '0.85rem', color: 'var(--color-pending)', display: 'flex', gap: '16px' }}>
                            <span><strong>Reviewer:</strong> {log.reviewer_name}</span>
                            <span><strong>Notes:</strong> {log.reviewer_notes || 'None'}</span>
                            <span><strong>Status:</strong> {log.review_status}</span>
                          </div>
                        )}
                      </div>

                      {isExpanded && (
                        <div className="audit-item-details" onClick={(e) => e.stopPropagation()} style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '12px', borderTop: '1px solid var(--card-border)', paddingTop: '12px' }}>
                          <div>
                            <strong>Parameters Payload:</strong>
                            <pre style={{ marginTop: '6px', fontSize: '0.85rem' }}>{JSON.stringify(log.params, null, 2)}</pre>
                          </div>

                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
                            {/* Layer 1 */}
                            <div style={{ backgroundColor: 'rgba(255,255,255,0.01)', padding: '12px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 'bold', fontSize: '0.9rem', marginBottom: '8px' }}>
                                📋 L1: YAML Rules
                              </div>
                              <div style={{ fontSize: '0.85rem' }}>
                                <div><strong>Outcome:</strong> <span className={`outcome-badge-inline ${log.layer1_outcome || log.outcome}`}>{log.layer1_outcome || log.outcome}</span></div>
                                <div style={{ marginTop: '4px' }}><strong>Rule:</strong> <code>{log.layer1_rule || log.matched_rule}</code></div>
                              </div>
                            </div>

                            {/* Layer 2 */}
                            <div style={{ backgroundColor: 'rgba(255,255,255,0.01)', padding: '12px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 'bold', fontSize: '0.9rem', marginBottom: '8px' }}>
                                🏷️ L2: Data Classification
                              </div>
                              <div style={{ fontSize: '0.85rem' }}>
                                <div><strong>Risk Level:</strong> <span style={{ textTransform: 'uppercase', fontWeight: 'bold', color: log.layer2_risk_level === 'critical' ? '#f87171' : log.layer2_risk_level === 'high' ? '#fb923c' : log.layer2_risk_level === 'medium' ? '#fbbf24' : '#34d399' }}>{log.layer2_risk_level || 'low'}</span></div>
                                <div style={{ marginTop: '6px', display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                                  <strong>Tags:</strong>
                                  {log.layer2_tags && log.layer2_tags.length > 0 ? (
                                    log.layer2_tags.map((t, i) => (
                                      <span key={i} style={{ fontSize: '0.7rem', backgroundColor: t === 'PII' || t === 'LEGAL_HOLD' ? 'rgba(248,113,113,0.15)' : t === 'FINANCIAL' || t === 'EXECUTIVE' ? 'rgba(251,146,60,0.15)' : 'rgba(52,211,153,0.15)', color: t === 'PII' || t === 'LEGAL_HOLD' ? '#f87171' : t === 'FINANCIAL' || t === 'EXECUTIVE' ? '#fb923c' : '#34d399', padding: '1px 6px', borderRadius: '4px', fontWeight: 'bold' }}>{t}</span>
                                    ))
                                  ) : (
                                    <span style={{ opacity: 0.5 }}>none</span>
                                  )}
                                </div>
                              </div>
                            </div>

                            {/* Layer 3 */}
                            <div style={{ backgroundColor: 'rgba(255,255,255,0.01)', padding: '12px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 'bold', fontSize: '0.9rem', marginBottom: '8px' }}>
                                🧠 L3: Semantic Risk
                              </div>
                              <div style={{ fontSize: '0.85rem' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                                  <span><strong>Risk Score:</strong></span>
                                  <span style={{ fontWeight: 'bold', color: log.layer3_risk_score >= 61 ? '#f87171' : log.layer3_risk_score >= 31 ? '#fb923c' : '#34d399' }}>{log.layer3_risk_score ?? 0}/100</span>
                                </div>
                                <div style={{ height: '6px', backgroundColor: 'rgba(255,255,255,0.05)', borderRadius: '3px', overflow: 'hidden', marginBottom: '8px' }}>
                                  <div style={{ height: '100%', width: `${log.layer3_risk_score ?? 0}%`, backgroundColor: log.layer3_risk_score >= 61 ? '#f87171' : log.layer3_risk_score >= 31 ? '#fb923c' : '#34d399' }} />
                                </div>
                                <div style={{ fontSize: '0.75rem', opacity: 0.8, fontStyle: 'italic' }}>"{log.layer3_reasoning || 'No semantic evaluation required'}"</div>
                              </div>
                            </div>

                            {/* Layer 4 */}
                            <div style={{ backgroundColor: 'rgba(255,255,255,0.01)', padding: '12px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 'bold', fontSize: '0.9rem', marginBottom: '8px' }}>
                                📈 L4: Behaviour Monitor
                              </div>
                              <div style={{ fontSize: '0.85rem' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                                  <span><strong>Anomaly Score:</strong></span>
                                  <span style={{ fontWeight: 'bold', color: log.layer4_status === 'alert' ? '#f87171' : log.layer4_status === 'warning' ? '#fb923c' : '#34d399' }}>{log.layer4_anomaly_score ?? 0}/100</span>
                                </div>
                                <div style={{ height: '6px', backgroundColor: 'rgba(255,255,255,0.05)', borderRadius: '3px', overflow: 'hidden', marginBottom: '8px' }}>
                                  <div style={{ height: '100%', width: `${log.layer4_anomaly_score ?? 0}%`, backgroundColor: log.layer4_status === 'alert' ? '#f87171' : log.layer4_status === 'warning' ? '#fb923c' : '#34d399' }} />
                                </div>
                                <div style={{ fontSize: '0.75rem', opacity: 0.8 }}>
                                  <strong>Status:</strong> <span style={{ fontWeight: 'bold' }}>{log.layer4_status || 'normal'}</span>
                                  {log.layer4_flags && log.layer4_flags.length > 0 && (
                                    <div style={{ color: '#fb923c', fontSize: '0.7rem', marginTop: '4px' }}>Flags: {log.layer4_flags.join(', ')}</div>
                                  )}
                                </div>
                              </div>
                            </div>
                          </div>

                          <div style={{ borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '8px', fontSize: '0.85rem' }}>
                            <strong>Verdict Reason:</strong> <span style={{ color: 'var(--text-primary)', fontWeight: 'bold' }}>{log.final_reason || log.reason}</span>
                          </div>
                        </div>
                      )}
                    </div>
                  )
                })}
            </div>
          </div>
        )}

        {/* -------------------- VIEW 4.5: PATTERN ALERTS -------------------- */}
        {activeTab === 'Patterns' && (
          <div className="panel-card">
            <div className="panel-header">
              <h2>Cross-Session Pattern Alerts</h2>
              <p>Dynamic detection of slow data exfiltration, rule probing, and agent scope drift across sessions.</p>
            </div>

            {patternAlerts.length === 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '220px', gap: '16px', color: 'var(--text-secondary)' }}>
                <CheckCircle size={44} style={{ color: 'var(--color-allowed)' }} />
                <h3>No Active Pattern Anomalies</h3>
                <p>No multi-session security risks or exfiltration patterns detected.</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {patternAlerts.map((alert, idx) => (
                  <div key={idx} style={{ backgroundColor: 'rgba(255,255,255,0.02)', border: '1px solid var(--card-border)', borderRadius: '12px', padding: '20px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                      <span style={{ fontSize: '0.8rem', backgroundColor: 'rgba(255,255,255,0.05)', padding: '3px 10px', borderRadius: '12px', textTransform: 'uppercase', fontWeight: 'bold', color: 'var(--text-secondary)' }}>
                        ⚠️ {alert.type.replace('_', ' ')}
                      </span>
                      <span className={`outcome-badge ${alert.severity === 'critical' ? 'blocked' : 'pending_review'}`} style={{ textTransform: 'uppercase' }}>
                        {alert.severity}
                      </span>
                    </div>

                    <h3 style={{ fontSize: '1.1rem', color: 'var(--text-primary)', marginBottom: '8px' }}>{alert.description}</h3>
                    
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginTop: '12px', padding: '12px', backgroundColor: 'rgba(255,255,255,0.01)', borderRadius: '8px', fontSize: '0.85rem' }}>
                      <div><strong>Agent ID:</strong> <code>{alert.agent_id}</code></div>
                      <div><strong>Recommended Action:</strong> <span style={{ color: '#fb923c', fontWeight: 'bold' }}>{alert.recommended_action.toUpperCase()}</span></div>
                      <div><strong>Detected At:</strong> {alert.detected_at.split('.')[0].replace('T', ' ')}</div>
                      <div><strong>Evidence Count:</strong> {alert.evidence.length} log transactions</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* -------------------- VIEW 5: RULES -------------------- */}
        {activeTab === 'Rules' && (
          <div className="panel-card">
            <div className="panel-header">
              <h2>Configured Policy Engine Rules</h2>
              <p>Loaded security rules from rules.yaml matching agent decisions.</p>
            </div>

            <div className="rules-grid">
              {policyRules.rules.map((rule, idx) => (
                <div key={idx} className="rule-card">
                  <div className="rule-card-header">
                    <span className="rule-card-title">{rule.name}</span>
                    <span className={`outcome-badge ${
                      rule.action === 'block' ? 'blocked' : rule.action === 'require_hitl' ? 'pending_review' : 'allowed'
                    }`}>
                      {rule.action === 'block' ? 'block' : rule.action === 'require_hitl' ? 'HITL' : 'allow'}
                    </span>
                  </div>

                  <p className="rule-card-desc">{rule.description}</p>

                  <div className="rule-card-meta">
                    <div><strong>TOOL FILTERS:</strong> {rule.tool}</div>
                    {rule.condition && (
                      <div style={{ marginTop: '4px' }}>
                        <strong>CONDITIONS:</strong><br />
                        <code style={{ color: 'var(--color-emerald)' }}>{rule.condition}</code>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>

            <div style={{ backgroundColor: 'rgba(255,255,255,0.02)', padding: '16px 20px', borderRadius: '12px', border: '1px solid var(--card-border)', marginTop: '12px' }}>
              <strong>Default Policy Action:</strong> &nbsp;
              <span className={`outcome-badge ${
                policyRules.default_action === 'block' ? 'blocked' : policyRules.default_action === 'require_hitl' ? 'pending_review' : 'allowed'
              }`}>
                {policyRules.default_action}
              </span>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginTop: '8px' }}>
                If an incoming action does not trigger any of the matching rule filters above, the default fallback action is applied.
              </p>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

export default App
