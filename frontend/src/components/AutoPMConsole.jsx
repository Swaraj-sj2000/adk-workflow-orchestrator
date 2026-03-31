import React, { useState, useEffect } from 'react';

const API = 'http://localhost:8000';

export default function AutoPMConsole() {
  const [requestText, setRequestText] = useState('');
  const [projectId, setProjectId] = useState('');
  const [assignmentProjectId, setAssignmentProjectId] = useState('');
  const [simProjectId, setSimProjectId] = useState('');
  const [clientUpdateProjectId, setClientUpdateProjectId] = useState('');
  const [closeProjectId, setCloseProjectId] = useState('');
  const [assignments, setAssignments] = useState([]);
  const [assignmentId, setAssignmentId] = useState('');
  const [responseType, setResponseType] = useState('accepted');
  const [output, setOutput] = useState(null);
  const [digest, setDigest] = useState(null);
  const [loading, setLoading] = useState(false);

  const token = localStorage.getItem('token');
  const headers = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  };

  useEffect(() => {
    fetchAssignments();
  }, []);

  const fetchAssignments = async () => {
    try {
      const res = await fetch(`${API}/task-assignments`, { headers: { 'Authorization': `Bearer ${token}` } });
      if (res.ok) {
        const data = await res.json();
        setAssignments(data);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const runAction = async (fn) => {
    setLoading(true);
    try {
      const result = await fn();
      setOutput(result);
      await fetchAssignments();
    } catch (err) {
      setOutput({ error: err.message });
    }
    setLoading(false);
  };

  return (
    <div className="dashboard">
      <div className="card full-width">
        <h2>AutoPM Console</h2>
        <p style={{ color: '#666', marginBottom: '16px' }}>
          Intake → Assign → Employee Respond → Simulate → Client Update / Close
        </p>

        <div style={{ display: 'grid', gap: '10px', marginBottom: '15px' }}>
          <textarea
            rows={4}
            value={requestText}
            onChange={(e) => setRequestText(e.target.value)}
            placeholder="Describe a project request..."
          />
          <button
            className="btn btn-primary"
            disabled={loading || !requestText.trim()}
            onClick={() => runAction(async () => {
              const res = await fetch(`${API}/autopm/intake`, {
                method: 'POST',
                headers,
                body: JSON.stringify({ request_text: requestText, budget: 10000, priority: 'high' })
              });
              const data = await res.json();
              if (!res.ok) throw new Error(data.detail || 'Intake failed');
              setProjectId(String(data.project_id));
              setAssignmentProjectId(String(data.project_id));
              setSimProjectId(String(data.project_id));
              setClientUpdateProjectId(String(data.project_id));
              setCloseProjectId(String(data.project_id));
              return data;
            })}
          >
            Run Intake
          </button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '10px', marginBottom: '10px' }}>
          <input
            value={assignmentProjectId}
            onChange={(e) => setAssignmentProjectId(e.target.value)}
            placeholder="Project ID for assignment"
          />
          <button
            className="btn btn-secondary"
            disabled={loading || !assignmentProjectId}
            onClick={() => runAction(async () => {
              const res = await fetch(`${API}/autopm/projects/${assignmentProjectId}/assign`, {
                method: 'POST',
                headers
              });
              const data = await res.json();
              if (!res.ok) throw new Error(data.detail || 'Assign failed');
              return data;
            })}
          >
            Assign Team
          </button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr auto', gap: '10px', marginBottom: '10px' }}>
          <input
            value={assignmentId}
            onChange={(e) => setAssignmentId(e.target.value)}
            placeholder="Assignment ID"
          />
          <select value={responseType} onChange={(e) => setResponseType(e.target.value)}>
            <option value="accepted">accepted</option>
            <option value="denied">denied</option>
            <option value="negotiating">negotiating</option>
          </select>
          <input value={projectId} onChange={(e) => setProjectId(e.target.value)} placeholder="Project ID" />
          <button
            className="btn btn-secondary"
            disabled={loading || !assignmentId}
            onClick={() => runAction(async () => {
              const res = await fetch(`${API}/autopm/assignments/${assignmentId}/respond`, {
                method: 'POST',
                headers,
                body: JSON.stringify({ response: responseType })
              });
              const data = await res.json();
              if (!res.ok) throw new Error(data.detail || 'Response failed');
              return data;
            })}
          >
            Submit Response
          </button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr auto auto auto', gap: '10px', marginBottom: '10px' }}>
          <input
            value={simProjectId}
            onChange={(e) => setSimProjectId(e.target.value)}
            placeholder="Project ID for simulation"
          />
          <button
            className="btn btn-primary"
            disabled={loading || !simProjectId}
            onClick={() => runAction(async () => {
              const res = await fetch(`${API}/autopm/projects/${simProjectId}/simulate`, {
                method: 'POST',
                headers,
                body: JSON.stringify({ seed: 42 })
              });
              const data = await res.json();
              if (!res.ok) throw new Error(data.detail || 'Simulation failed');
              return data;
            })}
          >
            Run Simulation
          </button>
          <button
            className="btn btn-secondary"
            disabled={loading || !clientUpdateProjectId}
            onClick={() => runAction(async () => {
              const res = await fetch(`${API}/autopm/projects/${clientUpdateProjectId}/client-update`, {
                method: 'POST',
                headers
              });
              const data = await res.json();
              if (!res.ok) throw new Error(data.detail || 'Client update failed');
              return data;
            })}
          >
            Client Update
          </button>
          <button
            className="btn btn-secondary"
            disabled={loading || !closeProjectId}
            onClick={() => runAction(async () => {
              const res = await fetch(`${API}/autopm/projects/${closeProjectId}/close`, {
                method: 'POST',
                headers
              });
              const data = await res.json();
              if (!res.ok) throw new Error(data.detail || 'Close failed');
              return data;
            })}
          >
            Close Project
          </button>
        </div>

        <button
          className="btn"
          disabled={loading}
          onClick={() => runAction(async () => {
            const res = await fetch(`${API}/autopm/digest/daily`, { headers: { 'Authorization': `Bearer ${token}` } });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Digest failed');
            setDigest(data);
            return data;
          })}
        >
          Generate Daily Digest
        </button>
      </div>

      <div className="card full-width">
        <h2>Assignment Offers</h2>
        {assignments.length === 0 ? (
          <p>No assignments yet</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Task</th>
                <th>Employee</th>
                <th>Status</th>
                <th>Confidence</th>
              </tr>
            </thead>
            <tbody>
              {assignments.slice(0, 20).map(a => (
                <tr key={a.id}>
                  <td>{a.id}</td>
                  <td>{a.task_id}</td>
                  <td>{a.employee_id}</td>
                  <td>{a.status}</td>
                  <td>{a.assignment_confidence ? a.assignment_confidence.toFixed(2) : '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {digest && (
        <div className="card full-width">
          <h2>Daily Digest</h2>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: '12px' }}>
            {JSON.stringify(digest, null, 2)}
          </pre>
        </div>
      )}

      {output && (
        <div className="card full-width">
          <h2>Last Action Output</h2>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: '12px' }}>
            {JSON.stringify(output, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
