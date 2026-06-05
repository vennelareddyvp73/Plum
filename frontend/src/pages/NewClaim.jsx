import React, { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import axios from 'axios'
import DocumentUpload from '../components/DocumentUpload'
import DecisionCard from '../components/DecisionCard'

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
  heading: { fontSize: 26, fontWeight: 800, color: '#1e293b', marginBottom: 6, letterSpacing: '-0.5px' },
  sub: { color: '#64748b', fontSize: 14, marginBottom: 28 },
  tabsContainer: { display: 'flex', gap: 4, background: '#e2e8f0', padding: 4, borderRadius: 12, marginBottom: 28, maxWidth: 320 },
  tabBtn: (active) => ({
    flex: 1,
    padding: '8px 16px',
    borderRadius: 8,
    border: 'none',
    background: active ? '#fff' : 'transparent',
    color: active ? '#6d28d9' : '#64748b',
    fontWeight: 600,
    fontSize: 13,
    cursor: 'pointer',
    boxShadow: active ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
    transition: 'all 0.2s ease',
  }),
  card: { background: '#fff', borderRadius: 16, padding: 28, boxShadow: '0 4px 6px -1px rgba(0,0,0,.05), 0 2px 4px -1px rgba(0,0,0,.03)', border: '1px solid #e2e8f0', marginBottom: 24 },
  sectionTitle: { fontWeight: 700, marginBottom: 16, fontSize: 16, color: '#1e293b', display: 'flex', alignItems: 'center', gap: 8 },
  row: { display: 'flex', gap: 16, marginBottom: 16, flexWrap: 'wrap' },
  field: { display: 'flex', flexDirection: 'column', flex: 1, minWidth: 220 },
  label: { fontSize: 12, fontWeight: 600, color: '#475569', marginBottom: 6 },
  input: {
    border: '1px solid #cbd5e1', borderRadius: 8, padding: '10px 14px',
    fontSize: 14, outline: 'none', width: '100%', transition: 'border-color 0.2s',
  },
  btn: (loading, variant = 'primary') => ({
    background: loading ? '#a78bfa' : (variant === 'primary' ? '#6d28d9' : '#f1f5f9'),
    color: variant === 'primary' ? '#fff' : '#475569',
    border: 'none', borderRadius: 10,
    padding: '12px 32px', fontSize: 14, fontWeight: 600,
    cursor: loading ? 'not-allowed' : 'pointer', width: '100%',
    transition: 'all 0.2s',
  }),
  err: { background: '#fff1f2', border: '1px solid #fca5a5', borderRadius: 10, padding: 14, fontSize: 13, color: '#b91c1c', marginBottom: 20 },
  
  // Dashboard Styles
  kpiGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 16, marginBottom: 28 },
  kpiCard: (color) => ({
    background: '#fff',
    borderRadius: 16,
    padding: '24px 20px',
    boxShadow: '0 4px 6px -1px rgba(0,0,0,.03)',
    borderLeft: `5px solid ${color}`,
    borderTop: '1px solid #f1f5f9',
    borderRight: '1px solid #f1f5f9',
    borderBottom: '1px solid #f1f5f9',
  }),
  kpiVal: { fontSize: 24, fontWeight: 800, color: '#0f172a', margin: '4px 0 2px 0' },
  kpiLabel: { fontSize: 11, fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px' },
  
  // Member eligibility tracker styles
  badge: (active) => ({
    background: active ? '#dcfce7' : '#fee2e2',
    color: active ? '#15803d' : '#b91c1c',
    borderRadius: 6,
    padding: '2px 8px',
    fontSize: 11,
    fontWeight: 700,
    display: 'inline-block',
  }),
  metaText: { fontSize: 13, color: '#64748b', marginBottom: 4 },
  metaVal: { fontWeight: 600, color: '#1e293b' },
  limitsGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 14, marginTop: 16, marginBottom: 24 },
  limitCard: {
    background: '#f8fafc',
    border: '1px solid #e2e8f0',
    borderRadius: 12,
    padding: 16,
    position: 'relative',
    overflow: 'hidden',
  },
  progressContainer: { height: 6, background: '#e2e8f0', borderRadius: 3, width: '100%', marginTop: 10, overflow: 'hidden' },
  progressBar: (pct) => ({
    height: '100%',
    width: `${Math.min(pct, 100)}%`,
    borderRadius: 3,
    background: pct > 80 ? '#ef4444' : pct > 50 ? '#f59e0b' : '#10b981',
    transition: 'width 0.4s ease',
  }),
  
  // Table
  table: { width: '100%', borderCollapse: 'collapse', background: '#fff', borderRadius: 12, overflow: 'hidden', border: '1px solid #e2e8f0' },
  th: { padding: '12px 16px', textAlign: 'left', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color: '#64748b', background: '#f8fafc', borderBottom: '1px solid #e2e8f0' },
  td: { padding: '14px 16px', fontSize: 13, color: '#1e293b', borderBottom: '1px solid #f1f5f9' },
  statusBadge: (st) => ({
    display: 'inline-block',
    background: `${STATUS_COLORS[st] || '#94a3b8'}15`,
    color: STATUS_COLORS[st] || '#64748b',
    borderRadius: 6,
    padding: '2px 8px',
    fontSize: 12,
    fontWeight: 600,
  }),
}

