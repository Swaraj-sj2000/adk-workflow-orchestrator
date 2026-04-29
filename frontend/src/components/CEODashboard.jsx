import React, { useEffect, useState } from 'react';
import Dashboard from './Dashboard';
import { CeoAnalytics } from './Analytics';
import { formatCurrency } from '../utils/currency';

export default function CEODashboard({ currentUser, API_BASE_URL, onNavigate, tenantLogoUrl, onCompanyUpdate }) {
  const currency = currentUser?.currency || 'USD';
  const fmt$ = (v) => formatCurrency(v, currency);
  const [loading, setLoading] = useState(true);
  const [ceoMode, setCeoMode] = useState(localStorage.getItem('ceo_mode') === 'true');
  const [overview, setOverview] = useState(null);
  const [financials, setFinancials] = useState(null);
  const [teams, setTeams] = useState(null);
  const [clients, setClients] = useState([]);
  const [risks, setRisks] = useState([]);
  const [recentActivity, setRecentActivity] = useState([]); // Quick win #2: Live agent activity ticker

  const [showAnalytics, setShowAnalytics] = useState(false);

  // Company profile state
  const [companyProfile, setCompanyProfile] = useState(null);
  const [companyForm, setCompanyForm] = useState({ name: '', description: '', logo_url: '' });
  const [companyMsg, setCompanyMsg] = useState('');
  const [savingCompany, setSavingCompany] = useState(false);
  const [showCompanyEditor, setShowCompanyEditor] = useState(false);

  // Talent pool state
  const [talentPool, setTalentPool] = useState({ members: [], pending_invites: [] });
  const [inviteForm, setInviteForm] = useState({ email: '', role_title: '' });
  const [inviteMsg, setInviteMsg] = useState('');
  const [sendingInvite, setSendingInvite] = useState(false);
  const [showTeamPanel, setShowTeamPanel] = useState(false);
  const [teamTab, setTeamTab] = useState('direct'); // 'direct' | 'invite'

  // Direct add state
  const [directForm, setDirectForm] = useState({ email: '', full_name: '', role: 'employee', role_title: '' });
  const [directMsg, setDirectMsg] = useState(null); // null | { type: 'success'|'error', text, creds }
  const [addingDirect, setAddingDirect] = useState(false);

  const token = localStorage.getItem('token');
  const headers = { Authorization: `Bearer ${token}` };
  const jsonHeaders = { ...headers, 'Content-Type': 'application/json' };

  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetch(`${API_BASE_URL}/ceo/overview`, { headers }).then((r) => r.ok ? r.json() : null),
      fetch(`${API_BASE_URL}/ceo/financials`, { headers }).then((r) => r.ok ? r.json() : null),
      fetch(`${API_BASE_URL}/ceo/teams`, { headers }).then((r) => r.ok ? r.json() : null),
      fetch(`${API_BASE_URL}/ceo/clients`, { headers }).then((r) => r.ok ? r.json() : []),
      fetch(`${API_BASE_URL}/ceo/risks`, { headers }).then((r) => r.ok ? r.json() : []),
      fetch(`${API_BASE_URL}/settings/company`, { headers }).then((r) => r.ok ? r.json() : null),
      fetch(`${API_BASE_URL}/invite/talent-pool`, { headers }).then((r) => r.ok ? r.json() : { members: [], pending_invites: [] }),
      fetch(`${API_BASE_URL}/ceo/recent-activity`, { headers }).then((r) => r.ok ? r.json() : []),
    ])
      .then(([overviewData, financialData, teamData, clientData, riskData, companyData, poolData, activityData]) => {
        setOverview(overviewData);
        setFinancials(financialData);
        setTeams(teamData);
        setClients(Array.isArray(clientData) ? clientData : []);
        setRisks(Array.isArray(riskData) ? riskData : []);
        if (companyData) {
          setCompanyProfile(companyData);
          setCompanyForm({
            name: companyData.name || '',
            description: companyData.description || '',
            logo_url: companyData.logo_url || '',
            industry: companyData.industry || '',
            website_url: companyData.website_url || '',
            headquarters: companyData.headquarters || '',
            employee_count_range: companyData.employee_count_range || '',
            founded_year: companyData.founded_year || '',
            contact_email: companyData.contact_email || '',
            contact_phone: companyData.contact_phone || '',
          });
        }
        setTalentPool(poolData || { members: [], pending_invites: [] });
        setRecentActivity(Array.isArray(activityData) ? activityData : []);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [API_BASE_URL]);

  useEffect(() => {
    localStorage.setItem('ceo_mode', String(ceoMode));
  }, [ceoMode]);

  const handleSaveCompany = async () => {
    setSavingCompany(true);
    setCompanyMsg('');
    try {
      const res = await fetch(`${API_BASE_URL}/settings/company`, {
        method: 'PATCH',
        headers: jsonHeaders,
        body: JSON.stringify(companyForm),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Save failed');
      setCompanyProfile(data);
      setCompanyMsg('Company profile saved.');
      if (onCompanyUpdate) onCompanyUpdate(data);
    } catch (err) {
      setCompanyMsg(err.message);
    } finally {
      setSavingCompany(false);
    }
  };

  const handleSendInvite = async (e) => {
    e.preventDefault();
    if (!inviteForm.email.trim()) return;
    setSendingInvite(true);
    setInviteMsg('');
    try {
      const res = await fetch(`${API_BASE_URL}/invite/org`, {
        method: 'POST',
        headers: jsonHeaders,
        body: JSON.stringify({ email: inviteForm.email.trim(), role_title: inviteForm.role_title.trim() || null }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Invite failed');
      setInviteMsg(`Invite sent to ${inviteForm.email}.`);
      setInviteForm({ email: '', role_title: '' });
      // Refresh talent pool
      fetch(`${API_BASE_URL}/invite/talent-pool`, { headers })
        .then((r) => r.ok ? r.json() : null)
        .then((d) => d && setTalentPool(d));
    } catch (err) {
      setInviteMsg(err.message);
    } finally {
      setSendingInvite(false);
    }
  };

  const handleDirectAdd = async (e) => {
    e.preventDefault();
    setAddingDirect(true);
    setDirectMsg(null);
    try {
      const res = await fetch(`${API_BASE_URL}/invite/direct-add`, {
        method: 'POST',
        headers: jsonHeaders,
        body: JSON.stringify(directForm),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to add member');
      setDirectMsg({
        type: 'success',
        text: `${data.full_name} added successfully.`,
        creds: { email: data.email, password: data.temp_password, role: data.role },
      });
      setDirectForm({ email: '', full_name: '', role: 'employee', role_title: '' });
      fetch(`${API_BASE_URL}/invite/talent-pool`, { headers })
        .then((r) => r.ok ? r.json() : null)
        .then((d) => d && setTalentPool(d));
    } catch (err) {
      setDirectMsg({ type: 'error', text: err.message });
    } finally {
      setAddingDirect(false);
    }
  };

  if (ceoMode) {
    return (
      <div>
        <div className="card" style={{ marginBottom: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <p className="eyebrow">Technical View</p>
            <h2 style={{ marginBottom: 6 }}>CEO Technical Console</h2>
            <p style={{ margin: 0 }}>Deep operational detail is enabled for executive review.</p>
          </div>
          <button className="btn btn-secondary" onClick={() => setCeoMode(false)}>Back to Business View</button>
        </div>
        <Dashboard role="admin" />
      </div>
    );
  }

  const healthScore = overview?.health_score || 0;
  const healthColor = healthScore > 75 ? '#15803d' : healthScore >= 50 ? '#ca8a04' : '#dc2626';

  return (
    <div className="dashboard">

      {/* Header */}
      <div className="card full-width" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          {(companyProfile?.logo_url || tenantLogoUrl) && (
            <img
              src={companyProfile?.logo_url || tenantLogoUrl}
              alt="Company logo"
              style={{ height: 52, maxWidth: 160, objectFit: 'contain', borderRadius: 8 }}
            />
          )}
          <div>
            <p className="eyebrow">CEO Dashboard</p>
            <h2 style={{ marginBottom: 8 }}>{companyProfile?.name || currentUser.tenant_name || 'Company Overview'}</h2>
            {companyProfile?.description && (
              <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 4 }}>{companyProfile.description}</p>
            )}
            <div style={{ display: 'inline-flex', gap: 10, alignItems: 'center', background: 'var(--surface-soft)', padding: '8px 12px', borderRadius: 999, marginTop: 8 }}>
              <span>Health Score</span>
              <strong style={{ color: healthColor }}>{healthScore.toFixed(1)}</strong>
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <button className="btn btn-secondary" onClick={() => { setShowAnalytics(false); setShowCompanyEditor((v) => !v); }}>
            {showCompanyEditor ? 'Close Company Editor' : 'Edit Company Profile'}
          </button>
          <button className="btn btn-secondary" onClick={() => { setShowAnalytics(false); setShowTeamPanel((v) => !v); }}>
            {showTeamPanel ? 'Close Team Panel' : 'Team Management'}
          </button>
          <button className="btn btn-secondary" onClick={() => { setShowCompanyEditor(false); setShowTeamPanel(false); setShowAnalytics((v) => !v); }}>
            {showAnalytics ? 'Close Analytics' : 'Business Analytics'}
          </button>
          <button className="btn btn-primary" onClick={() => setCeoMode(true)}>Technical View</button>
        </div>
      </div>

      {/* Company Profile Editor */}
      {showCompanyEditor && (
        <div className="card full-width">
          <p className="eyebrow">Company Settings</p>
          <h2 style={{ marginBottom: 16 }}>Company Profile</h2>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            {[
              { key: 'name', label: 'Company Name', placeholder: 'Acme Corp' },
              { key: 'industry', label: 'Industry', placeholder: 'Software / Technology' },
              { key: 'website_url', label: 'Website', placeholder: 'https://acmecorp.com' },
              { key: 'headquarters', label: 'Headquarters', placeholder: 'Mumbai, India' },
              { key: 'contact_email', label: 'Company Email', placeholder: 'hello@acmecorp.com' },
              { key: 'contact_phone', label: 'Company Phone', placeholder: '+91 98765 43210' },
            ].map(({ key, label, placeholder }) => (
              <div key={key}>
                <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 6 }}>{label}</label>
                <input
                  style={{ width: '100%', padding: '10px 12px', border: '1px solid var(--border-soft)', borderRadius: 8, background: 'var(--surface-soft)', color: 'var(--text-primary)', fontSize: 14, boxSizing: 'border-box' }}
                  value={companyForm[key] || ''}
                  onChange={(e) => setCompanyForm((f) => ({ ...f, [key]: e.target.value }))}
                  placeholder={placeholder}
                />
              </div>
            ))}
            <div>
              <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 6 }}>Team Size</label>
              <select
                style={{ width: '100%', padding: '10px 12px', border: '1px solid var(--border-soft)', borderRadius: 8, background: 'var(--surface-soft)', color: 'var(--text-primary)', fontSize: 14 }}
                value={companyForm.employee_count_range || ''}
                onChange={(e) => setCompanyForm((f) => ({ ...f, employee_count_range: e.target.value }))}
              >
                <option value="">Select size</option>
                {['1–10', '11–50', '51–200', '201–500', '500+'].map(s => <option key={s} value={s}>{s} employees</option>)}
              </select>
            </div>
            <div>
              <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 6 }}>Founded Year</label>
              <input
                type="number"
                min="1900" max="2030"
                style={{ width: '100%', padding: '10px 12px', border: '1px solid var(--border-soft)', borderRadius: 8, background: 'var(--surface-soft)', color: 'var(--text-primary)', fontSize: 14, boxSizing: 'border-box' }}
                value={companyForm.founded_year || ''}
                onChange={(e) => setCompanyForm((f) => ({ ...f, founded_year: e.target.value ? Number(e.target.value) : null }))}
                placeholder="2019"
              />
            </div>
            <div style={{ gridColumn: '1 / -1' }}>
              <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 6 }}>About the Company</label>
              <textarea
                style={{ width: '100%', padding: '10px 12px', border: '1px solid var(--border-soft)', borderRadius: 8, background: 'var(--surface-soft)', color: 'var(--text-primary)', fontSize: 14, resize: 'vertical', minHeight: 80, boxSizing: 'border-box' }}
                value={companyForm.description || ''}
                onChange={(e) => setCompanyForm((f) => ({ ...f, description: e.target.value }))}
                placeholder="What your company does, your mission, and key focus areas."
              />
            </div>
            <div style={{ gridColumn: '1 / -1' }}>
              <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 6 }}>Company Logo URL</label>
              <input
                style={{ width: '100%', padding: '10px 12px', border: '1px solid var(--border-soft)', borderRadius: 8, background: 'var(--surface-soft)', color: 'var(--text-primary)', fontSize: 14, boxSizing: 'border-box' }}
                value={companyForm.logo_url || ''}
                onChange={(e) => setCompanyForm((f) => ({ ...f, logo_url: e.target.value }))}
                placeholder="https://yourdomain.com/logo.png"
              />
              <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>Direct image URL — PNG or SVG, transparent background preferred. Displayed in navbar and dashboard.</p>
            </div>
            {companyForm.logo_url && (
              <div style={{ gridColumn: '1 / -1' }}>
                <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>Logo preview:</p>
                <img
                  src={companyForm.logo_url}
                  alt="Logo preview"
                  style={{ height: 48, maxWidth: 200, objectFit: 'contain', borderRadius: 6, border: '1px solid var(--border-soft)', padding: 6, background: 'var(--surface-soft)' }}
                  onError={(e) => { e.target.style.display = 'none'; }}
                />
              </div>
            )}
            <div style={{ gridColumn: '1 / -1' }}>
              {savingCompany && (
                <div style={{ height: 3, background: 'var(--border-soft)', borderRadius: 2, overflow: 'hidden', marginBottom: 10 }}>
                  <div style={{ height: '100%', width: '40%', background: 'var(--accent)', borderRadius: 2, animation: 'indeterminate 1.4s ease-in-out infinite' }} />
                  <style>{`@keyframes indeterminate { 0%{transform:translateX(-100%)} 100%{transform:translateX(350%)} }`}</style>
                </div>
              )}
              <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                <button className="btn btn-primary" onClick={handleSaveCompany} disabled={savingCompany}>
                  {savingCompany ? 'Saving…' : 'Save Company Profile'}
                </button>
                {companyMsg && (
                  <span style={{ fontSize: 13, color: companyMsg.includes('saved') ? '#15803d' : '#dc2626' }}>{companyMsg}</span>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Team Management Panel */}
      {showTeamPanel && (
        <div className="card full-width">
          <p className="eyebrow">Org Talent Pool</p>
          <h2 style={{ marginBottom: 4 }}>Team Management</h2>

          {/* Tab switcher */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 20, marginTop: 12 }}>
            {[['direct', 'Add Member Directly'], ['invite', 'Send Email Invite']].map(([key, label]) => (
              <button
                key={key}
                className={`btn ${teamTab === key ? 'btn-primary' : 'btn-secondary'}`}
                style={{ fontSize: 13 }}
                onClick={() => { setTeamTab(key); setDirectMsg(null); setInviteMsg(''); }}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Direct Add form */}
          {teamTab === 'direct' && (
            <form onSubmit={handleDirectAdd} style={{ display: 'grid', gap: 14, maxWidth: 560 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>Full Name *</label>
                  <input
                    required
                    style={{ width: '100%', padding: '10px 12px', border: '1px solid var(--border-soft)', borderRadius: 8, background: 'var(--surface-soft)', color: 'var(--text-primary)', fontSize: 14, boxSizing: 'border-box' }}
                    value={directForm.full_name}
                    onChange={(e) => setDirectForm((f) => ({ ...f, full_name: e.target.value }))}
                    placeholder="Priya Sharma"
                  />
                </div>
                <div>
                  <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>Email *</label>
                  <input
                    type="email"
                    required
                    style={{ width: '100%', padding: '10px 12px', border: '1px solid var(--border-soft)', borderRadius: 8, background: 'var(--surface-soft)', color: 'var(--text-primary)', fontSize: 14, boxSizing: 'border-box' }}
                    value={directForm.email}
                    onChange={(e) => setDirectForm((f) => ({ ...f, email: e.target.value }))}
                    placeholder="priya@goldmine.ai"
                  />
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>Role *</label>
                  <select
                    style={{ width: '100%', padding: '10px 12px', border: '1px solid var(--border-soft)', borderRadius: 8, background: 'var(--surface-soft)', color: 'var(--text-primary)', fontSize: 14 }}
                    value={directForm.role}
                    onChange={(e) => setDirectForm((f) => ({ ...f, role: e.target.value }))}
                  >
                    <option value="employee">Employee</option>
                    <option value="admin">Admin</option>
                    <option value="client">Client</option>
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>Job Title (optional)</label>
                  <input
                    style={{ width: '100%', padding: '10px 12px', border: '1px solid var(--border-soft)', borderRadius: 8, background: 'var(--surface-soft)', color: 'var(--text-primary)', fontSize: 14, boxSizing: 'border-box' }}
                    value={directForm.role_title}
                    onChange={(e) => setDirectForm((f) => ({ ...f, role_title: e.target.value }))}
                    placeholder="Senior Developer"
                  />
                </div>
              </div>
              {addingDirect && (
                <div style={{ height: 3, background: 'var(--border-soft)', borderRadius: 2, overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: '40%', background: 'var(--accent)', borderRadius: 2, animation: 'indeterminate 1.4s ease-in-out infinite' }} />
                  <style>{`@keyframes indeterminate{0%{transform:translateX(-100%)}100%{transform:translateX(350%)}}`}</style>
                </div>
              )}
              <button type="submit" className="btn btn-primary" disabled={addingDirect} style={{ width: 'fit-content' }}>
                {addingDirect ? 'Adding…' : 'Add Member'}
              </button>
              {directMsg && (
                <div style={{
                  padding: '12px 16px', borderRadius: 8, fontSize: 13,
                  background: directMsg.type === 'success' ? 'rgba(21,128,61,0.08)' : 'rgba(220,38,38,0.08)',
                  color: directMsg.type === 'success' ? '#15803d' : '#dc2626',
                  border: `1px solid ${directMsg.type === 'success' ? 'rgba(21,128,61,0.2)' : 'rgba(220,38,38,0.2)'}`,
                }}>
                  <strong>{directMsg.text}</strong>
                  {directMsg.creds && (
                    <div style={{ marginTop: 8, fontFamily: 'monospace', display: 'grid', gap: 2 }}>
                      <span>Email: {directMsg.creds.email}</span>
                      <span>Password: {directMsg.creds.password}</span>
                      <span>Role: {directMsg.creds.role}</span>
                      <span style={{ fontSize: 11, opacity: 0.7, marginTop: 4 }}>Share these credentials with the new member. They can change the password after login.</span>
                    </div>
                  )}
                </div>
              )}
            </form>
          )}

          {/* Email Invite form */}
          {teamTab === 'invite' && (
            <>
              <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginBottom: 16 }}>
                Send an invite link to their email. They register using the link.
              </p>
              <form onSubmit={handleSendInvite} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: 10, alignItems: 'end', marginBottom: 24 }}>
                <div>
                  <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>Email Address</label>
                  <input
                    type="email"
                    required
                    style={{ width: '100%', padding: '10px 12px', border: '1px solid var(--border-soft)', borderRadius: 8, background: 'var(--surface-soft)', color: 'var(--text-primary)', fontSize: 14 }}
                    value={inviteForm.email}
                    onChange={(e) => setInviteForm((f) => ({ ...f, email: e.target.value }))}
                    placeholder="new.hire@email.com"
                  />
                </div>
                <div>
                  <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>Role / Title (optional)</label>
                  <input
                    style={{ width: '100%', padding: '10px 12px', border: '1px solid var(--border-soft)', borderRadius: 8, background: 'var(--surface-soft)', color: 'var(--text-primary)', fontSize: 14 }}
                    value={inviteForm.role_title}
                    onChange={(e) => setInviteForm((f) => ({ ...f, role_title: e.target.value }))}
                    placeholder="Senior Developer"
                  />
                </div>
                <button type="submit" className="btn btn-primary" disabled={sendingInvite} style={{ whiteSpace: 'nowrap' }}>
                  {sendingInvite ? 'Sending...' : 'Send Invite'}
                </button>
              </form>
              {inviteMsg && (
                <p style={{ fontSize: 13, color: inviteMsg.includes('sent') ? '#15803d' : '#dc2626', marginBottom: 16 }}>{inviteMsg}</p>
              )}
            </>
          )}

          {/* Pending invites */}
          {talentPool.pending_invites?.length > 0 && (
            <div style={{ marginBottom: 24 }}>
              <h3 style={{ marginBottom: 10, fontSize: 14, color: 'var(--text-secondary)' }}>Pending Invites ({talentPool.pending_invites.length})</h3>
              <div className="list">
                {talentPool.pending_invites.map((inv) => (
                  <div key={inv.id} className="list-item" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <strong>{inv.email}</strong>
                      {inv.role_title && <span style={{ marginLeft: 8, fontSize: 12, color: 'var(--text-secondary)' }}>{inv.role_title}</span>}
                    </div>
                    <span className="status-badge status-pending">Pending</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Current members */}
          <div>
            <h3 style={{ marginBottom: 10, fontSize: 14, color: 'var(--text-secondary)' }}>
              Active Members ({talentPool.members?.length || 0})
            </h3>
            {(talentPool.members?.length || 0) === 0 ? (
              <div className="list-item"><p style={{ color: 'var(--text-secondary)' }}>No team members yet. Send invites to build your talent pool.</p></div>
            ) : (
              <div className="list">
                {talentPool.members.map((m) => (
                  <div key={m.user_id} className="list-item" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <strong>{m.full_name || m.email}</strong>
                      {m.full_name && <span style={{ marginLeft: 6, fontSize: 12, color: 'var(--text-secondary)' }}>{m.email}</span>}
                      {m.role_title && <span style={{ marginLeft: 8, fontSize: 12, color: 'var(--accent)' }}>{m.role_title}</span>}
                    </div>
                    <span className="status-badge status-available">{m.status}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Analytics Panel */}
      {showAnalytics && (
        <div className="card full-width">
          <p className="eyebrow">Business Intelligence</p>
          <h2 style={{ marginBottom: 20 }}>Company Analytics</h2>
          <CeoAnalytics />
        </div>
      )}

      {/* KPI cards */}
      {(loading ? Array.from({ length: 4 }) : [
        { label: 'Total Projects', value: overview?.total_projects, meta: `${overview?.projects_on_track || 0} on track / ${overview?.projects_at_risk || 0} at risk / ${overview?.projects_delayed || 0} delayed` },
        { label: 'Team Utilization', value: `${teams?.overall_utilization_pct || 0}%`, meta: `${overview?.employees_overloaded || 0} overloaded employees` },
        { label: 'Outstanding Payments', value: fmt$(financials?.total_outstanding || 0), meta: `${financials?.overdue_payments?.length || 0} overdue accounts` },
        { label: 'Active Blockers', value: overview?.active_blockers || 0, meta: `${risks.filter((r) => r.type === 'unresolved_blocker').length} critical blockers` },
      ]).map((card, index) => (
        <div key={card?.label || index} className="card">
          {loading ? <div style={{ height: 120, background: 'var(--surface-soft)', borderRadius: 14 }} /> : (
            <>
              <p className="eyebrow">{card.label}</p>
              <h2>{card.value}</h2>
              <p>{card.meta}</p>
            </>
          )}
        </div>
      ))}

      {/* Quick win #2: Live agent activity ticker */}
      {recentActivity.length > 0 && (
        <div className="card full-width" style={{ background: 'linear-gradient(90deg, var(--surface-card) 0%, var(--surface-soft) 100%)', borderLeft: '4px solid var(--accent)' }}>
          <p className="eyebrow">Live Agent Activity</p>
          <h2 style={{ marginBottom: 12 }}>Recent Actions</h2>
          <div style={{ 
            display: 'flex', 
            gap: 0, 
            overflowX: 'auto', 
            paddingBottom: 8,
            scrollBehavior: 'smooth',
          }}>
            {recentActivity.slice(0, 10).map((activity, idx) => (
              <div 
                key={activity.id || idx} 
                style={{ 
                  minWidth: 220, 
                  maxWidth: 280, 
                  padding: '12px 16px', 
                  marginRight: 12, 
                  background: 'var(--surface-card)', 
                  borderRadius: 10, 
                  border: '1px solid var(--border-soft)',
                  flexShrink: 0,
                }}
              >
                <div style={{ fontSize: 11, color: 'var(--accent)', fontWeight: 600, marginBottom: 4 }}>
                  {activity.agent_name || 'Agent'}
                </div>
                <div style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.4 }}>
                  {activity.message}
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 8 }}>
                  {activity.timestamp ? new Date(activity.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : ''}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="card">
        <p className="eyebrow">Risk Flags</p>
        <h2>Immediate Attention</h2>
        <div style={{ maxHeight: 280, overflowY: 'auto', display: 'grid', gap: 10 }}>
          {risks.length === 0 && <p>No active risk flags.</p>}
          {risks.map((risk) => (
            <button
              key={`${risk.type}-${risk.entity_id}`}
              onClick={() => onNavigate('projects')}
              style={{
                textAlign: 'left',
                border: '1px solid var(--border-soft)',
                background: 'var(--surface-soft)',
                borderRadius: 12,
                padding: 14,
                cursor: 'pointer',
              }}
            >
              <strong style={{ color: risk.severity === 'critical' ? '#dc2626' : risk.severity === 'high' ? '#ca8a04' : 'var(--accent)' }}>
                {risk.severity.toUpperCase()}
              </strong>
              <div style={{ marginTop: 6 }}>{risk.message}</div>
            </button>
          ))}
        </div>
      </div>

      <div className="card">
        <p className="eyebrow">Team Utilization</p>
        <h2>Capacity by Team</h2>
        <div style={{ display: 'grid', gap: 12 }}>
          {(teams?.teams || []).map((team) => (
            <div key={team.team_id}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <strong>{team.team_name}</strong>
                <span>{team.avg_utilization_pct}%</span>
              </div>
              <div className="progress">
                <div className="progress-fill" style={{ width: `${Math.min(team.avg_utilization_pct, 100)}%` }} />
              </div>
              <p>{team.project_name} • {team.member_count} members • {team.active_blockers} blockers</p>
            </div>
          ))}
        </div>
      </div>

      <div className="card full-width">
        <p className="eyebrow">Client Status</p>
        <h2>Portfolio Accounts</h2>
        <div style={{ overflowX: 'auto' }}>
          <table className="table">
            <thead>
              <tr>
                <th>Company</th>
                <th>Projects</th>
                <th>Billed</th>
                <th>Paid</th>
                <th>Outstanding</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {clients.map((client) => (
                <tr key={client.client_id}>
                  <td>{client.company_name}</td>
                  <td>{client.active_projects} active / {client.completed_projects} complete</td>
                  <td>{fmt$(client.total_billed)}</td>
                  <td>{fmt$(client.total_paid)}</td>
                  <td>{fmt$(client.outstanding)}</td>
                  <td>{client.payment_status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
