import React, { useState, useEffect } from 'react';

const API = 'http://localhost:8000';

export default function EmployeeView({ role }) {
  const [employees, setEmployees] = useState([]);
  const [selectedEmployee, setSelectedEmployee] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchEmployees();
  }, []);

  const fetchEmployees = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API}/employees`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) setEmployees(await res.json());
    } catch (err) {
      console.error('Error:', err);
    }
    setLoading(false);
  };

  if (loading) return <div className="loading"><div className="spinner"></div></div>;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '20px' }}>
      <div className="card">
        <h2>Employees</h2>
        <div className="list">
          {employees.map(e => (
            <div
              key={e.id}
              className="list-item"
              onClick={() => setSelectedEmployee(e)}
              style={{
                background: selectedEmployee?.id === e.id ? '#f0f0ff' : '#f9f9f9',
                borderLeftColor: selectedEmployee?.id === e.id ? '#667eea' : '#ddd'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <strong>Employee #{e.id}</strong>
                <span className={`status-badge status-${e.availability_status}`}>
                  {e.availability_status}
                </span>
              </div>
              <p style={{ fontSize: '12px', color: '#666', marginTop: '5px' }}>
                {e.current_load?.toFixed(1) || 0}h / {e.max_capacity}h capacity
              </p>
            </div>
          ))}
        </div>
      </div>

      {selectedEmployee && (
        <div className="card">
          <h2>Employee #{selectedEmployee.id} Details</h2>
          
          <h3>Skills</h3>
          <div style={{ marginBottom: '15px' }}>
            {Object.entries(selectedEmployee.skills || {}).map(([skill, level]) => (
              <div key={skill} style={{ marginBottom: '8px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <span>{skill}</span>
                  <span style={{ color: '#667eea', fontWeight: 600 }}>
                    {Math.round(level * 100)}%
                  </span>
                </div>
                <div className="progress">
                  <div
                    className="progress-fill"
                    style={{ width: `${level * 100}%` }}
                  ></div>
                </div>
              </div>
            ))}
          </div>

          <h3>Workload</h3>
          <div className="progress">
            <div
              className="progress-fill"
              style={{
                width: `${Math.min((selectedEmployee.current_load / selectedEmployee.max_capacity) * 100, 100)}%`,
                background: selectedEmployee.current_load > selectedEmployee.max_capacity ? '#dc2626' : '#667eea'
              }}
            ></div>
          </div>
          <p style={{ fontSize: '12px', color: '#666', marginTop: '5px' }}>
            {selectedEmployee.current_load?.toFixed(1) || 0}h / {selectedEmployee.max_capacity}h
            ({Math.round((selectedEmployee.current_load / selectedEmployee.max_capacity) * 100)}%)
          </p>

          <h3>Status</h3>
          <p>
            <strong>Department:</strong> {selectedEmployee.department || 'Not assigned'}
          </p>
          <p>
            <strong>Availability:</strong> {selectedEmployee.availability_status}
          </p>
          
          {role === 'admin' && (
            <div className="button-group">
              <button className="btn btn-primary">View Metrics</button>
              <button className="btn btn-secondary">Edit Profile</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