const DOC_LABELS = {
  prescription:   '📋 Prescription Details',
  pharmacy_bill:  '💊 Pharmacy Bill Details',
  diagnosis_test: '🧪 Lab Report Details',
  medical_bill:   '🏥 Medical Bill Details',
}

const DOC_FIELDS = {
  prescription: [
    ['Doctor',       d => d.doctor_name],
    ['Reg. No.',     d => d.doctor_registration],
    ['Patient',      d => d.patient_name],
    ['Date',         d => d.date],
    ['Diagnosis',    d => d.diagnosis],
    ['Medicines',    d => d.medicines?.map(m => m.name).join(', ')],
    ['Tests advised',d => d.investigations_advised?.join(', ')],
    ['Stamp',        d => d.has_doctor_stamp ? 'Yes' : 'No'],
  ],
  pharmacy_bill: [
    ['Pharmacy',     d => d.pharmacy_name],
    ['Patient',      d => d.patient_name],
    ['Bill No.',     d => d.bill_number],
    ['Date',         d => d.date],
    ['Items',        d => d.items?.map(i => i.name).join(', ')],
    ['Total',        d => d.total_amount != null ? `₹${Number(d.total_amount).toLocaleString('en-IN')}` : null],
  ],
  diagnosis_test: [
    ['Lab',          d => d.lab_name],
    ['Patient',      d => d.patient_name],
    ['Date',         d => d.date],
    ['Tests',        d => d.tests?.map(t => t.test_name).join(', ')],
    ['Remarks',      d => d.remarks],
  ],
  medical_bill: [
    ['Hospital',     d => d.hospital_name],
    ['Patient',      d => d.patient_name],
    ['Bill No.',     d => d.bill_number],
    ['Date',         d => d.date],
    ['Items',        d => d.items?.map(i => i.description).join(', ')],
    ['Total',        d => d.total_amount != null ? `₹${Number(d.total_amount).toLocaleString('en-IN')}` : null],
  ],
}

const docStyles = {
  docGrid:      { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 12, marginTop: 12 },
  docCard:      { background: '#f8fafc', borderRadius: 10, padding: 14, border: '1px solid #e2e8f0', textAlign: 'left' },
  docType:      { fontWeight: 600, fontSize: 13, color: '#1e293b', marginBottom: 6 },
  confRow:      { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 },
  bar:          { flex: 1, height: 6, background: '#e2e8f0', borderRadius: 3, overflow: 'hidden' },
  fill:   (c)  => ({ height: '100%', width: `${Math.round(c * 100)}%`, borderRadius: 3, background: c > 0.7 ? '#16a34a' : c > 0.4 ? '#d97706' : '#dc2626' }),
  confLabel:(c) => ({ fontSize: 11, fontWeight: 600, color: c > 0.7 ? '#16a34a' : c > 0.4 ? '#d97706' : '#dc2626', whiteSpace: 'nowrap' }),
  toggle:       { fontSize: 12, color: '#6d28d9', cursor: 'pointer', textDecoration: 'underline', marginTop: 4 },
  fieldRow:     { display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '4px 0', borderBottom: '1px solid #f1f5f9' },
  fieldLabel:   { color: '#94a3b8' },
  fieldVal:     { color: '#1e293b', fontWeight: 500, textAlign: 'right', maxWidth: '60%' },
  rawJson:      { fontSize: 11, background: '#f1f5f9', borderRadius: 6, padding: 10, overflow: 'auto', maxHeight: 220, marginTop: 8 },
}

