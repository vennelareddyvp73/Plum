import React, { useState } from 'react'

const COLORS = {
  APPROVED:       { bg: '#f0fdf4', border: '#16a34a', text: '#15803d', badge: '#dcfce7' },
  REJECTED:       { bg: '#fff1f2', border: '#dc2626', text: '#b91c1c', badge: '#fee2e2' },
  PARTIAL:        { bg: '#fffbeb', border: '#d97706', text: '#b45309', badge: '#fef3c7' },
  MANUAL_REVIEW:  { bg: '#eff6ff', border: '#2563eb', text: '#1d4ed8', badge: '#dbeafe' },
}

const LABELS = {
  APPROVED:      '✅ Approved',
  REJECTED:      '❌ Rejected',
  PARTIAL:       '⚠️ Partially Approved',
  MANUAL_REVIEW: '🔍 Under Manual Review',
}

const CAT_LABELS = {
  consultation: 'Consultation',
  diagnostic: 'Diagnostic Tests',
  pharmacy: 'Pharmacy',
  dental_routine: 'Dental (Routine Checkup)',
  dental_procedure: 'Dental (Procedure)',
  dental: 'Dental',
  vision: 'Vision',
  alternative: 'Alternative Medicine',
  procedure: 'Procedure',
  other: 'Other',
}

const s = {
  card: (d) => ({
    border: `2px solid ${COLORS[d]?.border || '#cbd5e1'}`,
    borderRadius: 16,
    background: COLORS[d]?.bg || '#fff',
    padding: 28,
    marginBottom: 24,
  }),
  badge: (d) => ({
    display: 'inline-block',
    background: COLORS[d]?.badge || '#f1f5f9',
    color: COLORS[d]?.text || '#334155',
    borderRadius: 8,
    padding: '6px 16px',
    fontWeight: 700,
    fontSize: 16,
    marginBottom: 20,
  }),
  row: { display: 'flex', justifyContent: 'space-between', marginBottom: 8, fontSize: 14 },
  label: { color: '#64748b' },
  value: { fontWeight: 600, color: '#1e293b' },
  section: { marginTop: 20, borderTop: '1px solid #e2e8f0', paddingTop: 16 },
  sectionTitle: { fontWeight: 700, marginBottom: 12, fontSize: 14, color: '#475569' },
  reasonItem: { background: '#fef2f2', border: '1px solid #fee2e2', borderRadius: 12, padding: '14px 18px', marginBottom: 12, display: 'flex', flexDirection: 'column', gap: 6 },
  ruleCode: { fontWeight: 800, fontSize: 12, color: '#dc2626', letterSpacing: '0.5px', textTransform: 'uppercase', background: '#fecaca', padding: '2px 8px', borderRadius: 4, alignSelf: 'flex-start' },
  explanation: { fontSize: 13.5, color: '#991b1b', lineHeight: 1.5, fontWeight: 500 },
  deductionRow: { display: 'flex', justifyContent: 'space-between', fontSize: 13, padding: '6px 0', borderBottom: '1px solid #f1f5f9' },
  confidence: { display: 'flex', alignItems: 'center', gap: 10, marginTop: 12 },
  bar: { flex: 1, height: 8, background: '#e2e8f0', borderRadius: 4, overflow: 'hidden' },
  fill: (score) => ({
    height: '100%',
    width: `${score * 100}%`,
    background: score > 0.8 ? '#16a34a' : score > 0.6 ? '#d97706' : '#dc2626',
    borderRadius: 4,
    transition: 'width .5s',
  }),
  nextSteps: { background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8, padding: 14, fontSize: 13, color: '#475569', lineHeight: 1.6 },
  fraudBadge: { display: 'inline-block', background: '#fff1f2', color: '#e11d48', border: '1px solid #fecdd3', borderRadius: 8, padding: '4px 12px', fontSize: 12, fontWeight: 600, marginRight: 8, marginBottom: 8 },
  manualReviewItem: { background: '#eff6ff', border: '1px solid #dbeafe', borderRadius: 12, padding: '10px 14px', marginBottom: 8, color: '#1e40af', fontSize: 13, fontWeight: 500, lineHeight: 1.5 },
  toggleBtn: { background: 'none', border: 'none', color: '#6d28d9', cursor: 'pointer', fontSize: 13, textDecoration: 'underline', padding: 0 },
  table: { width: '100%', borderCollapse: 'collapse', marginTop: 12, marginBottom: 12, background: '#fff', borderRadius: 8, overflow: 'hidden', border: '1px solid #e2e8f0' },
  th: { padding: '8px 10px', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color: '#64748b', background: '#f8fafc', borderBottom: '1px solid #e2e8f0', textAlign: 'left' },
  td: { padding: '8px 10px', fontSize: 13, color: '#1e293b', borderBottom: '1px solid #f1f5f9' },
  catName: { fontWeight: 600, color: '#1e293b', textTransform: 'capitalize' },
  deductedText: { color: '#dc2626', fontWeight: 500 },
  approvedText: { color: '#16a34a', fontWeight: 600 },
  remainingText: { color: '#0284c7', fontWeight: 600 },
}

