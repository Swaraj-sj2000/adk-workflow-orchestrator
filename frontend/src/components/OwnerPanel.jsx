import React, { useEffect, useMemo, useState } from 'react';

const BILLING_STATUS = {
  active:         { label: 'Active',         bg: '#2e7d32', border: 'var(--border-soft)' },
  expiring_soon:  { label: 'Expiring Soon',  bg: '#e6a817', border: '#e6a817' },
  grace_period:   { label: 'Grace Period',   bg: '#e65100', border: '#e65100' },
  expired:        { label: 'Expired',        bg: '#b71c1c', border: '#b71c1c' },
  suspended:      { label: 'Suspended',      bg: '#b71c1c', border: '#e53935' },
};

function fmt(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}

function daysUntil(iso) {
  if (!iso) return null;
  const diff = Math.ceil((new Date(iso) - Date.now()) / 86400000);
  return diff;
}

function PlanBadge({ tier }) {
  const colors = {
    trial: '#607d8b', starter: '#1565c0', pro: '#6a1b9a', enterprise: '#bf360c',
  };
  return (
    <span style={{
      fontSize: 10, fontWeight: 700, letterSpacing: '0.07em', textTransform: 'uppercase',
      padding: '2px 8px', borderRadius: 20, background: colors[tier] || '#444', color: '#fff',
    }}>
      {tier}
    </span>
  );
}

function BillingStatusBadge({ status }) {
  const cfg = BILLING_STATUS[status] || BILLING_STATUS.active;
  return (
    <span style={{
      fontSize: 10, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase',
      padding: '2px 10px', borderRadius: 20, background: cfg.bg, color: '#fff',
    }}>
      {cfg.label}
    </span>
  );
}

function LimitDisplay({ label, value }) {
  const display = value === -1 ? '∞' : value;
  return (
    <span style={{ fontSize: 12, opacity: 0.75 }}>
      <strong>{display}</strong> {label}
    </span>
  );
}

