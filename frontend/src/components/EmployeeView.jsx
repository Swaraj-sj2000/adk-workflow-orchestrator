import React, { useEffect, useState } from 'react';

const API = 'http://localhost:8000';

export default function EmployeeView({ role }) {
  const [data, setData] = useState(null);
  const [selectedTask, setSelectedTask] = useState(null);
  const [selectedMember, setSelectedMember] = useState(null);
  const [concernForm, setConcernForm] = useState({ blocker_type: 'ambiguity', severity: 'medium', description: '' });
  const [inviteNotes, setInviteNotes] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, [role]);

  const token = localStorage.getItem('token');
  const headers = { Authorization: `Bearer ${token}` };

  const fetchData = async () => {
    setLoading(true);
    try {
      const endpoint = role === 'admin' ? `${API}/system/team-dashboard` : `${API}/employees/my-work`;
      const res = await fetch(endpoint, { headers });
      if (res.ok) {
        const nextData = await res.json();
        setData(nextData);
        if (role === 'admin' && selectedMember) {
          const refreshedMember = (nextData.members || []).find((member) => member.employee_id === selectedMember.employee_id);
          setSelectedMember(refreshedMember || null);
        }
        if (role !== 'admin' && selectedTask) {
          const refreshedTask = (nextData.tasks || []).find((task) => task.assignment_id === selectedTask.assignment_id);
          setSelectedTask(refreshedTask || null);
        }
      }
    } catch (error) {
      console.error(error);
    }
    setLoading(false);
  };

  const toggleCheckpoint = async (checkpointId, completed) => {
    try {
      const res = await fetch(`${API}/employees/checkpoints/${checkpointId}`, {
        method: 'PATCH',
        headers: {
          ...headers,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ completed }),
      });
      if (res.ok) {
        await fetchData();
      }
    } catch (error) {
      console.error(error);
    }
  };

  const submitConcern = async (event) => {
    event.preventDefault();
    if (!selectedTask) return;

    try {
      const res = await fetch(`${API}/blockers/`, {
        method: 'POST',
        headers: {
          ...headers,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          task_id: selectedTask.task_id,
          blocker_type: concernForm.blocker_type,
          severity: concernForm.severity,
          description: concernForm.description,
        }),
      });
      if (res.ok) {
        setConcernForm({ blocker_type: 'ambiguity', severity: 'medium', description: '' });
        await fetchData();
      }
    } catch (error) {
      console.error(error);
    }
  };

  const respondToInvite = async (projectId, accepted) => {
    try {
      const res = await fetch(`${API}/projects/${projectId}/invite-response`, {
        method: 'POST',
        headers: {
          ...headers,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          accepted,
          note: inviteNotes[projectId] || '',
        }),
      });
      if (res.ok) {
        setInviteNotes((current) => ({ ...current, [projectId]: '' }));
        await fetchData();
      }
    } catch (error) {
      console.error(error);
    }
  };

  if (loading) return <div className="loading"><div className="spinner"></div></div>;

  if (role === 'admin') {
    const members = data?.members || [];
    const summary = data?.summary || {};
    return (
      <div className="dashboard">
        <div className="card full-width">
          <p className="eyebrow">Team Dashboard</p>
          <h2>Employee status across your AI service team</h2>
          <div className="summary-grid">
            <div className="summary-card">
              <p>Free Right Now</p>
              <div className="metric">{summary.free_now || 0}</div>
            </div>
            <div className="summary-card">
              <p>Busy</p>
              <div className="metric">{summary.busy || 0}</div>
            </div>
            <div className="summary-card">
              <p>On Leave</p>
              <div className="metric">{summary.on_leave || 0}</div>
            </div>
            <div className="summary-card">
              <p>Team Size</p>
              <div className="metric">{data?.team_size || 0}</div>
            </div>
          </div>
        </div>

        <div className="card">
          <h2>Team Members</h2>
          <div className="list">
            {members.map((member) => (
              <div
                key={member.employee_id}
                className="list-item"
                onClick={() => setSelectedMember(member)}
                style={{
                  background: selectedMember?.employee_id === member.employee_id ? '#eef7f3' : '#f9faf8',
                  borderLeftColor: selectedMember?.employee_id === member.employee_id ? '#2f7d62' : '#d5dcd8',
                }}
              >
                <div className="task-line">
                  <div>
                    <strong>{member.name}</strong>
                    <p>{member.title}</p>
                  </div>
                  <span className={`status-badge status-${(member.availability_status || 'available').replace(/\s+/g, '-')}`}>
                    {member.shift_status}
                  </span>
                </div>
                <p>{member.workload_percent}% workload</p>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          {selectedMember ? (
            <>
              <h2>{selectedMember.name}</h2>
              <div className="project-mini-grid">
                <div className="info-pill">
                  <span>Email</span>
                  <strong>{selectedMember.email}</strong>
                </div>
                <div className="info-pill">
                  <span>Role</span>
                  <strong>{selectedMember.title}</strong>
                </div>
                <div className="info-pill">
                  <span>Department</span>
                  <strong>{selectedMember.department}</strong>
                </div>
                <div className="info-pill">
                  <span>Workload</span>
                  <strong>{selectedMember.workload_percent}%</strong>
                </div>
                <div className="info-pill">
                  <span>Active Assignments</span>
                  <strong>{selectedMember.active_assignment_count}</strong>
                </div>
                <div className="info-pill">
                  <span>Capacity</span>
                  <strong>{selectedMember.current_load} / {selectedMember.max_capacity}h</strong>
                </div>
              </div>

              <div className="info-pill">
                <span>Current Projects</span>
                <strong>{(selectedMember.active_projects || []).join(', ') || 'No active projects right now'}</strong>
              </div>

              <h3>Skill Profile</h3>
              <div className="list">
                {Object.entries(selectedMember.skills || {}).map(([skill, score]) => (
                  <div key={skill} className="list-item">
                    <div className="task-line">
                      <strong>{skill}</strong>
                      <span className="status-badge status-approved">{Math.round(Number(score) * 100)}%</span>
                    </div>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="empty-state">
              <p>Select a team member to see their detailed status, active projects, and skill profile.</p>
            </div>
          )}
        </div>
      </div>
    );
  }

  const tasks = data?.tasks || [];
  const projects = data?.projects || [];
  const projectInvites = data?.project_invites || [];
  const plannedTracks = data?.planned_tracks || [];
  const employee = data?.employee || {};

  return (
    <div className="dashboard">
      <div className="card full-width">
        <p className="eyebrow">My Work</p>
        <h2>{employee.name}</h2>
        <div className="summary-grid">
          <div className="summary-card">
            <p>Role</p>
            <div className="detail-card-value">{employee.title}</div>
          </div>
          <div className="summary-card">
            <p>Assigned Tasks</p>
            <div className="metric">{data?.summary?.assigned_tasks || 0}</div>
          </div>
          <div className="summary-card">
            <p>My Progress</p>
            <div className="metric">{data?.summary?.personal_progress_percent || 0}%</div>
          </div>
          <div className="summary-card">
            <p>Workload</p>
            <div className="metric">{employee.workload_percent || 0}%</div>
          </div>
          <div className="summary-card">
            <p>Pending Invites</p>
            <div className="metric">{data?.summary?.pending_invites || 0}</div>
          </div>
        </div>
      </div>

      <div className="card">
        <h2>Project Invitations</h2>
        <div className="list">
          {projectInvites.length > 0 ? projectInvites.map((invite) => (
            <div key={`${invite.project_id}-${invite.title}`} className="list-item">
              <div className="task-line">
                <div>
                  <strong>{invite.project_name}</strong>
                  <p>Project #{invite.project_id} • {invite.title}</p>
                </div>
                <span className={`status-badge status-${(invite.status || 'pending').replace(/\s+/g, '-')}`}>
                  {invite.status}
                </span>
              </div>
              <p>{invite.viewer_guidance}</p>
              <p><strong>Decision Support:</strong> {invite.decision_support}</p>
              <p><strong>Join Window:</strong> {invite.join_deadline || 'Waiting for admin confirmation'}</p>
              <p><strong>Role Focus:</strong> {(invite.role_focus || []).join(', ') || 'Role focus will appear after planning.'}</p>
              <p><strong>Why You:</strong> {invite.capacity_reasoning || 'Selected for role fit and current availability.'}</p>
              {(invite.planned_tasks || []).length > 0 && (
                <div className="info-pill">
                  <span>Planned Work Track</span>
                  <strong>{invite.planned_tasks.map((task) => task.task_name).join(', ')}</strong>
                </div>
              )}
              <div className="form-group">
                <label>Response Note</label>
                <textarea
                  rows="2"
                  value={inviteNotes[invite.project_id] || ''}
                  onChange={(event) => setInviteNotes((current) => ({ ...current, [invite.project_id]: event.target.value }))}
                  placeholder="Share any acceptance note, capacity concern, or blocker."
                />
              </div>
              {invite.status === 'pending' && (
                <div className="project-card-actions">
                  <button className="btn btn-primary" onClick={() => respondToInvite(invite.project_id, true)}>
                    Accept Project
                  </button>
                  <button className="btn btn-danger" onClick={() => respondToInvite(invite.project_id, false)}>
                    Reject Project
                  </button>
                </div>
              )}
            </div>
          )) : (
            <div className="list-item">
              <p>No pending project invitations right now.</p>
            </div>
          )}
        </div>
      </div>

      <div className="card">
        <h2>Planned Task Track</h2>
        <div className="list">
          {plannedTracks.length > 0 ? plannedTracks.map((track) => (
            <div key={`${track.project_id}-${track.role_title}`} className="list-item">
              <div className="task-line">
                <div>
                  <strong>{track.project_name}</strong>
                  <p>Project #{track.project_id} • {track.role_title}</p>
                </div>
                <span className={`status-badge status-${(track.invite_status || 'pending').replace(/\s+/g, '-')}`}>
                  {track.invite_status}
                </span>
              </div>
              {(track.tasks || []).map((task) => (
                <div key={task.task_id} style={{ marginTop: '10px' }}>
                  <p><strong>{task.task_name}</strong> • {task.estimated_hours}h</p>
                  <p>{(task.delivery_steps || []).join(' | ') || 'Detailed steps will appear here once activation completes.'}</p>
                </div>
              ))}
            </div>
          )) : (
            <div className="list-item">
              <p>No planned task track yet. Once you are shortlisted for a project, your role-aligned work track will appear here.</p>
            </div>
          )}
        </div>
      </div>

      <div className="card">
        <h2>My Projects</h2>
        <div className="list">
          {projects.map((project) => (
            <div key={project.project_id} className="list-item">
              <div className="task-line">
                <div>
                  <strong>{project.name}</strong>
                  <p>Project ID: #{project.project_id}</p>
                </div>
                <span className={`status-badge status-${(project.status || 'planning').replace(/\s+/g, '-')}`}>
                  {project.status}
                </span>
              </div>
              <p>{project.public_status_label}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <h2>My Task Path</h2>
        <div className="list">
          {tasks.map((task) => (
            <div
              key={task.assignment_id}
              className="list-item"
              onClick={() => setSelectedTask(task)}
              style={{
                background: selectedTask?.assignment_id === task.assignment_id ? '#eef7f3' : '#f9faf8',
                borderLeftColor: selectedTask?.assignment_id === task.assignment_id ? '#2f7d62' : '#d5dcd8',
              }}
            >
              <div className="task-line">
                <div>
                  <strong>{task.task_name}</strong>
                  <p>Project #{task.project_id}</p>
                </div>
                <span className={`status-badge status-${(task.status || 'pending').replace(/\s+/g, '-')}`}>
                  {task.status}
                </span>
              </div>
              <p>{task.completion_percentage}% complete</p>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        {selectedTask ? (
          <>
            <h2>{selectedTask.task_name}</h2>
            <p>Project ID: #{selectedTask.project_id}</p>
            <div className="project-mini-grid">
              <div className="info-pill">
                <span>Status</span>
                <strong>{selectedTask.status}</strong>
              </div>
              <div className="info-pill">
                <span>Progress</span>
                <strong>{selectedTask.completion_percentage}%</strong>
              </div>
              <div className="info-pill">
                <span>Estimate</span>
                <strong>{selectedTask.estimated_hours}h</strong>
              </div>
            </div>
            <div className="info-pill">
              <span>Agent Brief</span>
              <strong>{selectedTask.notes}</strong>
            </div>
            <div className="info-pill">
              <span>Concern Path</span>
              <strong>{selectedTask.concern_path}</strong>
            </div>
            <h3>Checkpoints</h3>
            <div className="list">
              {selectedTask.checkpoints.map((checkpoint) => (
                <div key={checkpoint.id} className="list-item">
                  <div className="task-line">
                    <label style={{ display: 'flex', gap: '10px', alignItems: 'center', cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={checkpoint.status === 'completed'}
                        onChange={(event) => toggleCheckpoint(checkpoint.id, event.target.checked)}
                      />
                      <strong>{checkpoint.title}</strong>
                    </label>
                    <span className={`status-badge status-${checkpoint.status}`}>
                      {checkpoint.status}
                    </span>
                  </div>
                  <p>{checkpoint.notes}</p>
                </div>
              ))}
            </div>

            <h3>Raise a Concern</h3>
            <form className="project-create-form" onSubmit={submitConcern}>
              <div className="form-group">
                <label>Concern Type</label>
                <select
                  value={concernForm.blocker_type}
                  onChange={(event) => setConcernForm((current) => ({ ...current, blocker_type: event.target.value }))}
                >
                  <option value="ambiguity">Ambiguity</option>
                  <option value="dependency">Dependency</option>
                  <option value="resource">Resource</option>
                  <option value="external">External</option>
                </select>
              </div>
              <div className="form-group">
                <label>Severity</label>
                <select
                  value={concernForm.severity}
                  onChange={(event) => setConcernForm((current) => ({ ...current, severity: event.target.value }))}
                >
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </select>
              </div>
              <div className="form-group form-span-2">
                <label>Description</label>
                <textarea
                  rows="3"
                  value={concernForm.description}
                  onChange={(event) => setConcernForm((current) => ({ ...current, description: event.target.value }))}
                  placeholder="Describe the blocker or concern clearly."
                  required
                />
              </div>
              <div className="form-actions form-span-2">
                <button className="btn btn-secondary" type="submit">Ask AI Lead</button>
              </div>
            </form>

            <h3>Open Concerns</h3>
            <div className="list">
              {(selectedTask.blockers || []).length > 0 ? selectedTask.blockers.map((blocker) => (
                <div key={blocker.id} className="list-item">
                  <div className="task-line">
                    <strong>{blocker.description}</strong>
                    <span className={`status-badge status-${blocker.severity}`}>
                      {blocker.severity}
                    </span>
                  </div>
                  <p><strong>AI Response:</strong> {blocker.ai_response || 'Pending'}</p>
                  <p><strong>Next Action:</strong> {blocker.next_action || 'Pending'}</p>
                </div>
              )) : (
                <div className="list-item">
                  <p>No open concerns for this task yet.</p>
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="empty-state">
            <p>{tasks.length > 0 ? 'Select one of your tasks to see the generated execution brief, checkpoints, and completion controls.' : 'Your task path will appear here after the invited team is fully confirmed and the AI manager activates assignments.'}</p>
          </div>
        )}
      </div>
    </div>
  );
}
