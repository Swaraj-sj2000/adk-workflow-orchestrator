import React, { useEffect, useState } from 'react';
import { API_BASE_URL as API } from '../config';
import { formatCurrency } from '../utils/currency';
import './Analytics.css';

function getCurrency() {
  try { return JSON.parse(localStorage.getItem('user'))?.currency || 'USD'; }
  catch { return 'USD'; }
}

/* ─── Primitive Chart Components ─────────────────────────────────── */

function DonutChart({ value, max, label, color = 'var(--accent)', size = 120 }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  const r = 44;
  const circ = 2 * Math.PI * r;
  const dash = (pct / 100) * circ;
  return (
    <div className="an-donut-wrap">
      <svg width={size} height={size} viewBox="0 0 100 100">
        <circle cx="50" cy="50" r={r} fill="none" stroke="var(--border-soft)" strokeWidth="10" />
        <circle
          cx="50" cy="50" r={r} fill="none"
          stroke={color} strokeWidth="10"
          strokeDasharray={`${dash} ${circ}`}
          strokeLinecap="round"
          transform="rotate(-90 50 50)"
        />
        <text x="50" y="54" textAnchor="middle" fontSize="18" fontWeight="700" fill="var(--text-primary)">
          {Math.round(pct)}%
        </text>
      </svg>
      <p className="an-donut-label">{label}</p>
    </div>
  );
}

function HBar({ label, value, max, color = 'var(--accent)', fmt = (v) => v }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div className="an-hbar-row">
      <span className="an-hbar-label">{label}</span>
      <div className="an-hbar-track">
        <div className="an-hbar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="an-hbar-val">{fmt(value)}</span>
    </div>
  );
}

function StatCard({ label, value, sub, color }) {
  return (
    <div className="an-stat-card">
      <p className="an-stat-label">{label}</p>
      <div className="an-stat-value" style={color ? { color } : {}}>{value ?? '—'}</div>
      {sub && <p className="an-stat-sub">{sub}</p>}
    </div>
  );
}

function SectionHead({ title, sub }) {
  return (
    <div className="an-section-head">
      <h3>{title}</h3>
      {sub && <p>{sub}</p>}
    </div>
  );
}

const fmtPct = (v) => `${v}%`;

/* ─── Shared Analytics Panel ─────────────────────────────────────── */

