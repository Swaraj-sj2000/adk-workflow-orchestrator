import React, { useState, useRef, useEffect } from 'react';
import { API_BASE_URL } from '../config';
import manhAvatar from '../assets/manh_assistant.png';

const TYPE_ICON = {
  approval_needed: '🔔',
  fyi: 'ℹ️',
  escalation: '⚠️',
  invite_received: '📩',
  accepted: '✅',
  rejection_record: '📋',
};

export default function PlatformAssistant({ currentUser }) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState('chat');
  const [showBubble, setShowBubble] = useState(false);
  const bubbleTimerRef = useRef(null);

  // Notifications
  const [notifications, setNotifications] = useState([]);
  const [unread, setUnread] = useState(0);
  const prevUnreadRef = useRef(0);
  const [actionLoading, setActionLoading] = useState(null);
  const [actionError, setActionError] = useState({});
  const [showReason, setShowReason] = useState({});
  const [reasonText, setReasonText] = useState({});

  // Chat
  const firstName = currentUser?.full_name?.split(' ')[0] || 'there';
  const [messages, setMessages] = useState([{
    role: 'assistant',
    text: `Hi ${firstName}! I'm ManH, your AI assistant. I have live access to your account data — ask me anything about the platform, your projects, your team, or how features work.`,
  }]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  const getHeaders = () => ({ Authorization: `Bearer ${localStorage.getItem('token')}` });
  const getJsonHeaders = () => ({ ...getHeaders(), 'Content-Type': 'application/json' });

  // ── Notification helpers ─────────────────────────────────────────────────────
  const fetchCount = async () => {
    try {
      const r = await fetch(`${API_BASE_URL}/notifications/unread-count`, { headers: getHeaders() });
      if (r.ok) { const d = await r.json(); setUnread(d.count || 0); }
    } catch {}
  };

  const fetchNotifications = async () => {
    try {
      const r = await fetch(`${API_BASE_URL}/notifications`, { headers: getHeaders() });
      if (r.ok) { const d = await r.json(); setNotifications(Array.isArray(d) ? d : []); }
    } catch {}
  };

  const triggerBubble = () => {
    setShowBubble(true);
    if (bubbleTimerRef.current) clearTimeout(bubbleTimerRef.current);
    bubbleTimerRef.current = setTimeout(() => setShowBubble(false), 5000);
  };

  // Poll unread count every 30s
  useEffect(() => {
    fetchCount();
    const iv = setInterval(fetchCount, 30000);
    return () => clearInterval(iv);
  }, []);

  // Show bubble once per session on mount if there are unreads
  useEffect(() => {
    if (!sessionStorage.getItem('mh_bubble_shown')) {
      (async () => {
        try {
          const r = await fetch(`${API_BASE_URL}/notifications/unread-count`, { headers: getHeaders() });
          if (r.ok) {
            const d = await r.json();
            if ((d.count || 0) > 0) {
              sessionStorage.setItem('mh_bubble_shown', '1');
              triggerBubble();
            }
          }
        } catch {}
      })();
    }
    return () => { if (bubbleTimerRef.current) clearTimeout(bubbleTimerRef.current); };
  }, []);

  // Show bubble when new unread notification arrives during session
  useEffect(() => {
    if (prevUnreadRef.current > 0 && unread > prevUnreadRef.current && !open) {
      triggerBubble();
    }
    prevUnreadRef.current = unread;
  }, [unread, open]);

  // Fetch notifications when notifications tab opens
  useEffect(() => {
    if (open && tab === 'notifications') fetchNotifications();
  }, [open, tab]);

  // ── Notification actions ─────────────────────────────────────────────────────
  const markRead = async (id) => {
    await fetch(`${API_BASE_URL}/notifications/${id}/read`, { method: 'PATCH', headers: getHeaders() });
    setNotifications(ns => ns.map(n => n.id === id ? { ...n, read: true } : n));
    setUnread(u => Math.max(0, u - 1));
  };

  const markAll = async () => {
    await fetch(`${API_BASE_URL}/notifications/read-all`, { method: 'PATCH', headers: getJsonHeaders() });
    setNotifications(ns => ns.map(n => ({ ...n, read: true })));
    setUnread(0);
  };

  const getNotificationActionConfig = (notif, positive, reason = '') => {
    const refId = notif.reference_id;
    if (!refId) return null;

    if (notif.type === 'invite_received') {
      return {
        endpoint: `/company/invite-request/${refId}/employee-action`,
        body: { accepted: positive, reason: reason || null },
      };
    }

    if (notif.reference_type === 'team_size_request') {
      return {
        endpoint: `/company/team-size-request/${refId}/ceo-action`,
        body: positive
          ? { approved: true }
          : { approved: false, rejection_reason: reason || null },
      };
    }

    if (currentUser?.role === 'ceo') {
      return {
        endpoint: `/company/invite-request/${refId}/ceo-action`,
        body: { approved: positive, reason: reason || null },
      };
    }

    return {
      endpoint: `/company/invite-request/${refId}/manager-action`,
      body: { approved: positive, reason: reason || null },
    };
  };

  const doInviteAction = async (notif, positive, reason = '') => {
    const actionConfig = getNotificationActionConfig(notif, positive, reason);
    if (!actionConfig) return;

    setActionLoading(notif.id);
    setActionError(s => ({ ...s, [notif.id]: '' }));
    try {
      const r = await fetch(`${API_BASE_URL}${actionConfig.endpoint}`, {
        method: 'POST',
        headers: getJsonHeaders(),
        body: JSON.stringify(actionConfig.body),
      });
      if (r.ok) {
        if (!notif.read) await markRead(notif.id);
        await fetchNotifications();
        await fetchCount();
      } else {
        const data = await r.json().catch(() => null);
        setActionError(s => ({
          ...s,
          [notif.id]: data?.detail || 'This action could not be completed. Please refresh and try again.',
        }));
      }
    } catch {
      setActionError(s => ({
        ...s,
        [notif.id]: 'Network error while submitting this action. Please try again.',
      }));
    }
    setActionLoading(null);
    setShowReason(s => ({ ...s, [notif.id]: false }));
  };

  // ── Chat helpers ─────────────────────────────────────────────────────────────
  useEffect(() => {
    if (open && tab === 'chat' && bottomRef.current) bottomRef.current.scrollIntoView({ behavior: 'smooth' });
  }, [messages, open, tab]);

  useEffect(() => {
    if (open && tab === 'chat' && inputRef.current) inputRef.current.focus();
  }, [open, tab]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;
    const newMessages = [...messages, { role: 'user', text }];
    setMessages(newMessages);
    setInput('');
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/assistant/chat`, {
        method: 'POST',
        headers: getJsonHeaders(),
        body: JSON.stringify({ message: text, history: messages.slice(-10).map(m => ({ role: m.role, text: m.text })) }),
      });
      if (res.ok) {
        const data = await res.json();
        setMessages(prev => [...prev, { role: 'assistant', text: data.reply }]);
      } else {
        setMessages(prev => [...prev, { role: 'assistant', text: "I couldn't process that right now — please try again." }]);
      }
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', text: "Network error — please check your connection." }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  const clearChat = () => setMessages([{
    role: 'assistant',
    text: `Hi ${firstName}! I'm ManH. What can I help you with?`,
  }]);

  return (
    <>
      <style>{`
        @keyframes manhDot { 0%,80%,100%{transform:scale(0.6);opacity:0.4} 40%{transform:scale(1);opacity:1} }
        @keyframes manhSlideUp { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
      `}</style>

      {/* Unread bubble tooltip */}
      {showBubble && !open && (
        <div style={bubbleTooltipStyle}>
          <span
            style={{ cursor: 'pointer', flex: 1, fontSize: 13 }}
            onClick={() => { setOpen(true); setTab('notifications'); setShowBubble(false); }}>
            {unread > 0
              ? `You have ${unread > 99 ? '99+' : unread} unread notification${unread === 1 ? '' : 's'}`
              : 'New notification'}
          </span>
          <button
            onClick={() => setShowBubble(false)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'inherit', fontSize: 14, lineHeight: 1, padding: 0, marginLeft: 10, flexShrink: 0 }}>
            ✕
          </button>
        </div>
      )}

      {/* FAB */}
      <button
        onClick={() => setOpen(o => !o)}
        style={fabStyle}
        title="ManH Assistant & Notifications"
        aria-label="Open ManH Assistant">
        {open ? (
          <span style={{ fontSize: 18, lineHeight: 1, color: '#fff', fontWeight: 700 }}>✕</span>
        ) : (
          <>
            <img src={manhAvatar} alt="ManH" style={{ width: 38, height: 38, borderRadius: '50%', objectFit: 'cover' }} />
            {unread > 0 && (
              <span style={{
                position: 'absolute', top: 2, right: 2,
                background: '#dc2626', color: '#fff',
                borderRadius: '50%', fontSize: 10, fontWeight: 700,
                minWidth: 16, height: 16, lineHeight: 1,
                display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0 3px',
              }}>
                {unread > 99 ? '99+' : unread}
              </span>
            )}
          </>
        )}
      </button>

      {/* Panel */}
      {open && (
        <div style={panelStyle}>
          {/* Tab bar */}
          <div style={{ display: 'flex', borderBottom: '1px solid var(--border-soft)', flexShrink: 0 }}>
            <button onClick={() => setTab('chat')} style={tabBtnStyle(tab === 'chat')}>Chat</button>
            <button onClick={() => { setTab('notifications'); fetchNotifications(); }} style={tabBtnStyle(tab === 'notifications')}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                Notifications
                {unread > 0 && (
                  <span style={{ background: '#dc2626', color: '#fff', borderRadius: 10, fontSize: 10, fontWeight: 700, padding: '1px 5px', lineHeight: 1 }}>
                    {unread > 99 ? '99+' : unread}
                  </span>
                )}
              </span>
            </button>
          </div>

          {/* ── Chat tab ── */}
          {tab === 'chat' && (
            <>
              <div style={chatHeaderStyle}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <img src={manhAvatar} alt="ManH" style={{ width: 32, height: 32, borderRadius: '50%', objectFit: 'cover', flexShrink: 0 }} />
                  <div>
                    <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--text-primary)' }}>Assistant ManH</div>
                    <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Gemini 2.5 Flash · live context</div>
                  </div>
                </div>
                <button onClick={clearChat} style={clearBtnStyle}>Clear</button>
              </div>
              <div style={messagesAreaStyle}>
                {messages.map((msg, i) => (
                  <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start', marginBottom: 12 }}>
                    {msg.role === 'assistant' ? (
                      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 6 }}>
                        <img src={manhAvatar} alt="ManH" style={{ width: 22, height: 22, borderRadius: '50%', objectFit: 'cover', flexShrink: 0, marginBottom: 2 }} />
                        <div style={assistantBubbleStyle}>{formatText(msg.text)}</div>
                      </div>
                    ) : (
                      <div style={userBubbleStyle}>{msg.text}</div>
                    )}
                  </div>
                ))}
                {loading && (
                  <div style={{ display: 'flex', alignItems: 'flex-end', gap: 6, marginBottom: 12 }}>
                    <img src={manhAvatar} alt="ManH" style={{ width: 22, height: 22, borderRadius: '50%', objectFit: 'cover', flexShrink: 0 }} />
                    <div style={{ ...assistantBubbleStyle, opacity: 0.6 }}><TypingDots /></div>
                  </div>
                )}
                <div ref={bottomRef} />
              </div>
              <div style={inputAreaStyle}>
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask ManH anything…"
                  rows={2}
                  style={textareaStyle}
                  disabled={loading}
                />
                <button
                  onClick={sendMessage}
                  disabled={loading || !input.trim()}
                  style={{ ...sendBtnStyle, opacity: loading || !input.trim() ? 0.4 : 1 }}>
                  ↑
                </button>
              </div>
              <div style={{ textAlign: 'center', fontSize: 10, color: 'var(--text-secondary)', opacity: 0.45, paddingBottom: 6 }}>
                Enter to send · Shift+Enter for new line
              </div>
            </>
          )}

          {/* ── Notifications tab ── */}
          {tab === 'notifications' && (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 14px', borderBottom: '1px solid var(--border-soft)', flexShrink: 0 }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>Inbox</span>
                {unread > 0 && (
                  <button onClick={markAll} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 12, color: 'var(--accent)' }}>
                    Mark all read
                  </button>
                )}
              </div>
              <div style={{ overflowY: 'auto', flex: 1 }}>
                {notifications.length === 0 ? (
                  <p style={{ padding: '24px 16px', textAlign: 'center', fontSize: 13, color: 'var(--text-secondary)' }}>
                    No notifications yet.
                  </p>
                ) : notifications.map(n => {
                  const isActionable = ['approval_needed', 'invite_received'].includes(n.type) && n.reference_id && !n.read;
                  const isLoading = actionLoading === n.id;
                  const isShowingReason = !!showReason[n.id];
                  const posLabel = n.type === 'invite_received' ? 'Accept' : 'Approve';
                  const negLabel = n.type === 'invite_received' ? 'Decline' : 'Reject';

                  return (
                    <div
                      key={n.id}
                      onClick={() => !n.read && !isActionable && markRead(n.id)}
                      style={{
                        padding: '12px 14px',
                        borderBottom: '1px solid var(--border-soft)',
                        background: n.read ? 'transparent' : 'rgba(79,70,229,0.05)',
                        cursor: !n.read && !isActionable ? 'pointer' : 'default',
                      }}>
                      <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                        <span style={{ fontSize: 16, flexShrink: 0, marginTop: 1 }}>{TYPE_ICON[n.type] || '🔔'}</span>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontSize: 13, fontWeight: n.read ? 400 : 600, color: 'var(--text-primary)', marginBottom: 2 }}>{n.title}</div>
                          <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.4 }}>{n.body}</div>
                          {n.llm_annotation && (
                            <div style={{ fontSize: 11, color: 'var(--accent)', marginTop: 5, fontStyle: 'italic', lineHeight: 1.4 }}>
                              💡 {n.llm_annotation}
                            </div>
                          )}
                          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4, opacity: 0.7 }}>
                            {n.created_at ? new Date(n.created_at).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' }) : ''}
                          </div>
                          {actionError[n.id] && (
                            <div style={{ fontSize: 11, color: '#dc2626', marginTop: 6, lineHeight: 1.4 }}>
                              {actionError[n.id]}
                            </div>
                          )}

                          {isActionable && !isShowingReason && (
                            <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
                              <button
                                disabled={isLoading}
                                onClick={e => { e.stopPropagation(); doInviteAction(n, true); }}
                                style={{ fontSize: 11, padding: '4px 10px', borderRadius: 6, border: 'none', background: 'var(--accent)', color: '#fff', cursor: isLoading ? 'not-allowed' : 'pointer', opacity: isLoading ? 0.5 : 1 }}>
                                {isLoading ? '…' : posLabel}
                              </button>
                              <button
                                disabled={isLoading}
                                onClick={e => { e.stopPropagation(); setShowReason(s => ({ ...s, [n.id]: true })); }}
                                style={{ fontSize: 11, padding: '4px 10px', borderRadius: 6, border: '1px solid #dc2626', background: 'transparent', color: '#dc2626', cursor: 'pointer' }}>
                                {negLabel}
                              </button>
                            </div>
                          )}

                          {isActionable && isShowingReason && (
                            <div style={{ marginTop: 8 }}>
                              <input
                                placeholder={`Reason (optional)`}
                                value={reasonText[n.id] || ''}
                                onChange={e => setReasonText(s => ({ ...s, [n.id]: e.target.value }))}
                                onClick={e => e.stopPropagation()}
                                style={{ width: '100%', fontSize: 12, padding: '5px 8px', border: '1px solid var(--border-soft)', borderRadius: 6, background: 'var(--surface-soft)', color: 'var(--text-primary)', boxSizing: 'border-box', marginBottom: 6, outline: 'none' }}
                              />
                              <div style={{ display: 'flex', gap: 6 }}>
                                <button
                                  disabled={isLoading}
                                  onClick={e => { e.stopPropagation(); doInviteAction(n, false, reasonText[n.id] || ''); }}
                                  style={{ fontSize: 11, padding: '4px 10px', borderRadius: 6, border: 'none', background: '#dc2626', color: '#fff', cursor: 'pointer', opacity: isLoading ? 0.5 : 1 }}>
                                  {isLoading ? '…' : `Confirm ${negLabel}`}
                                </button>
                                <button
                                  onClick={e => { e.stopPropagation(); setShowReason(s => ({ ...s, [n.id]: false })); }}
                                  style={{ fontSize: 11, padding: '4px 10px', borderRadius: 6, border: '1px solid var(--border-soft)', background: 'transparent', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                                  Cancel
                                </button>
                              </div>
                            </div>
                          )}
                        </div>
                        {!n.read && !isActionable && (
                          <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--accent)', flexShrink: 0, marginTop: 4 }} />
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </>
  );
}

function formatText(text) {
  const lines = text.split('\n');
  return lines.map((line, i) => {
    const parts = line.split(/(\*\*[^*]+\*\*)/g).map((part, j) => {
      if (part.startsWith('**') && part.endsWith('**')) return <strong key={j}>{part.slice(2, -2)}</strong>;
      return part;
    });
    const isBullet = line.trimStart().startsWith('- ') || line.trimStart().startsWith('• ');
    return (
      <span key={i} style={{ display: isBullet ? 'flex' : 'inline', gap: isBullet ? 4 : 0 }}>
        {isBullet && <span style={{ opacity: 0.5, flexShrink: 0 }}>•</span>}
        <span style={{ marginLeft: isBullet ? 2 : 0 }}>{isBullet ? parts.slice(1) : parts}</span>
        {i < lines.length - 1 && <br />}
      </span>
    );
  });
}

function TypingDots() {
  return (
    <span style={{ display: 'inline-flex', gap: 3, alignItems: 'center', height: 16 }}>
      {[0, 1, 2].map(i => (
        <span key={i} style={{
          width: 6, height: 6, borderRadius: '50%',
          background: 'var(--text-secondary)',
          display: 'inline-block',
          animation: `manhDot 1.2s ease-in-out ${i * 0.2}s infinite`,
          opacity: 0.6,
        }} />
      ))}
    </span>
  );
}

const bubbleTooltipStyle = {
  position: 'fixed', bottom: 92, right: 90,
  background: 'var(--surface-card)',
  border: '1px solid var(--border-soft)',
  borderRadius: 10, padding: '10px 14px',
  boxShadow: '0 4px 16px rgba(0,0,0,0.15)',
  zIndex: 8001, maxWidth: 260,
  color: 'var(--text-primary)',
  display: 'flex', alignItems: 'center',
  animation: 'manhSlideUp 0.25s ease',
};

const fabStyle = {
  position: 'fixed', bottom: 28, right: 28,
  width: 52, height: 52, borderRadius: '50%',
  background: 'var(--accent)',
  border: 'none', cursor: 'pointer',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  zIndex: 8000, boxShadow: '0 4px 20px rgba(0,0,0,0.25)',
  transition: 'transform 0.2s, box-shadow 0.2s',
  padding: 0, overflow: 'hidden',
};

const panelStyle = {
  position: 'fixed', bottom: 92, right: 28,
  width: 370, maxHeight: 560,
  background: 'var(--surface-card)',
  border: '1px solid var(--border-soft)',
  borderRadius: 18,
  display: 'flex', flexDirection: 'column',
  zIndex: 8000, boxShadow: '0 16px 50px rgba(0,0,0,0.2)',
  overflow: 'hidden',
};

const tabBtnStyle = (active) => ({
  flex: 1, padding: '10px 12px', border: 'none', cursor: 'pointer',
  background: 'none', fontSize: 13, fontWeight: active ? 600 : 400,
  color: active ? 'var(--accent)' : 'var(--text-secondary)',
  borderBottom: active ? '2px solid var(--accent)' : '2px solid transparent',
  transition: 'all 0.15s', display: 'flex', alignItems: 'center', justifyContent: 'center',
});

const chatHeaderStyle = {
  padding: '10px 14px',
  borderBottom: '1px solid var(--border-soft)',
  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  flexShrink: 0,
};

const clearBtnStyle = {
  background: 'none', border: 'none', cursor: 'pointer',
  color: 'var(--text-secondary)', fontSize: 12,
  padding: '4px 8px', borderRadius: 6,
};

const messagesAreaStyle = {
  flex: 1, overflowY: 'auto',
  padding: '14px 14px 6px',
  display: 'flex', flexDirection: 'column',
};

const userBubbleStyle = {
  maxWidth: '80%', background: 'var(--accent)', color: '#fff',
  borderRadius: '14px 14px 2px 14px',
  padding: '9px 13px', fontSize: 13, lineHeight: 1.5, wordBreak: 'break-word',
};

const assistantBubbleStyle = {
  maxWidth: '85%', background: 'var(--surface-soft)', color: 'var(--text-primary)',
  borderRadius: '14px 14px 14px 2px',
  padding: '9px 13px', fontSize: 13, lineHeight: 1.6, wordBreak: 'break-word',
  border: '1px solid var(--border-soft)',
};

const inputAreaStyle = {
  padding: '10px 10px 6px', borderTop: '1px solid var(--border-soft)',
  display: 'flex', gap: 8, alignItems: 'flex-end', flexShrink: 0,
};

const textareaStyle = {
  flex: 1, resize: 'none',
  border: '1px solid var(--border-soft)', borderRadius: 10,
  padding: '8px 10px', fontSize: 13,
  background: 'var(--surface-soft)', color: 'var(--text-primary)',
  lineHeight: 1.4, outline: 'none', fontFamily: 'inherit',
};

const sendBtnStyle = {
  width: 36, height: 36, borderRadius: '50%',
  background: 'var(--accent)', color: '#fff',
  border: 'none', cursor: 'pointer', fontSize: 18,
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  flexShrink: 0, transition: 'opacity 0.15s',
};
