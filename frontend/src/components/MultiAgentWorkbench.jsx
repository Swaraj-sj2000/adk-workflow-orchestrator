import React, { useEffect, useState } from 'react';
import './MultiAgentWorkbench.css';
import { API_BASE_URL as API } from '../config';

// ── Agent card ────────────────────────────────────────────────────────────────

const AGENT_META = {
  intake_agent:                 { label: 'Intake Agent',               icon: '📥', color: '#6366f1' },
  planning_agent:               { label: 'Planning Agent',             icon: '🗺️', color: '#0891b2' },
  staffing_agent:               { label: 'Staffing Agent',             icon: '👥', color: '#0d9488' },
  risk_agent:                   { label: 'Risk Agent',                 icon: '⚠️', color: '#d97706' },
  execution_coordinator_agent:  { label: 'Execution Coordinator',      icon: '⚙️', color: '#7c3aed' },
  communication_agent:          { label: 'Communication Agent',        icon: '📢', color: '#0284c7' },
  escalation_agent:             { label: 'Escalation Agent',           icon: '🚨', color: '#dc2626' },
  project_observer_agent:       { label: 'Project Observer',           icon: '🔭', color: '#475569' },
  delivery_review_agent:        { label: 'Delivery Review Agent',      icon: '📦', color: '#059669' },
  rebalance_agent:              { label: 'Rebalance Agent',            icon: '⚖️', color: '#db2777' },
  loop_communication_agent:     { label: 'Loop Communication Agent',   icon: '🔄', color: '#0284c7' },
  loop_escalation_agent:        { label: 'Loop Escalation Agent',      icon: '🔺', color: '#dc2626' },
};

function ConfidenceBar({ value }) {
  const pct = Math.round((value || 0) * 100);
  const color = pct >= 80 ? '#16a34a' : pct >= 60 ? '#d97706' : '#dc2626';
  return (
    <div className="maw-conf-bar">
      <div className="maw-conf-fill" style={{ width: `${pct}%`, background: color }} />
      <span className="maw-conf-label">{pct}%</span>
    </div>
  );
}

function RiskBadge({ level }) {
  const colors = { high: '#fee2e2', medium: '#fef3c7', low: '#dcfce7', critical: '#fce7f3' };
  const text   = { high: '#991b1b', medium: '#92400e', low: '#166534', critical: '#9d174d' };
  const l = (level || 'unknown').toLowerCase();
  return (
    <span className="maw-badge" style={{ background: colors[l] || '#f1f5f9', color: text[l] || '#334155' }}>
      {l}
    </span>
  );
}

function DecisionBadge({ decision }) {
  const autonomous = decision === 'continue_autonomously';
  return (
    <span className="maw-badge" style={{ background: autonomous ? '#dcfce7' : '#fee2e2', color: autonomous ? '#166534' : '#991b1b' }}>
      {autonomous ? '✓ Autonomous' : '⚠ Human review required'}
    </span>
  );
}

