import React, { useRef } from 'react'

const DOC_CONFIG = {
  prescription:   { label: 'Medical Prescription', icon: '📋', hint: 'JPG, PNG, PDF' },
  pharmacy_bill:  { label: 'Pharmacy Bill',         icon: '💊', hint: 'JPG, PNG, PDF' },
  diagnosis_test: { label: 'Diagnosis / Lab Report',icon: '🧪', hint: 'JPG, PNG, PDF' },
  medical_bill:   { label: 'Medical Bill / Invoice', icon: '🏥', hint: 'JPG, PNG, PDF' },
}

const s = {
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 },
  card: (active) => ({
    border: `2px dashed ${active ? '#6d28d9' : '#cbd5e1'}`,
    borderRadius: 12,
    padding: 20,
    textAlign: 'center',
    cursor: 'pointer',
    background: active ? '#f5f3ff' : '#fff',
    transition: 'all .15s',
  }),
  icon: { fontSize: 32, marginBottom: 8 },
  label: { fontWeight: 600, fontSize: 14, color: '#1e293b', marginBottom: 4 },
  hint: { fontSize: 12, color: '#94a3b8' },
  filename: { fontSize: 12, color: '#6d28d9', marginTop: 8, wordBreak: 'break-all' },
  remove: { fontSize: 11, color: '#ef4444', cursor: 'pointer', marginTop: 4, textDecoration: 'underline' },
}

export default function DocumentUpload({ files, onChange }) {
  const refs = {
    prescription:   useRef(),
    pharmacy_bill:  useRef(),
    diagnosis_test: useRef(),
    medical_bill:   useRef(),
  }

  const handleFile = (docType, e) => {
    const file = e.target.files[0]
    if (file) onChange(docType, file)
  }

  const remove = (docType, e) => {
    e.stopPropagation()
    onChange(docType, null)
    refs[docType].current.value = ''
  }

  return (
    <div style={s.grid}>
      {Object.entries(DOC_CONFIG).map(([docType, cfg]) => (
        <div
          key={docType}
          style={s.card(!!files[docType])}
          onClick={() => refs[docType].current.click()}
        >
          <div style={s.icon}>{cfg.icon}</div>
          <div style={s.label}>{cfg.label}</div>
          <div style={s.hint}>{cfg.hint} · optional</div>
          {files[docType] && (
            <>
              <div style={s.filename}>✓ {files[docType].name}</div>
              <div style={s.remove} onClick={(e) => remove(docType, e)}>Remove</div>
            </>
          )}
          <input
            ref={refs[docType]}
            type="file"
            accept=".jpg,.jpeg,.png,.tiff,.bmp,.pdf"
            style={{ display: 'none' }}
            onChange={(e) => handleFile(docType, e)}
          />
        </div>
      ))}
    </div>
  )
}