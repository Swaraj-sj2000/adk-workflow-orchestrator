import React, { useEffect, useState } from 'react';
import Dashboard from './Dashboard';

export default function CEODashboard({ currentUser, API_BASE_URL, onNavigate }) {
  const [loading, setLoading] = useState(true);
  const [ceoMode, setCeoMode] = useState(localStorage.getItem('ceo_mode') === 'true');
  const [overview, setOverview] = useState(null);
  const [financials, setFinancials] = useState(null);
  const [teams, setTeams] = useState(null);
  const [clients, setClients] = useState([]);
  const [risks, setRisks] = useState([]);

  useEffect(() => {
    const token = localStorage.getItem('token');
    const headers = { Authorization: `Bearer ${token}` };
    setLoading(true);
    Promise.all([
      fetch(`${API_BASE_URL}/ceo/overview`, { headers }).then((res) => res.json()),
      fetch(`${API_BASE_URL}/ceo/financials`, { headers }).then((res) => res.json()),
      fetch(`${API_BASE_URL}/ceo/teams`, { headers }).then((res) => res.json()),
      fetch(`${API_BASE_URL}/ceo/clients`, { headers }).then((res) => res.json()),
      fetch(`${API_BASE_URL}/ceo/risks`, { headers }).then((res) => res.json()),
    ])
      .then(([overviewData, financialData, teamData, clientData, riskData]) => {
        setOverview(overviewData);
        setFinancials(financialData);
        setTeams(teamData);
        setClients(clientData || []);
        setRisks(riskData || []);
      })
      .finally(() => setLoading(false));
  }, [API_BASE_URL]);

  useEffect(() => {
    localStorage.setItem('ceo_mode', String(ceoMode));
  }, [ceoMode]);

  if (ceoMode) {
    return (
      <div>
        <div className="card" style={{ marginBottom: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <p className="eyebrow">Technical View</p>
            <h2 style={{ marginBottom: 6 }}>CEO Technical Console</h2>
            <p style={{ margin: 0 }}>Deep operational detail is enabled for executive review.</p>
          </div>
          <button className="btn btn-secondary" onClick={() => setCeoMode(false)}>Back to Business View</button>
        </div>
        <Dashboard role="admin" />
      </div>
    );
  }

  const healthScore = overview?.health_score || 0;
  const healthColor = healthScore > 75 ? '#15803d' : healthScore >= 50 ? '#ca8a04' : '#dc2626';

  return (
    <div className="dashboard">
      <div className="card full-width" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <p className="eyebrow">CEO Dashboard</p>
          <h2 style={{ marginBottom: 8 }}>{currentUser.tenant_name || 'Company Overview'}</h2>
          <div style={{ display: 'inline-flex', gap: 10, alignItems: 'center', background: 'var(--surface-soft)', padding: '10px 14px', borderRadius: 999 }}>
            <span>Health Score</span>
            <strong style={{ color: healthColor }}>{healthScore.toFixed(1)}</strong>
          </div>
        </div>
        <button className="btn btn-primary" onClick={() => setCeoMode(true)}>Technical View</button>
      </div>

      {(loading ? Array.from({ length: 4 }) : [
        { label: 'Total Projects', value: overview?.total_projects, meta: `${overview?.projects_on_track || 0} on track / ${overview?.projects_at_risk || 0} at risk / ${overview?.projects_delayed || 0} delayed` },
        { label: 'Team Utilization', value: `${teams?.overall_utilization_pct || 0}%`, meta: `${overview?.employees_overloaded || 0} overloaded employees` },
        { label: 'Outstanding Payments', value: financials?.total_outstanding || 0, meta: `${financials?.overdue_payments?.length || 0} overdue accounts` },
        { label: 'Active Blockers', value: overview?.active_blockers || 0, meta: `${risks.filter((risk) => risk.type === 'unresolved_blocker').length} critical blockers` },
      ]).map((card, index) => (
        <div key={card?.label || index} className="card">
          {loading ? <div style={{ height: 120, background: 'var(--surface-soft)', borderRadius: 14 }} /> : (
            <>
              <p className="eyebrow">{card.label}</p>
              <h2>{card.value}</h2>
              <p>{card.meta}</p>
            </>
          )}
        </div>
      ))}

      <div className="card">
        <p className="eyebrow">Risk Flags</p>
        <h2>Immediate Attention</h2>
        <div style={{ maxHeight: 280, overflowY: 'auto', display: 'grid', gap: 10 }}>
          {risks.length === 0 && <p>No active risk flags.</p>}
          {risks.map((risk) => (
            <button
              key={`${risk.type}-${risk.entity_id}`}
              onClick={() => onNavigate('projects')}
              style={{
                textAlign: 'left',
                border: '1px solid var(--border-soft)',
                background: 'var(--surface-soft)',
                borderRadius: 12,
                padding: 14,
                cursor: 'pointer',
              }}
            >
              <strong style={{ color: risk.severity === 'critical' ? '#dc2626' : risk.severity === 'high' ? '#ca8a04' : 'var(--accent)' }}>
                {risk.severity.toUpperCase()}
              </strong>
              <div style={{ marginTop: 6 }}>{risk.message}</div>
            </button>
          ))}
        </div>
      </div>

      <div className="card">
        <p className="eyebrow">Team Utilization</p>
        <h2>Capacity by Team</h2>
        <div style={{ display: 'grid', gap: 12 }}>
          {(teams?.teams || []).map((team) => (
            <div key={team.team_id}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <strong>{team.team_name}</strong>
                <span>{team.avg_utilization_pct}%</span>
              </div>
              <div className="progress">
                <div className="progress-fill" style={{ width: `${Math.min(team.avg_utilization_pct, 100)}%` }} />
              </div>
              <p>{team.project_name} • {team.member_count} members • {team.active_blockers} blockers</p>
            </div>
          ))}
        </div>
      </div>

      <div className="card full-width">
        <p className="eyebrow">Client Status</p>
        <h2>Portfolio Accounts</h2>
        <div style={{ overflowX: 'auto' }}>
          <table className="table">
            <thead>
              <tr>
                <th>Company</th>
                <th>Projects</th>
                <th>Billed</th>
                <th>Paid</th>
                <th>Outstanding</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {clients.map((client) => (
                <tr key={client.client_id}>
                  <td>{client.company_name}</td>
                  <td>{client.active_projects} active / {client.completed_projects} complete</td>
                  <td>{client.total_billed}</td>
                  <td>{client.total_paid}</td>
                  <td>{client.outstanding}</td>
                  <td>{client.payment_status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