function AgentHighlights({ name, payload }) {
  if (!payload) return null;
  switch (name) {
    case 'intake_agent': {
      const brief = payload.parsed_brief || {};
      return (
        <div className="maw-highlights">
          {brief.project_title && <div className="maw-hl-row"><span>Project</span><strong>{brief.project_title}</strong></div>}
          <div className="maw-hl-row"><span>Tasks identified</span><strong>{(brief.tasks || []).length}</strong></div>
          {brief.project_complexity != null && <div className="maw-hl-row"><span>Complexity</span><strong>{(brief.project_complexity * 100).toFixed(0)}%</strong></div>}
        </div>
      );
    }
    case 'planning_agent': {
      const tasks = payload.tasks || [];
      return (
        <div className="maw-highlights">
          <div className="maw-hl-row"><span>Tasks planned</span><strong>{tasks.length}</strong></div>
          <div className="maw-hl-row"><span>Dependencies</span><strong>{(payload.dependencies || []).length}</strong></div>
          <div className="maw-task-list">
            {tasks.slice(0, 6).map((t) => (
              <div key={t.sequence} className="maw-task-row">
                <span className="maw-task-seq">{t.sequence}</span>
                <span className="maw-task-title">{t.title}</span>
                <span className="maw-task-meta">{t.difficulty} · {t.estimated_time}h</span>
              </div>
            ))}
          </div>
        </div>
      );
    }
    case 'staffing_agent': {
      return (
        <div className="maw-highlights">
          <div className="maw-hl-row"><span>Tasks staffed</span><strong>{(payload.staffing_recommendations || []).length}</strong></div>
          <div className="maw-hl-row"><span>Under-staffed</span><strong style={{ color: payload.under_staffed_task_count > 0 ? '#dc2626' : '#16a34a' }}>{payload.under_staffed_task_count || 0}</strong></div>
          {(payload.staffing_recommendations || []).slice(0, 4).map((r, i) => (
            <div key={i} className="maw-task-row">
              <span className="maw-task-seq">T{r.task_sequence}</span>
              <span className="maw-task-title">{r.recommended_owner ? `Employee #${r.recommended_owner.employee_profile_id}` : 'No match'}</span>
              <span className="maw-task-meta">{r.recommended_owner ? `${(r.recommended_owner.score * 100).toFixed(0)}% fit` : '—'}</span>
            </div>
          ))}
        </div>
      );
    }
    case 'risk_agent': {
      return (
        <div className="maw-highlights">
          <div className="maw-hl-row"><span>Risk level</span><RiskBadge level={payload.risk_level} /></div>
          {payload.narrative && <p className="maw-narrative">{payload.narrative}</p>}
          {(payload.risks || []).map((r, i) => (
            <div key={i} className="maw-risk-row">
              <RiskBadge level={r.severity} />
              <span>{r.type}: {r.reason}</span>
            </div>
          ))}
        </div>
      );
    }
    case 'execution_coordinator_agent': {
      return (
        <div className="maw-highlights">
          <div className="maw-hl-row"><span>Autonomous tasks</span><strong style={{ color: '#16a34a' }}>{payload.autonomous_task_count || 0}</strong></div>
          <div className="maw-hl-row"><span>Needs review</span><strong style={{ color: payload.review_required_task_count > 0 ? '#d97706' : '#16a34a' }}>{payload.review_required_task_count || 0}</strong></div>
          {(payload.next_actions || []).length > 0 && (
            <div className="maw-action-list">
              {(payload.next_actions || []).map((a, i) => <div key={i} className="maw-action-row">→ {a}</div>)}
            </div>
          )}
        </div>
      );
    }
    case 'escalation_agent':
    case 'loop_escalation_agent': {
      return (
        <div className="maw-highlights">
          <div className="maw-hl-row"><span>Decision</span><DecisionBadge decision={payload.decision} /></div>
          {payload.narrative && <p className="maw-narrative">{payload.narrative}</p>}
          {(payload.reasons || []).map((r, i) => <div key={i} className="maw-action-row">· {r}</div>)}
        </div>
      );
    }
    case 'communication_agent':
    case 'loop_communication_agent': {
      const msgs = payload.messages || [];
      return (
        <div className="maw-highlights">
          <div className="maw-hl-row"><span>Messages drafted</span><strong>{msgs.length}</strong></div>
          {msgs.slice(0, 2).map((m, i) => (
            <div key={i} className="maw-task-row">
              <span className="maw-task-seq">{m.recipient_role || 'all'}</span>
              <span className="maw-task-title">{m.subject || m.message_type || 'Message'}</span>
            </div>
          ))}
        </div>
      );
    }
    case 'delivery_review_agent': {
      return (
        <div className="maw-highlights">
          {payload.llm_health_status && <div className="maw-hl-row"><span>Health</span><RiskBadge level={payload.llm_health_status === 'on_track' ? 'low' : payload.llm_health_status === 'at_risk' ? 'medium' : 'high'} /></div>}
          {payload.llm_narrative && <p className="maw-narrative">{payload.llm_narrative}</p>}
          {(payload.priority_actions || []).map((a, i) => <div key={i} className="maw-action-row">→ {a}</div>)}
          {(payload.delivery_blockers || []).length > 0 && <div className="maw-hl-row"><span>Blockers</span><strong style={{ color: '#dc2626' }}>{payload.delivery_blockers.length}</strong></div>}
        </div>
      );
    }
    case 'rebalance_agent': {
      const cap = payload.capacity_summary || {};
      return (
        <div className="maw-highlights">
          <div className="maw-hl-row"><span>Rebalance needed</span><strong style={{ color: payload.rebalance_needed ? '#dc2626' : '#16a34a' }}>{payload.rebalance_needed ? 'Yes' : 'No'}</strong></div>
          {cap.overloaded_count > 0 && <div className="maw-hl-row"><span>Overloaded employees</span><strong style={{ color: '#dc2626' }}>{cap.overloaded_count}</strong></div>}
          {cap.deficit_hours > 0 && <div className="maw-hl-row"><span>Capacity deficit</span><strong style={{ color: '#d97706' }}>{cap.deficit_hours}h</strong></div>}
          {payload.llm_narrative && <p className="maw-narrative">{payload.llm_narrative}</p>}
          {(payload.llm_actions || []).map((a, i) => <div key={i} className="maw-action-row">→ {a}</div>)}
          {payload.admin_alert && payload.admin_message && (
            <div className="maw-alert-box">⚠ Admin notified: {payload.admin_message}</div>
          )}
        </div>
      );
    }
    case 'project_observer_agent': {
      const state = payload.project_state || payload;
      return (
        <div className="maw-highlights">
          {state.project?.status && <div className="maw-hl-row"><span>Project status</span><strong>{state.project.status}</strong></div>}
          {state.open_blocker_count != null && <div className="maw-hl-row"><span>Open blockers</span><strong style={{ color: state.open_blocker_count > 0 ? '#dc2626' : '#16a34a' }}>{state.open_blocker_count}</strong></div>}
          {state.total_tasks != null && <div className="maw-hl-row"><span>Tasks</span><strong>{state.completed_tasks || 0} / {state.total_tasks} done</strong></div>}
        </div>
      );
    }
    default:
      return null;
  }
}

