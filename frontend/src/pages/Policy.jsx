import React, { useEffect, useState } from 'react'
import axios from 'axios'

const s = {
  section: { marginBottom: 32 },
  card: {
    background: '#fff',
    border: '1px solid #e5e7eb',
    borderRadius: 10,
    padding: '20px 24px',
    marginBottom: 16,
  },
  h2: { fontSize: 20, fontWeight: 700, color: '#1e1b4b', marginBottom: 16 },
  h3: { fontSize: 15, fontWeight: 600, color: '#374151', marginBottom: 10 },
  row: { display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid #f3f4f6', fontSize: 14 },
  label: { color: '#6b7280' },
  value: { fontWeight: 600, color: '#111827' },
  badge: {
    display: 'inline-block',
    padding: '2px 10px',
    borderRadius: 12,
    fontSize: 12,
    fontWeight: 600,
    background: '#ede9fe',
    color: '#6d28d9',
    marginRight: 6,
    marginBottom: 6,
  },
  redBadge: {
    display: 'inline-block',
    padding: '2px 10px',
    borderRadius: 12,
    fontSize: 12,
    fontWeight: 600,
    background: '#fee2e2',
    color: '#dc2626',
    marginRight: 6,
    marginBottom: 6,
  },
  greenBadge: {
    display: 'inline-block',
    padding: '2px 10px',
    borderRadius: 12,
    fontSize: 12,
    fontWeight: 600,
    background: '#dcfce7',
    color: '#16a34a',
    marginRight: 6,
    marginBottom: 6,
  },
  grid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 },
  error: { color: '#dc2626', padding: 16, textAlign: 'center' },
  loading: { color: '#6b7280', padding: 16, textAlign: 'center' },
}

function Row({ label, value }) {
  return (
    <div style={s.row}>
      <span style={s.label}>{label}</span>
      <span style={s.value}>{value}</span>
    </div>
  )
}