function AmountRow({ label, value, highlight }) {
  return (
    <div style={s.row}>
      <span style={s.label}>{label}</span>
      <span style={{ ...s.value, color: highlight ? '#16a34a' : '#1e293b' }}>₹{Number(value || 0).toLocaleString('en-IN')}</span>
    </div>
  )
}

export default function DecisionCard({ decision, claimId, onAppeal, categoryClaimed, categoryApproved, categoryBalances }) {
  const [showDocs, setShowDocs] = useState(false)
  if (!decision) return null

  const {
    decision: verdict,
    claimed_amount, approved_amount, deductions = [],
    rejection_reasons = [], violation_reasoning = [],
    fraud_flags = [], medical_necessity_verdict,
    confidence_score, notes, next_steps,
    requires_manual_review, manual_review_reasons = [],
  } = decision

  const reasoningMap = Object.fromEntries(violation_reasoning.map(r => [r.rule_code, r.explanation]))

  return (
    <div style={s.card(verdict)}>
      <div style={s.badge(verdict)}>{LABELS[verdict] || verdict}</div>

      {/* Amounts */}
      <AmountRow label="Claimed Amount" value={claimed_amount} />
      {deductions.map((d, i) => (
        <AmountRow key={i} label={`− ${d.description}`} value={d.amount} />
      ))}
      <div style={{ ...s.row, borderTop: '1px solid #e2e8f0', paddingTop: 10, marginTop: 6 }}>
        <span style={{ ...s.label, fontWeight: 700 }}>Approved Amount</span>
        <span style={{ fontWeight: 700, fontSize: 20, color: COLORS[verdict]?.text }}>
          ₹{Number(approved_amount || 0).toLocaleString('en-IN')}
        </span>
      </div>

      {/* Category Breakdown & Sub-limits Table */}
      {(() => {
        const hasCategoryData = categoryClaimed && Object.keys(categoryClaimed).length > 0;
        const activeCategories = hasCategoryData
          ? Object.keys(categoryClaimed).filter(cat => (categoryClaimed[cat] > 0 || (categoryApproved && categoryApproved[cat] > 0)))
          : [];
        if (activeCategories.length === 0) return null;
        return (
          <div style={s.section}>
            <div style={s.sectionTitle}>Category Breakdown & Sub-limits</div>
            <div style={{ overflowX: 'auto' }}>
              <table style={s.table}>
                <thead>
                  <tr>
                    <th style={s.th}>Category</th>
                    <th style={s.th}>Claimed</th>
                    <th style={s.th}>Deducted</th>
                    <th style={s.th}>Approved</th>
                    <th style={s.th}>Remaining Limit</th>
                  </tr>
                </thead>
                <tbody>
                  {activeCategories.map(cat => {
                    const claimed = categoryClaimed[cat] || 0;
                    const approved = (categoryApproved && categoryApproved[cat]) || 0;
                    const deducted = Math.max(claimed - approved, 0);
                    const bal = categoryBalances?.[cat];
                    const remaining = bal !== undefined ? bal.remaining : null;
                    const limit = bal !== undefined ? bal.limit : null;
                    return (
                      <tr key={cat}>
                        <td style={{ ...s.td, ...s.catName }}>{CAT_LABELS[cat] || cat}</td>
                        <td style={s.td}>₹{Number(claimed).toLocaleString('en-IN')}</td>
                        <td style={{ ...s.td, ...s.deductedText }}>
                          {deducted > 0 ? `− ₹${Number(deducted).toLocaleString('en-IN')}` : '₹0'}
                        </td>
                        <td style={{ ...s.td, ...s.approvedText }}>₹{Number(approved).toLocaleString('en-IN')}</td>
                        <td style={{ ...s.td, ...s.remainingText }}>
                          {remaining !== null ? `₹${Number(remaining).toLocaleString('en-IN')} / ₹${Number(limit).toLocaleString('en-IN')}` : '—'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        );
      })()}

      {/* Confidence score */}
      {confidence_score != null && (
        <div style={s.confidence}>
          <span style={{ fontSize: 12, color: '#64748b', whiteSpace: 'nowrap' }}>Confidence</span>
          <div style={s.bar}><div style={s.fill(confidence_score)} /></div>
          <span style={{ fontSize: 12, fontWeight: 600 }}>{Math.round(confidence_score * 100)}%</span>
        </div>
      )}

      {/* Rejection reasons with LLM explanations */}
      {rejection_reasons.length > 0 && (
        <div style={s.section}>
          <div style={{ ...s.sectionTitle, color: '#dc2626', display: 'flex', alignItems: 'center', gap: 6 }}>
            <span>🚫</span> Policy Rejection Reasons
          </div>
          {rejection_reasons.map((code, i) => (
            <div key={i} style={s.reasonItem} className="premium-card">
              <div style={s.ruleCode}>{code}</div>
              <div style={s.explanation}>
                {reasoningMap[code] || 'This item violates the policy guidelines. Please contact support or correct details.'}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Fraud flags */}
      {fraud_flags.length > 0 && (
        <div style={s.section}>
          <div style={{ ...s.sectionTitle, color: '#b91c1c', display: 'flex', alignItems: 'center', gap: 6 }}>
            <span>⚠️</span> Risk & Inconsistency Flags
          </div>
          <div style={{ marginTop: 8 }}>
            {fraud_flags.map((f, i) => <span key={i} style={s.fraudBadge}>{f}</span>)}
          </div>
        </div>
      )}

      {/* Manual review reasons */}
      {requires_manual_review && manual_review_reasons.length > 0 && (
        <div style={s.section}>
          <div style={{ ...s.sectionTitle, color: '#2563eb', display: 'flex', alignItems: 'center', gap: 6 }}>
            <span>🔍</span> Manual Verification Checklist
          </div>
          {manual_review_reasons.map((r, i) => (
            <div key={i} style={s.manualReviewItem} className="premium-card">
              • {r}
            </div>
          ))}
        </div>
      )}

      {/* Medical necessity */}
      {medical_necessity_verdict && (
        <div style={s.section}>
          <div style={s.sectionTitle}>Medical Necessity Assessment</div>
          <div style={{ fontSize: 13, color: '#475569' }}>{medical_necessity_verdict}</div>
        </div>
      )}

      {/* Notes */}
      {notes && (
        <div style={s.section}>
          <div style={s.sectionTitle}>Adjudicator Notes</div>
          <div style={s.nextSteps}>{notes}</div>
        </div>
      )}

      {/* Next steps */}
      {next_steps && (
        <div style={s.section}>
          <div style={s.sectionTitle}>Next Steps</div>
          <div style={s.nextSteps}>{next_steps}</div>
        </div>
      )}

      {/* Appeal button */}
      {verdict !== 'APPROVED' && onAppeal && (
        <div style={{ marginTop: 20 }}>
          <button
            onClick={onAppeal}
            style={{
              background: '#6d28d9', color: '#fff', border: 'none',
              borderRadius: 8, padding: '10px 20px', cursor: 'pointer', fontSize: 14,
            }}
          >
            Request Manual Review
          </button>
        </div>
      )}
    </div>
  )
}