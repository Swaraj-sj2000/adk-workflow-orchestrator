import React, { useEffect, useState } from 'react';
import './MultiAgentWorkbench.css';
import { API_BASE_URL as API } from '../config';

function prettyJson(value) {
  return JSON.stringify(value, null, 2);
}

export default function MultiAgentWorkbench() {
  const [requestText, setRequestText] = useState('');
  const [budget, setBudget] = useState(25000);
  const [priority, setPriority] = useState('high');
  const [persistProject, setPersistProject] = useState(true);
  const [loopProjectId, setLoopProjectId] = useState('');
  const [persistFollowupMessages, setPersistFollowupMessages] = useState(true);
  const [workflows, setWorkflows] = useState([]);
  const [selectedWorkflow, setSelectedWorkflow] = useState(null);
  const [queueStatus, setQueueStatus] = useState(null);
  const [failedEvents, setFailedEvents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  const token = localStorage.getItem('token');
  const authHeaders = { 'Authorization': `Bearer ${token}` };

  useEffect(() => {
    fetchWorkflows();
    fetchQueueHealth();
  }, []);

  const fetchWorkflows = async (workflowId = null) => {
    try {
      const res = await fetch(`${API}/multi-agent/workflows?limit=25`, { headers: authHeaders });
      if (!res.ok) throw new Error('Failed to load workflow runs');
      const data = await res.json();
      setWorkflows(data);

      const selectedId = workflowId || selectedWorkflow?.id || data[0]?.id;
      if (selectedId) {
        await fetchWorkflowDetail(selectedId);
      }
    } catch (err) {
      setMessage(`Failed to load workflows: ${err.message}`);
    }
  };

  const fetchWorkflowDetail = async (workflowId) => {
    try {
      const res = await fetch(`${API}/multi-agent/workflows/${workflowId}`, { headers: authHeaders });
      if (!res.ok) throw new Error('Failed to load workflow detail');
      const data = await res.json();
      setSelectedWorkflow(data);
    } catch (err) {
      setMessage(`Failed to load workflow detail: ${err.message}`);
    }
  };

  const fetchQueueHealth = async () => {
    try {
      const [statusRes, failedRes] = await Promise.all([
        fetch(`${API}/system/queue/status`, { headers: authHeaders }),
        fetch(`${API}/system/queue/failed?limit=10`, { headers: authHeaders }),
      ]);

      if (statusRes.ok) {
        setQueueStatus(await statusRes.json());
      }
      if (failedRes.ok) {
        setFailedEvents(await failedRes.json());
      }
    } catch (err) {
      setMessage(`Failed to load queue health: ${err.message}`);
    }
  };

  const runWorkflow = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage('');

    try {
      const res = await fetch(`${API}/multi-agent/workflows/intake`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders,
        },
        body: JSON.stringify({
          request_text: requestText,
          budget: Number(budget),
          priority,
          persist_project: persistProject,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Workflow launch failed');

      setMessage(`Workflow #${data.id} completed with status: ${data.final_output?.autonomy_status || data.status}`);
      setRequestText('');
      await fetchWorkflows(data.id);
      await fetchQueueHealth();
    } catch (err) {
      setMessage(`Workflow failed: ${err.message}`);
    }

    setLoading(false);
  };

  const approveWorkflow = async () => {
    if (!selectedWorkflow) return;
    setLoading(true);
    setMessage('');
    try {
      const res = await fetch(`${API}/multi-agent/workflows/${selectedWorkflow.id}/approve`, {
        method: 'POST',
        headers: authHeaders,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Approval failed');
      setSelectedWorkflow(data);
      await fetchWorkflows(data.id);
      await fetchQueueHealth();
      setMessage(`Workflow #${data.id} approved. ${data.final_output?.execution_persistence?.created_assignment_count || 0} assignment offer(s) are now persisted.`);
    } catch (err) {
      setMessage(`Approval failed: ${err.message}`);
    }
    setLoading(false);
  };

  const runProjectLoop = async () => {
    if (!loopProjectId) return;
    setLoading(true);
    setMessage('');
    try {
      const res = await fetch(`${API}/multi-agent/projects/${loopProjectId}/loop`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders,
        },
        body: JSON.stringify({
          persist_followup_messages: persistFollowupMessages,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Project loop failed');
      setMessage(`Project loop workflow #${data.id} completed for project ${loopProjectId}.`);
      await fetchWorkflows(data.id);
      await fetchQueueHealth();
    } catch (err) {
      setMessage(`Project loop failed: ${err.message}`);
    }
    setLoading(false);
  };

  const finalOutput = selectedWorkflow?.final_output || {};
  const executionPersistence = finalOutput.execution_persistence;

  return (
    <div className="dashboard multi-agent-workbench">
      <div className="card full-width">
        <h2>Multi-Agent Workbench</h2>
        <p>
          Run the new orchestrated workflow and inspect each agent stage, confidence score,
          escalation packet, and any assignment offers the system persisted.
        </p>

        {message && (
          <div className={`auth-message ${message.includes('failed') || message.includes('Failed') ? 'error' : 'success'}`}>
            {message}
          </div>
        )}

        <form onSubmit={runWorkflow} className="multi-agent-form">
          <textarea
            rows={5}
            value={requestText}
            onChange={(e) => setRequestText(e.target.value)}
            placeholder="Describe the project request for the multi-agent system..."
            required
          />

          <div className="multi-agent-form-grid">
            <input
              type="number"
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
              placeholder="Budget"
              min="0"
            />

            <select value={priority} onChange={(e) => setPriority(e.target.value)}>
              <option value="low">low</option>
              <option value="medium">medium</option>
              <option value="high">high</option>
              <option value="critical">critical</option>
            </select>

            <label className="multi-agent-checkbox">
              <input
                type="checkbox"
                checked={persistProject}
                onChange={(e) => setPersistProject(e.target.checked)}
              />
              Persist project + task graph
            </label>
          </div>

          <div className="button-group">
            <button className="btn btn-primary" type="submit" disabled={loading || !requestText.trim()}>
              {loading ? 'Running Workflow...' : 'Run Multi-Agent Workflow'}
            </button>
            <button
              className="btn btn-secondary"
              type="button"
              disabled={loading}
              onClick={() => fetchWorkflows()}
            >
              Refresh Runs
            </button>
          </div>
        </form>

        <div className="multi-agent-loop-box">
          <h3>Run Existing Project Loop</h3>
          <p>
            Re-enter the orchestrator on a live project to reassess delivery health, rebalance work,
            and draft follow-up actions.
          </p>
          <div className="multi-agent-form-grid">
            <input
              type="number"
              value={loopProjectId}
              onChange={(e) => setLoopProjectId(e.target.value)}
              placeholder="Existing Project ID"
              min="1"
            />
            <label className="multi-agent-checkbox">
              <input
                type="checkbox"
                checked={persistFollowupMessages}
                onChange={(e) => setPersistFollowupMessages(e.target.checked)}
              />
              Persist follow-up messages
            </label>
            <button
              className="btn btn-secondary"
              type="button"
              disabled={loading || !loopProjectId}
              onClick={runProjectLoop}
            >
              {loading ? 'Running Loop...' : 'Run Project Loop'}
            </button>
          </div>
        </div>
      </div>

      <div className="card full-width">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px' }}>
          <h2>Worker Queue Health</h2>
          <button className="btn btn-secondary" type="button" disabled={loading} onClick={fetchQueueHealth}>
            Refresh Queue
          </button>
        </div>

        <div className="multi-agent-summary-grid">
          <div className="health-item">
            <h4>Pending</h4>
            <div className="metric">{queueStatus?.pending || 0}</div>
          </div>
          <div className="health-item">
            <h4>Completed</h4>
            <div className="metric">{queueStatus?.completed || 0}</div>
          </div>
          <div className="health-item">
            <h4>Failed</h4>
            <div className="metric">{queueStatus?.failed || 0}</div>
          </div>
          <div className="health-item">
            <h4>Latest Event</h4>
            <div style={{ fontSize: '13px', color: '#475569' }}>
              {queueStatus?.latest_event?.event_type || 'none'}
            </div>
          </div>
        </div>

        {failedEvents.length > 0 && (
          <details style={{ marginTop: '16px' }}>
            <summary>Failed Queue Events</summary>
            <pre className="workflow-pre">{prettyJson(failedEvents)}</pre>
          </details>
        )}
      </div>

      <div className="card">
        <h2>Workflow Runs</h2>
        <div className="list">
          {workflows.length === 0 ? (
            <p>No workflow runs yet</p>
          ) : (
            workflows.map((workflow) => (
              <div
                key={workflow.id}
                className="list-item"
                onClick={() => fetchWorkflowDetail(workflow.id)}
                style={{
                  borderLeftColor: selectedWorkflow?.id === workflow.id ? '#0f766e' : '#667eea',
                  background: selectedWorkflow?.id === workflow.id ? '#ecfeff' : '#f9f9f9',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px' }}>
                  <strong>Workflow #{workflow.id}</strong>
                  <span className={`status-badge status-${workflow.requires_human_review ? 'high' : 'low'}`}>
                    {workflow.final_output?.autonomy_status || workflow.status}
                  </span>
                </div>
                <p>{workflow.workflow_type}</p>
                <p>
                  Project: {workflow.project_id || 'not persisted'}
                </p>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="card" style={{ gridColumn: 'span 2' }}>
        <h2>Workflow Detail</h2>
        {!selectedWorkflow ? (
          <p>Select a workflow run to inspect it.</p>
        ) : (
          <div className="multi-agent-detail">
            <div className="multi-agent-summary-grid">
              <div className="health-item">
                <h4>Workflow</h4>
                <div className="metric">#{selectedWorkflow.id}</div>
              </div>
              <div className="health-item">
                <h4>Autonomy</h4>
                <div className={`risk-badge risk-${selectedWorkflow.requires_human_review ? 'high' : 'low'}`}>
                  {finalOutput.autonomy_status || selectedWorkflow.status}
                </div>
              </div>
              <div className="health-item">
                <h4>Project</h4>
                <div className="metric" style={{ fontSize: '22px' }}>{selectedWorkflow.project_id || 'N/A'}</div>
              </div>
              <div className="health-item">
                <h4>Agent Stages</h4>
                <div className="metric">{selectedWorkflow.agent_runs?.length || 0}</div>
              </div>
            </div>

            <div className="alert alert-info">
              <strong>Next Actions:</strong>
              <ul className="multi-agent-actions">
                {(finalOutput.recommended_next_actions || []).map((action) => (
                  <li key={action}>{action}</li>
                ))}
              </ul>
            </div>

            {selectedWorkflow.requires_human_review && (
              <div className="button-group">
                <button className="btn btn-primary" disabled={loading} onClick={approveWorkflow}>
                  {loading ? 'Approving...' : 'Approve And Continue'}
                </button>
              </div>
            )}

            <div className="multi-agent-panels">
              <div className="card">
                <h2>Agent Trace</h2>
                <div className="list">
                  {(selectedWorkflow.agent_runs || []).map((run) => (
                    <div key={run.id} className="list-item" style={{ cursor: 'default' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'center' }}>
                        <strong>{run.agent_name}</strong>
                        <span className={`status-badge status-${run.requires_human_review ? 'high' : 'low'}`}>
                          {(run.confidence || 0).toFixed(2)}
                        </span>
                      </div>
                      <p>{run.role} · {run.stage}</p>
                      <p>{run.reasoning}</p>
                      <details>
                        <summary>Output Payload</summary>
                        <pre className="workflow-pre">{prettyJson(run.output_payload)}</pre>
                      </details>
                    </div>
                  ))}
                </div>
              </div>

              <div className="card">
                <h2>Recommended Team</h2>
                {finalOutput.staffing?.staffing_recommendations ? (
                  <div className="list">
                    {finalOutput.staffing.staffing_recommendations.map((rec) => (
                      <div key={rec.task_sequence} className="list-item">
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                          <strong>Task {rec.task_sequence}: {rec.task_title}</strong>
                          {rec.recommended_owner && (
                            <span className={`status-badge status-${rec.recommended_owner.score > 0.7 ? 'low' : 'high'}`}>
                              {(rec.recommended_owner.score * 100).toFixed(0)}% match
                            </span>
                          )}
                        </div>
                        {rec.recommended_owner ? (
                          <div style={{ marginLeft: '12px', fontSize: '14px' }}>
                            <p style={{ margin: '4px 0' }}>
                              <strong>Recommended:</strong> Employee #{rec.recommended_owner.employee_profile_id}
                            </p>
                            <p style={{ margin: '4px 0', color: '#6b7280' }}>
                              Workload: {rec.recommended_owner.current_load}/{rec.recommended_owner.max_capacity} hours 
                              ({((rec.recommended_owner.current_load / rec.recommended_owner.max_capacity) * 100).toFixed(0)}% capacity)
                            </p>
                            <p style={{ margin: '4px 0', color: '#6b7280' }}>
                              Skills: {Object.entries(rec.recommended_owner.skills || {})
                                .map(([skill, level]) => `${skill} (${(level * 100).toFixed(0)}%)`)
                                .join(', ') || 'No skills listed'}
                            </p>
                          </div>
                        ) : (
                          <p style={{ color: '#ef4444', marginLeft: '12px' }}>⚠️ No suitable employee found for this task</p>
                        )}
                        
                        {rec.recommended_candidates && rec.recommended_candidates.length > 1 && (
                          <details style={{ marginTop: '8px', marginLeft: '12px' }}>
                            <summary style={{ cursor: 'pointer', color: '#667eea' }}>
                              View {rec.recommended_candidates.length - 1} alternative candidate(s)
                            </summary>
                            <div style={{ marginTop: '8px' }}>
                              {rec.recommended_candidates.slice(1).map((candidate) => (
                                <div key={candidate.employee_profile_id} style={{ marginLeft: '12px', marginTop: '8px', paddingLeft: '12px', borderLeft: '2px solid #e5e7eb' }}>
                                  <p style={{ margin: '2px 0', fontSize: '13px' }}>
                                    <strong>Employee #{candidate.employee_profile_id}</strong> - {(candidate.score * 100).toFixed(0)}% match
                                  </p>
                                  <p style={{ margin: '2px 0', fontSize: '12px', color: '#9ca3af' }}>
                                    Workload: {candidate.current_load}/{candidate.max_capacity} hours
                                  </p>
                                </div>
                              ))}
                            </div>
                          </details>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p>No staffing recommendations available. Run an intake workflow with persist_project enabled.</p>
                )}
              </div>

              <div className="card">
                <h2>Execution Outcome</h2>
                {finalOutput.execution_coordination ? (
                  <>
                    <p>
                      Autonomous tasks: {finalOutput.execution_coordination?.autonomous_task_count || 0}
                    </p>
                    <p>
                      Review required: {finalOutput.execution_coordination?.review_required_task_count || 0}
                    </p>
                    <p>
                      Persisted offers: {executionPersistence?.created_assignment_count || 0}
                    </p>
                  </>
                ) : (
                  <>
                    <p>
                      Project status: {finalOutput.project_state?.project?.status || 'unknown'}
                    </p>
                    <p>
                      Open blockers: {finalOutput.project_state?.open_blocker_count || 0}
                    </p>
                    <p>
                      Reassignment suggestions: {finalOutput.rebalance?.reassignment_suggestions?.length || 0}
                    </p>
                  </>
                )}

                <details open>
                  <summary>Escalation Packet</summary>
                  <pre className="workflow-pre">{prettyJson(finalOutput.escalation || {})}</pre>
                </details>

                <details>
                  <summary>Communications Draft</summary>
                  <pre className="workflow-pre">{prettyJson(finalOutput.communications || {})}</pre>
                </details>

                <details>
                  <summary>Execution Persistence</summary>
                  <pre className="workflow-pre">{prettyJson(executionPersistence || {})}</pre>
                </details>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
