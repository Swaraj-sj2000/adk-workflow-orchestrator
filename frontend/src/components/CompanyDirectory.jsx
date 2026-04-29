import React, { useEffect, useState } from 'react';

export default function CompanyDirectory({ API_BASE_URL, currentUser, onInviteSent }) {
  const [members, setMembers] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);
  const [inviteState, setInviteState] = useState({}); // { [profileId]: { open, role, sending, msg } }

  const token = localStorage.getItem('token');
  const headers = { Authorization: `Bearer ${token}` };
  const jsonHeaders = { ...headers, 'Content-Type': 'application/json' };

  const fetchDirectory = () => {
    setLoading(true);
    fetch(`${API_BASE_URL}/company/directory`, { headers })
      .then(r => r.ok ? r.json() : [])
      .then(d => setMembers(Array.isArray(d) ? d : []))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchDirectory(); }, [API_BASE_URL]);

  const filtered = members.filter(m =>
    !search.trim() ||
    m.name.toLowerCase().includes(search.toLowerCase()) ||
    m.email.toLowerCase().includes(search.toLowerCase()) ||
    (m.role_title || '').toLowerCase().includes(search.toLowerCase())
  );

  const toggleInvite = (profileId) => {
    setInviteState(s => ({
      ...s,
      [profileId]: s[profileId]?.open
        ? { open: false }
        : { open: true, role: '', sending: false, msg: null },
    }));
  };

  const sendInvite = async (profileId) => {
    const state = inviteState[profileId] || {};
    setInviteState(s => ({ ...s, [profileId]: { ...s[profileId], sending: true, msg: null } }));
    try {
      const res = await fetch(`${API_BASE_URL}/company/invite-request`, {
        method: 'POST', headers: jsonHeaders,
        body: JSON.stringify({ employee_profile_id: profileId, proposed_role: state.role || null }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to send invite');
      setInviteState(s => ({ ...s, [profileId]: { open: false, msg: { type: 'ok', text: 'Invite sent.' } } }));
      fetchDirectory();
      if (onInviteSent) onInviteSent();
    } catch (err) {
      setInviteState(s => ({ ...s, [profileId]: { ...s[profileId], sending: false, msg: { type: 'err', text: err.message } } }));
    }
  };

  const statusColor = { available: '#15803d', busy: '#ca8a04', on_leave: '#dc2626' };

  return (
    <div>
      <input
        value={search}
        onChange={e => setSearch(e.target.value)}
        placeholder="Search by name, email or title…"
        style={{
          width: '100%', padding: '10px 14px', border: '1px solid var(--border-soft)',
          borderRadius: 8, background: 'var(--surface-soft)', color: 'var(--text-primary)',
          fontSize: 14, boxSizing: 'border-box', marginBottom: 14,
        }}
      />

      {loading && <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Loading directory…</p>}

      <div style={{ display: 'grid', gap: 8 }}>
        {filtered.map(m => {
          const isSelf = m.user_id === currentUser?.id;
          const inv = inviteState[m.profile_id] || {};
          const hasPending = !!m.pending_invite;

          return (
            <div key={m.user_id} style={{
              padding: '12px 14px', border: '1px solid var(--border-soft)',
              borderRadius: 10, background: 'var(--surface-soft)',
              display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap',
            }}>
              {/* Avatar initial */}
              <div style={{
                width: 36, height: 36, borderRadius: '50%', background: 'var(--accent)',
                color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontWeight: 700, fontSize: 14, flexShrink: 0,
              }}>
                {(m.name || '?')[0].toUpperCase()}
              </div>

              {/* Info */}
              <div style={{ flex: 1, minWidth: 120 }}>
                <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--text-primary)' }}>{m.name}</div>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{m.email}</div>
                {m.role_title && <div style={{ fontSize: 11, color: 'var(--accent)', marginTop: 1 }}>{m.role_title}</div>}
              </div>

              {/* Manager badge */}
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', textAlign: 'right', minWidth: 110 }}>
                {m.manager
                  ? <span>Under <strong>{m.manager.name.split(' ')[0]}</strong></span>
                  : <span style={{ color: '#ca8a04' }}>Unassigned</span>
                }
                <div style={{ marginTop: 2, color: statusColor[m.availability_status] || 'var(--text-secondary)', fontSize: 11 }}>
                  ● {m.availability_status || 'unknown'}
                </div>
              </div>

              {/* Invite button / status */}
              {!isSelf && (
                <div style={{ minWidth: 110, textAlign: 'right' }}>
                  {hasPending ? (
                    <span style={{ fontSize: 12, color: '#ca8a04', fontWeight: 500 }}>
                      Invite {m.pending_invite.status.replace('pending_', '⏳ ').replace('_', ' ')}
                    </span>
                  ) : inv.msg?.type === 'ok' ? (
                    <span style={{ fontSize: 12, color: '#15803d' }}>✓ {inv.msg.text}</span>
                  ) : (
                    <button
                      className="btn btn-secondary"
                      style={{ fontSize: 12, padding: '5px 12px' }}
                      onClick={() => toggleInvite(m.profile_id)}
                    >
                      {inv.open ? 'Cancel' : 'Send Invite'}
                    </button>
                  )}
                </div>
              )}

              {/* Inline invite form */}
              {inv.open && !isSelf && (
                <div style={{ width: '100%', display: 'flex', gap: 8, alignItems: 'center', marginTop: 4, paddingTop: 10, borderTop: '1px solid var(--border-soft)' }}>
                  <input
                    value={inv.role || ''}
                    onChange={e => setInviteState(s => ({ ...s, [m.profile_id]: { ...s[m.profile_id], role: e.target.value } }))}
                    placeholder="Role offered (e.g. Backend Lead)"
                    style={{ flex: 1, padding: '8px 10px', border: '1px solid var(--border-soft)', borderRadius: 6, background: 'var(--surface-soft)', color: 'var(--text-primary)', fontSize: 13 }}
                  />
                  <button
                    className="btn btn-primary"
                    style={{ fontSize: 12, padding: '8px 14px', whiteSpace: 'nowrap' }}
                    disabled={inv.sending}
                    onClick={() => sendInvite(m.profile_id)}
                  >
                    {inv.sending ? 'Sending…' : 'Confirm Invite'}
                  </button>
                  {inv.msg?.type === 'err' && <span style={{ fontSize: 12, color: '#dc2626' }}>{inv.msg.text}</span>}
                </div>
              )}
            </div>
          );
        })}

        {!loading && filtered.length === 0 && (
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', textAlign: 'center', padding: 16 }}>
            {search ? 'No members match your search.' : 'No members in the directory yet.'}
          </p>
        )}
      </div>
    </div>
  );
}
