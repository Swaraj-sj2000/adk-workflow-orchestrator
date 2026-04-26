import React, { useEffect, useState } from 'react';
import './Projects.css';
import { API_BASE_URL as API } from '../config';

export default function Projects({ role }) {
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState(null);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRoleTitle, setInviteRoleTitle] = useState('');
  const [actionKey, setActionKey] = useState('');

  const token = localStorage.getItem('token');
  const headers = { Authorization: `Bearer ${token}` };

  useEffect(() => {
    fetchProjects();
  }, []);

  const fetchProjects = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/projects/`, { headers });
      if (res.ok) {
        const data = await res.json();
        setProjects(Array.isArray(data) ? data : data.items || []);
      }
    } catch (error) {
      console.error(error);
    }
    setLoading(false);
  };

  const openProject = async (projectId) => {
    try {
      const res = await fetch(`${API}/projects/${projectId}/status`, { headers });
      if (res.ok) {
        setSelectedProject(await res.json());
      }
    } catch (error) {
      console.error(error);
    }
  };

  const updateApproval = async (projectId, approved) => {
    if (actionKey) return;
    setActionKey(`${approved ? 'approve' : 'reject'}-${projectId}`);
    try {
      const res = await fetch(`${API}/projects/${projectId}/team-approval`, {
        method: 'POST',
        headers: {
          ...headers,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          approved,
          note: approved ? 'Approved from project center.' : 'Rejected from project center.',
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not update team approval');
      setSelectedProject(data);
      setMessage(approved ? 'Project team plan approved.' : 'Project sent back for admin review.');
      fetchProjects();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setActionKey('');
    }
  };

  const deleteProject = async (projectId) => {
    const confirmed = window.confirm('Delete this project and roll back assignments, workload, and team state?');
    if (!confirmed) return;
    if (actionKey) return;
    setActionKey(`delete-${projectId}`);

    try {
      const res = await fetch(`${API}/projects/${projectId}`, {
        method: 'DELETE',
        headers,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not delete project');
      setMessage('Project deleted successfully.');
      if (selectedProject?.id === projectId) {
        setSelectedProject(null);
      }
      fetchProjects();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setActionKey('');
    }
  };

  const inviteMember = async () => {
    if (!selectedProject || !inviteEmail.trim()) return;
    if (actionKey) return;
    setActionKey(`invite-${selectedProject.id}`);

    try {
      const res = await fetch(`${API}/invite`, {
        method: 'POST',
        headers: {
          ...headers,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          project_id: selectedProject.id,
          email: inviteEmail.trim().toLowerCase(),
          role_title: inviteRoleTitle.trim() || null,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not create invite');
      setMessage(data.existing_user ? 'Invite created and is now visible in the employee dashboard.' : 'Pending invite created. It will attach automatically when the user registers with that email.');
      setInviteEmail('');
      setInviteRoleTitle('');
      openProject(selectedProject.id);
      fetchProjects();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setActionKey('');
    }
  };

  if (loading) return <div className="loading"><div className="spinner"></div></div>;

  return (
    <div className="projects-container">
      <div className="projects-header">
        <div>
          <p className="eyebrow">{role === 'admin' ? 'Project Center' : role === 'employee' ? 'My Projects' : 'Client Project Status'}</p>
          <h1>{role === 'admin' ? 'Portfolio and detailed status' : role === 'employee' ? 'Assigned project visibility' : 'Business project overview'}</h1>
        </div>
      </div>

      {message && (
        <div className={`project-message ${message.toLowerCase().includes('error') || message.toLowerCase().includes('could not') ? 'error' : 'success'}`}>
          {message}
        </div>
      )}

      <div className="projects-layout">
        <div className="projects-grid">
          {projects.map((project) => {
            const pid = project.project_id || project.id;
            const dl = project.deadline
              ? new Date(project.deadline).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
              : null;
            return (
            <article key={project.id} className="project-card project-card-collapsible">
              <details>
                <summary className="project-card-summary">
                  <div className="project-summary-row">
                    <div className="project-summary-main">
                      <span className="project-summary-name">{project.name}</span>
                      <span className="project-summary-meta">
                        #{pid}
                        {project.client_name ? ` · ${project.client_name}` : project.client_id ? ` · Client #${project.client_id}` : ''}
                        {dl ? ` · Due ${dl}` : ''}
                      </span>
                    </div>
                    <span className={`status-badge status-${(project.status || 'planning').replace(/\s+/g, '-')}`}>
                      {project.status}
                    </span>
                  </div>
                </summary>

                <div className="project-card-body">
                  <p className="project-description">{role === 'client' ? project.public_status_label : project.description}</p>

                  <div className="project-details">
                    {role === 'admin' && <div className="detail-item"><strong>Client ID:</strong> {project.client_id ? `#${project.client_id}` : 'Not linked'}</div>}
                    {role !== 'client' && <div className="detail-item"><strong>Client:</strong> {project.client_name || `Client #${project.client_id || 'NA'}`}</div>}
                    {role === 'admin' && <div className="detail-item"><strong>Client Contact:</strong> {project.client_contact_person || project.client_user_name || 'Not set'}</div>}
                    <div className="detail-item"><strong>Payment:</strong> {project.payment_status}</div>
                    <div className="detail-item"><strong>Approval:</strong> {project.approval_status || 'n/a'}</div>
                    <div className="detail-item"><strong>Phase:</strong> {project.current_phase || 'n/a'}</div>
                  </div>

                  {role === 'admin' && project.approval_status === 'awaiting-team-join' && (
                    <div className="info-pill">
                      <span>Pending Responses</span>
                      <strong>
                        {project.pending_team_invite_count > 0
                          ? (project.pending_team_invite_names || []).join(', ')
                          : 'All drafted members have responded'}
                      </strong>
                    </div>
                  )}

                  <div className="info-pill">
                    <span>Manager Brief</span>
                    <strong>{project.viewer_guidance || 'No stage brief available yet.'}</strong>
                  </div>
                  {project.today_status && (
                    <div className="info-pill">
                      <span>Today's Status</span>
                      <strong>{project.today_status}</strong>
                    </div>
                  )}

                  <div className="progress">
                    <div className="progress-fill" style={{ width: `${project.progress || 0}%` }} />
                  </div>
                  <p className="progress-text">{project.progress || 0}% complete</p>

                  <div className="project-card-actions">
                    <button className="btn btn-secondary" onClick={() => openProject(project.id)} data-tooltip="Open full project status">
                      Open Status
                    </button>
                    {role === 'admin' && project.approval_status === 'awaiting-admin-approval' && (
                      <button className="btn btn-primary" onClick={() => updateApproval(project.id, true)} disabled={Boolean(actionKey)} data-tooltip="Approve the generated team plan">
                        {actionKey === `approve-${project.id}` ? 'Approving...' : 'Approve'}
                      </button>
                    )}
                    {role === 'admin' && (
                      <button className="btn btn-danger" onClick={() => deleteProject(project.id)} disabled={Boolean(actionKey)} data-tooltip="Delete the project with a full rollback">
                        {actionKey === `delete-${project.id}` ? 'Deleting...' : 'Delete'}
                      </button>
                    )}
                  </div>
                </div>
              </details>
            </article>
            );
          })}
        </div>

        <div className="project-detail-card">
          {selectedProject ? (
            <>
              <div className="project-header-card">
                <div>
                  <h2>{selectedProject.name}</h2>
                  <p className="id-line">
                    Project ID: #{selectedProject.project_id || selectedProject.id}
                    {role === 'admin' && selectedProject.client_id ? ` | Client ID: #${selectedProject.client_id}` : ''}
                  </p>
                </div>
                <span className={`status-badge status-${(selectedProject.status || 'planning').replace(/\s+/g, '-')}`}>
                  {selectedProject.status}
                </span>
              </div>

              <p className="project-description">{role === 'client' ? selectedProject.public_status_label : selectedProject.description}</p>

              <div className="project-mini-grid">
                <div className="info-pill">
                  <span>Project ID</span>
                  <strong>#{selectedProject.project_id || selectedProject.id}</strong>
                </div>
                {role === 'admin' && (
                  <div className="info-pill">
                    <span>Client ID</span>
                    <strong>{selectedProject.client_id ? `#${selectedProject.client_id}` : 'Not linked'}</strong>
                  </div>
                )}
                {role === 'admin' && (
                  <div className="info-pill">
                    <span>Client Contact</span>
                    <strong>{selectedProject.client_contact_person || selectedProject.client_user_name || 'Not set'}</strong>
                  </div>
                )}
                <div className="info-pill">
                  <span>Client Status</span>
                  <strong>{selectedProject.client_status}</strong>
                </div>
                <div className="info-pill">
                  <span>Client Responses</span>
                  <strong>{selectedProject.client_response_status}</strong>
                </div>
                <div className="info-pill">
                  <span>Payment</span>
                  <strong>{selectedProject.payment_status}</strong>
                </div>
                <div className="info-pill">
                  <span>Next Decision</span>
                  <strong>{selectedProject.next_decision}</strong>
                </div>
              </div>

              {role === 'admin' && selectedProject.approval_status === 'awaiting-admin-approval' && (
                <>
                  <h3>Draft Team Recommendations</h3>
                  <div className="people-list">
                    {(selectedProject.draft_team || []).map((member) => (
                      <div key={member.employee_id} className="person-chip">
                        <strong>{member.name}</strong>
                        <span>{member.title}</span>
                        <span>{member.workload_percent}% workload</span>
                        <span>{member.shift_status || member.availability_status}</span>
                      </div>
                    ))}
                  </div>
                </>
              )}

              <div className="project-mini-grid">
                <div className="info-pill">
                  <span>Manager Brief</span>
                  <strong>{selectedProject.viewer_guidance || 'No stage brief available yet.'}</strong>
                </div>
                <div className="info-pill">
                  <span>Decision Support</span>
                  <strong>{selectedProject.decision_support || 'No decision memo available yet.'}</strong>
                </div>
                {selectedProject.today_status && (
                  <div className="info-pill">
                    <span>Today's Status</span>
                    <strong>{selectedProject.today_status}</strong>
                  </div>
                )}
                {selectedProject.report_text && (
                  <div className="info-pill">
                    <span>Project Report</span>
                    <strong>{selectedProject.report_text}</strong>
                  </div>
                )}
              </div>

              {role === 'admin' && (
                <>
                  <h3>AI Role Clusters</h3>
                  <div className="people-list">
                    {(selectedProject.role_clusters || []).map((cluster) => (
                      <div key={cluster.role} className="person-chip">
                        <strong>{cluster.role}</strong>
                        <span>{cluster.task_count} workstreams • {cluster.total_hours}h</span>
                        <span>Suggested headcount: {cluster.suggested_headcount}</span>
                      </div>
                    ))}
                  </div>

                  <h3>Team Invite Status</h3>
                  <div className="people-list">
                    {(selectedProject.team_invites || []).map((invite) => (
                      <div key={`${invite.invite_id || invite.email}-${invite.title || invite.email}`} className="person-chip">
                        <strong>{invite.name}</strong>
                        <span>{invite.title || invite.email}</span>
                        <span>{invite.status}</span>
                      </div>
                    ))}
                  </div>

                  <h3>Add Team Member By Email</h3>
                  <div className="project-create-form">
                    <div className="form-group">
                      <label>Email</label>
                      <input
                        type="email"
                        value={inviteEmail}
                        onChange={(event) => setInviteEmail(event.target.value)}
                        placeholder="engineer@company.com"
                      />
                    </div>
                    <div className="form-group">
                      <label>Role</label>
                      <input
                        value={inviteRoleTitle}
                        onChange={(event) => setInviteRoleTitle(event.target.value)}
                        placeholder="Backend Engineer"
                      />
                    </div>
                    <div className="form-actions form-span-2">
                      <button className="btn btn-primary" type="button" onClick={inviteMember} disabled={Boolean(actionKey)} data-tooltip="Create a tenant-scoped team invite by email">
                        {actionKey === `invite-${selectedProject.id}` ? 'Sending...' : 'Send Team Invite'}
                      </button>
                    </div>
                  </div>

                  {(selectedProject.replacement_suggestions || []).length > 0 && (
                    <>
                      <h3>Replacement Suggestions</h3>
                      <div className="people-list">
                        {selectedProject.replacement_suggestions.map((member) => (
                          <div key={member.employee_id} className="person-chip">
                            <strong>{member.name}</strong>
                            <span>{member.title}</span>
                            <span>{member.workload_percent}% workload</span>
                          </div>
                        ))}
                      </div>
                    </>
                  )}

                  <h3>Employees Involved</h3>
                  <div className="people-list">
                    {(selectedProject.emp_involved || []).map((member) => (
                      <div key={member.employee_id} className="person-chip">
                        <strong>{member.name}</strong>
                        <span>{member.title}</span>
                        <span>{member.workload_percent}% workload</span>
                      </div>
                    ))}
                  </div>

                  <h3>Tasks</h3>
                  <div className="list">
                    {(selectedProject.tasks || []).map((task) => (
                      <div key={task.id} className="list-item">
                        <div className="task-line">
                          <strong>{task.description}</strong>
                          <span className={`status-badge status-${(task.status || 'pending').replace(/\s+/g, '-')}`}>
                            {task.status}
                          </span>
                        </div>
                        <p>{task.required_role || 'Unmapped role'} • {task.estimated_time}h estimated</p>
                      </div>
                    ))}
                  </div>
                </>
              )}

              {role === 'employee' && (
                <div className="info-pill">
                  <span>Personal View</span>
                  <strong>Use the My Work page for your task path, checkpoints, and step-by-step execution plan.</strong>
                </div>
              )}

              {role === 'client' && (
                <div className="info-pill">
                  <span>Business Update</span>
                  <strong>{selectedProject.public_status_label || 'The team is moving through the current delivery stage.'}</strong>
                </div>
              )}

              {role === 'admin' && selectedProject.approval_status === 'awaiting-admin-approval' && (
                <div className="project-card-actions">
                  <button className="btn btn-primary" onClick={() => updateApproval(selectedProject.id, true)} disabled={Boolean(actionKey)}>
                    {actionKey === `approve-${selectedProject.id}` ? 'Approving...' : 'Approve Team Plan'}
                  </button>
                  <button className="btn btn-danger" onClick={() => updateApproval(selectedProject.id, false)} disabled={Boolean(actionKey)}>
                    {actionKey === `reject-${selectedProject.id}` ? 'Rejecting...' : 'Reject Team Plan'}
                  </button>
                </div>
              )}
              {actionKey && (
                <div className="action-loading-bar-wrap">
                  <div className="action-loading-label">
                    <div className="action-loading-spinner" />
                    {actionKey.startsWith('approve') ? 'Approving…' : actionKey.startsWith('reject') ? 'Rejecting…' : actionKey.startsWith('delete') ? 'Deleting…' : 'Applying…'}
                  </div>
                  <div className="action-loading-track">
                    <div className="action-loading-fill" />
                  </div>
                </div>
              )}
              {role === 'admin' && (
                <div className="project-card-actions">
                  <button className="btn btn-danger" onClick={() => deleteProject(selectedProject.id)} disabled={Boolean(actionKey)} data-tooltip="Delete the project with a full rollback">
                    {actionKey === `delete-${selectedProject.id}` ? 'Deleting...' : 'Delete Project'}
                  </button>
                </div>
              )}
            </>
          ) : (
            <div className="empty-state">
              <p>Select a project to open its detailed status, task view, and employee involvement.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
