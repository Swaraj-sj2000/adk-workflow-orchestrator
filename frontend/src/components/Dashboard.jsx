import React, { useState, useEffect } from 'react';
import './Dashboard.css';

const API = 'http://localhost:8000';

export default function Dashboard({ role }) {
  const [projects, setProjects] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedProject, setSelectedProject] = useState(null);

  useEffect(() => {
    fetchData();
  }, [role]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const headers = { 'Authorization': `Bearer ${token}` };

      const pRes = await fetch(`${API}/projects`, { headers });
      if (pRes.ok) setProjects(await pRes.json());

      if (role === 'admin') {
        const eRes = await fetch(`${API}/employees`, { headers });
        if (eRes.ok) setEmployees(await eRes.json());
      }

      if (selectedProject) {
        const hRes = await fetch(`${API}/system/health/${selectedProject}`, { headers });
        if (hRes.ok) setHealth(await hRes.json());
      }
    } catch (err) {
      console.error('Error:', err);
    }
    setLoading(false);
  };

  if (loading) return <div className="loading"><div className="spinner"></div></div>;

  if (role === 'admin') {
    return (
      <div className="dashboard">
        <div className="card full-width">
          <h2>Projects Overview</h2>
          <div className="project-grid">
            {projects.map(p => (
              <div
                key={p.id}
                className="project-card"
                onClick={() => {
                  setSelectedProject(p.id);
                  fetch(`${API}/system/health/${p.id}`, {
                    headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
                  }).then(r => r.json()).then(setHealth);
                }}
              >
                <div>
                  <h3>{p.name}</h3>
                  <p>{p.description}</p>
                  <div className="progress">
                    <div className="progress-fill" style={{ width: `${p.progress}%` }}></div>
                  </div>
                  <p className="progress-text">{p.progress}% Complete</p>
                </div>
                <div className="risk-level" style={{
                  background: p.status === 'on-track' ? '#d1fae5' : '#fee2e2',
                  color: p.status === 'on-track' ? '#047857' : '#dc2626'
                }}>
                  {p.status}
                </div>
              </div>
            ))}
          </div>
        </div>

        {health && (
          <div className="card full-width">
            <h2>Project Health: {health.project_id}</h2>
            <div className="health-grid">
              <div className="health-item">
                <h4>Risk Level</h4>
                <div className={`risk-badge risk-${health.risk_level}`}>
                  {health.risk_level.toUpperCase()}
                </div>
              </div>
              <div className="health-item">
                <h4>Warnings</h4>
                <div className="metric">{health.overload_alerts?.length || 0}</div>
              </div>
              <div className="health-item">
                <h4>Blocked Tasks</h4>
                <div className="metric">{health.blocked_tasks?.length || 0}</div>
              </div>
              <div className="health-item">
                <h4>At Risk</h4>
                <div className="metric">{health.delay_alerts?.length || 0}</div>
              </div>
            </div>

            {health.overload_alerts && health.overload_alerts.length > 0 && (
              <div className="alert alert-warning">
                <strong>⚠️ Overload Alerts:</strong>
                <ul>
                  {health.overload_alerts.map(a => (
                    <li key={a.employee_id}>
                      Employee {a.employee_id}: {Math.round(a.utilization * 100)}% utilized
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        <div className="card full-width">
          <h2>Employee Utilization</h2>
          <table className="table">
            <thead>
              <tr>
                <th>Employee ID</th>
                <th>Current Load</th>
                <th>Capacity</th>
                <th>Utilization</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {employees.map(e => (
                <tr key={e.id}>
                  <td>#{e.id}</td>
                  <td>{e.current_load?.toFixed(1)}h</td>
                  <td>{e.max_capacity}h</td>
                  <td>
                    <div className="progress" style={{ width: '120px', height: '6px' }}>
                      <div
                        className="progress-fill"
                        style={{
                          width: `${Math.min((e.current_load / e.max_capacity) * 100, 100)}%`,
                          background: e.current_load > e.max_capacity ? '#dc2626' : '#667eea'
                        }}
                      ></div>
                    </div>
                  </td>
                  <td>
                    <span className={`status-badge status-${
                      e.current_load > e.max_capacity ? 'overloaded' : 
                      e.current_load > e.max_capacity * 0.9 ? 'busy' :
                      'available'
                    }`}>
                      {e.availability_status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  // Employee View
  return (
    <div className="dashboard">
      <div className="card full-width">
        <h2>My Projects</h2>
        {projects.length === 0 ? (
          <p>No projects assigned yet</p>
        ) : (
          <div className="list">
            {projects.map(p => (
              <div key={p.id} className="list-item">
                <h3>{p.name}</h3>
                <p>{p.description}</p>
                <div className="progress">
                  <div className="progress-fill" style={{ width: `${p.progress}%` }}></div>
                </div>
                <p style={{ fontSize: '12px', color: '#666' }}>{p.progress}% Complete</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