export default function Policy() {
  const [policy, setPolicy] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    axios.get('/api/policy')
      .then(r => setPolicy(r.data))
      .catch(() => setError('Failed to load policy'))
  }, [])

  if (error) return <p style={s.error}>{error}</p>
  if (!policy) return <p style={s.loading}>Loading policy...</p>

  const cov = policy.coverage_details
  const wp  = policy.waiting_periods

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, color: '#1e1b4b', margin: 0 }}>{policy.policy_name}</h1>
        <p style={{ color: '#6b7280', marginTop: 4, fontSize: 14 }}>
          Policy ID: {policy.policy_id} &nbsp;·&nbsp; Effective: {policy.effective_date}
        </p>
      </div>

      {/* Coverage Summary */}
      <div style={s.card}>
        <h2 style={s.h2}>Coverage Limits</h2>
        <div style={s.grid}>
          <div>
            <Row label="Annual Limit"            value={`₹${cov.annual_limit.toLocaleString()}`} />
            <Row label="Per-Claim Limit"         value={`₹${cov.per_claim_limit.toLocaleString()}`} />
            <Row label="Family Floater Limit"    value={`₹${cov.family_floater_limit.toLocaleString()}`} />
          </div>
          <div>
            <Row label="Consultation Sub-limit"  value={`₹${cov.consultation_fees.sub_limit.toLocaleString()}`} />
            <Row label="Pharmacy Sub-limit"      value={`₹${cov.pharmacy.sub_limit.toLocaleString()}`} />
            <Row label="Diagnostics Sub-limit"   value={`₹${cov.diagnostic_tests.sub_limit.toLocaleString()}`} />
          </div>
        </div>
      </div>

      <div style={s.grid}>
        {/* Consultation */}
        <div style={s.card}>
          <h3 style={s.h3}>Consultation</h3>
          <Row label="Covered"          value={cov.consultation_fees.covered ? 'Yes' : 'No'} />
          <Row label="Sub-limit"        value={`₹${cov.consultation_fees.sub_limit.toLocaleString()}`} />
          <Row label="Co-pay"           value={`${cov.consultation_fees.copay_percentage}%`} />
          <Row label="Network Discount" value={`${cov.consultation_fees.network_discount}%`} />
        </div>

        {/* Pharmacy */}
        <div style={s.card}>
          <h3 style={s.h3}>Pharmacy</h3>
          <Row label="Covered"               value={cov.pharmacy.covered ? 'Yes' : 'No'} />
          <Row label="Sub-limit"             value={`₹${cov.pharmacy.sub_limit.toLocaleString()}`} />
          <Row label="Generic Mandatory"     value={cov.pharmacy.generic_drugs_mandatory ? 'Yes' : 'No'} />
          <Row label="Branded Drug Co-pay"   value={`${cov.pharmacy.branded_drugs_copay}%`} />
        </div>

        {/* Dental */}
        <div style={s.card}>
          <h3 style={s.h3}>Dental</h3>
          <Row label="Covered"            value={cov.dental.covered ? 'Yes' : 'No'} />
          <Row label="Procedure Sub-limit" value={`₹${cov.dental.sub_limit.toLocaleString()}`} />
          <Row label="Routine Checkup Limit" value={`₹${cov.dental.routine_checkup_limit.toLocaleString()}`} />
          <Row label="Cosmetic Procedures" value="Not covered" />
          <div style={{ marginTop: 10 }}>
            {cov.dental.procedures_covered.map(p => <span key={p} style={s.badge}>{p}</span>)}
          </div>
        </div>

        {/* Vision */}
        <div style={s.card}>
          <h3 style={s.h3}>Vision</h3>
          <Row label="Covered"             value={cov.vision.covered ? 'Yes' : 'No'} />
          <Row label="Sub-limit"           value={`₹${cov.vision.sub_limit.toLocaleString()}`} />
          <Row label="Eye Test"            value={cov.vision.eye_test_covered ? 'Covered' : 'No'} />
          <Row label="Glasses / Lenses"    value={cov.vision.glasses_contact_lenses ? 'Covered' : 'No'} />
          <Row label="LASIK Surgery"       value={cov.vision.lasik_surgery ? 'Covered' : 'Not covered'} />
        </div>

        {/* Alternative Medicine */}
        <div style={s.card}>
          <h3 style={s.h3}>Alternative Medicine</h3>
          <Row label="Covered"          value={cov.alternative_medicine.covered ? 'Yes' : 'No'} />
          <Row label="Sub-limit"        value={`₹${cov.alternative_medicine.sub_limit.toLocaleString()}`} />
          <Row label="Session Limit"    value={`${cov.alternative_medicine.therapy_sessions_limit} sessions`} />
          <div style={{ marginTop: 10 }}>
            {cov.alternative_medicine.covered_treatments.map(t => <span key={t} style={s.badge}>{t}</span>)}
          </div>
        </div>

        {/* Diagnostics */}
        <div style={s.card}>
          <h3 style={s.h3}>Diagnostic Tests</h3>
          <Row label="Covered"   value={cov.diagnostic_tests.covered ? 'Yes' : 'No'} />
          <Row label="Sub-limit" value={`₹${cov.diagnostic_tests.sub_limit.toLocaleString()}`} />
          <div style={{ marginTop: 10 }}>
            {cov.diagnostic_tests.covered_tests.map(t => <span key={t} style={s.badge}>{t}</span>)}
          </div>
        </div>
      </div>

      {/* Waiting Periods */}
      <div style={s.card}>
        <h2 style={s.h2}>Waiting Periods</h2>
        <div style={s.grid}>
          <div>
            <Row label="Initial Waiting Period"    value={`${wp.initial_waiting} days`} />
            <Row label="Pre-existing Diseases"     value={`${wp.pre_existing_diseases} days`} />
            <Row label="Maternity"                 value={`${wp.maternity} days`} />
          </div>
          <div>
            <Row label="Diabetes / Hypertension"   value={`${wp.specific_ailments.diabetes} days`} />
            <Row label="Joint Replacement"         value={`${wp.specific_ailments.joint_replacement} days`} />
          </div>
        </div>
      </div>

      {/* Network Hospitals */}
      <div style={s.card}>
        <h2 style={s.h2}>Network Hospitals</h2>
        <p style={{ fontSize: 13, color: '#6b7280', marginBottom: 12 }}>
          Cashless treatment available. Network hospitals receive a {cov.consultation_fees.network_discount}% discount instead of standard co-pay.
        </p>
        <div>
          {policy.network_hospitals.map(h => <span key={h} style={s.greenBadge}>{h}</span>)}
        </div>
      </div>

      {/* Exclusions */}
      <div style={s.card}>
        <h2 style={s.h2}>Exclusions</h2>
        <div>
          {policy.exclusions.map(e => <span key={e} style={s.redBadge}>{e}</span>)}
        </div>
      </div>

      {/* Claim Requirements */}
      <div style={s.card}>
        <h2 style={s.h2}>Claim Requirements</h2>
        <Row label="Submission Window"  value={`${policy.claim_requirements.submission_timeline_days} days from treatment`} />
        <Row label="Minimum Claim"      value={`₹${policy.claim_requirements.minimum_claim_amount}`} />
        <div style={{ marginTop: 12 }}>
          <h3 style={s.h3}>Required Documents</h3>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 14, color: '#374151', lineHeight: 1.9 }}>
            {policy.claim_requirements.documents_required.map(d => <li key={d}>{d}</li>)}
          </ul>
        </div>
      </div>
    </div>
  )
}