import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'

const STATUS_COLORS = {
  APPROVED:      '#16a34a',
  REJECTED:      '#dc2626',
  PARTIAL:       '#d97706',
  MANUAL_REVIEW: '#2563eb',
  PENDING:       '#94a3b8',
}

const CAT_LABELS = {
  consultation: 'Consultation Fees',
  pharmacy: 'Pharmacy Expenses',
  diagnostic: 'Diagnostic Tests',
  dental_routine: 'Dental Routine Checkup',
  dental_procedure: 'Dental Procedure',
  vision: 'Vision Care',
  alternative: 'Alternative Medicine',
}

const CAT_ICONS = {
  consultation: '🩺',
  pharmacy: '💊',
  diagnostic: '🧪',
  dental_routine: '🦷',
  dental_procedure: '🏥',
  vision: '👓',
  alternative: '🌿',
}

const s = {
  heading:    { fontSize: 24, fontWeight: 700, marginBottom: 6 },
  sub:        { color: '#64748b', fontSize: 14, marginBottom: 28 },
  searchRow:  { display: 'flex', gap: 12, marginBottom: 24 },
  input:      { border: '1px solid #cbd5e1', borderRadius: 8, padding: '10px 14px', fontSize: 14, flex: 1, outline: 'none' },
  btn:        { background: '#6d28d9', color: '#fff', border: 'none', borderRadius: 8, padding: '10px 24px', cursor: 'pointer', fontSize: 14, fontWeight: 600 },
  statsGrid:  { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12, marginBottom: 24 },
  statCard:   { background: '#fff', borderRadius: 12, padding: '16px 20px', boxShadow: '0 1px 4px rgba(0,0,0,.07)', border: '1px solid #f1f5f9' },
  statLabel:  { fontSize: 11, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '.5px', marginBottom: 6 },
  statValue:  { fontSize: 20, fontWeight: 700, color: '#1e293b' },
  statSub:    { fontSize: 11, color: '#94a3b8', marginTop: 2 },
  bar:        { height: 6, background: '#e2e8f0', borderRadius: 3, overflow: 'hidden', marginTop: 8 },
  barFill: pct => ({
    height: '100%', borderRadius: 3,
    width: `${Math.min(pct, 100)}%`,
    background: pct > 80 ? '#dc2626' : pct > 60 ? '#d97706' : '#16a34a',
  }),
  table:      { width: '100%', borderCollapse: 'collapse', background: '#fff', borderRadius: 12, overflow: 'hidden', boxShadow: '0 1px 4px rgba(0,0,0,.08)' },
  th:         { padding: '12px 16px', textAlign: 'left', fontSize: 12, fontWeight: 700, color: '#64748b', background: '#f8fafc', borderBottom: '1px solid #e2e8f0' },
  td:         { padding: '14px 16px', fontSize: 14, color: '#1e293b', borderBottom: '1px solid #f1f5f9', cursor: 'pointer' },
  badge: st  => ({ display: 'inline-block', background: `${STATUS_COLORS[st] || '#94a3b8'}22`, color: STATUS_COLORS[st] || '#64748b', borderRadius: 6, padding: '2px 10px', fontSize: 12, fontWeight: 600 }),
  empty:      { textAlign: 'center', padding: 48, color: '#94a3b8' },
  error:      { color: '#dc2626', fontSize: 13, marginBottom: 16 },
  profileCard: { background: '#fff', borderRadius: 16, padding: 24, border: '1px solid #e2e8f0', boxShadow: '0 2px 4px rgba(0,0,0,.04)', marginBottom: 24 },
  sectionTitle: { fontWeight: 700, fontSize: 15, color: '#1e293b', marginBottom: 16 },
  metaText: { fontSize: 13, color: '#64748b', marginBottom: 6 },
  metaVal: { fontWeight: 600, color: '#1e293b' },
  limitsGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 14, marginTop: 16 },
  limitCard: { background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 12, padding: 16, position: 'relative' },
  progressContainer: { height: 6, background: '#e2e8f0', borderRadius: 3, width: '100%', marginTop: 8, overflow: 'hidden' },
  progressBar: pct => ({
    height: '100%',
    width: `${Math.min(pct, 100)}%`,
    borderRadius: 3,
    background: pct > 80 ? '#ef4444' : pct > 50 ? '#f59e0b' : '#10b981',
    transition: 'width 0.4s ease',
  }),
  policyBadge: active => ({
    background: active ? '#dcfce7' : '#fee2e2',
    color: active ? '#15803d' : '#b91c1c',
    borderRadius: 6,
    padding: '2px 8px',
    fontSize: 11,
    fontWeight: 700,
    display: 'inline-block',
  }),
}