function AnalyticsPanel({ data, currency = 'USD' }) {
  if (!data) return <div className="loading"><div className="spinner" /></div>;

  const fmt$ = (v) => formatCurrency(v, currency);
  const rev = data.revenue || {};
  const proj = data.projects || {};
  const tasks = data.tasks || {};
  const team = data.team || {};
  const clients = data.clients;
  const perProject = data.per_project || [];

  const statusColors = {
    planning: '#3b82f6', 'in-progress': '#8b5cf6', completed: '#10b981',
    'on-hold': '#f59e0b', cancelled: '#6b7280', unknown: '#9ca3af',
  };
  const priorityColors = { critical: '#dc2626', high: '#f97316', medium: '#eab308', low: '#22c55e' };

  const maxBudget = Math.max(...perProject.map(p => p.budget), 1);

  return (
    <div className="an-root">

      {/* Revenue */}
      <section className="an-section">
        <SectionHead title="Revenue & Profitability" sub="Across all projects in this tenant" />
        <div className="an-cards">
          <StatCard label="Total Contracted" value={fmt$(rev.total_budget)} />
          <StatCard label="Total Invoiced" value={fmt$(rev.total_invoiced)} />
          <StatCard label="Collected" value={fmt$(rev.total_collected)} color="#10b981" />
          <StatCard label="Outstanding" value={fmt$(rev.outstanding)} color={rev.outstanding > 0 ? '#f97316' : '#10b981'} />
          <StatCard label="Gross Profit" value={fmt$(rev.gross_profit)} color={rev.gross_profit >= 0 ? '#10b981' : '#dc2626'} />
          <StatCard label="Profit Margin" value={`${rev.profit_margin_pct ?? 0}%`} color={rev.profit_margin_pct >= 20 ? '#10b981' : '#f97316'} />
        </div>
        <div className="an-donut-row">
          <DonutChart value={rev.total_collected} max={rev.total_invoiced} label="Collection Rate" color="#10b981" />
          <DonutChart value={rev.gross_profit} max={rev.total_invoiced} label="Profit Margin" color={rev.profit_margin_pct >= 0 ? 'var(--accent)' : '#dc2626'} />
          <DonutChart value={rev.total_spent} max={rev.total_budget} label="Budget Used" color="#f97316" />
        </div>
      </section>

      {/* Projects */}
      <section className="an-section">
        <SectionHead title="Project Distribution" />
        <div className="an-cards">
          <StatCard label="Total" value={proj.total} />
          <StatCard label="Active" value={proj.active} color="#3b82f6" />
          <StatCard label="Completed" value={proj.completed} color="#10b981" />
          <StatCard label="Avg Progress" value={`${proj.avg_progress ?? 0}%`} />
        </div>
        <div className="an-two-col">
          <div>
            <p className="an-chart-title">By Status</p>
            {(proj.by_status || []).map(row => (
              <HBar key={row.label} label={row.label} value={row.value} max={proj.total || 1}
                color={statusColors[row.label] || '#8b5cf6'} />
            ))}
          </div>
          <div>
            <p className="an-chart-title">By Priority</p>
            {(proj.by_priority || []).map(row => (
              <HBar key={row.label} label={row.label} value={row.value} max={proj.total || 1}
                color={priorityColors[row.label] || '#8b5cf6'} />
            ))}
          </div>
        </div>
      </section>

      {/* Tasks */}
      <section className="an-section">
        <SectionHead title="Task Health" />
        <div className="an-cards">
          <StatCard label="Total Tasks" value={tasks.total} />
          <StatCard label="Completed" value={tasks.completed} color="#10b981" />
          <StatCard label="In Progress" value={tasks.in_progress} color="#3b82f6" />
          <StatCard label="Blocked" value={tasks.blocked} color="#dc2626" />
          {tasks.open_blockers != null && <StatCard label="Open Blockers" value={tasks.open_blockers} color="#f97316" />}
        </div>
        <DonutChart value={tasks.completed} max={tasks.total} label="Task Completion" color="#10b981" size={140} />
      </section>

      {/* Team */}
      <section className="an-section">
        <SectionHead title="Team Performance" />
        <div className="an-cards">
          <StatCard label="Team Size" value={team.total_employees} />
          <StatCard label="Avg Utilization" value={`${team.avg_utilization_pct ?? 0}%`} color={team.avg_utilization_pct > 85 ? '#dc2626' : team.avg_utilization_pct > 60 ? '#f97316' : '#10b981'} />
          <StatCard label="Avg Efficiency" value={`${team.avg_efficiency_pct ?? 0}%`} color="#10b981" />
          <StatCard label="Avg Reliability" value={`${team.avg_reliability_pct ?? 0}%`} color="var(--accent)" />
        </div>
        {(team.top_performers || []).length > 0 && (
          <div>
            <p className="an-chart-title">Top Performers</p>
            {team.top_performers.map((p, i) => (
              <HBar key={i} label={p.name}
                value={Math.round((p.efficiency + p.reliability) / 2)}
                max={100} color="var(--accent)"
                fmt={(v) => `${v}% avg · ${p.tasks_completed} tasks`} />
            ))}
          </div>
        )}
      </section>

      {/* Client payment (CEO only) */}
      {clients && (
        <section className="an-section">
          <SectionHead title="Client Payments" />
          <div className="an-cards">
            <StatCard label="Total Clients" value={clients.total} />
            <StatCard label="Collected" value={clients.payment_summary?.collected} color="#10b981" />
            <StatCard label="Pending" value={clients.payment_summary?.pending} color="#f97316" />
            <StatCard label="Partial" value={clients.payment_summary?.partial} color="#eab308" />
          </div>
        </section>
      )}

      {/* Per-project P&L */}
      {perProject.length > 0 && (
        <section className="an-section">
          <SectionHead title="Per-Project P&L" sub="Sorted by contract value — budget, spend, margin, and collection status" />
          <div className="an-table-wrap">
            <table className="an-table">
              <thead>
                <tr>
                  <th>Project</th>
                  <th>Status</th>
                  <th>Priority</th>
                  <th>Progress</th>
                  <th>Budget</th>
                  <th>Spent</th>
                  <th>Margin</th>
                  <th>Payment</th>
                  <th>Blockers</th>
                </tr>
              </thead>
              <tbody>
                {perProject.map(p => (
                  <tr key={p.id} className={p.open_blockers > 0 ? 'an-row-warn' : ''}>
                    <td><strong>{p.name}</strong></td>
                    <td><span className={`status-badge status-${(p.status || 'unknown').replace(/\s+/g, '-')}`}>{p.status}</span></td>
                    <td><span style={{ color: priorityColors[p.priority] || 'var(--text-secondary)', fontWeight: 600, fontSize: 12 }}>{p.priority}</span></td>
                    <td>
                      <div className="an-mini-bar-track">
                        <div className="an-mini-bar-fill" style={{ width: `${p.progress}%`, background: p.progress >= 80 ? '#10b981' : p.progress >= 40 ? 'var(--accent)' : '#f97316' }} />
                      </div>
                      <span className="an-mini-bar-pct">{Math.round(p.progress)}%</span>
                    </td>
                    <td>{fmt$(p.budget)}</td>
                    <td>{fmt$(p.spent)}</td>
                    <td style={{ color: p.profit_margin >= 0 ? '#10b981' : '#dc2626', fontWeight: 700 }}>{p.profit_margin}%</td>
                    <td><span className={`status-badge status-${(p.payment_status || 'pending').replace(/\s+/g, '-')}`}>{p.payment_status}</span></td>
                    <td style={{ color: p.open_blockers > 0 ? '#dc2626' : 'var(--text-secondary)', fontWeight: p.open_blockers > 0 ? 700 : 400 }}>{p.open_blockers}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

    </div>
  );
}

/* ─── CEO Analytics Page ─────────────────────────────────────────── */

export function CeoAnalytics() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const token = localStorage.getItem('token');
  const currency = getCurrency();

  useEffect(() => {
    fetch(`${API}/ceo/analytics`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : null)
      .then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="loading"><div className="spinner" /></div>;
  return <AnalyticsPanel data={data} currency={currency} />;
}

/* ─── Admin Analytics Page ───────────────────────────────────────── */

export function AdminAnalytics() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const token = localStorage.getItem('token');
  const currency = getCurrency();

  useEffect(() => {
    fetch(`${API}/system/admin-analytics`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : null)
      .then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="loading"><div className="spinner" /></div>;
  return <AnalyticsPanel data={data} currency={currency} />;
}