function AgentCard({ run }) {
  const meta = AGENT_META[run.agent_name] || { label: run.agent_name, icon: '🤖', color: '#64748b' };
  return (
    <div className="maw-agent-card" style={{ borderTopColor: meta.color }}>
      <div className="maw-agent-header">
        <div className="maw-agent-title">
          <span className="maw-agent-icon">{meta.icon}</span>
          <div>
            <div className="maw-agent-name">{meta.label}</div>
            <div className="maw-agent-role">{run.role} · {run.stage}</div>
          </div>
        </div>
        <div className="maw-agent-right">
          <ConfidenceBar value={run.confidence} />
          {run.requires_human_review && <span className="maw-badge" style={{ background: '#fee2e2', color: '#991b1b', marginTop: 4 }}>Needs review</span>}
        </div>
      </div>
      {run.reasoning && <p className="maw-reasoning">{run.reasoning}</p>}
      <AgentHighlights name={run.agent_name} payload={run.output_payload} />
    </div>
  );
}

// ── Workflow result view ───────────────────────────────────────────────────────

function WorkflowResultView({ workflow, onApprove, approving }) {
  if (!workflow) return null;
  const fo = workflow.final_output || {};
  const runs = workflow.agent_runs || [];
  const isIntake = workflow.workflow_type === 'project_intake';

  return (
    <div className="maw-result">
      <div className="maw-result-header">
        <div className="maw-result-meta">
          <span className="maw-result-id">Workflow #{workflow.id}</span>
          <span className="maw-result-type">{workflow.workflow_type}</span>
          {workflow.project_id && <span className="maw-result-type">Project #{workflow.project_id}</span>}
        </div>
        <DecisionBadge decision={fo.escalation?.decision || (workflow.requires_human_review ? 'human_review_required' : 'continue_autonomously')} />
      </div>

      {isIntake && fo.execution_plan && (
        <div className="maw-result-summary">
          <strong>{fo.execution_plan.project_title}</strong>
          <p>{fo.execution_plan.project_summary}</p>
          <div className="maw-result-stats">
            <div className="maw-stat"><span>Tasks</span><strong>{(fo.execution_plan.tasks || []).length}</strong></div>
            <div className="maw-stat"><span>Risk</span><RiskBadge level={fo.risk?.risk_level} /></div>
            <div className="maw-stat"><span>Autonomous</span><strong>{fo.execution_coordination?.autonomous_task_count || 0}</strong></div>
            <div className="maw-stat"><span>Agents run</span><strong>{runs.length}</strong></div>
          </div>
        </div>
      )}

      {workflow.requires_human_review && onApprove && isIntake && (
        <div className="maw-approve-bar">
          <p>This workflow requires human review before autonomous execution can proceed.</p>
          <button className="btn btn-primary" onClick={onApprove} disabled={approving}>
            {approving ? 'Approving…' : 'Approve and Continue'}
          </button>
        </div>
      )}

      <div className="maw-agents-grid">
        {runs.map((run) => <AgentCard key={run.id} run={run} />)}
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function MultiAgentWorkbench() {
  const [tab, setTab] = useState('brief');

  // New Brief tab
  const [briefText, setBriefText]       = useState('');
  const [briefBudget, setBriefBudget]   = useState('');
  const [briefPriority, setBriefPriority] = useState('high');
  const [briefDeadline, setBriefDeadline] = useState('');
  const [briefPersist, setBriefPersist] = useState(false);
  const [briefRunning, setBriefRunning] = useState(false);
  const [briefResult, setBriefResult]   = useState(null);

  // Project Loop tab
  const [projects, setProjects]           = useState([]);
  const [loopProjectId, setLoopProjectId] = useState('');
  const [loopPersist, setLoopPersist]     = useState(false);
  const [loopRunning, setLoopRunning]     = useState(false);
  const [loopResult, setLoopResult]       = useState(null);

  // History tab
  const [workflows, setWorkflows]           = useState([]);
  const [historyWorkflow, setHistoryWorkflow] = useState(null);
  const [historyLoading, setHistoryLoading] = useState(false);

  const [approving, setApproving] = useState(false);
  const [message, setMessage]     = useState('');

  const token = localStorage.getItem('token');
  const authHeaders = { Authorization: `Bearer ${token}` };

  useEffect(() => {
    fetchProjects();
    fetchWorkflows();
  }, []);

  const fetchProjects = async () => {
    try {
      const res = await fetch(`${API}/projects/`, { headers: authHeaders });
      if (res.ok) {
        const data = await res.json();
        setProjects(Array.isArray(data) ? data : data.items || []);
      }
    } catch (_) {}
  };

  const fetchWorkflows = async () => {
    try {
      const res = await fetch(`${API}/multi-agent/workflows?limit=30`, { headers: authHeaders });
      if (res.ok) setWorkflows(await res.json());
    } catch (_) {}
  };

  const fetchWorkflowDetail = async (id) => {
    setHistoryLoading(true);
    try {
      const res = await fetch(`${API}/multi-agent/workflows/${id}`, { headers: authHeaders });
      if (res.ok) setHistoryWorkflow(await res.json());
    } catch (_) {}
    setHistoryLoading(false);
  };

  const runBriefIntake = async () => {
    if (!briefText.trim() || briefRunning) return;
    setBriefRunning(true);
    setBriefResult(null);
    setMessage('');
    try {
      const body = {
        request_text: briefText.trim(),
        budget: parseFloat(briefBudget) || 0,
        priority: briefPriority,
        persist_project: briefPersist,
      };
      if (briefDeadline) body.deadline = new Date(briefDeadline).toISOString();
      const res = await fetch(`${API}/multi-agent/workflows/intake`, {
        method: 'POST',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Intake failed');
      setBriefResult(data);
      fetchWorkflows();
      if (briefPersist) fetchProjects();
      setMessage(briefPersist ? `Project #${data.project_id} created.` : 'Simulation complete — not saved.');
    } catch (err) {
      setMessage(`Error: ${err.message}`);
    }
    setBriefRunning(false);
  };

  const runProjectLoop = async () => {
    if (!loopProjectId || loopRunning) return;
    setLoopRunning(true);
    setLoopResult(null);
    setMessage('');
    try {
      const res = await fetch(`${API}/multi-agent/projects/${loopProjectId}/loop`, {
        method: 'POST',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({ persist_followup_messages: loopPersist }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Loop failed');
      setLoopResult(data);
      fetchWorkflows();
      setMessage(loopPersist ? 'Loop run complete — changes applied to project.' : 'Loop complete — view only, nothing changed.');
    } catch (err) {
      setMessage(`Error: ${err.message}`);
    }
    setLoopRunning(false);
  };

  const approveWorkflow = async (workflow) => {
    if (!workflow || approving) return;
    setApproving(true);
    try {
      const res = await fetch(`${API}/multi-agent/workflows/${workflow.id}/approve`, {
        method: 'POST',
        headers: authHeaders,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Approval failed');
      if (tab === 'brief') setBriefResult(data);
      if (tab === 'history') setHistoryWorkflow(data);
      fetchWorkflows();
      setMessage(`Workflow #${data.id} approved.`);
    } catch (err) {
      setMessage(`Approval failed: ${err.message}`);
    }
    setApproving(false);
  };

  const TABS = [
    { key: 'brief',   label: 'New Brief' },
    { key: 'loop',    label: 'Project Loop' },
    { key: 'history', label: 'History' },
  ];

  return (
    <div className="maw-root">
      <div className="maw-page-header">
        <div>
          <p className="eyebrow">AI Operations</p>
          <h1>Multi-Agent Workbench</h1>
          <p className="maw-page-sub">Observe, simulate, and control the full AI agent pipeline. Every agent decision is visible here.</p>
        </div>
      </div>

      {message && (
        <div className={`maw-message ${message.startsWith('Error') ? 'error' : 'success'}`}>
          {message}
          <button className="maw-message-close" onClick={() => setMessage('')}>✕</button>
        </div>
      )}

      <div className="maw-tabs">
        {TABS.map((t) => (
          <button key={t.key} className={`maw-tab ${tab === t.key ? 'active' : ''}`} onClick={() => setTab(t.key)}>
            {t.label}
          </button>
        ))}
      </div>

      {/* ── New Brief ── */}
      {tab === 'brief' && (
        <div className="maw-panel">
          <div className="maw-panel-body">
            <div className="maw-form-section">
              <h2>Run AI Intake Pipeline</h2>
              <p className="maw-form-hint">
                Describe a project. The agents will plan, staff, assess risk, and coordinate execution.
                Toggle <strong>Save as project</strong> to persist the result, or leave it off to simulate.
              </p>
              <textarea
                className="maw-textarea"
                rows={5}
                placeholder="e.g. Build an AI-powered customer support platform with live chat, ticket routing, sentiment analysis, and SLA dashboards for managers"
                value={briefText}
                onChange={(e) => setBriefText(e.target.value)}
                disabled={briefRunning}
              />
              <div className="maw-form-row">
                <div className="maw-form-field">
                  <label>Budget (₹)</label>
                  <input type="number" placeholder="250000" value={briefBudget} onChange={(e) => setBriefBudget(e.target.value)} disabled={briefRunning} />
                </div>
                <div className="maw-form-field">
                  <label>Priority</label>
                  <select value={briefPriority} onChange={(e) => setBriefPriority(e.target.value)} disabled={briefRunning}>
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                  </select>
                </div>
                <div className="maw-form-field">
                  <label>Deadline</label>
                  <input type="date" value={briefDeadline} onChange={(e) => setBriefDeadline(e.target.value)} disabled={briefRunning} />
                </div>
              </div>
              <div className="maw-persist-toggle">
                <label className={`maw-toggle ${briefPersist ? 'on' : 'off'}`}>
                  <input type="checkbox" checked={briefPersist} onChange={(e) => setBriefPersist(e.target.checked)} disabled={briefRunning} />
                  <span className="maw-toggle-track" />
                  <span className="maw-toggle-label">
                    {briefPersist ? '💾 Save as project' : '🔍 Simulate only'}
                  </span>
                </label>
                <p className="maw-toggle-hint">
                  {briefPersist
                    ? 'Project, tasks, and team recommendations will be created in the system.'
                    : 'Nothing will be saved. Use this to explore what the AI would do.'}
                </p>
              </div>
              <button
                className="btn btn-primary maw-run-btn"
                onClick={runBriefIntake}
                disabled={!briefText.trim() || briefRunning}
              >
                {briefRunning ? (
                  <><span className="maw-spinner" />Agents running…</>
                ) : (
                  briefPersist ? 'Run Agents and Create Project' : 'Simulate — Run Agents'
                )}
              </button>
              {briefRunning && (
                <p className="maw-running-hint">
                  Intake → Planning → Staffing → Risk → Execution → Communication → Escalation. Takes 30–90 seconds.
                </p>
              )}
            </div>
          </div>

          {briefResult && (
            <WorkflowResultView
              workflow={briefResult}
              onApprove={() => approveWorkflow(briefResult)}
              approving={approving}
            />
          )}
        </div>
      )}

      {/* ── Project Loop ── */}
      {tab === 'loop' && (
        <div className="maw-panel">
          <div className="maw-panel-body">
            <div className="maw-form-section">
              <h2>Run Project Execution Loop</h2>
              <p className="maw-form-hint">
                Select an existing project. The agents will assess delivery health, detect overloads,
                suggest rebalancing, and decide whether escalation is needed.
                Toggle <strong>Apply changes</strong> to actually update the project, or leave it off to observe only.
              </p>
              <div className="maw-form-row">
                <div className="maw-form-field" style={{ flex: 2 }}>
                  <label>Project</label>
                  <select value={loopProjectId} onChange={(e) => setLoopProjectId(e.target.value)} disabled={loopRunning}>
                    <option value="">Select a project…</option>
                    {projects.map((p) => (
                      <option key={p.id} value={p.id}>
                        #{p.id} — {p.name} ({p.status})
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="maw-persist-toggle">
                <label className={`maw-toggle ${loopPersist ? 'on' : 'off'}`}>
                  <input type="checkbox" checked={loopPersist} onChange={(e) => setLoopPersist(e.target.checked)} disabled={loopRunning} />
                  <span className="maw-toggle-track" />
                  <span className="maw-toggle-label">
                    {loopPersist ? '💾 Apply changes to project' : '🔍 View only'}
                  </span>
                </label>
                <p className="maw-toggle-hint">
                  {loopPersist
                    ? 'Agent decisions (reassignments, notifications, escalations) will be applied to the project.'
                    : 'Agents analyze the project but make no changes. Safe for observation.'}
                </p>
              </div>
              <button
                className="btn btn-primary maw-run-btn"
                onClick={runProjectLoop}
                disabled={!loopProjectId || loopRunning}
              >
                {loopRunning ? (
                  <><span className="maw-spinner" />Agents running…</>
                ) : (
                  loopPersist ? 'Run Loop and Apply Changes' : 'Run Loop — View Only'
                )}
              </button>
              {loopRunning && (
                <p className="maw-running-hint">
                  Observer → Delivery Review → Rebalance → Communication → Escalation. Takes 20–60 seconds.
                </p>
              )}
            </div>
          </div>

          {loopResult && (
            <WorkflowResultView workflow={loopResult} onApprove={null} approving={false} />
          )}
        </div>
      )}

      {/* ── History ── */}
      {tab === 'history' && (
        <div className="maw-panel maw-history-layout">
          <div className="maw-history-list">
            <div className="maw-history-list-header">
              <h2>Workflow Runs</h2>
              <button className="btn btn-secondary" onClick={fetchWorkflows} style={{ fontSize: 12, padding: '4px 10px' }}>Refresh</button>
            </div>
            {workflows.length === 0 ? (
              <p className="maw-empty">No workflow runs yet.</p>
            ) : (
              workflows.map((w) => {
                const fo = w.final_output || {};
                const isSelected = historyWorkflow?.id === w.id;
                return (
                  <div
                    key={w.id}
                    className={`maw-history-item ${isSelected ? 'selected' : ''}`}
                    onClick={() => fetchWorkflowDetail(w.id)}
                  >
                    <div className="maw-history-item-top">
                      <strong>#{w.id} {w.workflow_type === 'project_intake' ? '📥 Intake' : '🔄 Loop'}</strong>
                      <DecisionBadge decision={fo.escalation?.decision || (w.requires_human_review ? 'human_review_required' : 'continue_autonomously')} />
                    </div>
                    {w.project_id && <div className="maw-history-item-sub">Project #{w.project_id}</div>}
                    <div className="maw-history-item-sub">{(w.agent_runs || []).length} agents · {w.status}</div>
                  </div>
                );
              })
            )}
          </div>

          <div className="maw-history-detail">
            {historyLoading ? (
              <div className="maw-loading"><div className="maw-spinner large" /></div>
            ) : historyWorkflow ? (
              <WorkflowResultView
                workflow={historyWorkflow}
                onApprove={() => approveWorkflow(historyWorkflow)}
                approving={approving}
              />
            ) : (
              <div className="maw-empty-detail">
                <p>Select a workflow run on the left to inspect agent decisions.</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