function MemberStats({ stats }) {
  const usedPct = stats.annual_limit > 0
    ? Math.round((stats.ytd_approved / stats.annual_limit) * 100)
    : 0

  return (
    <div style={{ marginBottom: 24 }} className="fade-in">
      {/* Dynamic Summary Cards */}
      <div style={s.statsGrid}>
        <div style={s.statCard}>
          <div style={s.statLabel}>Member</div>
          <div style={{ fontSize: 16, fontWeight: 700, color: '#1e293b' }}>{stats.member_name}</div>
          <div style={s.statSub}>{stats.member_id}</div>
        </div>
        <div style={s.statCard}>
          <div style={s.statLabel}>YTD Approved</div>
          <div style={s.statValue}>₹{Number(stats.ytd_approved).toLocaleString('en-IN')}</div>
          <div style={s.bar}><div style={s.barFill(usedPct)} /></div>
          <div style={s.statSub}>{usedPct}% of annual limit used</div>
        </div>
        <div style={s.statCard}>
          <div style={s.statLabel}>Remaining Limit</div>
          <div style={{ ...s.statValue, color: stats.remaining_limit < 5000 ? '#dc2626' : '#16a34a' }}>
            ₹{Number(stats.remaining_limit).toLocaleString('en-IN')}
          </div>
          <div style={s.statSub}>of ₹{Number(stats.annual_limit).toLocaleString('en-IN')} annual</div>
        </div>
        <div style={s.statCard}>
          <div style={s.statLabel}>Total Claims</div>
          <div style={s.statValue}>{stats.total_claims}</div>
          <div style={s.statSub}>{stats.approved_claims} approved</div>
        </div>
      </div>

      {/* Member Details & Remaining Limits Grid */}
      <div style={s.profileCard} className="premium-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div style={{ ...s.sectionTitle, marginBottom: 0 }}>👤 Coverage Profile Details</div>
          <span style={s.policyBadge(stats.is_active)}>
            {stats.is_active ? 'Active Policy' : 'Inactive Policy'}
          </span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16, borderBottom: '1px solid #f1f5f9', paddingBottom: 16 }}>
          <div>
            <div style={s.metaText}>Gender: <span style={s.metaVal}>{stats.gender || '—'}</span></div>
            <div style={s.metaText}>Age: <span style={s.metaVal}>{stats.age || '—'} years</span></div>
          </div>
          <div>
            <div style={s.metaText}>Policy ID: <span style={s.metaVal}>{stats.member_id}</span></div>
            <div style={s.metaText}>Policy Year: <span style={s.metaVal}>{stats.policy_year}</span></div>
          </div>
          <div>
            <div style={s.metaText}>Policy Start: <span style={s.metaVal}>{stats.policy_start_date || '—'}</span></div>
            <div style={s.metaText}>Policy End: <span style={s.metaVal}>{stats.policy_end_date || '—'}</span></div>
          </div>
        </div>

        {/* Category limit tracker */}
        {stats.category_balances && (
          <>
            <div style={{ fontWeight: 700, fontSize: 13, color: '#475569', marginTop: 16 }}>
              Category Balance Tracker
            </div>
            <div style={s.limitsGrid}>
              {Object.entries(stats.category_balances).map(([cat, info]) => {
                const pct = info.limit > 0 ? (info.spent / info.limit) * 100 : 0
                return (
                  <div key={cat} style={s.limitCard}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
                      <span style={{ fontWeight: 600, color: '#334155' }}>
                        {CAT_ICONS[cat] || '📋'} {CAT_LABELS[cat] || cat}
                      </span>
                    </div>
                    <div style={{ fontSize: 16, fontWeight: 800, color: info.remaining < 1000 ? '#ef4444' : '#16a34a' }}>
                      ₹{Number(info.remaining).toLocaleString('en-IN')}
                    </div>
                    <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 1 }}>
                      remaining of ₹{Number(info.limit).toLocaleString('en-IN')}
                    </div>
                    <div style={s.progressContainer}>
                      <div style={s.progressBar(pct)} />
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: '#94a3b8', marginTop: 4 }}>
                      <span>{Math.round(pct)}% Used</span>
                      <span>₹{Number(info.spent).toLocaleString('en-IN')} spent</span>
                    </div>
                  </div>
                )
              })}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export default function ClaimHistory() {
  const navigate = useNavigate()
  const [memberId, setMemberId] = useState('')
  const [claims, setClaims]     = useState(null)
  const [stats, setStats]       = useState(null)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState('')

  const search = async () => {
    const id = memberId.trim()
    if (!id) return setError('Enter a Member ID.')
    setError('')
    setLoading(true)
    setClaims(null)
    setStats(null)
    try {
      const [claimsRes, statsRes] = await Promise.allSettled([
        axios.get('/api/claims', { params: { member_id: id } }),
        axios.get(`/api/members/${id}/stats`),
      ])
      if (claimsRes.status === 'fulfilled') setClaims(claimsRes.value.data)
      else setError('Failed to fetch claims. Check the Member ID.')
      if (statsRes.status === 'fulfilled') setStats(statsRes.value.data)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <h1 style={s.heading}>Claim History</h1>
      <p style={s.sub}>Look up all claims and policy usage for a member</p>

      <div style={s.searchRow}>
        <input
          style={s.input}
          placeholder="Enter Member ID (e.g. EMP001)"
          value={memberId}
          onChange={e => setMemberId(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && search()}
        />
        <button style={s.btn} onClick={search} disabled={loading}>
          {loading ? 'Loading…' : 'Search'}
        </button>
      </div>

      {error && <div style={s.error}>{error}</div>}

      {stats && <MemberStats stats={stats} />}

      {claims !== null && (
        claims.length === 0
          ? <div style={s.empty}>No claims found for {memberId}.</div>
          : (
            <table style={s.table}>
              <thead>
                <tr>
                  {['Claim ID', 'Treatment Date', 'Claimed (₹)', 'Approved (₹)', 'Status', 'Submitted'].map(h => (
                    <th key={h} style={s.th}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {claims.map(c => (
                  <tr
                    key={c.claim_id}
                    onClick={() => navigate(`/claims/${c.claim_id}`)}
                    onMouseEnter={e => e.currentTarget.style.background = '#f8fafc'}
                    onMouseLeave={e => e.currentTarget.style.background = ''}
                  >
                    <td style={s.td}><span style={{ fontFamily: 'monospace', fontSize: 13 }}>{c.claim_id}</span></td>
                    <td style={s.td}>{c.treatment_date}</td>
                    <td style={s.td}>₹{Number(c.claimed_amount || 0).toLocaleString('en-IN')}</td>
                    <td style={s.td}>{c.approved_amount != null ? `₹${Number(c.approved_amount).toLocaleString('en-IN')}` : '—'}</td>
                    <td style={s.td}><span style={s.badge(c.status)}>{c.status}</span></td>
                    <td style={s.td}>{c.submission_date?.split('T')[0]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
      )}
    </>
  )
}