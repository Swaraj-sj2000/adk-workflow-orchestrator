import React, { useEffect, useMemo, useState } from 'react';

export default function OwnerPanel({ currentUser, API_BASE_URL }) {
  const [metrics, setMetrics] = useState(null);
  const [tenants, setTenants] = useState([]);
  const [tickets, setTickets] = useState([]);
  const [statusFilter, setStatusFilter] = useState('open');
  const [responseDrafts, setResponseDrafts] = useState({});

  const token = localStorage.getItem('token');
  const headers = useMemo(() => ({
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
  }), [token]);

  const fetchData = async () => {
    const [metricsRes, tenantsRes, ticketsRes] = await Promise.all([
      fetch(`${API_BASE_URL}/owner/metrics`, { headers }),
      fetch(`${API_BASE_URL}/owner/tenants`, { headers }),
      fetch(`${API_BASE_URL}/owner/support-tickets?status=${statusFilter}`, { headers }),
    ]);
    if (metricsRes.ok) setMetrics(await metricsRes.json());
    if (tenantsRes.ok) setTenants(await tenantsRes.json());
    if (ticketsRes.ok) setTickets(await ticketsRes.json());
  };

  useEffect(() => {
    fetchData();
  }, [statusFilter]);

  const mutateTenant = async (tenantId, action) => {
    const options = { method: 'POST', headers };
    if (action === 'suspend') {
      const reason = window.prompt('Suspension reason?');
      if (!reason) return;
      options.body = JSON.stringify({ reason });
    }
    await fetch(`${API_BASE_URL}/owner/tenants/${tenantId}/${action}`, options);
    fetchData();
  };

  const respondToTicket = async (ticketId) => {
    const response = responseDrafts[ticketId];
    if (!response) return;
    await fetch(`${API_BASE_URL}/owner/support-tickets/${ticketId}`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify({ response }),
    });
    setResponseDrafts((current) => ({ ...current, [ticketId]: '' }));
    fetchData();
  };

  return (
    <div className="dashboard">
      <div className="card full-width">
        <p className="eyebrow">Platform Owner</p>
        <h2>{currentUser.full_name || currentUser.email}</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 12, marginTop: 16 }}>
          {[
            ['Total Tenants', metrics?.total_tenants],
            ['Active', metrics?.active_tenants],
            ['Suspended', metrics?.suspended_tenants],
            ['Trial', metrics?.trial_tenants],
            ['Paid', metrics?.paid_tenants],
            ['MRR', metrics?.mrr_estimate],
          ].map(([label, value]) => (
            <div key={label} className="info-pill">
              <span>{label}</span>
              <strong>{value ?? '—'}</strong>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <p className="eyebrow">Tenants</p>
        <h2>Company Directory</h2>
        <div style={{ display: 'grid', gap: 12 }}>
          {tenants.map((tenant) => (
            <div key={tenant.tenant_id} style={{ border: '1px solid var(--border-soft)', borderRadius: 12, padding: 14 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                <div>
                  <strong>{tenant.tenant_name}</strong>
                  <p>{tenant.plan_tier} • {tenant.user_count} users • {tenant.project_count} projects</p>
                  <p>{tenant.admin_emails?.join(', ') || 'No admins listed'}</p>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button className="btn btn-secondary" onClick={() => mutateTenant(tenant.tenant_id, 'activate')}>Activate</button>
                  <button className="btn btn-danger" onClick={() => mutateTenant(tenant.tenant_id, 'suspend')}>Suspend</button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <p className="eyebrow">Support Inbox</p>
            <h2>Tenant Tickets</h2>
          </div>
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="open">Open</option>
            <option value="in_progress">In Progress</option>
            <option value="resolved">Resolved</option>
          </select>
        </div>
        <div style={{ display: 'grid', gap: 12, marginTop: 12 }}>
          {tickets.map((ticket) => (
            <div key={ticket.id} style={{ border: '1px solid var(--border-soft)', borderRadius: 12, padding: 14 }}>
              <strong>{ticket.tenant_name} • {ticket.subject}</strong>
              <p>{ticket.user_full_name || ticket.user_email}</p>
              <p>{ticket.body}</p>
              <textarea
                value={responseDrafts[ticket.id] || ''}
                onChange={(event) => setResponseDrafts((current) => ({ ...current, [ticket.id]: event.target.value }))}
                placeholder="Write a response"
                style={{ width: '100%', minHeight: 100, marginTop: 10 }}
              />
              <div style={{ marginTop: 10 }}>
                <button className="btn btn-primary" onClick={() => respondToTicket(ticket.id)}>Send Response</button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
