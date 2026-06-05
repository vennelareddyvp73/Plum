import React from 'react'
import { Routes, Route, Link, useLocation } from 'react-router-dom'
import NewClaim from './pages/NewClaim'
import ClaimDetail from './pages/ClaimDetail'
import ClaimHistory from './pages/ClaimHistory'
import Policy from './pages/Policy'

const s = {
  nav: {
    background: '#6d28d9',
    padding: '0 32px',
    display: 'flex',
    alignItems: 'center',
    gap: 32,
    height: 56,
    boxShadow: '0 2px 8px rgba(109,40,217,.3)',
  },
  logo: { color: '#fff', fontWeight: 700, fontSize: 18, textDecoration: 'none', letterSpacing: '-0.3px' },
  main: { maxWidth: 920, margin: '36px auto', padding: '0 20px' },
}

function NavLink({ to, children }) {
  const location = useLocation()
  const isDashboardActive = to === '/?tab=dashboard' && (location.pathname === '/' && (!location.search || location.search.includes('tab=dashboard')))
  const isNewClaimActive = to === '/?tab=new-claim' && location.pathname === '/' && location.search.includes('tab=new-claim')
  const isOtherActive = to !== '/?tab=dashboard' && to !== '/?tab=new-claim' && location.pathname === to
  
  const active = isDashboardActive || isNewClaimActive || isOtherActive
  return (
    <Link to={to} style={{
      color: active ? '#fff' : '#c4b5fd',
      textDecoration: 'none',
      fontSize: 14,
      fontWeight: active ? 600 : 400,
    }}>
      {children}
    </Link>
  )
}

export default function App() {
  return (
    <>
      <nav style={s.nav}>
        <Link to="/?tab=dashboard" style={s.logo}>Plum Claims</Link>
        <NavLink to="/?tab=dashboard">Dashboard</NavLink>
        <NavLink to="/?tab=new-claim">New Claim</NavLink>
        <NavLink to="/history">History</NavLink>
        <NavLink to="/policy">Policy</NavLink>
      </nav>
      <main style={s.main}>
        <Routes>
          <Route path="/"                    element={<NewClaim />} />
          <Route path="/claims/:claimId"     element={<ClaimDetail />} />
          <Route path="/history"             element={<ClaimHistory />} />
          <Route path="/policy"              element={<Policy />} />
        </Routes>
      </main>
    </>
  )
}