function DocCard({ doc }) {
  const [showRaw, setShowRaw] = useState(false)
  const conf   = doc.extraction_confidence
  const fields = DOC_FIELDS[doc.doc_type] || []
  const data   = doc.extracted_data || {}

  return (
    <div style={docStyles.docCard} className="premium-card">
      <div style={docStyles.docType}>{DOC_LABELS[doc.doc_type] || doc.doc_type}</div>

      {conf != null && (
        <div style={docStyles.confRow}>
          <div style={docStyles.bar}><div style={docStyles.fill(conf)} /></div>
          <span style={docStyles.confLabel(conf)}>{Math.round(conf * 100)}% confidence</span>
        </div>
      )}

      {fields.map(([label, fn]) => {
        const val = fn(data)
        if (!val) return null
        return (
          <div key={label} style={docStyles.fieldRow}>
            <span style={docStyles.fieldLabel}>{label}</span>
            <span style={docStyles.fieldVal}>{String(val)}</span>
          </div>
        )
      })}


    </div>
  )
}

export default function NewClaim() {
  const navigate = useNavigate()
  const location = useLocation()
  
  // Parse tab from query param
  const queryParams = new URLSearchParams(location.search)
  const activeTab = queryParams.get('tab') === 'new-claim' ? 'new-claim' : 'dashboard'
  
  // --- Dashboard States ---
  const [dbStats, setDbStats] = useState(null)
  const [statsLoading, setStatsLoading] = useState(false)
  
  // --- New Claim / Eligibility States ---
  const [memberId, setMemberId] = useState('')
  const [treatmentDate, setTreatmentDate] = useState('')
  const [memberStats, setMemberStats] = useState(null)
  const [memberClaims, setMemberClaims] = useState([])
  const [lookupLoading, setLookupLoading] = useState(false)
  const [lookupError, setLookupError] = useState('')
  
  // --- Upload / Submission States ---
  const [step, setStep] = useState(0) // 0: details/eligibility, 1: processing, 2: results
  const [files, setFiles] = useState({ prescription: null, pharmacy_bill: null, diagnosis_test: null, medical_bill: null })
  const [submitLoading, setSubmitLoading] = useState(false)
  const [submitError, setSubmitError] = useState('')
  const [statusMsg, setStatusMsg] = useState('')
  const [decisionResult, setDecisionResult] = useState(null)
  const [createdClaimId, setCreatedClaimId] = useState('')
  const [submittedDocs, setSubmittedDocs] = useState([])

  // Fetch dashboard stats if tab is dashboard
  useEffect(() => {
    if (activeTab === 'dashboard') {
      setStatsLoading(true)
      axios.get('/api/claims/dashboard-stats')
        .then(r => setDbStats(r.data))
        .catch(() => {})
        .finally(() => setStatsLoading(false))
    }
  }, [activeTab])

  // Trigger eligibility & history lookup automatically when EMPID and date are present
  useEffect(() => {
    const memId = memberId.trim()
    if (memId && treatmentDate && activeTab === 'new-claim') {
      setLookupLoading(true)
      setLookupError('')
      setMemberStats(null)
      setMemberClaims([])
      
      Promise.allSettled([
        axios.get(`/api/members/${memId}/stats`, { params: { treatment_date: treatmentDate } }),
        axios.get('/api/claims', { params: { member_id: memId } }),
      ]).then(([statsRes, claimsRes]) => {
        if (statsRes.status === 'fulfilled') {
          setMemberStats(statsRes.value.data)
        } else {
          setLookupError(statsRes.reason?.response?.data?.detail || 'Member details could not be found. Check ID.')
        }
        
        if (claimsRes.status === 'fulfilled') {
          setMemberClaims(claimsRes.value.data)
        }
      }).catch(e => {
        setLookupError('Lookup failed. Make sure member ID is correct.')
      }).finally(() => {
        setLookupLoading(false)
      })
    } else {
      // Clear stats if inputs cleared
      if (!memId || !treatmentDate) {
        setMemberStats(null)
        setMemberClaims([])
      }
    }
  }, [memberId, treatmentDate, activeTab])

  const handleFile = (docType, file) => setFiles(f => ({ ...f, [docType]: file }))
  const hasAnyFile = Object.values(files).some(Boolean)

  const submit = async () => {
    setSubmitError('')
    if (!memberId.trim()) return setSubmitError('Member ID is required.')
    if (!treatmentDate) return setSubmitError('Treatment date is required.')
    if (!hasAnyFile) return setSubmitError('Please upload at least one document.')

    setSubmitLoading(true)
    setStep(1)
    setStatusMsg('Uploading documents…')

    const form = new FormData()
    form.append('member_id', memberId.trim())
    form.append('treatment_date', treatmentDate)
    Object.entries(files).forEach(([k, f]) => { if (f) form.append(k, f) })

    try {
      setStatusMsg('Initiating AI OCR document parsing…')
      const { data } = await axios.post('/api/claims/submit', form)
      
      // Re-fetch member stats to get updated remaining limits and YTD approved values
      try {
        const statsRes = await axios.get(`/api/members/${memberId.trim()}/stats`, { params: { treatment_date: treatmentDate } })
        setMemberStats(statsRes.data)
      } catch (err) {
        console.error("Failed to re-fetch member stats after submission", err)
      }

      setCreatedClaimId(data.claim_id)
      setDecisionResult(data.decision)
      setSubmittedDocs(data.documents || [])
      setStep(2) // Move to inline decision page
    } catch (e) {
      setSubmitError(e.response?.data?.detail || 'Adjudication submission failed. Please try again.')
      setStep(0)
    } finally {
      setSubmitLoading(false)
    }
  }

  const resetClaimForm = () => {
    setFiles({ prescription: null, pharmacy_bill: null, diagnosis_test: null, medical_bill: null })
    setDecisionResult(null)
    setSubmittedDocs([])
    setCreatedClaimId('')
    setMemberStats(null)
    setMemberClaims([])
    setMemberId('')
    setTreatmentDate('')
    setStep(0)
  }

  const switchTab = (tabName) => {
    navigate(`/?tab=${tabName}`)
  }

  return (
    <div className="fade-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <div>
          <h1 style={s.heading}>Plum Claims Portal</h1>
          <p style={s.sub}>AI-Assisted OPD Medical Claims Processing</p>
        </div>
        <div style={s.tabsContainer}>
          <button style={s.tabBtn(activeTab === 'dashboard')} onClick={() => switchTab('dashboard')}>
            Dashboard
          </button>
          <button style={s.tabBtn(activeTab === 'new-claim')} onClick={() => switchTab('new-claim')}>
            New Claim
          </button>
        </div>
      </div>

      {/* --- DASHBOARD TAB --- */}
      {activeTab === 'dashboard' && (
        <div className="fade-in">
          {statsLoading ? (
            <div style={{ textAlign: 'center', padding: 48, color: '#94a3b8' }}>Loading dashboard stats…</div>
          ) : dbStats ? (
            <>
              {/* KPI Cards */}
              <div style={s.kpiGrid}>
                <div style={s.kpiCard('#16a34a')} className="premium-card">
                  <div style={s.kpiLabel}>Total Approved Money</div>
                  <div style={{ ...s.kpiVal, color: '#16a34a' }}>
                    ₹{Number(dbStats.total_approved_amount || 0).toLocaleString('en-IN')}
                  </div>
                  <div style={{ fontSize: 11, color: '#64748b' }}>Across all adjudicated claims</div>
                </div>
                <div style={s.kpiCard('#10b981')} className="premium-card">
                  <div style={s.kpiLabel}>Approved Claims</div>
                  <div style={s.kpiVal}>{dbStats.count_approved}</div>
                  <div style={{ fontSize: 11, color: '#64748b' }}>Fully approved claims</div>
                </div>
                <div style={s.kpiCard('#d97706')} className="premium-card">
                  <div style={s.kpiLabel}>Partially Approved</div>
                  <div style={s.kpiVal}>{dbStats.count_partially_approved}</div>
                  <div style={{ fontSize: 11, color: '#64748b' }}>With partial deductions</div>
                </div>
                <div style={s.kpiCard('#dc2626')} className="premium-card">
                  <div style={s.kpiLabel}>Rejected Claims</div>
                  <div style={s.kpiVal}>{dbStats.count_rejected}</div>
                  <div style={{ fontSize: 11, color: '#64748b' }}>Uncovered/policy violations</div>
                </div>
                <div style={s.kpiCard('#2563eb')} className="premium-card">
                  <div style={s.kpiLabel}>Manual Review Needed</div>
                  <div style={s.kpiVal}>{dbStats.count_manual_review}</div>
                  <div style={{ fontSize: 11, color: '#64748b' }}>Flagged for administrator review</div>
                </div>
              </div>

              {/* Recent Claims Feed */}
              <div style={s.card}>
                <div style={s.sectionTitle}>
                  <span>🕒</span> Recent Live Activity
                </div>
                {dbStats.recent_claims?.length === 0 ? (
                  <div style={{ color: '#94a3b8', textAlign: 'center', padding: 24 }}>No claims submitted yet.</div>
                ) : (
                  <div style={{ overflowX: 'auto' }}>
                    <table style={s.table}>
                      <thead>
                        <tr>
                          <th style={s.th}>Claim ID</th>
                          <th style={s.th}>Member Name</th>
                          <th style={s.th}>Treatment Date</th>
                          <th style={s.th}>Claimed Amount</th>
                          <th style={s.th}>Approved Amount</th>
                          <th style={s.th}>Status</th>
                          <th style={s.th}>Submitted</th>
                        </tr>
                      </thead>
                      <tbody>
                        {dbStats.recent_claims.map((c) => (
                          <tr
                            key={c.claim_id}
                            style={{ cursor: 'pointer' }}
                            onClick={() => navigate(`/claims/${c.claim_id}`)}
                            onMouseEnter={e => e.currentTarget.style.background = '#f8fafc'}
                            onMouseLeave={e => e.currentTarget.style.background = ''}
                          >
                            <td style={s.td}><span style={{ fontFamily: 'monospace', fontWeight: 600 }}>{c.claim_id}</span></td>
                            <td style={s.td}>{c.member_name}</td>
                            <td style={s.td}>{c.treatment_date}</td>
                            <td style={s.td}>₹{Number(c.claimed_amount).toLocaleString('en-IN')}</td>
                            <td style={s.td}>{c.approved_amount != null ? `₹${Number(c.approved_amount).toLocaleString('en-IN')}` : '—'}</td>
                            <td style={s.td}><span style={s.statusBadge(c.status)}>{c.status}</span></td>
                            <td style={s.td}>{c.submission_date?.split(' ')[0]}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </>
          ) : (
            <div style={{ textAlign: 'center', padding: 48, color: '#94a3b8' }}>Failed to load dashboard data.</div>
          )}
        </div>
      )}

      {/* --- NEW CLAIM TAB --- */}
      {activeTab === 'new-claim' && (
        <div className="fade-in">
          {submitError && <div style={s.err}>{submitError}</div>}

          {/* STEP 0: Initial inputs & benefit checker */}
          {step === 0 && (
            <>
              {/* Profile Lookup Input */}
              <div style={s.card}>
                <div style={s.sectionTitle}>
                  <span>🔍</span> Step 1: Member Benefit & Eligibility Check
                </div>
                <div style={s.row}>
                  <div style={s.field}>
                    <label style={s.label}>Member ID (EMPID) *</label>
                    <input
                      style={s.input}
                      placeholder="e.g. EMP001"
                      value={memberId}
                      onChange={(e) => setMemberId(e.target.value)}
                    />
                  </div>
                  <div style={s.field}>
                    <label style={s.label}>Treatment Date *</label>
                    <input
                      style={s.input}
                      type="date"
                      value={treatmentDate}
                      onChange={(e) => setTreatmentDate(e.target.value)}
                    />
                  </div>
                </div>
                {!memberStats && !lookupLoading && (
                  <p style={{ fontSize: 13, color: '#94a3b8', fontStyle: 'italic' }}>
                    💡 Fill both fields to instantly load coverage limits, age, and claims history.
                  </p>
                )}

                {lookupLoading && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: 12 }}>
                    <div className="spin-slow" style={{ fontSize: 18 }}>⚙️</div>
                    <span style={{ fontSize: 13, color: '#64748b' }}>Fetching eligibility parameters…</span>
                  </div>
                )}

                {lookupError && <div style={{ ...s.err, marginTop: 12, marginBottom: 0 }}>{lookupError}</div>}
              </div>

              {/* Dynamic Member Benefit Details Panel */}
              {memberStats && (
                <div className="fade-in">
                  <div style={s.card}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, flexWrap: 'wrap', gap: 10 }}>
                      <div style={{ ...s.sectionTitle, marginBottom: 0 }}>
                        <span>👤</span> Member Coverage Profile
                      </div>
                      <span style={s.badge(memberStats.is_active)}>
                        {memberStats.is_active ? 'Active Policy' : 'Inactive Policy'}
                      </span>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16, marginBottom: 20 }}>
                      <div>
                        <div style={s.metaText}>Name: <span style={s.metaVal}>{memberStats.member_name}</span></div>
                        <div style={s.metaText}>Gender: <span style={s.metaVal}>{memberStats.gender}</span></div>
                        <div style={s.metaText}>Age: <span style={s.metaVal}>{memberStats.age || '—'} years</span></div>
                      </div>
                      <div>
                        <div style={s.metaText}>Policy ID: <span style={s.metaVal}>{memberStats.member_id}</span></div>
                        <div style={s.metaText}>Policy Start: <span style={s.metaVal}>{memberStats.policy_start_date}</span></div>
                        <div style={s.metaText}>Policy End: <span style={s.metaVal}>{memberStats.policy_end_date}</span></div>
                      </div>
                      <div>
                        <div style={s.metaText}>YTD Approved: <span style={s.metaVal}>₹{Number(memberStats.ytd_approved).toLocaleString('en-IN')}</span></div>
                        <div style={s.metaText}>Annual Coverage: <span style={s.metaVal}>₹{Number(memberStats.annual_limit).toLocaleString('en-IN')}</span></div>
                        <div style={s.metaText}>Remaining Cover: <span style={{ ...s.metaVal, color: '#16a34a' }}>₹{Number(memberStats.remaining_limit).toLocaleString('en-IN')}</span></div>
                      </div>
                    </div>

                    {/* Category Remaining Limits Tracker */}
                    <div style={{ fontWeight: 700, fontSize: 14, color: '#475569', borderTop: '1px solid #e2e8f0', paddingTop: 16, marginTop: 12 }}>
                      Category Balance Tracker (for {memberStats.policy_year})
                    </div>
                    
                    <div style={s.limitsGrid}>
                      {Object.entries(memberStats.category_balances || {}).map(([cat, info]) => {
                        const pct = info.limit > 0 ? (info.spent / info.limit) * 100 : 0
                        return (
                          <div key={cat} style={s.limitCard} className="premium-card">
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 13, marginBottom: 6 }}>
                              <span style={{ fontWeight: 600, color: '#1e293b' }}>
                                {CAT_ICONS[cat] || '📋'} {CAT_LABELS[cat] || cat}
                              </span>
                            </div>
                            <div style={{ fontSize: 18, fontWeight: 800, color: info.remaining < 1000 ? '#ef4444' : '#10b981' }}>
                              ₹{Number(info.remaining).toLocaleString('en-IN')}
                            </div>
                            <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>
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

                    {/* Previous claims check */}
                    {memberClaims && memberClaims.length > 0 && (
                      <div style={{ marginTop: 20 }}>
                        <div style={{ fontWeight: 700, fontSize: 14, color: '#475569', marginBottom: 10 }}>
                          Claim History ({memberClaims.length} Claim{memberClaims.length > 1 ? 's' : ''})
                        </div>
                        <div style={{ maxHeight: 200, overflowY: 'auto', border: '1px solid #e2e8f0', borderRadius: 8 }}>
                          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                            <thead>
                              <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
                                <th style={{ ...s.th, padding: '8px 12px' }}>Claim ID</th>
                                <th style={{ ...s.th, padding: '8px 12px' }}>Treatment Date</th>
                                <th style={{ ...s.th, padding: '8px 12px' }}>Claimed Amount</th>
                                <th style={{ ...s.th, padding: '8px 12px' }}>Approved Amount</th>
                                <th style={{ ...s.th, padding: '8px 12px' }}>Status</th>
                              </tr>
                            </thead>
                            <tbody>
                              {memberClaims.map((claim) => (
                                <tr key={claim.claim_id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                                  <td style={{ ...s.td, padding: '8px 12px', fontFamily: 'monospace' }}>{claim.claim_id}</td>
                                  <td style={{ ...s.td, padding: '8px 12px' }}>{claim.treatment_date}</td>
                                  <td style={{ ...s.td, padding: '8px 12px' }}>₹{Number(claim.claimed_amount).toLocaleString('en-IN')}</td>
                                  <td style={{ ...s.td, padding: '8px 12px' }}>{claim.approved_amount != null ? `₹${Number(claim.approved_amount).toLocaleString('en-IN')}` : '—'}</td>
                                  <td style={{ ...s.td, padding: '8px 12px' }}><span style={s.statusBadge(claim.status)}>{claim.status}</span></td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* STEP 2: File upload unlocking */}
                  <div style={s.card} className="fade-in">
                    <div style={s.sectionTitle}>
                      <span>📤</span> Step 2: Upload Medical Bills & Documents
                    </div>
                    <p style={{ fontSize: 13, color: '#64748b', marginBottom: 16 }}>
                      Select or drag medical claims files. The AI parser will scan items, match billing names, check copays and cross-reference policy terms.
                    </p>
                    
                    <DocumentUpload files={files} onChange={handleFile} />

                    <div style={{ marginTop: 24 }}>
                      <button
                        style={s.btn(submitLoading)}
                        onClick={submit}
                        disabled={submitLoading || !hasAnyFile}
                        className="premium-btn"
                      >
                        {submitLoading ? 'Processing…' : '🚀 Upload & Run AI Adjudication'}
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}

          {/* STEP 1: Processing Animation */}
          {step === 1 && (
            <div style={{ ...s.card, textAlign: 'center', padding: '64px 32px' }} className="fade-in">
              <div className="spin-slow" style={{ fontSize: 64, marginBottom: 24, display: 'inline-block' }}>⚙️</div>
              <div style={{ fontWeight: 800, fontSize: 22, color: '#1e293b', marginBottom: 12 }}>
                AI Adjudication In Progress…
              </div>
              <div style={{ color: '#4f46e5', fontWeight: 600, fontSize: 15, marginBottom: 8 }} className="pulse">
                {statusMsg}
              </div>
              <div style={{ color: '#94a3b8', fontSize: 13 }}>
                Running compliance checks, bill extraction, and sub-limits evaluations.
              </div>
              <div style={{ color: '#cbd5e1', fontSize: 11, marginTop: 16 }}>
                Please do not refresh. This takes approximately 10–25 seconds.
              </div>
            </div>
          )}

          {/* STEP 2: Inline AI Verdict Page */}
          {step === 2 && decisionResult && (
            <div className="fade-in">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                <h2 style={{ fontSize: 20, fontWeight: 800, color: '#0f172a' }}>AI Adjudication Report</h2>
                <div style={{ fontSize: 13, color: '#64748b', fontFamily: 'monospace' }}>
                  ID: {createdClaimId}
                </div>
              </div>

              <DecisionCard
                decision={decisionResult}
                claimId={createdClaimId}
                categoryClaimed={decisionResult.category_claimed_amounts}
                categoryApproved={decisionResult.category_approved_amounts}
                categoryBalances={memberStats?.category_balances}
                onAppeal={undefined} // handled or redirectable
              />

              {/* Display Extracted Document Data neatly! */}
              {submittedDocs.length > 0 && (
                <div style={{ ...s.card, marginTop: 24 }} className="fade-in">
                  <div style={s.sectionTitle}>
                    <span>📄</span> AI Extracted Information
                  </div>
                  <div style={docStyles.docGrid}>
                    {submittedDocs.map((doc, i) => <DocCard key={i} doc={doc} />)}
                  </div>
                </div>
              )}

              <div style={{ display: 'flex', gap: 12, marginTop: 12, marginBottom: 36 }}>
                <button
                  style={{ ...s.btn(false, 'secondary'), flex: 1 }}
                  onClick={resetClaimForm}
                  className="premium-btn"
                >
                  Submit Another Claim
                </button>
                <button
                  style={{ ...s.btn(false, 'primary'), flex: 1 }}
                  onClick={() => navigate(`/claims/${createdClaimId}`)}
                  className="premium-btn"
                >
                  View Full Claims Report
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}