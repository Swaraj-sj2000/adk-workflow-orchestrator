import React, { useEffect, useState } from 'react';
import './Dashboard.css';
import { apiUrl } from '../lib/api';

const initialForm = {
  name: '',
  description: '',
  budget: '',
  priority: 'medium',
  deadline: '',
  payment_status: 'pending',
  client_mode: 'existing',
  client_id: '',
  client_email: '',
  client_company_name: '',
  client_contact_person: '',
  client_phone: '',
  client_address: '',
  client_user_full_name: '',
  client_user_password: '',
};

export default function Dashboard({ role }) {
  const [dashboard, setDashboard] = useState(null);
  const [projectStatus, setProjectStatus] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [formData, setFormData] = useState(initialForm);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [showClientPassword, setShowClientPassword] = useState(false);

  useEffect(() => {
    fetchDashboard();
  }, [role]);

  const token = localStorage.getItem('token');
  const headers = { Authorization: `Bearer ${token}` };

  const fetchDashboard = async () => {
    setLoading(true);
    try {
      if (role === 'admin') {
        const res = await fetch(apiUrl('/system/admin-dashboard'), { headers });
        if (res.ok) {
          const data = await res.json();
          setDashboard(data);
        }
      } else if (role === 'employee') {
        const res = await fetch(apiUrl('/employees/my-work'), { headers });
        if (res.ok) {
          setDashboard(await res.json());
        }
      } else {
        const res = await fetch(apiUrl('/employees/client-workspace'), { headers });
        if (res.ok) {
          setDashboard(await res.json());
        }
      }
    } catch (error) {
      console.error(error);
    }
    setLoading(false);
  };

  const fetchProjectStatus = async (projectId) => {
    try {
      const res = await fetch(apiUrl(`/projects/${projectId}/status`), { headers });
      if (res.ok) {
        setProjectStatus(await res.json());
      }
    } catch (error) {
      console.error(error);
    }
  };

  const handleInputChange = ({ target }) => {
    const { name, value } = target;
    setFormData((current) => ({ ...current, [name]: value }));
  };

  const handleCreateProject = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    setMessage('');

    const payload = {
      ...formData,
      budget: Number(formData.budget || 0),
      client_id: formData.client_id ? Number(formData.client_id) : null,
      deadline: formData.deadline ? new Date(formData.deadline).toISOString() : null,
    };

    try {
      const res = await fetch(apiUrl('/projects/'), {
        method: 'POST',
        headers: {
          ...headers,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Project creation failed');
      }

      setMessage(`Project created for ${data.client_name || 'the selected client'}. Review the AI-generated role draft, then invite the proposed team.`);
      setFormData(initialForm);
      setShowClientPassword(false);
      setShowCreate(false);
      setProjectStatus(data);
      fetchDashboard();
    } catch (error) {
      setMessage(error.message);
    }

    setSubmitting(false);
  };

  const handleApproval = async (projectId, approved) => {
    try {
      const res = await fetch(apiUrl(`/projects/${projectId}/team-approval`), {
        method: 'POST',
        headers: {
          ...headers,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          approved,
          note: approved ? 'Approved from admin dashboard.' : 'Rejected from admin dashboard for rework.',
        }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Could not update approval');
      }
      const data = await res.json();
      setProjectStatus(data);
      setMessage(approved ? 'Team draft approved. The selected employees now need to accept the project invite.' : 'Team draft rejected and admin review meeting created.');
      fetchDashboard();
    } catch (error) {
      setMessage(error.message);
    }
  };

  if (loading) return <div className="loading"><div className="spinner"></div></div>;

  if (role === 'employee') {
    return (
      <div className="dashboard">
        <div className="card full-width">
          <p className="eyebrow">My Dashboard</p>
          <h2>My assigned work and project context</h2>
          <div className="summary-grid">
            <SummaryCard label="My Projects" value={dashboard?.summary?.active_projects || 0} />
            <SummaryCard label="Assigned Tasks" value={dashboard?.summary?.assigned_tasks || 0} />
            <SummaryCard label="My Progress" value={`${dashboard?.summary?.personal_progress_percent || 0}%`} />
            <SummaryCard label="Workload" value={`${dashboard?.employee?.workload_percent || 0}%`} />
            <SummaryCard label="Pending Invites" value={dashboard?.summary?.pending_invites || 0} />
          </div>
        </div>
        <div className="card full-width">
        <h2>My Projects</h2>
          <div className="project-grid">
            {(dashboard?.projects || []).map((project) => (
              <article key={project.project_id} className="project-shell">
                <div className="project-card-top">
                  <div>
                    <h3>{project.name}</h3>
                    <p className="id-line">Project ID: #{project.project_id}</p>
                    <p>{project.public_status_label}</p>
                  </div>
                  <span className={`status-badge status-${(project.status || 'planning').replace(/\s+/g, '-')}`}>
                    {project.status}
                  </span>
                </div>
                <div className="info-pill">
                  <span>Guidance</span>
                  <strong>{project.viewer_guidance || 'No guidance available yet.'}</strong>
                </div>
                <div className="info-pill">
                  <span>Decision Support</span>
                  <strong>{project.decision_support || 'No decision support available yet.'}</strong>
                </div>
                <div className="progress">
                  <div className="progress-fill" style={{ width: `${project.progress || 0}%` }}></div>
                </div>
                <p className="progress-text">{project.progress || 0}% complete</p>
              </article>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (role === 'client') {
    return (
      <div className="dashboard">
        <div className="card full-width">
          <p className="eyebrow">Client Dashboard</p>
          <h2>{dashboard?.client?.company_name || 'Client'} project overview</h2>
          <p>Business-language updates with the right level of visibility.</p>
        </div>
        <div className="card full-width">
          <div className="project-grid">
            {(dashboard?.projects || []).map((project) => (
              <article key={project.project_id} className="project-shell">
                <div className="project-card-top">
                  <div>
                    <h3>{project.name}</h3>
                    <p className="id-line">Project ID: #{project.project_id}</p>
                    <p>{project.business_summary}</p>
                  </div>
                  <span className={`status-badge status-${(project.status || 'planning').replace(/\s+/g, '-')}`}>
                    {project.status}
                  </span>
                </div>
                <div className="project-mini-grid">
                  <InfoPill label="Progress" value={`${project.progress || 0}%`} />
                  <InfoPill label="Status" value={project.client_status || 'active'} />
                  <InfoPill label="Payment" value={project.payment_status} />
                </div>
                <div className="info-pill">
                  <span>Update</span>
                  <strong>{project.viewer_guidance || 'The team will share the next update soon.'}</strong>
                </div>
              </article>
            ))}
          </div>
        </div>
      </div>
    );
  }

  const summary = dashboard?.summary || {};
  const clients = dashboard?.clients || [];
  const activeProjects = dashboard?.active_projects || [];
  const completedProjects = dashboard?.completed_projects || [];

  return (
    <div className="dashboard dashboard-admin">
      {message && (
        <div className={`alert full-width ${message.toLowerCase().includes('failed') || message.toLowerCase().includes('error') ? 'alert-danger' : 'alert-info'}`}>
          {message}
        </div>
      )}

      <div className="card full-width admin-hero">
        <div>
          <p className="eyebrow">Admin Operations Dashboard</p>
          <h2>Handle multiple client projects from one place</h2>
          <p>
            Track project status, client response health, payment state, employee involvement, and the current decision waiting on the team.
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowCreate((current) => !current)}>
          {showCreate ? 'Close New Project Form' : 'New Project'}
        </button>
      </div>

      <div className="summary-grid full-width">
        <SummaryCard label="Active Projects" value={summary.active_projects || 0} />
        <SummaryCard label="Completed Projects" value={summary.completed_projects || 0} />
        <SummaryCard label="Clients" value={summary.clients || 0} />
        <SummaryCard label="Team Available Now" value={summary.employees_available_now || 0} />
        <SummaryCard label="Average Workload" value={`${summary.average_team_workload || 0}%`} />
        <SummaryCard label="Waiting Approval" value={summary.projects_waiting_approval || 0} />
      </div>

      {showCreate && (
        <div className="card full-width create-project-card">
          <h2>Create New Project</h2>
          <form className="project-create-form" onSubmit={handleCreateProject}>
            <div className="form-group form-span-2">
              <label>Project Title</label>
              <input name="name" value={formData.name} onChange={handleInputChange} placeholder="AI onboarding assistant for support operations" required />
            </div>

            <div className="form-group form-span-2">
              <label>Clean English Description</label>
              <textarea
                name="description"
                value={formData.description}
                onChange={handleInputChange}
                rows="4"
                placeholder="Describe the business problem, expected outcome, and any non-negotiable requirements."
                required
              />
            </div>

            <div className="form-group">
              <label>Client Mode</label>
              <select name="client_mode" value={formData.client_mode} onChange={handleInputChange}>
                <option value="existing">Existing Client</option>
                <option value="new">New Client Registration</option>
              </select>
            </div>

            <div className="form-group">
              <label>Priority</label>
              <select name="priority" value={formData.priority} onChange={handleInputChange}>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </div>

            <div className="form-group">
              <label>Budget</label>
              <input type="number" name="budget" value={formData.budget} onChange={handleInputChange} placeholder="50000" />
            </div>

            <div className="form-group">
              <label>Deadline</label>
              <input type="date" name="deadline" value={formData.deadline} onChange={handleInputChange} />
            </div>

            <div className="form-group">
              <label>Payment Status</label>
              <select name="payment_status" value={formData.payment_status} onChange={handleInputChange}>
                <option value="pending">Pending</option>
                <option value="partial">Partial</option>
                <option value="completed">Completed</option>
              </select>
            </div>

            {formData.client_mode === 'existing' ? (
              <div className="form-group form-span-2">
                <label>Registered Client</label>
                <select name="client_id" value={formData.client_id} onChange={handleInputChange} required>
                  <option value="">Select client</option>
                  {clients.map((client) => (
                    <option key={client.id} value={client.id}>
                      {client.company_name} ({client.email})
                    </option>
                  ))}
                </select>
              </div>
            ) : (
              <>
                <div className="form-group">
                  <label>Client Email</label>
                  <input name="client_email" value={formData.client_email} onChange={handleInputChange} required={formData.client_mode === 'new'} />
                </div>
                <div className="form-group">
                  <label>Client Password</label>
                  <div className="password-field">
                    <input
                      type={showClientPassword ? 'text' : 'password'}
                      name="client_user_password"
                      value={formData.client_user_password}
                      onChange={handleInputChange}
                      required={formData.client_mode === 'new'}
                    />
                    <button
                      type="button"
                      className="password-toggle"
                      onClick={() => setShowClientPassword((current) => !current)}
                    >
                      {showClientPassword ? 'Hide' : 'Peek'}
                    </button>
                  </div>
                </div>
                <div className="form-group">
                  <label>Company Name</label>
                  <input name="client_company_name" value={formData.client_company_name} onChange={handleInputChange} required={formData.client_mode === 'new'} />
                </div>
                <div className="form-group">
                  <label>Contact Person</label>
                  <input name="client_contact_person" value={formData.client_contact_person} onChange={handleInputChange} />
                </div>
                <div className="form-group">
                  <label>Client Full Name</label>
                  <input name="client_user_full_name" value={formData.client_user_full_name} onChange={handleInputChange} />
                </div>
                <div className="form-group">
                  <label>Phone</label>
                  <input name="client_phone" value={formData.client_phone} onChange={handleInputChange} />
                </div>
                <div className="form-group form-span-2">
                  <label>Address</label>
                  <input name="client_address" value={formData.client_address} onChange={handleInputChange} />
                </div>
              </>
            )}

            <div className="form-actions form-span-2">
              <button className="btn btn-primary" type="submit" disabled={submitting}>
                {submitting ? 'Creating Project...' : 'Create Project and Start Agentic Intake'}
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="card full-width">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Current Projects</p>
            <h2>Open a live status view for any project</h2>
          </div>
        </div>
        <div className="project-grid">
          {activeProjects.map((project) => (
            <article key={project.id} className="project-shell">
              <div className="project-card-top">
                <div>
                  <h3>{project.name}</h3>
                  <p className="id-line">
                    Project ID: #{project.project_id || project.id}
                    {role === 'admin' && project.client_id ? ` | Client ID: #${project.client_id}` : ''}
                  </p>
                  <p>{project.description}</p>
                </div>
                <span className={`status-badge status-${(project.status || 'planning').replace(/\s+/g, '-')}`}>
                  {project.status}
                </span>
              </div>

              <div className="project-mini-grid">
                <InfoPill label="Project ID" value={`#${project.project_id || project.id}`} />
                {role === 'admin' && <InfoPill label="Client ID" value={project.client_id ? `#${project.client_id}` : 'Not linked'} />}
                <InfoPill label="Client" value={project.client_name || `Client #${project.client_id || 'NA'}`} />
                <InfoPill label="Payment" value={project.payment_status} />
                <InfoPill label="Client Reply" value={project.client_response_status || 'pending'} />
                <InfoPill label="Approval" value={project.approval_status || 'pending'} />
              </div>

              {project.approval_status === 'awaiting-team-join' && (
                <div className="info-pill">
                  <span>Waiting On</span>
                  <strong>
                    {project.pending_team_invite_count > 0
                      ? `${project.pending_team_invite_count} pending: ${(project.pending_team_invite_names || []).join(', ')}`
                      : 'All drafted members have responded.'}
                  </strong>
                </div>
              )}

              <div className="info-pill">
                <span>Manager Brief</span>
                <strong>{project.viewer_guidance || 'No stage brief available yet.'}</strong>
              </div>

              <div className="progress">
                <div className="progress-fill" style={{ width: `${project.progress || 0}%` }}></div>
              </div>
              <p className="progress-text">{project.progress || 0}% complete</p>

              <div className="project-card-actions">
                <button className="btn btn-secondary" onClick={() => fetchProjectStatus(project.id)}>
                  Open Project Status
                </button>
                {project.approval_status === 'awaiting-admin-approval' && (
                  <button className="btn btn-primary" onClick={() => handleApproval(project.id, true)}>
                    Approve Team Plan
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
      </div>

      {projectStatus && (
        <div className="card full-width project-status-panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Project Status</p>
              <h2>{projectStatus.name}</h2>
              <p className="id-line">
                Project ID: #{projectStatus.project_id || projectStatus.id}
                {role === 'admin' && projectStatus.client_id ? ` | Client ID: #${projectStatus.client_id}` : ''}
              </p>
            </div>
            <div className="project-card-actions">
              {projectStatus.approval_status === 'awaiting-admin-approval' && (
                <>
                  <button className="btn btn-primary" onClick={() => handleApproval(projectStatus.id, true)}>
                    Approve
                  </button>
                  <button className="btn btn-danger" onClick={() => handleApproval(projectStatus.id, false)}>
                    Reject
                  </button>
                </>
              )}
            </div>
          </div>

          <div className="project-status-grid">
            <DetailCard title="Project ID" value={`#${projectStatus.project_id || projectStatus.id}`} />
            {role === 'admin' && <DetailCard title="Client ID" value={projectStatus.client_id ? `#${projectStatus.client_id}` : 'Not linked'} />}
            <DetailCard title="Client Status" value={projectStatus.client_status} />
            <DetailCard title="Client Responses" value={projectStatus.client_response_status} />
            <DetailCard title="Payment Status" value={projectStatus.payment_status} />
            <DetailCard title="Current Decision" value={projectStatus.next_decision} />
          </div>

          {projectStatus.approval_status === 'awaiting-team-join' && (
            <div className="info-pill">
              <span>Pending Team Responses</span>
              <strong>
                {(projectStatus.team_invites || []).filter((invite) => invite.status === 'pending').length > 0
                  ? (projectStatus.team_invites || [])
                      .filter((invite) => invite.status === 'pending')
                      .map((invite) => `${invite.name} (${invite.title})`)
                      .join(', ')
                  : 'No pending responses'}
              </strong>
            </div>
          )}

          <div className="project-mini-grid">
            <div className="info-pill">
              <span>Manager Brief</span>
              <strong>{projectStatus.viewer_guidance || 'No stage brief available yet.'}</strong>
            </div>
            <div className="info-pill">
              <span>Decision Support</span>
              <strong>{projectStatus.decision_support || 'No decision memo available yet.'}</strong>
            </div>
          </div>

          <div className="task-summary-bar">
            <span>Total Tasks: {projectStatus.task_summary?.total || 0}</span>
            <span>Completed: {projectStatus.task_summary?.completed || 0}</span>
            <span>In Progress: {projectStatus.task_summary?.in_progress || 0}</span>
            <span>Blocked: {projectStatus.task_summary?.blocked || 0}</span>
          </div>

          <div className="two-column-layout">
            <div>
              <h3>AI Role Clusters</h3>
              <div className="people-list">
                {(projectStatus.role_clusters || []).map((cluster) => (
                  <div key={cluster.role} className="person-chip">
                    <strong>{cluster.role}</strong>
                    <span>{cluster.task_count} workstreams</span>
                    <span>{cluster.total_hours}h planned</span>
                    <span>Headcount {cluster.suggested_headcount}</span>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <h3>Team Join Status</h3>
              <div className="people-list">
                {(projectStatus.team_invites || []).map((invite) => (
                  <div key={`${invite.employee_id}-${invite.title}`} className="person-chip">
                    <strong>{invite.name}</strong>
                    <span>{invite.title}</span>
                    <span>{invite.status}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="two-column-layout">
            <div>
              <h3>Employees Involved</h3>
              <div className="people-list">
                {(projectStatus.emp_involved || []).map((member) => (
                  <div key={member.employee_id} className="person-chip">
                    <strong>{member.name}</strong>
                    <span>{member.title}</span>
                    <span>{member.workload_percent}% workload</span>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <h3>Task Status</h3>
              <div className="list">
                {(projectStatus.tasks || []).map((task) => (
                  <div key={task.id} className="list-item">
                    <div className="task-line">
                      <strong>{task.description}</strong>
                      <span className={`status-badge status-${(task.status || 'pending').replace(/\s+/g, '-')}`}>
                        {task.status}
                      </span>
                    </div>
                    <p>Role: {task.required_role || 'Unmapped'} | Difficulty: {task.difficulty} | Urgency: {task.urgency} | Estimated: {task.estimated_time}h</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="card full-width">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Completed Projects</p>
            <h2>Brief delivery history and TXT reports</h2>
          </div>
        </div>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Project ID</th>
                <th>Project</th>
                <th>Client ID</th>
                <th>Client</th>
                <th>Payment</th>
                <th>Report</th>
              </tr>
            </thead>
            <tbody>
              {completedProjects.map((project) => (
                <tr key={project.project_id}>
                  <td>#{project.project_id}</td>
                  <td>{project.project_name}</td>
                  <td>#{project.client_id}</td>
                  <td>{project.client_name}</td>
                  <td>{project.payment_status}</td>
                  <td className="report-preview">{project.report_text || 'TXT report pending'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function SummaryCard({ label, value }) {
  return (
    <div className="summary-card">
      <p>{label}</p>
      <div className="metric">{value}</div>
    </div>
  );
}

function DetailCard({ title, value }) {
  return (
    <div className="health-item">
      <h4>{title}</h4>
      <div className="detail-card-value">{value || 'Not available'}</div>
    </div>
  );
}

function InfoPill({ label, value }) {
  return (
    <div className="info-pill">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
