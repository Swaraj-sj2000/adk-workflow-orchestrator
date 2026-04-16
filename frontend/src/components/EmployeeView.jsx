import React, { useEffect, useState } from 'react';
import { API_BASE_URL as API } from '../config';

const initialConcernForm = {
  blocker_type: 'ambiguity',
  severity: 'medium',
  description: '',
};

const initialInviteForm = {
  projectId: '',
  email: '',
  roleTitle: '',
};

const initialProfileForm = {
  skillsText: '',
  dutyStart: '09:00',
  dutyEnd: '18:00',
  onLeave: false,
};

const initialTaskChangeForm = {
  action: 'add',
  targetType: 'subtask',
  targetSubtaskId: '',
  proposedTitle: '',
  proposedDescription: '',
  note: '',
};

export default function EmployeeView({ role }) {
  const [data, setData] = useState(null);
  const [selectedTask, setSelectedTask] = useState(null);
  const [selectedMember, setSelectedMember] = useState(null);
  const [concernForm, setConcernForm] = useState(initialConcernForm);
  const [inviteNotes, setInviteNotes] = useState({});
  const [inviteForm, setInviteForm] = useState(initialInviteForm);
  const [profileForm, setProfileForm] = useState(initialProfileForm);
  const [taskChangeForm, setTaskChangeForm] = useState(initialTaskChangeForm);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [actionKey, setActionKey] = useState('');

  useEffect(() => {
    fetchData();
  }, [role]);

  useEffect(() => {
    setTaskChangeForm(initialTaskChangeForm);
  }, [selectedTask?.task_id]);

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
        if (role === 'admin') {
          if (selectedMember) {
            const refreshedMember = (nextData.members || []).find((member) => member.employee_id === selectedMember.employee_id);
            setSelectedMember(refreshedMember || null);
          }
          setInviteForm((current) => ({
            ...current,
            projectId: current.projectId || String(nextData.invite_targets?.[0]?.project_id || ''),
          }));
        } else {
          if (selectedTask) {
            const refreshedTask = (nextData.tasks || []).find((task) => task.assignment_id === selectedTask.assignment_id);
            setSelectedTask(refreshedTask || null);
          }
          setProfileForm({
            skillsText: formatSkillsText(nextData.employee?.skills || {}),
            dutyStart: toHourInput(nextData.employee?.duty_start_hour),
            dutyEnd: toHourInput(nextData.employee?.duty_end_hour),
            onLeave: Boolean(nextData.employee?.on_leave),
          });
        }
      }
    } catch (error) {
      console.error(error);
      setMessage('Could not load workspace data.');
    }
    setLoading(false);
  };

  const toggleCheckpoint = async (checkpointId, completed) => {
    if (actionKey) return;
    setActionKey(`checkpoint-${checkpointId}`);
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
        setMessage('Checkpoint updated.');
        await fetchData();
      }
    } catch (error) {
      console.error(error);
      setMessage('Could not update checkpoint.');
    } finally {
      setActionKey('');
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
        setConcernForm(initialConcernForm);
        setMessage('Concern submitted to the AI lead.');
        await fetchData();
      }
    } catch (error) {
      console.error(error);
      setMessage('Could not submit concern.');
    }
  };

  const toggleTaskStatus = async (taskId, completed, label = 'Task') => {
    if (actionKey) return;
    setActionKey(`task-status-${taskId}`);
    try {
      const res = await fetch(`${API}/tasks/${taskId}/status`, {
        method: 'PATCH',
        headers: {
          ...headers,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          status: completed ? 'done' : 'pending',
        }),
      });
      const payload = await res.json();
      if (!res.ok) {
        throw new Error(payload.detail || `Could not update ${label.toLowerCase()}.`);
      }
      setMessage(`${label} updated.`);
      await fetchData();
    } catch (error) {
      console.error(error);
      setMessage(error.message);
    } finally {
      setActionKey('');
    }
  };

  const submitTaskChangeRequest = async (event) => {
    event.preventDefault();
    if (!selectedTask || actionKey) return;

    const isAdd = taskChangeForm.action === 'add';
    const isSubtask = taskChangeForm.targetType === 'subtask';
    const payload = {
      action: taskChangeForm.action,
      target_type: taskChangeForm.targetType,
      target_task_id: null,
      parent_task_id: null,
      proposed_title: isAdd ? taskChangeForm.proposedTitle.trim() : null,
      proposed_description: isAdd ? taskChangeForm.proposedDescription.trim() || null : null,
      note: taskChangeForm.note.trim(),
    };

    if (isAdd && !payload.proposed_title) {
      setMessage('Add requests need a clear title so the agent can review them properly.');
      return;
    }

    if (isAdd) {
      if (isSubtask) {
        payload.parent_task_id = selectedTask.task_id;
      } else {
        payload.target_task_id = selectedTask.task_id;
      }
    } else if (isSubtask) {
      payload.target_task_id = Number(taskChangeForm.targetSubtaskId || 0) || null;
    } else {
      payload.target_task_id = selectedTask.task_id;
    }

    if (!isAdd && isSubtask && !payload.target_task_id) {
      setMessage('Choose the subtask you want to remove before sending the request.');
      return;
    }

    setActionKey(`task-change-${selectedTask.task_id}`);
    try {
      const res = await fetch(`${API}/projects/${selectedTask.project_id}/task-change-requests`, {
        method: 'POST',
        headers: {
          ...headers,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Could not submit task change request.');
      }
      setTaskChangeForm(initialTaskChangeForm);
      setMessage('Task list change request sent for agent review and admin approval.');
      await fetchData();
    } catch (error) {
      console.error(error);
      setMessage(error.message);
    } finally {
      setActionKey('');
    }
  };

  const respondToInvite = async (projectId, accepted) => {
    if (actionKey) return;
    setActionKey(`${accepted ? 'accept' : 'reject'}-${projectId}`);
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
        setMessage(accepted ? 'Project invite accepted.' : 'Project invite rejected.');
        await fetchData();
      }
    } catch (error) {
      console.error(error);
      setMessage('Could not update invite response.');
    } finally {
      setActionKey('');
    }
  };

  const inviteMember = async (event) => {
    event.preventDefault();
    if (!inviteForm.projectId || !inviteForm.email.trim()) return;
    if (actionKey) return;
    setActionKey(`invite-${inviteForm.projectId}`);

    try {
      const res = await fetch(`${API}/invite`, {
        method: 'POST',
        headers: {
          ...headers,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          project_id: Number(inviteForm.projectId),
          email: inviteForm.email.trim().toLowerCase(),
          role_title: inviteForm.roleTitle.trim() || null,
        }),
      });
      const payload = await res.json();
      if (!res.ok) {
        throw new Error(payload.detail || 'Could not create invite');
      }
      setInviteForm((current) => ({ ...current, email: '', roleTitle: '' }));
      setMessage(payload.existing_user ? 'Invite created. The employee can now accept it from their dashboard.' : 'Pending invite created. It will attach automatically when the user registers.');
      await fetchData();
    } catch (error) {
      console.error(error);
      setMessage(error.message);
    } finally {
      setActionKey('');
    }
  };

  const saveProfile = async (availabilityOverride = null) => {
    const employeeId = data?.employee?.employee_id;
    if (!employeeId) return;
    if (actionKey) return;
    setActionKey(`profile-${employeeId}`);

    try {
      const res = await fetch(`${API}/employees/${employeeId}/profile`, {
        method: 'PATCH',
        headers: {
          ...headers,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          skills: parseSkillsText(profileForm.skillsText),
          duty_start_hour: fromHourInput(profileForm.dutyStart),
          duty_end_hour: fromHourInput(profileForm.dutyEnd),
          availability_status: availabilityOverride || (profileForm.onLeave ? 'on-leave' : 'available'),
        }),
      });
      const payload = await res.json();
      if (!res.ok) {
        throw new Error(payload.detail || 'Could not update profile');
      }
      setMessage('Profile updated. Team board status will refresh automatically.');
      await fetchData();
    } catch (error) {
      console.error(error);
      setMessage(error.message);
    } finally {
      setActionKey('');
    }
  };

  const toggleLeaveStatus = async () => {
    const nextOnLeave = !profileForm.onLeave;
    setProfileForm((current) => ({ ...current, onLeave: nextOnLeave }));
    await saveProfile(nextOnLeave ? 'on-leave' : 'available');
  };

  if (loading) return <div className="loading"><div className="spinner"></div></div>;

  if (role === 'admin') {
    const members = data?.members || [];
    const summary = data?.summary || {};
    const inviteTargets = data?.invite_targets || [];
    const pendingInvites = data?.pending_invites || [];

    return (
      <div className="dashboard">
        {message && (
          <div className={`card full-width workspace-message workspace-${messageTone(message)}`}>
            <strong>{message}</strong>
          </div>
        )}

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
          <h2>Add Member By Email</h2>
          <form className="project-create-form" onSubmit={inviteMember}>
            <div className="form-group">
              <label>Project Team</label>
              <select
                value={inviteForm.projectId}
                onChange={(event) => setInviteForm((current) => ({ ...current, projectId: event.target.value }))}
                required
              >
                <option value="">Select project</option>
                {inviteTargets.map((project) => (
                  <option key={project.project_id} value={project.project_id}>
                    {project.name} ({project.status})
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label>Employee Email</label>
              <input
                type="email"
                value={inviteForm.email}
                onChange={(event) => setInviteForm((current) => ({ ...current, email: event.target.value }))}
                placeholder="nitin@orchestrator.ai"
                required
              />
            </div>
            <div className="form-group form-span-2">
              <label>Role Title</label>
              <input
                value={inviteForm.roleTitle}
                onChange={(event) => setInviteForm((current) => ({ ...current, roleTitle: event.target.value }))}
                placeholder="Backend Engineer"
              />
            </div>
            <div className="form-actions form-span-2">
              <button className="btn btn-primary" type="submit" disabled={Boolean(actionKey)}>
                {actionKey === `invite-${inviteForm.projectId}` ? 'Sending...' : 'Send Team Invite'}
              </button>
            </div>
          </form>
        </div>

        <div className="card">
          <h2>Pending Team Invites</h2>
          <div className="list">
            {pendingInvites.length > 0 ? pendingInvites.map((invite) => (
              <div key={invite.invite_id} className="list-item">
                <div className="task-line">
                  <div>
                    <strong>{invite.email}</strong>
                    <p>{invite.project_name}</p>
                  </div>
                  <span className="status-badge status-pending">pending</span>
                </div>
                <p>{invite.role_title || 'Role to be finalized by admin'}</p>
              </div>
            )) : (
              <div className="list-item">
                <p>No pending invites right now.</p>
              </div>
            )}
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
                <p>{member.duty_window || 'Duty hours not set'} | XP {Math.round(member.experience_points || 0)}</p>
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
                  <span>Duty Window</span>
                  <strong>{selectedMember.duty_window || 'Not set'}</strong>
                </div>
                <div className="info-pill">
                  <span>Status</span>
                  <strong>{selectedMember.shift_status}</strong>
                </div>
                <div className="info-pill">
                  <span>XP Grade</span>
                  <strong>{selectedMember.experience_grade}</strong>
                </div>
                <div className="info-pill">
                  <span>XP Points</span>
                  <strong>{Math.round(selectedMember.experience_points || 0)}</strong>
                </div>
                <div className="info-pill">
                  <span>Efficiency</span>
                  <strong>{Math.round((selectedMember.efficiency_score || 0) * 100)}%</strong>
                </div>
                <div className="info-pill">
                  <span>Reliability</span>
                  <strong>{Math.round((selectedMember.reliability_score || 0) * 100)}%</strong>
                </div>
                <div className="info-pill">
                  <span>Completed Tasks</span>
                  <strong>{selectedMember.tasks_completed}</strong>
                </div>
                <div className="info-pill">
                  <span>Delayed Tasks</span>
                  <strong>{selectedMember.tasks_delayed}</strong>
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
              <p>Select a team member to see their detailed status, active projects, duty hours, and experience profile.</p>
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
      {message && (
        <div className={`card full-width workspace-message workspace-${messageTone(message)}`}>
          <strong>{message}</strong>
        </div>
      )}

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
          <div className="summary-card">
            <p>XP Grade</p>
            <div className="detail-card-value">{employee.experience_grade || 'Starter'}</div>
          </div>
        </div>
      </div>

      <div className="card">
        <h2>My Availability and Skills</h2>
        <div className="project-mini-grid">
          <div className="info-pill">
            <span>Current Status</span>
            <strong>{employee.shift_status || 'On Duty'}</strong>
          </div>
          <div className="info-pill">
            <span>Duty Window</span>
            <strong>{employee.duty_window || 'Not set'}</strong>
          </div>
          <div className="info-pill">
            <span>XP Points</span>
            <strong>{Math.round(employee.experience_points || 0)}</strong>
          </div>
          <div className="info-pill">
            <span>Efficiency</span>
            <strong>{Math.round((employee.efficiency_score || 0) * 100)}%</strong>
          </div>
          <div className="info-pill">
            <span>Reliability</span>
            <strong>{Math.round((employee.reliability_score || 0) * 100)}%</strong>
          </div>
          <div className="info-pill">
            <span>Completed Tasks</span>
            <strong>{employee.tasks_completed || 0}</strong>
          </div>
        </div>

        <form
          className="project-create-form"
          onSubmit={(event) => {
            event.preventDefault();
            saveProfile();
          }}
        >
          <div className="form-group form-span-2">
            <label>Skills</label>
            <textarea
              rows="5"
              value={profileForm.skillsText}
              onChange={(event) => setProfileForm((current) => ({ ...current, skillsText: event.target.value }))}
              placeholder={`python: 0.9\nfastapi: 0.8\nreact: 0.7`}
            />
            <p className="muted-copy">Use one skill per line. Scores accept `0.0-1.0` or percentages like `85`.</p>
          </div>
          <div className="form-group">
            <label>Duty Start</label>
            <input
              type="time"
              value={profileForm.dutyStart}
              onChange={(event) => setProfileForm((current) => ({ ...current, dutyStart: event.target.value }))}
            />
          </div>
          <div className="form-group">
            <label>Duty End</label>
            <input
              type="time"
              value={profileForm.dutyEnd}
              onChange={(event) => setProfileForm((current) => ({ ...current, dutyEnd: event.target.value }))}
            />
          </div>
          <div className="form-actions form-span-2 split-actions">
            <button className="btn btn-primary" type="submit" disabled={Boolean(actionKey)}>
              {actionKey === `profile-${data?.employee?.employee_id}` ? 'Saving...' : 'Save Skills and Duty Hours'}
            </button>
            <button className="btn btn-secondary" type="button" onClick={toggleLeaveStatus} disabled={Boolean(actionKey)}>
              {actionKey === `profile-${data?.employee?.employee_id}` ? 'Updating...' : profileForm.onLeave ? 'Mark Back On Duty' : 'Mark On Leave'}
            </button>
          </div>
        </form>
      </div>

      <div className="card">
        <h2>Project Invitations</h2>
        <div className="list">
          {projectInvites.length > 0 ? projectInvites.map((invite) => (
            <div key={`${invite.project_id}-${invite.title}`} className="list-item">
              <div className="task-line">
                <div>
                  <strong>{invite.project_name}</strong>
                  <p>Project #{invite.project_id} | {invite.title}</p>
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
                  <button className="btn btn-primary" onClick={() => respondToInvite(invite.project_id, true)} disabled={Boolean(actionKey)}>
                    {actionKey === `accept-${invite.project_id}` ? 'Accepting...' : 'Accept Project'}
                  </button>
                  <button className="btn btn-danger" onClick={() => respondToInvite(invite.project_id, false)} disabled={Boolean(actionKey)}>
                    {actionKey === `reject-${invite.project_id}` ? 'Rejecting...' : 'Reject Project'}
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
                  <p>Project #{track.project_id} | {track.role_title}</p>
                </div>
                <span className={`status-badge status-${(track.invite_status || 'pending').replace(/\s+/g, '-')}`}>
                  {track.invite_status}
                </span>
              </div>
              {(track.tasks || []).map((task) => (
                <div key={task.task_id} style={{ marginTop: '10px' }}>
                  <p><strong>{task.task_name}</strong> | {task.estimated_hours}h</p>
                  <p>{(task.delivery_steps || []).join(' | ') || 'Detailed steps will appear here as soon as your invite is accepted and the work package is generated.'}</p>
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
              <p><strong>Project Progress:</strong> {project.progress || 0}%</p>
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
              <p><strong>Project Progress:</strong> {task.project_progress || 0}%</p>
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
                <span>Project Progress</span>
                <strong>{selectedTask.project_progress || 0}%</strong>
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
            <h3>Task and Subtask Control</h3>
            <div className="list">
              <div className="list-item">
                <div className="task-line">
                  <label style={{ display: 'flex', gap: '10px', alignItems: 'center', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={selectedTask.status === 'done'}
                      disabled={Boolean(actionKey)}
                      onChange={(event) => toggleTaskStatus(selectedTask.task_id, event.target.checked, 'Task')}
                    />
                    <strong>Mark parent task complete</strong>
                  </label>
                  <span className={`status-badge status-${(selectedTask.status || 'pending').replace(/\s+/g, '-')}`}>
                    {selectedTask.status}
                  </span>
                </div>
                <p>Directly checking the parent task updates project progress. Subtask checks only move this task until all subtasks are finished.</p>
              </div>
              {(selectedTask.subtasks || []).length > 0 ? selectedTask.subtasks.map((subtask) => (
                <div key={subtask.id} className="list-item">
                  <div className="task-line">
                    <label style={{ display: 'flex', gap: '10px', alignItems: 'center', cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={subtask.status === 'done'}
                        disabled={Boolean(actionKey)}
                        onChange={(event) => toggleTaskStatus(subtask.id, event.target.checked, 'Subtask')}
                      />
                      <strong>{subtask.title}</strong>
                    </label>
                    <span className={`status-badge status-${(subtask.status || 'pending').replace(/\s+/g, '-')}`}>
                      {subtask.status}
                    </span>
                  </div>
                  <p>{subtask.completion_percentage || (subtask.status === 'done' ? 100 : 0)}% progress • {subtask.estimated_hours || 0}h estimate</p>
                </div>
              )) : (
                <div className="list-item">
                  <p>No subtasks have been approved for this task yet.</p>
                </div>
              )}
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
                        disabled={Boolean(actionKey)}
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

            <h3>Request Task List Change</h3>
            <form className="project-create-form" onSubmit={submitTaskChangeRequest}>
              <div className="form-group">
                <label>Change Type</label>
                <select
                  value={taskChangeForm.action}
                  onChange={(event) => setTaskChangeForm((current) => ({ ...current, action: event.target.value }))}
                >
                  <option value="add">Add</option>
                  <option value="delete">Delete</option>
                </select>
              </div>
              <div className="form-group">
                <label>Target</label>
                <select
                  value={taskChangeForm.targetType}
                  onChange={(event) => setTaskChangeForm((current) => ({ ...current, targetType: event.target.value, targetSubtaskId: '' }))}
                >
                  <option value="task">Parent task</option>
                  <option value="subtask">Subtask</option>
                </select>
              </div>
              {taskChangeForm.action === 'delete' && taskChangeForm.targetType === 'subtask' && (
                <div className="form-group form-span-2">
                  <label>Subtask To Remove</label>
                  <select
                    value={taskChangeForm.targetSubtaskId}
                    onChange={(event) => setTaskChangeForm((current) => ({ ...current, targetSubtaskId: event.target.value }))}
                    required
                  >
                    <option value="">Choose subtask</option>
                    {(selectedTask.subtasks || []).map((subtask) => (
                      <option key={subtask.id} value={subtask.id}>
                        {subtask.title}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              {taskChangeForm.action === 'add' && (
                <>
                  <div className="form-group form-span-2">
                    <label>Proposed Title</label>
                    <input
                      value={taskChangeForm.proposedTitle}
                      onChange={(event) => setTaskChangeForm((current) => ({ ...current, proposedTitle: event.target.value }))}
                      placeholder={taskChangeForm.targetType === 'task' ? 'Add a sibling task for this workstream' : 'Add a new subtask under this task'}
                      required
                    />
                  </div>
                  <div className="form-group form-span-2">
                    <label>Proposed Details</label>
                    <textarea
                      rows="3"
                      value={taskChangeForm.proposedDescription}
                      onChange={(event) => setTaskChangeForm((current) => ({ ...current, proposedDescription: event.target.value }))}
                      placeholder="Explain the work, scope, or correction you want the agent to review."
                    />
                  </div>
                </>
              )}
              <div className="form-group form-span-2">
                <label>Why should this change happen?</label>
                <textarea
                  rows="3"
                  value={taskChangeForm.note}
                  onChange={(event) => setTaskChangeForm((current) => ({ ...current, note: event.target.value }))}
                  placeholder="Explain the issue, risk, or improvement clearly. This is reviewed by the agent and then by admin."
                  required
                />
              </div>
              <div className="form-actions form-span-2">
                <button className="btn btn-secondary" type="submit" disabled={Boolean(actionKey)}>
                  {actionKey === `task-change-${selectedTask.task_id}` ? 'Submitting...' : 'Send For Review'}
                </button>
              </div>
            </form>

            <h3>Task Change Requests</h3>
            <div className="list">
              {(selectedTask.task_change_requests || []).length > 0 ? selectedTask.task_change_requests.map((request) => (
                <div key={request.request_id} className="list-item">
                  <div className="task-line">
                    <strong>{request.action} {request.target_type}</strong>
                    <span className={`status-badge status-${(request.status || 'pending').replace(/\s+/g, '-')}`}>
                      {request.status}
                    </span>
                  </div>
                  <p><strong>Reason:</strong> {request.note}</p>
                  {request.proposed_title && <p><strong>Proposal:</strong> {request.proposed_title}</p>}
                  {request.proposed_description && <p><strong>Details:</strong> {request.proposed_description}</p>}
                  <p><strong>Agent Review:</strong> {request.agent_review || 'Review pending.'}</p>
                  {request.admin_note && <p><strong>Admin Note:</strong> {request.admin_note}</p>}
                </div>
              )) : (
                <div className="list-item">
                  <p>No task change requests yet for this workstream.</p>
                </div>
              )}
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
                <button className="btn btn-secondary" type="submit" disabled={Boolean(actionKey)}>Ask AI Lead</button>
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
            <p>{tasks.length > 0 ? 'Select one of your tasks to see the generated execution brief, checkpoints, and completion controls.' : 'Your task path will appear here as soon as you accept a team invite and assignments are activated for your role.'}</p>
          </div>
        )}
      </div>
    </div>
  );
}

function formatSkillsText(skills) {
  return Object.entries(skills || {})
    .map(([skill, score]) => `${skill}: ${score}`)
    .join('\n');
}

function parseSkillsText(text) {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .reduce((accumulator, line) => {
      const [rawSkill, rawScore] = line.split(':');
      if (!rawSkill) return accumulator;
      const skill = rawSkill.trim().toLowerCase();
      if (!skill) return accumulator;

      let score = Number(String(rawScore || '0').trim());
      if (Number.isNaN(score)) score = 0;
      if (score > 1) score = score / 100;
      accumulator[skill] = Math.max(0, Math.min(score, 1));
      return accumulator;
    }, {});
}

function toHourInput(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '09:00';
  const totalMinutes = Math.round(Number(value) * 60);
  const hours = `${Math.floor(totalMinutes / 60) % 24}`.padStart(2, '0');
  const minutes = `${totalMinutes % 60}`.padStart(2, '0');
  return `${hours}:${minutes}`;
}

function fromHourInput(value) {
  if (!value) return null;
  const [hours, minutes] = value.split(':').map(Number);
  if (Number.isNaN(hours) || Number.isNaN(minutes)) return null;
  return Number((hours + minutes / 60).toFixed(2));
}

function messageTone(message) {
  const lowered = String(message || '').toLowerCase();
  return lowered.includes('could not') || lowered.includes('failed') || lowered.includes('error') ? 'error' : 'success';
}