export default function OwnerPanel({ currentUser, API_BASE_URL }) {
  const [metrics, setMetrics]           = useState(null);
  const [tenants, setTenants]           = useState([]);
  const [tickets, setTickets]           = useState([]);
  const [statusFilter, setStatusFilter] = useState('open');
  const [responseDrafts, setResponseDrafts] = useState({});
  const [suspendModal, setSuspendModal] = useState(null);
  const [suspendReason, setSuspendReason] = useState('');
  const [loadingId, setLoadingId]       = useState(null);
  const [planSelections, setPlanSelections] = useState({});
  const [planMsg, setPlanMsg] = useState({});
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const token   = localStorage.getItem('token');
  const headers = useMemo(() => ({
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
  }), [token]);

  const fetchData = async () => {
    const [mRes, tRes, tkRes] = await Promise.all([
      fetch(`${API_BASE_URL}/owner/metrics`, { headers }),
      fetch(`${API_BASE_URL}/owner/tenants`, { headers }),
      fetch(`${API_BASE_URL}/owner/support-tickets?status=${statusFilter}`, { headers }),
    ]);
    if (mRes.ok)  setMetrics(await mRes.json());
    if (tRes.ok)  setTenants(await tRes.json());
    if (tkRes.ok) setTickets(await tkRes.json());
  };

  useEffect(() => { fetchData(); }, [statusFilter]);

  const activateTenant = async (tenantId) => {
    setLoadingId(tenantId);
    await fetch(`${API_BASE_URL}/owner/tenants/${tenantId}/activate`, { method: 'POST', headers });
    await fetchData();
    setLoadingId(null);
  };

  const applyPlan = async (tenantId, tenantName) => {
    const tier = planSelections[tenantId];
    if (!tier) return;
    setLoadingId(tenantId);
    const res = await fetch(`${API_BASE_URL}/owner/tenants/${tenantId}/plan`, {
      method: 'PATCH', headers,
      body: JSON.stringify({ plan_tier: tier }),
    });
    if (res.ok) {
      setPlanMsg(prev => ({ ...prev, [tenantId]: `${tenantName} upgraded to ${tier}` }));
      await fetchData();
    } else {
      const d = await res.json();
      setPlanMsg(prev => ({ ...prev, [tenantId]: d.detail || 'Failed' }));
    }
    setLoadingId(null);
  };

  const confirmSuspend = async () => {
    if (!suspendReason.trim()) return;
    setLoadingId(suspendModal.tenantId);
    await fetch(`${API_BASE_URL}/owner/tenants/${suspendModal.tenantId}/suspend`, {
      method: 'POST', headers,
      body: JSON.stringify({ reason: suspendReason.trim() }),
    });
    setSuspendModal(null);
    await fetchData();
    setLoadingId(null);
  };

  const deleteTenant = async (tenantId) => {
    setDeleting(true);
    setLoadingId(tenantId);
    await fetch(`${API_BASE_URL}/owner/tenants/${tenantId}`, { method: 'DELETE', headers });
    setDeleteConfirm(null);
    setDeleting(false);
    await fetchData();
    setLoadingId(null);
  };

  const respondToTicket = async (ticketId) => {
    const response = responseDrafts[ticketId];
    if (!response?.trim()) return;
    await fetch(`${API_BASE_URL}/owner/support-tickets/${ticketId}`, {
      method: 'PATCH', headers, body: JSON.stringify({ response }),
    });
    setResponseDrafts((c) => ({ ...c, [ticketId]: '' }));
    fetchData();
  };

  const metricItems = [
    ['Total Tenants', metrics?.total_tenants],
    ['Active',        metrics?.active_tenants],
    ['Suspended',     metrics?.suspended_tenants],
    ['Trial',         metrics?.trial_tenants],
    ['Paid',          metrics?.paid_tenants],
    ['MRR est.',      metrics?.mrr_estimate != null ? `₹${Math.round(metrics.mrr_estimate).toLocaleString('en-IN')}` : null],
  ];

  return (
    <div className="dashboard">

      {/* ── Suspend Modal ─────────────────────────────────────────── */}
      {suspendModal && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
        }}>
          <div style={{
            background: 'var(--surface-card)', color: 'var(--text-primary)',
            borderRadius: 16, padding: 28,
            width: 440, maxWidth: '90vw',
            boxShadow: '0 8px 40px rgba(0,0,0,0.45)',
            border: '1px solid var(--border-soft)',
          }}>
            <h3 style={{ marginBottom: 6, color: 'var(--text-primary)' }}>Suspend {suspendModal.tenantName}?</h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginBottom: 16 }}>
              All users in this company will be locked out immediately and notified by email.
            </p>
            <textarea
              autoFocus
              placeholder="Reason for suspension (required)…"
              value={suspendReason}
              onChange={(e) => setSuspendReason(e.target.value)}
              style={{
                width: '100%', minHeight: 90, marginBottom: 16,
                background: 'var(--surface-soft)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-soft)',
              }}
            />
            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <button className="btn btn-secondary" onClick={() => setSuspendModal(null)}>Cancel</button>
              <button className="btn btn-danger" disabled={!suspendReason.trim()} onClick={confirmSuspend}>
                Confirm Suspend
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Delete Confirmation Modal ─────────────────────────────── */}
      {deleteConfirm && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: 'var(--surface-card)', borderRadius: 16, padding: 28, width: 420, maxWidth: '90vw', boxShadow: '0 8px 40px rgba(0,0,0,0.45)', border: '2px solid #b71c1c' }}>
            <h3 style={{ marginBottom: 8, color: '#b71c1c' }}>Delete {deleteConfirm.tenantName}?</h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginBottom: 20 }}>
              This permanently deletes the company and <strong>all its data</strong> — users, projects, tasks, teams, and tickets. This cannot be undone.
            </p>
            {deleting && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 8 }}>Deleting all company data…</div>
                <div style={{ height: 6, borderRadius: 4, background: 'var(--border-soft)', overflow: 'hidden' }}>
                  <div style={{
                    height: '100%', borderRadius: 4, background: '#b71c1c',
                    animation: 'indeterminate 1.4s ease-in-out infinite',
                    width: '40%',
                  }} />
                </div>
                <style>{`@keyframes indeterminate { 0%{transform:translateX(-100%)} 100%{transform:translateX(350%)} }`}</style>
              </div>
            )}
            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <button className="btn btn-secondary" disabled={deleting} onClick={() => setDeleteConfirm(null)}>Cancel</button>
              <button className="btn btn-danger" disabled={deleting} onClick={() => deleteTenant(deleteConfirm.tenantId)}>
                {deleting ? 'Deleting…' : 'Yes, Delete Everything'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Platform metrics ──────────────────────────────────────── */}
      <div className="card full-width">
        <p className="eyebrow">Platform Owner</p>
        <h2>{currentUser.full_name || currentUser.email}</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px,1fr))', gap: 12, marginTop: 16 }}>
          {metricItems.map(([label, value]) => (
            <div key={label} className="info-pill">
              <span>{label}</span>
              <strong>{value ?? '—'}</strong>
            </div>
          ))}
        </div>
      </div>

      {/* ── Tenant directory ─────────────────────────────────────── */}
      <div className="card">
        <p className="eyebrow">Tenants</p>
        <h2>Company Directory</h2>
        <div style={{ display: 'grid', gap: 14, marginTop: 12 }}>
          {tenants.map((t) => {
            const bs        = t.billing_status || 'active';
            const bsCfg     = BILLING_STATUS[bs] || BILLING_STATUS.active;
            const isLoading = loadingId === t.tenant_id;
            const daysLeft  = daysUntil(t.subscription_expires_at);
            const graceDays = daysUntil(t.grace_period_ends_at);

            return (
              <div key={t.tenant_id} style={{
                border: `2px solid ${bsCfg.border}`,
                borderRadius: 14, padding: 18,
                background: t.suspended ? 'rgba(229,57,53,0.04)'
                  : bs === 'grace_period' ? 'rgba(230,81,0,0.04)'
                  : bs === 'expiring_soon' ? 'rgba(230,168,23,0.04)'
                  : 'transparent',
                transition: 'border-color 0.25s, background 0.25s',
              }}>

                {/* Top row: name + badges + buttons */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 6 }}>
                      <strong style={{ fontSize: 16 }}>{t.tenant_name}</strong>
                      <PlanBadge tier={t.plan_tier} />
                      <BillingStatusBadge status={bs} />
                    </div>
                    <p style={{ margin: '2px 0', fontSize: 13, opacity: 0.65 }}>
                      {t.user_count} users &nbsp;·&nbsp; {t.project_count} projects
                      &nbsp;·&nbsp; {t.admin_emails?.join(', ') || 'No admins'}
                    </p>
                    {/* Plan limits row */}
                    <div style={{ display: 'flex', gap: 16, marginTop: 8, flexWrap: 'wrap' }}>
                      <LimitDisplay label="teams"    value={t.max_teams} />
                      <LimitDisplay label="projects" value={t.max_projects} />
                      <LimitDisplay label="users"    value={t.max_users} />
                      <LimitDisplay label="AI calls/mo" value={t.max_ai_calls} />
                      <span style={{ fontSize: 12, fontWeight: 700, opacity: 0.75 }}>
                        ₹{(t.price_inr || 0).toLocaleString('en-IN')}{t.billing_days === 180 ? '/6mo' : t.billing_days === 365 ? '/yr' : '/mo'}
                      </span>
                    </div>

                    {/* Subscription timeline */}
                    <div style={{ marginTop: 10, display: 'flex', gap: 20, flexWrap: 'wrap' }}>
                      {t.subscription_expires_at && (
                        <div style={{ fontSize: 12 }}>
                          <span style={{ opacity: 0.55 }}>Subscription expires </span>
                          <strong style={{ color: daysLeft != null && daysLeft < 0 ? '#e53935' : daysLeft != null && daysLeft <= 7 ? '#e6a817' : 'inherit' }}>
                            {fmt(t.subscription_expires_at)}
                            {daysLeft != null && daysLeft >= 0 && ` (${daysLeft}d left)`}
                            {daysLeft != null && daysLeft < 0 && ` (expired ${Math.abs(daysLeft)}d ago)`}
                          </strong>
                        </div>
                      )}
                      {t.grace_period_ends_at && (
                        <div style={{ fontSize: 12 }}>
                          <span style={{ opacity: 0.55 }}>Grace period ends </span>
                          <strong style={{ color: '#e65100' }}>
                            {fmt(t.grace_period_ends_at)}
                            {graceDays != null && graceDays >= 0 && ` (${graceDays}d left)`}
                          </strong>
                        </div>
                      )}
                      {t.next_billing_date && !t.grace_period_ends_at && (
                        <div style={{ fontSize: 12 }}>
                          <span style={{ opacity: 0.55 }}>Next billing </span>
                          <strong>{fmt(t.next_billing_date)}</strong>
                        </div>
                      )}
                    </div>

                    {/* Suspension reason */}
                    {t.suspended && t.suspension_reason && (
                      <p style={{ margin: '8px 0 0', fontSize: 13, color: '#e53935' }}>
                        Suspended: {t.suspension_reason}
                        {t.suspended_at && ` · ${fmt(t.suspended_at)}`}
                      </p>
                    )}

                    {/* Grace period warning banner */}
                    {bs === 'grace_period' && (
                      <p style={{ margin: '8px 0 0', fontSize: 13, color: '#e65100', fontWeight: 600 }}>
                        ⚠ Subscription expired — auto-suspend in {graceDays}d if not renewed
                      </p>
                    )}
                  </div>

                  {/* Plan setter + suspend/activate */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8, minWidth: 160 }}>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <select
                        value={planSelections[t.tenant_id] || t.plan_tier || 'trial'}
                        onChange={(e) => setPlanSelections(prev => ({ ...prev, [t.tenant_id]: e.target.value }))}
                        style={{ flex: 1, fontSize: 13, padding: '4px 6px', borderRadius: 6, border: '1px solid var(--border-soft)', background: 'var(--surface-soft)', color: 'var(--text-primary)' }}
                      >
                        <option value="trial">Trial</option>
                        <option value="starter">Starter</option>
                        <option value="pro">Pro</option>
                        <option value="enterprise">Enterprise</option>
                      </select>
                      <button
                        className="btn btn-primary"
                        disabled={isLoading}
                        onClick={() => applyPlan(t.tenant_id, t.tenant_name)}
                        style={{ fontSize: 12, padding: '4px 10px', whiteSpace: 'nowrap' }}
                      >
                        {isLoading ? '…' : 'Apply'}
                      </button>
                    </div>
                    {planMsg[t.tenant_id] && <p style={{ fontSize: 11, color: '#15803d', margin: 0 }}>{planMsg[t.tenant_id]}</p>}
                    {t.suspended ? (
                      <button
                        className="btn btn-secondary"
                        disabled={isLoading}
                        onClick={() => activateTenant(t.tenant_id)}
                        style={{ width: '100%', borderColor: '#2e7d32', color: '#2e7d32' }}
                      >
                        {isLoading ? '…' : '▶ Activate'}
                      </button>
                    ) : (
                      <button
                        className="btn btn-danger"
                        disabled={isLoading}
                        onClick={() => setSuspendModal({ tenantId: t.tenant_id, tenantName: t.tenant_name })}
                        style={{ width: '100%' }}
                      >
                        {isLoading ? '…' : '⏸ Suspend'}
                      </button>
                    )}
                    <button
                      disabled={isLoading}
                      onClick={() => setDeleteConfirm({ tenantId: t.tenant_id, tenantName: t.tenant_name })}
                      style={{ width: '100%', background: 'none', border: '1px solid #b71c1c', color: '#b71c1c', borderRadius: 8, padding: '4px 0', fontSize: 12, cursor: 'pointer' }}
                    >
                      Delete Company
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Support inbox ────────────────────────────────────────── */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <p className="eyebrow">Support Inbox</p>
            <h2>Tenant Tickets</h2>
          </div>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="open">Open</option>
            <option value="in_progress">In Progress</option>
            <option value="resolved">Resolved</option>
          </select>
        </div>

        <div style={{ display: 'grid', gap: 12, marginTop: 12 }}>
          {tickets.length === 0 && (
            <p style={{ opacity: 0.5, textAlign: 'center', padding: 24 }}>
              No {statusFilter} tickets.
            </p>
          )}
          {tickets.map((ticket) => (
            <div key={ticket.id} style={{
              border: '1px solid var(--border-soft)', borderRadius: 12, padding: 16,
              borderLeft: `4px solid ${ticket.status === 'resolved' ? '#2e7d32' : '#e6a817'}`,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <strong>{ticket.tenant_name} · {ticket.subject}</strong>
                <span style={{
                  fontSize: 11, fontWeight: 700, textTransform: 'uppercase',
                  padding: '2px 8px', borderRadius: 20,
                  background: ticket.status === 'resolved' ? '#2e7d32' : '#e6a817', color: '#fff',
                }}>
                  {ticket.status}
                </span>
              </div>
              <p style={{ margin: '2px 0', fontSize: 13, opacity: 0.6 }}>
                {ticket.user_full_name || ticket.user_email}
              </p>
              <p style={{ margin: '10px 0', fontSize: 14 }}>{ticket.body}</p>
              {ticket.admin_response && (
                <div style={{
                  background: 'rgba(46,125,50,0.08)', borderRadius: 8,
                  padding: '10px 14px', marginBottom: 10, borderLeft: '3px solid #2e7d32',
                }}>
                  <p style={{ fontSize: 12, opacity: 0.6, marginBottom: 4 }}>Your response</p>
                  <p style={{ fontSize: 13, margin: 0 }}>{ticket.admin_response}</p>
                </div>
              )}
              {ticket.status !== 'resolved' && (
                <>
                  <textarea
                    value={responseDrafts[ticket.id] || ''}
                    onChange={(e) => setResponseDrafts((c) => ({ ...c, [ticket.id]: e.target.value }))}
                    placeholder="Write a response…"
                    style={{ width: '100%', minHeight: 90, marginTop: 8 }}
                  />
                  <button
                    className="btn btn-primary"
                    style={{ marginTop: 8 }}
                    disabled={!responseDrafts[ticket.id]?.trim()}
                    onClick={() => respondToTicket(ticket.id)}
                  >
                    Send Response
                  </button>
                </>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
