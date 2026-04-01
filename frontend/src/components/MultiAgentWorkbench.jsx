import React, { useEffect, useState } from 'react';
import './MultiAgentWorkbench.css';
import { apiFetchJson } from '../lib/http';

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

  useEffect(() => {
    fetchWorkflows();
    fetchQueueHealth();
  }, []);

  const fetchWorkflows = async (workflowId = null) => {
    try {
      const data = await apiFetchJson('/multi-agent/workflows?limit=25', { auth: true });
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
      const data = await apiFetchJson(`/multi-agent/workflows/${workflowId}`, { auth: true });
      setSelectedWorkflow(data);
    } catch (err) {
      setMessage(`Failed to load workflow detail: ${err.message}`);
    }
  };

  const fetchQueueHealth = async () => {
    try {
      const [statusData, failedData] = await Promise.all([
        apiFetchJson('/system/queue/status', { auth: true }),
        apiFetchJson('/system/queue/failed?limit=10', { auth: true }),
      ]);
      setQueueStatus(statusData);
      setFailedEvents(failedData);
    } catch (err) {
      setMessage(`Failed to load queue health: ${err.message}`);
    }
  };

  const runWorkflow = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage('');

    try {
      const data = await apiFetchJson('/multi-agent/workflows/intake', {
        method: 'POST',
        auth: true,
        body: {
          request_text: requestText,
          budget: Number(budget),
          priority,
          persist_project: persistProject,
        },
      });

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
      const data = await apiFetchJson(`/multi-agent/workflows/${selectedWorkflow.id}/approve`, {
        method: 'POST',
        auth: true,
      });
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
      const data = await apiFetchJson(`/multi-agent/projects/${loopProjectId}/loop`, {
        method: 'POST',
        auth: true,
        body: {
          persist_followup_messages: persistFollowupMessages,
        },
      });
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
            <button 
              className="btn btn-primary" 
              type="submit" 
              disabled={loading || !requestText.trim()}
              data-tooltip="Execute all agents: intake → planning → staffing → risk → execution"
            >
              {loading ? 'Running Workflow...' : 'Run Multi-Agent Workflow'}
            </button>
            <button
              className="btn btn-secondary"
              type="button"
              disabled={loading}
              onClick={() => fetchWorkflows()}
              data-tooltip="Reload the list of recent workflow executions"
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
          <button 
            className="btn btn-secondary" 
            type="button" 
            disabled={loading} 
            onClick={fetchQueueHealth}
            data-tooltip="Check the status of background task workers"
          >
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
                <button 
                  className="btn btn-primary" 
                  disabled={loading} 
                  onClick={approveWorkflow}
                  data-tooltip="Approve this workflow to proceed with task assignments and execution"
                >
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
