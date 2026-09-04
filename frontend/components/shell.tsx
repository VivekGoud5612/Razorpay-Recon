'use client'

import { Link, useLocation } from 'react-router-dom'
import { Bell, ChevronRight, CircleDot, GitBranch, LayoutDashboard, Menu, Search, WalletCards } from 'lucide-react'
import { pretty } from '@/lib/format'

export function Shell({ children }: { children: React.ReactNode }) {
  const loc = useLocation()

  return (
    <div className="app">
      <aside>
        <div className="brand">
          <span className="brand-mark">R</span>
          reconcile<span className="muted">/ops</span>
        </div>
        <div className="workspace">
          <span className="eyebrow">WORKSPACE</span>
          <b>Acme Payments</b>
          <span className="muted">Production</span>
        </div>
        <nav>
          <Nav to="/" icon={<LayoutDashboard />} label="Overview" />
          <Nav to="/reconciliations" icon={<WalletCards />} label="Reconciliations" />
          <Nav to="/reconciliations/new" icon={<CircleDot />} label="New reconciliation" />
        </nav>
        <div className="sidebar-foot">
          <div className="avatar">AS</div>
          <div>
            <b>Alex Shah</b>
            <span className="muted">Finance Ops</span>
          </div>
          <Menu size={16} />
        </div>
      </aside>
      <section className="content">
        <header>
          <div className="crumb">
            <span className="mobile-brand">reconcile/ops</span>
            {loc.pathname !== '/' && (
              <>
                <ChevronRight size={14} />
                <span>{loc.pathname.split('/')[1]}</span>
              </>
            )}
          </div>
          <div className="top-actions">
            <button className="icon-btn" aria-label="Search">
              <Search size={17} />
            </button>
            <button className="icon-btn" aria-label="Notifications">
              <Bell size={17} />
            </button>
            <button className="user-btn">
              <span className="avatar small">AS</span>
              Alex Shah
            </button>
          </div>
        </header>
        {children}
      </section>
    </div>
  )
}

export function Nav({ to, icon, label }: { to: string; icon: React.ReactNode; label: string }) {
  const active = useLocation().pathname === to
  return (
    <Link className={active ? 'active' : ''} to={to}>
      {icon}
      <span>{label}</span>
    </Link>
  )
}

export function Title({ eyebrow, title, action }: { eyebrow: string; title: string; action?: React.ReactNode }) {
  return (
    <div className="page-title">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
      </div>
      {action}
    </div>
  )
}

export function Status({ value }: { value: string }) {
  return <span className={`status ${value}`}>{pretty(value)}</span>
}

export function Kpi({ label, value, sub, tone }: { label: string; value: string; sub: string; tone?: string }) {
  return (
    <div className="kpi">
      <span>{label}</span>
      <strong className={tone}>{value}</strong>
      <small>{sub}</small>
    </div>
  )
}

export function Table({ headers, rows }: { headers: string[]; rows: React.ReactNode[][] }) {
  return (
    <div className="table-card">
      <table>
        <thead>
          <tr>
            {headers.map((h) => (
              <th key={h}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => (
                <td key={j}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
