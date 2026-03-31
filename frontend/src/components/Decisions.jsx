import React, { useState, useEffect } from 'react';

const API = 'http://localhost:8000';

export default function Decisions() {
  const [decisions, setDecisions] = useState([]);
  const [risky, setRisky] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');

  useEffect(() => {
    fetchDecisions();
  }, []);

  const fetchDecisions = async () => {
    try {
      const token = localStorage.getItem('token');
      const headers = { 'Authorization': `Bearer ${token}` };

      const dRes = await fetch(`${API}/decisions/`, { headers });
      if (dRes.ok) setDecisions(await dRes.json());

      const rRes = await fetch(`${API}/decisions/risky`, { headers });
      if (rRes.ok) setRisky(await rRes.json());

      const sRes = await fetch(`${API}/decisions/statistics`, { headers });
      if (sRes.ok) {
        const data = await sRes.json();
        setStats(data.statistics);
      }
    } catch (err) {
      console.error('Error:', err);
    }
    setLoading(false);
  };

  if (loading) return <div className="loading"><div className="spinner"></div></div>;

  const displayDecisions = filter === 'risky' ? risky : decisions;

  return (
    <div className="dashboard">
      {stats && (
        <div className="card full-width">
          <h2>System Decision Analytics</h2>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
            gap: '15px'
          }}>
            <div style={{ background: '#f9f9f9', padding: '15px', borderRadius: '6px' }}>
              <p style={{ fontSize: '12px', color: '#666', marginBottom: '8px' }}>Total Decisions</p>
              <div className="metric">{stats.total_decisions}</div>
            </div>
            <div style={{ background: '#f9f9f9', padding: '15px', borderRadius: '6px' }}>
              <p style={{ fontSize: '12px', color: '#666', marginBottom: '8px' }}>Automation Level</p>
              <div className="metric">{stats.automation_level?.toFixed(1)}%</div>
            </div>
            <div style={{ background: '#f9f9f9', padding: '15px', borderRadius: '6px' }}>
              <p style={{ fontSize: '12px', color: '#666', marginBottom: '8px' }}>Avg Confidence</p>
              <div className="metric">{stats.avg_confidence?.toFixed(2)}</div>
            </div>
            <div style={{ background: '#f9f9f9', padding: '15px', borderRadius: '6px' }}>
              <p style={{ fontSize: '12px', color: '#666', marginBottom: '8px' }}>Overrides</p>
              <div className="metric">{stats.overridden_count}</div>
            </div>
          </div>
        </div>
      )}

      <div className="card full-width">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
          <h2>Decisions Log</h2>
          <div className="button-group">
            <button
              className="btn"
              style={{
                background: filter === 'all' ? '#667eea' : '#e0e0e0',
                color: filter === 'all' ? 'white' : '#333'
              }}
              onClick={() => setFilter('all')}
            >
              All ({decisions.length})
            </button>
            <button
              className="btn"
              style={{
                background: filter === 'risky' ? '#dc2626' : '#e0e0e0',
                color: filter === 'risky' ? 'white' : '#333'
              }}
              onClick={() => setFilter('risky')}
            >
              Risky ({risky.length})
            </button>
          </div>
        </div>

        {displayDecisions.length === 0 ? (
          <p style={{ color: '#999' }}>No decisions found</p>
        ) : (
          <div className="list">
            {displayDecisions.map(d => (
              <div key={d.id} className="list-item">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                  <div style={{ flex: 1 }}>
                    <h3 style={{ fontSize: '14px', fontWeight: 600 }}>
                      {d.decision_type.toUpperCase()} - {d.entity_type}
                    </h3>
                    <p style={{ fontSize: '13px', color: '#666', margin: '5px 0' }}>
                      {d.decision_taken}
                    </p>
                    {d.reasoning && (
                      <p style={{ fontSize: '12px', color: '#999', fontStyle: 'italic', margin: '5px 0' }}>
                        💭 {d.reasoning}
                      </p>
                    )}
                  </div>
                  <div style={{ textAlign: 'right', marginLeft: '15px' }}>
                    <div style={{
                      background: d.confidence > 0.7 ? '#d1fae5' : d.confidence > 0.5 ? '#fef3c7' : '#fee2e2',
                      color: d.confidence > 0.7 ? '#047857' : d.confidence > 0.5 ? '#92400e' : '#991b1b',
                      padding: '6px 12px',
                      borderRadius: '4px',
                      fontSize: '12px',
                      fontWeight: 600,
                      whiteSpace: 'nowrap'
                    }}>
                      {(d.confidence * 100).toFixed(0)}%
                    </div>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '15px', marginTop: '8px', fontSize: '12px', color: '#999' }}>
                  <span>🆔 {d.entity_id}</span>
                  <span>📅 {new Date(d.created_at).toLocaleDateString()}</span>
                  {d.override_by_admin && <span style={{ color: '#dc2626' }}>🔴 OVERRIDDEN</span>}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
