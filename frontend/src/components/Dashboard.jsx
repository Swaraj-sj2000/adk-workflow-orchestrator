import React, { useEffect, useState } from 'react';
import './Dashboard.css';
import { API_BASE_URL as API } from '../config';

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

const initialPaymentForm = {
  payment_status: 'pending',
  note: '',
};

export default function Dashboard({ role }) {
  const [dashboard, setDashboard] = useState(null);
  const [projectStatus, setProjectStatus] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [formData, setFormData] = useState(initialForm);
  const [paymentForm, setPaymentForm] = useState(initialPaymentForm);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [showClientPassword, setShowClientPassword] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(true);

  useEffect(() => {
    fetchDashboard();
  }, [role]);

  const token = localStorage.getItem('token');
  const headers = { Authorization: `Bearer ${token}` };

  const fetchDashboard = async () => {
    setLoading(true);
    try {
      if (role === 'admin') {
        const res = await fetch(`${API}/system/admin-dashboard`, { headers });
        if (res.ok) setDashboard(await res.json());
      } else if (role === 'employee') {
        const res = await fetch(`${API}/employees/my-work`, { headers });
        if (res.ok) setDashboard(await res.json());
      } else {
        const res = await fetch(`${API}/employees/client-workspace`, { headers });
        if (res.ok) setDashboard(await res.json());
      }
    } catch (error) {
      console.error(error);
      setMessage('Could not load dashboard data.');
    }
    setLoading(false);
  };

  const fetchProjectStatus = async (projectId) => {
    try {
      const res = await fetch(`${API}/projects/${projectId}/status`, { headers });
      if (res.ok) {
        const data = await res.json();
        setProjectStatus(data);
        setPaymentForm({
          payment_status: data.payment_status || 'pending',
          note: '',
        });
      }
    } catch (error) {
      console.error(error);
      setMessage('Could not load project status.');
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
      const res = await fetch(`${API}/projects/`, {
        method: 'POST',
        headers: {
          ...headers,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Project creation failed');

      setMessage(`Project created for ${data.client_name || 'the selected client'}. Review the AI-generated draft, then invite the team.`);
      setFormData(initialForm);
      setShowClientPassword(false);
      setShowCreate(false);
      setProjectStatus(data);
      setPaymentForm({ payment_status: data.payment_status || 'pending', note: '' });
      fetchDashboard();
    } catch (error) {
      setMessage(error.message);
    }

    setSubmitting(false);
  };

  const handleApproval = async (projectId, approved) => {
    try {
      const res = await fetch(`${API}/projects/${projectId}/team-approval`, {
        method: 'POST',
        headers: {
          ...headers,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          approved,
          note: approved ? 'Approved from dashboard.' : 'Rejected from dashboard for rework.',
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not update approval');
      setProjectStatus(data);
      setMessage(approved ? 'Team draft approved.' : 'Team draft rejected and returned for review.');
      fetchDashboard();
    } catch (error) {
      setMessage(error.message);
    }
  };

  const handleDeleteProject = async (projectId) => {
    const confirmed = window.confirm('Delete this project and roll back assignments, workload, and team state?');
    if (!confirmed) return;

    try {
      const res = await fetch(`${API}/projects/${projectId}`, {
        method: 'DELETE',
        headers,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not delete project');
      setMessage('Project deleted successfully.');
      if (projectStatus?.id === projectId) setProjectStatus(null);
      fetchDashboard();
    } catch (error) {
      setMessage(error.message);
    }
  };

  const handlePaymentUpdate = async (projectId) => {
    try {
      const res = await fetch(`${API}/projects/${projectId}/payment-status`, {
        method: 'PATCH',
        headers: {
          ...headers,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(paymentForm),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not update payment status');
      setProjectStatus(data);
      setPaymentForm((current) => ({ ...current, note: '' }));
      setMessage('Payment status updated.');
      fetchDashboard();
    } catch (error) {
      setMessage(error.message);
    }
  };

  if (loading) return <div className="loading"><div className="spinner"></div></div>;

  const notifications = dashboard?.notifications || [];

  if (role === 'employee') {
    const employee = dashboard?.employee || {};
    return (
      <div className="dashboard">
        {message && <Alert message={message} />}
        <div className="card full-width">
          <IdentityBanner
            eyebrow="Employee Workspace"
            title={employee.name}
            subtitle={`${employee.title || 'Team Member'} | Employee ID #${employee.employee_id || 'NA'}`}
            roleBadge={employee.role || 'employee'}
            meta={[
              `Status: ${employee.shift_status || 'On Duty'}`,
              `Duty: ${employee.duty_window || 'Not set'}`,
              `Tasks: ${dashboard?.summary?.assigned_tasks || 0}`,
            ]}
            level={{
              label: employee.experience_grade || 'Starter',
              currentLevel: employee.current_level || 1,
              points: employee.current_level_points || 0,
              next: employee.next_level_points || 100,
            }}
          />
        </div>

        <div className="card full-width">
          <NotificationsPanel
            title="Notifications"
            open={notificationsOpen}
            onToggle={() => setNotificationsOpen((current) => !current)}
            notifications={notifications}
            emptyText="No recent experience or invite notifications."
          />
        </div>

        <div className="card full-width">
          <h2>My Dashboard</h2>
          <div className="summary-grid">
            <SummaryCard label="My Projects" value={dashboard?.summary?.active_projects || 0} />
            <SummaryCard label="Assigned Tasks" value={dashboard?.summary?.assigned_tasks || 0} />
            <SummaryCard label="My Progress" value={`${dashboard?.summary?.personal_progress_percent || 0}%`} />
            <SummaryCard label="Workload" value={`${employee.workload_percent || 0}%`} />
            <SummaryCard label="Pending Invites" value={dashboard?.summary?.pending_invites || 0} />
            <SummaryCard label="XP Total" value={Math.round(employee.experience_points || 0)} />
          </div>
        </div>

        <ProjectSection
          title="Active Projects"
          eyebrow="Current Work"
          projects={dashboard?.projects || []}
          emptyText="No active projects yet."
          renderExtra={(project) => (
            <>
              <div className="info-pill">
                <span>Guidance</span>
                <strong>{project.viewer_guidance || 'No guidance available yet.'}</strong>
              </div>
              <div className="info-pill">
                <span>Decision Support</span>
                <strong>{project.decision_support || 'No decision support available yet.'}</strong>
              </div>
              {project.report_text && (
                <div className="info-pill">
                  <span>Latest Report</span>
                  <strong>{project.report_text}</strong>
                </div>
              )}
            </>
          )}
        />

        <ProjectSection
          title="Completed Project History"
          eyebrow="History"
          projects={dashboard?.history || []}
          emptyText="Completed project history will appear here."
          renderExtra={(project) => (
            <div className="info-pill">
              <span>Final Report</span>
              <strong>{project.report_text || 'Final report will appear here after project completion.'}</strong>
            </div>
          )}
        />
      </div>
    );
  }

  if (role === 'client') {
    const client = dashboard?.client || {};
    return (
      <div className="dashboard">
        {message && <Alert message={message} />}
        <div className="card full-width">
          <IdentityBanner
            eyebrow="Client Workspace"
            title={client.company_name || 'Client'}
            subtitle={`${client.full_name || client.contact_person || 'Primary contact'} | Client ID #${client.client_id || 'NA'}`}
            roleBadge={client.role || 'client'}
            meta={[
              `Email: ${client.email || 'Not available'}`,
              `Contact: ${client.contact_person || client.full_name || 'Not set'}`,
            ]}
          />
        </div>

        <div className="card full-width">
          <NotificationsPanel
            title="Notifications"
            open={notificationsOpen}
            onToggle={() => setNotificationsOpen((current) => !current)}
            notifications={notifications}
            emptyText="No recent project notifications."
          />
        </div>

        <ProjectSection
          title="Active Projects"
          eyebrow="Business View"
          projects={dashboard?.projects || []}
          emptyText="No active projects yet."
          renderExtra={(project) => (
            <>
              <div className="project-mini-grid">
                <InfoPill label="Delivery Status" value={project.delivery_status} />
                <InfoPill label="Overall Status" value={project.overall_status} />
                <InfoPill label="Payment" value={project.payment_status} />
                <InfoPill label="Today's Status" value={project.today_status} />
              </div>
              <div className="info-pill">
                <span>Business Plan</span>
                <strong>{project.plan_brief}</strong>
              </div>
              <div className="info-pill">
                <span>USP</span>
                <strong>{project.usp}</strong>
              </div>
              <div className="info-pill">
                <span>Feature Highlights</span>
                <strong>{(project.feature_highlights || []).join(', ') || 'Feature list is being refined.'}</strong>
              </div>
              <div className="info-pill">
                <span>Latest Status</span>
                <strong>{project.viewer_guidance || project.business_summary}</strong>
              </div>
              <PaymentEditor
                project={project}
                paymentForm={paymentForm}
                setPaymentForm={setPaymentForm}
                onSave={() => handlePaymentUpdate(project.project_id)}
              />
            </>
          )}
        />

        <ProjectSection
          title="Completed Project History"
          eyebrow="Delivered Work"
          projects={dashboard?.history || []}
          emptyText="Delivered project history will appear here."
          renderExtra={(project) => (
            <>
              <div className="info-pill">
                <span>Final Report</span>
                <strong>{project.final_report?.full_text || project.final_report?.executive_summary || 'Final report pending.'}</strong>
              </div>
              <div className="info-pill">
                <span>Payment Timeline</span>
                <strong>
                  {(project.payment_updates || []).length > 0
                    ? project.payment_updates.map((item) => `${item.status} by ${item.updated_by}`).join(' | ')
                    : 'No payment updates yet.'}
                </strong>
              </div>
            </>
          )}
        />
      </div>
    );
  }

  const summary = dashboard?.summary || {};
  const clients = dashboard?.clients || [];
  const activeProjects = dashboard?.active_projects || [];
  const completedProjects = dashboard?.completed_projects || [];
  const admin = dashboard?.admin || {};

  return (
    <div className="dashboard dashboard-admin">
      {message && <Alert message={message} />}

      <div className="card full-width">
        <IdentityBanner
          eyebrow="Admin Operations"
          title={admin.full_name || 'Admin'}
          subtitle={`${admin.email || 'No email'} | Admin ID #${admin.user_id || 'NA'}`}
          roleBadge={admin.role || 'admin'}
          meta={[
            `Tenant: ${admin.tenant_id || 'default'}`,
            `Active Projects: ${summary.active_projects || 0}`,
            `Clients: ${summary.clients || 0}`,
          ]}
        />
      </div>

      <div className="card full-width">
        <NotificationsPanel
          title="Notifications"
          open={notificationsOpen}
          onToggle={() => setNotificationsOpen((current) => !current)}
          notifications={notifications}
          emptyText="No recent project or payment notifications."
        />
      </div>

      <div className="card full-width admin-hero">
        <div>
          <p className="eyebrow">Admin Operations Dashboard</p>
          <h2>Handle multiple client projects from one place</h2>
          <p>Track planning, delivery, team involvement, payment state, final reporting, and archived history from one tenant-aware view.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowCreate((current) => !current)}>
          {showCreate ? 'Close New Project Form' : 'New Project'}
        </button>
      </div>

      <div className="summary-grid full-width">
        <SummaryCard label="Active Projects" value={summary.active_projects || 0} tooltip="Projects currently in planning or execution" />
        <SummaryCard label="Completed Projects" value={summary.completed_projects || 0} tooltip="Projects fully delivered and archived to history" />
        <SummaryCard label="Clients" value={summary.clients || 0} tooltip="Clients in the current tenant" />
        <SummaryCard label="Team Available" value={summary.employees_available_now || 0} tooltip="Members with capacity for new work" />
        <SummaryCard label="Average Workload" value={`${summary.average_team_workload || 0}%`} tooltip="Average current team utilization" />
        <SummaryCard label="Waiting Approval" value={summary.projects_waiting_approval || 0} tooltip="Projects waiting on admin action" />
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
              <label>Initial Payment Status</label>
              <select name="payment_status" value={formData.payment_status} onChange={handleInputChange}>
                <option value="pending">Pending</option>
                <option value="partial">Partial</option>
                <option value="client-confirmed">Client Confirmed</option>
                <option value="admin-confirmed">Admin Confirmed</option>
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
                    <button type="button" className="password-toggle" onClick={() => setShowClientPassword((current) => !current)}>
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

      <ProjectSection
        title="Current Projects"
        eyebrow="Open Work"
        projects={activeProjects}
        emptyText="No active projects yet."
        onOpen={fetchProjectStatus}
        actions={(project) => (
          <div className="project-card-actions">
            <button className="btn btn-secondary" onClick={() => fetchProjectStatus(project.id)}>Open Project Status</button>
            {project.approval_status === 'awaiting-admin-approval' && (
              <button className="btn btn-primary" onClick={() => handleApproval(project.id, true)}>Approve Team Plan</button>
            )}
            <button className="btn btn-danger" onClick={() => handleDeleteProject(project.id)}>Delete</button>
          </div>
        )}
        renderExtra={(project) => (
          <>
            <div className="project-mini-grid">
              <InfoPill label="Client ID" value={project.client_id ? `#${project.client_id}` : 'Not linked'} />
              <InfoPill label="Client Company" value={project.client_name || 'Not linked'} />
              <InfoPill label="Client Contact" value={project.client_contact_person || project.client_user_name || 'Not set'} />
              <InfoPill label="Payment" value={project.payment_status} />
              <InfoPill label="Today's Status" value={project.today_status || 'No update yet'} />
              <InfoPill label="Approval" value={project.approval_status || 'pending'} />
            </div>
            <div className="info-pill">
              <span>Manager Brief</span>
              <strong>{project.viewer_guidance || 'No stage brief available yet.'}</strong>
            </div>
            <div className="info-pill">
              <span>Feature Highlights</span>
              <strong>{(project.feature_highlights || []).join(', ') || 'Feature outline is being prepared.'}</strong>
            </div>
          </>
        )}
      />

      {projectStatus && (
        <div className="card full-width project-status-panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Project Status</p>
              <h2>{projectStatus.name}</h2>
              <p className="id-line">
                Project ID: #{projectStatus.project_id || projectStatus.id} | Client ID: {projectStatus.client_id ? `#${projectStatus.client_id}` : 'Not linked'} | Client: {projectStatus.client_name || 'Not linked'}
              </p>
            </div>
            <div className="project-card-actions">
              {projectStatus.approval_status === 'awaiting-admin-approval' && (
                <>
                  <button className="btn btn-primary" onClick={() => handleApproval(projectStatus.id, true)}>Approve</button>
                  <button className="btn btn-danger" onClick={() => handleApproval(projectStatus.id, false)}>Reject</button>
                </>
              )}
              <button className="btn btn-danger" onClick={() => handleDeleteProject(projectStatus.id)}>Delete</button>
            </div>
          </div>

          <div className="project-status-grid">
            <DetailCard title="Client Company" value={projectStatus.client_name} />
            <DetailCard title="Client Contact" value={projectStatus.client_contact_person || projectStatus.client_user_name} />
            <DetailCard title="Client Email" value={projectStatus.client_email} />
            <DetailCard title="Client Status" value={projectStatus.client_status} />
            <DetailCard title="Payment Status" value={projectStatus.payment_status} />
            <DetailCard title="Today's Status" value={projectStatus.today_status} />
          </div>

          <div className="project-mini-grid">
            <div className="info-pill">
              <span>Business Plan</span>
              <strong>{projectStatus.client_plan_brief}</strong>
            </div>
            <div className="info-pill">
              <span>USP</span>
              <strong>{projectStatus.usp}</strong>
            </div>
          </div>

          <div className="project-mini-grid">
            <InfoPill label="Delivery Status" value={projectStatus.delivery_status} />
            <InfoPill label="Overall Status" value={projectStatus.overall_status} />
            <InfoPill label="Decision Support" value={projectStatus.decision_support || 'No decision memo available yet.'} />
            <InfoPill label="Manager Brief" value={projectStatus.viewer_guidance || 'No stage brief available yet.'} />
          </div>

          <PaymentEditor
            project={projectStatus}
            paymentForm={paymentForm}
            setPaymentForm={setPaymentForm}
            onSave={() => handlePaymentUpdate(projectStatus.id)}
          />

          <div className="task-summary-bar">
            <span>Total Tasks: {projectStatus.task_summary?.total || 0}</span>
            <span>Completed: {projectStatus.task_summary?.completed || 0}</span>
            <span>In Progress: {projectStatus.task_summary?.in_progress || 0}</span>
            <span>Blocked: {projectStatus.task_summary?.blocked || 0}</span>
            <span>Project Progress: {projectStatus.progress || 0}%</span>
          </div>

          <div className="two-column-layout">
            <div>
              <h3>Team Join Status</h3>
              <div className="people-list">
                {(projectStatus.team_invites || []).map((invite) => (
                  <div key={`${invite.invite_id || invite.email}-${invite.title || invite.email}`} className="person-chip">
                    <strong>{invite.name}</strong>
                    <span>{invite.title}</span>
                    <span>{invite.status}</span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <h3>{projectStatus.approval_status === 'awaiting-admin-approval' ? 'Drafted Team (Pending Approval)' : 'Team Members'}</h3>
              {projectStatus.approval_status === 'awaiting-admin-approval' ? (
                <div className="team-grid">
                  {(projectStatus.team_invites || []).filter(invite => invite.employee_id).map((invite) => (
                    <div key={invite.employee_id || invite.email} className="team-member-card">
                      <div className="team-member-header">
                        <div className="team-member-avatar">
                          {invite.name?.charAt(0) || 'E'}
                        </div>
                        <div>
                          <strong>{invite.name || invite.email}</strong>
                          <p className="team-member-title">{invite.title || 'Team Member'}</p>
                          <p className="team-member-id">ID: #{invite.employee_id}</p>
                        </div>
                      </div>
                      
                      {invite.role_skills && invite.role_skills.length > 0 && (
                        <div className="team-member-skills">
                          {invite.role_skills.slice(0, 3).map((skill) => (
                            <span key={skill} className="skill-tag">
                              {skill}
                            </span>
                          ))}
                          {invite.role_skills.length > 3 && (
                            <span className="skill-tag">+{invite.role_skills.length - 3} more</span>
                          )}
                        </div>
                      )}
                      
                      <div className="team-member-status">
                        <span className={`status-badge status-${invite.status === 'accepted' ? 'approved' : 'pending'}`}>
                          {invite.status || 'Drafted'}
                        </span>
                        {invite.role_focus && invite.role_focus.length > 0 && (
                          <span className="duty-time" title={invite.role_focus.join(', ')}>
                            {invite.role_focus.length} task{invite.role_focus.length > 1 ? 's' : ''}
                          </span>
                        )}
                      </div>
                      
                      {invite.capacity_reasoning && (
                        <p style={{ fontSize: '12px', color: '#6b7280', marginTop: '8px', lineHeight: '1.4' }}>
                          {invite.capacity_reasoning}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="team-grid">
                  {(projectStatus.emp_involved || []).map((member) => (
                    <div key={member.employee_id} className="team-member-card">
                      <div className="team-member-header">
                        <div className="team-member-avatar">
                          {member.name?.charAt(0) || 'E'}
                        </div>
                        <div>
                          <strong>{member.name}</strong>
                          <p className="team-member-title">{member.title || 'Team Member'}</p>
                          <p className="team-member-id">ID: #{member.employee_id}</p>
                        </div>
                      </div>
                      
                      <div className="team-member-workload">
                        <div className="workload-bar-container">
                          <div 
                            className={`workload-bar workload-${
                              member.workload_percent > 80 ? 'high' : 
                              member.workload_percent > 50 ? 'medium' : 'low'
                            }`}
                            style={{ width: `${member.workload_percent}%` }}
                          ></div>
                        </div>
                        <span className="workload-label">{member.workload_percent}% capacity</span>
                      </div>
                      
                      {member.skills && Object.keys(member.skills).length > 0 && (
                        <div className="team-member-skills">
                          {Object.entries(member.skills).slice(0, 3).map(([skill, level]) => (
                            <span key={skill} className="skill-tag">
                              {skill} {(level * 100).toFixed(0)}%
                            </span>
                          ))}
                          {Object.keys(member.skills).length > 3 && (
                            <span className="skill-tag">+{Object.keys(member.skills).length - 3} more</span>
                          )}
                        </div>
                      )}
                      
                      <div className="team-member-status">
                        <span className={`status-badge status-${member.shift_status === 'available' ? 'approved' : 'pending'}`}>
                          {member.shift_status || 'On Duty'}
                        </span>
                        <span className="duty-time">{member.duty_window || '9:00 - 18:00'}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <ReportPanel report={projectStatus.final_report} fallbackText={projectStatus.report_text} />
        </div>
      )}

      <div className="card full-width">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Completed Projects</p>
            <h2>Archived delivery history and final reports</h2>
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
                  <td className="report-preview">{project.final_report?.full_text || project.report_text || 'Final report pending'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function Alert({ message }) {
  const isError = `${message}`.toLowerCase().includes('error') || `${message}`.toLowerCase().includes('could not');
  return (
    <div className={`alert full-width ${isError ? 'alert-danger' : 'alert-info'}`}>
      {message}
    </div>
  );
}

function IdentityBanner({ eyebrow, title, subtitle, roleBadge, meta = [], level }) {
  return (
    <div className="identity-banner">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h2>{title || 'Workspace'}</h2>
        <p className="id-line">{subtitle}</p>
        <div className="identity-meta">
          {meta.map((item) => (
            <span key={item} className="status-badge status-approved">{item}</span>
          ))}
          {roleBadge && <span className="status-badge status-pending">{roleBadge}</span>}
        </div>
      </div>
      {level ? (
        <div className="level-card">
          <p>Level {level.currentLevel}</p>
          <strong>{level.label}</strong>
          <div className="xp-progress" title={`${Math.round(level.points)}/${level.next} points`}>
            <div className="xp-progress-fill" style={{ width: `${Math.min(100, (level.points / level.next) * 100)}%` }}></div>
          </div>
          <span>{Math.round(level.points)} / {level.next} XP</span>
        </div>
      ) : null}
    </div>
  );
}

function NotificationsPanel({ title, notifications, open, onToggle, emptyText }) {
  return (
    <div>
      <div className="section-heading">
        <div>
          <h2>{title}</h2>
          <p className="id-line">Collapsible activity feed for recent project, invite, payment, and XP changes.</p>
        </div>
        <button className="btn btn-secondary" type="button" onClick={onToggle}>
          {open ? 'Collapse' : 'Expand'}
        </button>
      </div>
      {open && (
        <div className="list">
          {notifications.length > 0 ? notifications.map((notification, index) => (
            <div key={`${notification.created_at || index}-${notification.title || 'note'}`} className="list-item">
              <div className="task-line">
                <strong>{notification.title || 'Update'}</strong>
                <span className={`status-badge status-${(notification.kind || 'pending').replace(/\s+/g, '-')}`}>
                  {notification.kind || 'info'}
                </span>
              </div>
              <p>{notification.message}</p>
              <p className="id-line">{notification.actor ? `${notification.actor} | ` : ''}{notification.created_at || 'Just now'}</p>
            </div>
          )) : (
            <div className="list-item">
              <p>{emptyText}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ProjectSection({ title, eyebrow, projects, emptyText, renderExtra, actions, onOpen }) {
  return (
    <div className="card full-width">
      <div className="section-heading">
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h2>{title}</h2>
        </div>
      </div>
      <div className="project-grid">
        {projects.length > 0 ? projects.map((project) => (
          <article key={project.project_id || project.id} className="project-shell">
            <div className="project-card-top">
              <div>
                <h3>{project.name || project.project_name}</h3>
                <p className="id-line">Project ID: #{project.project_id || project.id}</p>
                <p>{project.public_status_label || project.business_summary || project.description}</p>
              </div>
              <span className={`status-badge status-${(project.status || 'planning').replace(/\s+/g, '-')}`}>
                {project.status}
              </span>
            </div>
            <div className="progress">
              <div className="progress-fill" style={{ width: `${project.progress || 0}%` }}></div>
            </div>
            <p className="progress-text">{project.progress || 0}% complete</p>
            {renderExtra ? renderExtra(project) : null}
            {actions ? actions(project) : onOpen ? (
              <div className="project-card-actions">
                <button className="btn btn-secondary" type="button" onClick={() => onOpen(project.project_id || project.id)}>Open Status</button>
              </div>
            ) : null}
          </article>
        )) : (
          <div className="empty-state full-width">
            <p>{emptyText}</p>
          </div>
        )}
      </div>
    </div>
  );
}

function PaymentEditor({ project, paymentForm, setPaymentForm, onSave }) {
  return (
    <div className="card payment-card">
      <h3>Payment Status</h3>
      <div className="project-create-form">
        <div className="form-group">
          <label>Status</label>
          <select
            value={paymentForm.payment_status}
            onChange={(event) => setPaymentForm((current) => ({ ...current, payment_status: event.target.value }))}
          >
            <option value="pending">Pending</option>
            <option value="partial">Partial</option>
            <option value="client-confirmed">Client Confirmed</option>
            <option value="admin-confirmed">Admin Confirmed</option>
            <option value="completed">Completed</option>
            <option value="disputed">Disputed</option>
          </select>
        </div>
        <div className="form-group form-span-2">
          <label>Note</label>
          <textarea
            rows="2"
            value={paymentForm.note}
            onChange={(event) => setPaymentForm((current) => ({ ...current, note: event.target.value }))}
            placeholder="Add a short payment or confirmation note."
          />
        </div>
        <div className="form-actions">
          <button className="btn btn-primary" type="button" onClick={onSave}>Save Payment Update</button>
        </div>
      </div>
      <div className="list" style={{ marginTop: '14px' }}>
        {(project.payment_updates || []).length > 0 ? project.payment_updates.map((update, index) => (
          <div key={`${update.updated_at || index}-${update.status}`} className="list-item">
            <div className="task-line">
              <strong>{update.status}</strong>
              <span className="status-badge status-approved">{update.actor_role}</span>
            </div>
            <p>{update.note || 'No note provided.'}</p>
            <p className="id-line">{update.updated_by} | {update.updated_at}</p>
          </div>
        )) : (
          <div className="list-item">
            <p>No payment updates yet.</p>
          </div>
        )}
      </div>
    </div>
  );
}

function ReportPanel({ report, fallbackText }) {
  if (!report && !fallbackText) return null;
  return (
    <div className="card report-card">
      <h3>Generated Project Report</h3>
      {report ? (
        <>
          <div className="project-mini-grid">
            <InfoPill label="Executive Summary" value={report.executive_summary} />
            <InfoPill label="Plan Brief" value={report.plan_brief} />
            <InfoPill label="USP" value={report.usp} />
            <InfoPill label="Delivery Status" value={report.delivery_status} />
          </div>
          <div className="info-pill">
            <span>Detailed Report</span>
            <strong>{report.full_text}</strong>
          </div>
        </>
      ) : (
        <div className="info-pill">
          <span>Detailed Report</span>
          <strong>{fallbackText}</strong>
        </div>
      )}
    </div>
  );
}

function SummaryCard({ label, value, tooltip }) {
  return (
    <div className="summary-card" data-tooltip={tooltip}>
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
      <strong>{value || 'Not available'}</strong>
    </div>
  );
}
