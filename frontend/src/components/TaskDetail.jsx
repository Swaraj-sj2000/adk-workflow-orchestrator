import React, { useState, useEffect } from 'react';
import { apiFetchJson } from '../lib/http';

export default function TaskDetail({ taskId }) {
  const [task, setTask] = useState(null);
  const [assignments, setAssignments] = useState([]);
  const [progress, setProgress] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTaskData();
  }, [taskId]);

  const fetchTaskData = async () => {
    try {
      const [taskResult, assignmentResult, progressResult] = await Promise.allSettled([
        apiFetchJson(`/tasks/${taskId}`, { auth: true }),
        apiFetchJson(`/task-assignments?task_id=${taskId}`, { auth: true }),
        apiFetchJson(`/task-progress?task_id=${taskId}`, { auth: true }),
      ]);

      if (taskResult.status === 'fulfilled') {
        setTask(taskResult.value);
      }
      if (assignmentResult.status === 'fulfilled') {
        setAssignments(assignmentResult.value);
      }
      if (progressResult.status === 'fulfilled') {
        setProgress(progressResult.value);
      }
    } catch (err) {
      console.error('Error:', err);
    }
    setLoading(false);
  };

  if (loading) return <div className="loading"><div className="spinner"></div></div>;
  if (!task) return <div className="card"><p>Task not found</p></div>;

  return (
    <div className="task-detail">
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '20px' }}>
          <div>
            <h2>{task.description}</h2>
            <p style={{ color: '#666' }}>Task #{task.id}</p>
          </div>
          <span className={`status-badge status-${task.status}`}>
            {task.status}
          </span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '15px', marginBottom: '20px' }}>
          <div>
            <p style={{ fontSize: '12px', color: '#999', marginBottom: '5px' }}>STATUS</p>
            <p className="metric" style={{ marginTop: 0 }}>{task.status}</p>
          </div>
          <div>
            <p style={{ fontSize: '12px', color: '#999', marginBottom: '5px' }}>DIFFICULTY</p>
            <p className="metric" style={{ marginTop: 0 }}>{task.difficulty}</p>
          </div>
          <div>
            <p style={{ fontSize: '12px', color: '#999', marginBottom: '5px' }}>URGENCY</p>
            <p className="metric" style={{ marginTop: 0 }}>{task.urgency}</p>
          </div>
          <div>
            <p style={{ fontSize: '12px', color: '#999', marginBottom: '5px' }}>EST. TIME</p>
            <p className="metric" style={{ marginTop: 0 }}>{task.estimated_time}h</p>
          </div>
        </div>

        {progress && (
          <div style={{ marginBottom: '20px' }}>
            <h3>Progress</h3>
            <div className="progress">
              <div
                className="progress-fill"
                style={{ width: `${progress.completion_percentage}%` }}
              ></div>
            </div>
            <p style={{ fontSize: '12px', color: '#666' }}>
              {progress.completion_percentage}% Complete
              ({progress.actual_hours_spent?.toFixed(1)}h / {task.estimated_time}h)
            </p>
          </div>
        )}

        <h3>Assignments</h3>
        {assignments.length === 0 ? (
          <p style={{ color: '#666' }}>No assignments yet</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Employee</th>
                <th>Status</th>
                <th>Confidence</th>
                <th>Est. Hours</th>
                <th>Actual Hours</th>
              </tr>
            </thead>
            <tbody>
              {assignments.map(a => (
                <tr key={a.id}>
                  <td>Employee #{a.employee_id}</td>
                  <td>{a.status}</td>
                  <td>{a.assignment_confidence?.toFixed(2) || 'N/A'}</td>
                  <td>{a.estimated_hours?.toFixed(1) || '—'}h</td>
                  <td>{a.actual_hours?.toFixed(1) || '—'}h</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <h3>Required Skills</h3>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
          {Object.entries(task.required_skills || {}).map(([skill, level]) => (
            <span
              key={skill}
              style={{
                background: '#f0f0ff',
                padding: '6px 12px',
                borderRadius: '4px',
                fontSize: '12px',
                border: '1px solid #667eea'
              }}
            >
              {skill} ({Math.round(level * 100)}%)
            </span>
          ))}
          {Object.keys(task.required_skills || {}).length === 0 && (
            <p style={{ color: '#999' }}>No specific skills required</p>
          )}
        </div>

        {task.deadline && (
          <div style={{ marginTop: '20px' }}>
            <h3>Deadline</h3>
            <p>{new Date(task.deadline).toLocaleDateString()}</p>
          </div>
        )}

        <div className="button-group">
          <button className="btn btn-primary">Update Progress</button>
          <button className="btn btn-secondary">Edit Task</button>
        </div>
      </div>
    </div>
  );
}
