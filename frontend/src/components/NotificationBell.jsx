import React, { useEffect, useRef, useState } from 'react';

const TYPE_ICON = {
  approval_needed: '🔔',
  fyi: 'ℹ️',
  escalation: '⚠️',
  invite_received: '📩',
  accepted: '✅',
  rejection_record: '📋',
};

export default function NotificationBell({ API_BASE_URL }) {
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unread, setUnread] = useState(0);
  const ref = useRef(null);
  const token = localStorage.getItem('token');
  const headers = { Authorization: `Bearer ${token}` };
  const jsonHeaders = { ...headers, 'Content-Type': 'application/json' };

  const fetchCount = () => {
    fetch(`${API_BASE_URL}/notifications/unread-count`, { headers })
      .then(r => r.ok ? r.json() : { count: 0 })
      .then(d => setUnread(d.count || 0))
      .catch(() => {});
  };

  const fetchAll = () => {
    fetch(`${API_BASE_URL}/notifications`, { headers })
      .then(r => r.ok ? r.json() : [])
      .then(d => setNotifications(Array.isArray(d) ? d : []))
      .catch(() => {});
  };

  useEffect(() => {
    fetchCount();
    const interval = setInterval(fetchCount, 30000);
    return () => clearInterval(interval);
  }, [API_BASE_URL]);

  useEffect(() => {
    if (!open) return;
    fetchAll();
  }, [open]);

  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const markRead = async (id) => {
    await fetch(`${API_BASE_URL}/notifications/${id}/read`, { method: 'PATCH', headers });
    setNotifications(n => n.map(x => x.id === id ? { ...x, read: true } : x));
    setUnread(u => Math.max(0, u - 1));
  };

  const markAll = async () => {
    await fetch(`${API_BASE_URL}/notifications/read-all`, { method: 'PATCH', headers: jsonHeaders });
    setNotifications(n => n.map(x => ({ ...x, read: true })));
    setUnread(0);
  };

  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-block' }}>
      <button
        onClick={() => setOpen(v => !v)}
        style={{
          background: 'none', border: 'none', cursor: 'pointer',
          position: 'relative', padding: '6px 8px', fontSize: 20,
          color: 'var(--text-primary)',
        }}
        title="Notifications"
      >
        🔔
        {unread > 0 && (
          <span style={{
            position: 'absolute', top: 2, right: 2,
            background: '#dc2626', color: '#fff',
            borderRadius: '50%', fontSize: 10, fontWeight: 700,
            minWidth: 16, height: 16, display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: '0 3px', lineHeight: 1,
          }}>
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div style={{
          position: 'absolute', right: 0, top: '110%', zIndex: 1000,
          width: 360, maxHeight: 480, overflowY: 'auto',
          background: 'var(--surface-card)', border: '1px solid var(--border-soft)',
          borderRadius: 12, boxShadow: '0 8px 32px rgba(0,0,0,0.18)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', borderBottom: '1px solid var(--border-soft)' }}>
            <strong style={{ fontSize: 14 }}>Notifications</strong>
            {unread > 0 && (
              <button onClick={markAll} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 12, color: 'var(--accent)' }}>
                Mark all read
              </button>
            )}
          </div>

          {notifications.length === 0 ? (
            <p style={{ padding: '24px 16px', fontSize: 13, color: 'var(--text-secondary)', textAlign: 'center' }}>No notifications yet.</p>
          ) : (
            notifications.map(n => (
              <div
                key={n.id}
                onClick={() => !n.read && markRead(n.id)}
                style={{
                  padding: '12px 16px', borderBottom: '1px solid var(--border-soft)',
                  background: n.read ? 'transparent' : 'rgba(var(--accent-rgb, 79,70,229), 0.06)',
                  cursor: n.read ? 'default' : 'pointer',
                  display: 'flex', gap: 10, alignItems: 'flex-start',
                }}
              >
                <span style={{ fontSize: 16, flexShrink: 0, marginTop: 1 }}>{TYPE_ICON[n.type] || '🔔'}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: n.read ? 400 : 600, color: 'var(--text-primary)', marginBottom: 2 }}>{n.title}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.4 }}>{n.body}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4, opacity: 0.7 }}>
                    {n.created_at ? new Date(n.created_at).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' }) : ''}
                  </div>
                </div>
                {!n.read && <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--accent)', flexShrink: 0, marginTop: 4 }} />}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
