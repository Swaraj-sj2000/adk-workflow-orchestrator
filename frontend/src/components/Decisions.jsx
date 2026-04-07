import React, { useEffect, useState } from 'react';
import { API_BASE_URL as API } from '../config';

export default function Decisions() {
  const [dashboard, setDashboard] = useState(null);
  const [stats, setStats] = useState(null);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  const token = localStorage.getItem('token');
  const headers = { Authorization: `Bearer ${token}` };

  const fetchData = async () => {
    setLoading(true);
    try {
      const [agenticRes, statsRes] = await Promise.all([
        fetch(`${API}/system/agentic-dashboard`, { headers }),
        fetch(`${API}/decisions/statistics`, { headers }),
      ]);

      if (agenticRes.ok) {
        setDashboard(await agenticRes.json());
      }

      if (statsRes.ok) {
        const data = await statsRes.json();
        setStats(data.statistics);
      }
    } catch (error) {
      console.error(error);
    }
    setLoading(false);
  };

  const actOnApproval = async (projectId, approved) => {
    try {
      const res = await fetch(`${API}/projects/${projectId}/team-approval`, {
        method: 'POST',
        headers: {
          ...headers,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          approved,
          note: approved ? 'Approved from agentic dashboard.' : 'Rejected from agentic dashboard.',
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not process approval');
      setMessage(approved ? 'Admin approval confirmed. Team invites are now waiting for employee responses.' : 'Plan rejected and admin review triggered.');
      fetchData();
    } catch (error) {
      setMessage(error.message);
    }
  };

  if (loading) return <div className="loading"><div className="spinner"></div></div>;

  return (
    <div className="dashboard">
      {message && <div className="alert alert-info full-width">{message}</div>}

      {stats && (
        <div className="card full-width">
          <p className="eyebrow">Agentic System Dashboard</p>
          <h2>Approval checks and decision health</h2>
          <div className="summary-grid">
            <div className="summary-card">
              <p>Total Decisions</p>
              <div className="metric">{stats.total_decisions}</div>
            </div>
            <div className="summary-card">
              <p>Automation Level</p>
              <div className="metric">{stats.automation_level}%</div>
            </div>
            <div className="summary-card">
              <p>Average Confidence</p>
              <div className="metric">{stats.avg_confidence}</div>
            </div>
            <div className="summary-card">
              <p>Overrides</p>
              <div className="metric">{stats.overridden_count}</div>
            </div>
            <div className="summary-card">
              <p>LLM</p>
              <div className="detail-card-value">{dashboard?.llm_status?.enabled ? 'Hugging Face live' : 'Fallback mode'}</div>
            </div>
          </div>
        </div>
      )}

      {dashboard?.llm_status && (
        <div className="card full-width">
          <h2>LLM Status</h2>
          <div className="project-mini-grid">
            <div className="info-pill">
              <span>Model</span>
              <strong>{dashboard.llm_status.model_id}</strong>
            </div>
            <div className="info-pill">
              <span>Mode</span>
              <strong>{dashboard.llm_status.enabled ? 'Live Hugging Face' : 'Deterministic fallback'}</strong>
            </div>
            <div className="info-pill">
              <span>Init Error</span>
              <strong>{dashboard.llm_status.init_error || 'None'}</strong>
            </div>
          </div>
        </div>
      )}

      <div className="card full-width">
        <h2>Current Approval Queue</h2>
        <div className="list">
          {(dashboard?.approvals || []).map((item) => (
            <div key={item.project_id} className="list-item">
              <div className="task-line">
                <div>
                  <strong>{item.project_name}</strong>
                  <p>{item.next_decision}</p>
                </div>
                <span className={`status-badge status-${(item.approval_status || 'pending').replace(/\s+/g, '-')}`}>
                  {item.approval_status}
                </span>
              </div>
              <p>Current phase: {item.current_phase}</p>
              <p>Approval deadline: {item.approval_deadline || item.team_join_deadline || 'n/a'}</p>
              <div className="people-list">
                {(item.recommended_team || []).map((member) => (
                  <div key={member.employee_id} className="person-chip">
                    <strong>{member.name}</strong>
                    <span>{member.title}</span>
                  </div>
                ))}
              </div>
              {item.approval_status === 'awaiting-team-join' && (
                <p>The team has been invited. Open project status from the admin panel to see which members are still pending.</p>
              )}
              {item.approval_status === 'awaiting-admin-approval' && (
                <div className="project-card-actions">
                  <button className="btn btn-primary" onClick={() => actOnApproval(item.project_id, true)}>
                    Approve
                  </button>
                  <button className="btn btn-danger" onClick={() => actOnApproval(item.project_id, false)}>
                    Reject
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <h2>Agentic Suggestions</h2>
        <div className="list">
          {(dashboard?.suggestions || []).map((item) => (
            <div key={item.project_id} className="list-item">
              <div className="task-line">
                <strong>{item.project_name}</strong>
                <span className={`status-badge ${item.requires_admin_attention ? 'status-critical' : 'status-low'}`}>
                  {item.requires_admin_attention ? 'Admin Attention' : 'Monitoring'}
                </span>
              </div>
              <p>{item.suggestion}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <h2>Low-Confidence Decisions</h2>
        <div className="list">
          {(dashboard?.low_confidence_decisions || []).map((decision) => (
            <div key={decision.id} className="list-item">
              <div className="task-line">
                <strong>{decision.decision_type}</strong>
                <span className="status-badge status-high">{Math.round(decision.confidence * 100)}%</span>
              </div>
              <p>{decision.decision_taken}</p>
              <p>{decision.reasoning}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="card full-width">
        <h2>Escalation Meetings</h2>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Meeting</th>
                <th>Project ID</th>
                <th>Type</th>
                <th>Scheduled At</th>
              </tr>
            </thead>
            <tbody>
              {(dashboard?.escalation_meetings || []).map((meeting) => (
                <tr key={meeting.meeting_id}>
                  <td>{meeting.title}</td>
                  <td>#{meeting.project_id}</td>
                  <td>{meeting.meeting_type}</td>
                  <td>{meeting.scheduled_at || 'TBD'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
