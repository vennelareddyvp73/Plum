import React, { useEffect, useState } from 'react'
import { useParams, useLocation } from 'react-router-dom'
import axios from 'axios'
import DecisionCard from '../components/DecisionCard'

const s = {
  heading:      { fontSize: 22, fontWeight: 700, marginBottom: 4 },
  claimId:      { fontSize: 13, color: '#94a3b8', marginBottom: 24 },
  card:         { background: '#fff', borderRadius: 16, padding: 24, boxShadow: '0 1px 4px rgba(0,0,0,.08)', marginBottom: 20 },
  sectionTitle: { fontWeight: 700, fontSize: 14, color: '#475569', marginBottom: 12 },
  docGrid:      { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 12 },
  docCard:      { background: '#f8fafc', borderRadius: 10, padding: 14, border: '1px solid #e2e8f0' },
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
  toast:        { background: '#f0fdf4', border: '1px solid #16a34a', borderRadius: 8, padding: 12, fontSize: 13, color: '#15803d', marginBottom: 16 },
  loader:       { textAlign: 'center', padding: 48, color: '#94a3b8' },
  metaRow:      { fontSize: 13, color: '#64748b', lineHeight: 2 },
  metaStrong:   { fontWeight: 600, color: '#1e293b' },
}

const DOC_LABELS = {
  prescription:   '📋 Prescription',
  pharmacy_bill:  '💊 Pharmacy Bill',
  diagnosis_test: '🧪 Lab Report',
  medical_bill:   '🏥 Medical Bill',
}

// Key fields to surface per doc type (avoids showing every null)
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

function DocCard({ doc }) {
  const [showRaw, setShowRaw] = useState(false)
  const conf   = doc.extraction_confidence
  const fields = DOC_FIELDS[doc.doc_type] || []
  const data   = doc.extracted_data || {}

  return (
    <div style={s.docCard}>
      <div style={s.docType}>{DOC_LABELS[doc.doc_type] || doc.doc_type}</div>

      {conf != null && (
        <div style={s.confRow}>
          <div style={s.bar}><div style={s.fill(conf)} /></div>
          <span style={s.confLabel(conf)}>{Math.round(conf * 100)}% confidence</span>
        </div>
      )}

      {fields.map(([label, fn]) => {
        const val = fn(data)
        if (!val) return null
        return (
          <div key={label} style={s.fieldRow}>
            <span style={s.fieldLabel}>{label}</span>
            <span style={s.fieldVal}>{String(val)}</span>
          </div>
        )
      })}


    </div>
  )
}

export default function ClaimDetail() {
  const { claimId }    = useParams()
  const location       = useLocation()
  const [data, setData]     = useState(null)
  const [loading, setLoading] = useState(true)
  const [appealMsg, setAppealMsg] = useState('')

  useEffect(() => {
    if (location.state?.decision) {
      setData({ claim_id: claimId, decision: location.state.decision, documents: [] })
      setLoading(false)
    }
    axios.get(`/api/claims/${claimId}`)
      .then(r => setData(r.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [claimId])

  const handleAppeal = async () => {
    try {
      await axios.post(`/api/claims/${claimId}/appeal`, null, {
        params: { notes: 'Claimant requested manual review' },
      })
      setAppealMsg('Your claim has been flagged for manual review. Our team will contact you within 2 business days.')
    } catch {
      setAppealMsg('Appeal request failed. Please contact support.')
    }
  }

  if (loading) return <div style={s.loader}>Loading claim details…</div>
  if (!data)   return <div style={s.loader}>Claim not found.</div>

  return (
    <>
      <h1 style={s.heading}>Claim Decision</h1>
      <div style={s.claimId}>Claim ID: {data.claim_id}</div>

      {appealMsg && <div style={s.toast}>{appealMsg}</div>}

      <DecisionCard
        decision={data.decision}
        claimId={data.claim_id}
        onAppeal={!appealMsg ? handleAppeal : undefined}
        categoryClaimed={data.category_claimed_amounts || data.decision?.category_claimed_amounts}
        categoryApproved={data.category_approved_amounts || data.decision?.category_approved_amounts}
        categoryBalances={data.category_balances}
      />

      {data.documents?.length > 0 && (
        <div style={s.card}>
          <div style={s.sectionTitle}>Extracted Document Data</div>
          <div style={s.docGrid}>
            {data.documents.map((doc, i) => <DocCard key={i} doc={doc} />)}
          </div>
        </div>
      )}

      {data.treatment_date && (
        <div style={s.card}>
          <div style={s.sectionTitle}>Claim Details</div>
          <div style={s.metaRow}>
            <div><span style={s.metaStrong}>Member ID: </span>{data.member_id}</div>
            <div><span style={s.metaStrong}>Treatment Date: </span>{data.treatment_date}</div>
            <div><span style={s.metaStrong}>Submitted: </span>{data.submission_date?.split('T')[0]}</div>
            <div><span style={s.metaStrong}>Status: </span>{data.status}</div>
            <div><span style={s.metaStrong}>Claimed: </span>₹{Number(data.claimed_amount || 0).toLocaleString('en-IN')}</div>
            {data.approved_amount != null && (
              <div><span style={s.metaStrong}>Approved: </span>₹{Number(data.approved_amount).toLocaleString('en-IN')}</div>
            )}
          </div>
        </div>
      )}
    </>
  )
}