import React, { useState, useRef, useEffect } from 'react';
import { API_BASE_URL } from '../config';
import manhAvatar from '../assets/manh_assistant.png';

export default function PlatformAssistant({ currentUser }) {
  const [open, setOpen] = useState(false);
  const firstName = currentUser?.full_name?.split(' ')[0] || 'there';
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      text: `Hi ${firstName}! I'm ManH, your AI assistant. I have live access to your account data — ask me anything about the platform, your projects, your team, or how features work.`,
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);
  const inputRef  = useRef(null);

  useEffect(() => {
    if (open && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, open]);

  useEffect(() => {
    if (open && inputRef.current) inputRef.current.focus();
  }, [open]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const newMessages = [...messages, { role: 'user', text }];
    setMessages(newMessages);
    setInput('');
    setLoading(true);

    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_BASE_URL}/assistant/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          message: text,
          history: messages.slice(-10).map(m => ({ role: m.role, text: m.text })),
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setMessages(prev => [...prev, { role: 'assistant', text: data.reply }]);
      } else {
        setMessages(prev => [...prev, { role: 'assistant', text: "I couldn't process that right now — please try again in a moment." }]);
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
      {/* Floating bubble */}
      <button onClick={() => setOpen(o => !o)} style={bubbleStyle} title="Assistant ManH" aria-label="Open Assistant ManH">
        {open ? (
          <span style={{ fontSize: 18, lineHeight: 1, color: '#fff', fontWeight: 700 }}>✕</span>
        ) : (
          <img src={manhAvatar} alt="ManH" style={{ width: 38, height: 38, borderRadius: '50%', objectFit: 'cover' }} />
        )}
      </button>

      {/* Chat panel */}
      {open && (
        <div style={panelStyle}>
          {/* Header */}
          <div style={headerStyle}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <img src={manhAvatar} alt="ManH" style={{ width: 36, height: 36, borderRadius: '50%', objectFit: 'cover', flexShrink: 0 }} />
              <div>
                <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--text-primary)' }}>Assistant ManH</div>
                <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Gemini 2.5 Flash · live account context</div>
              </div>
            </div>
            <button onClick={clearChat} style={clearBtnStyle} title="Clear conversation">
              Clear
            </button>
          </div>

          {/* Messages */}
          <div style={messagesAreaStyle}>
            {messages.map((msg, i) => (
              <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start', marginBottom: 12 }}>
                {msg.role === 'assistant' && (
                  <div style={{ display: 'flex', alignItems: 'flex-end', gap: 6 }}>
                    <img src={manhAvatar} alt="ManH" style={{ width: 22, height: 22, borderRadius: '50%', objectFit: 'cover', flexShrink: 0, marginBottom: 2 }} />
                    <div style={assistantBubble}>{formatText(msg.text)}</div>
                  </div>
                )}
                {msg.role === 'user' && (
                  <div style={userBubble}>{msg.text}</div>
                )}
              </div>
            ))}
            {loading && (
              <div style={{ display: 'flex', alignItems: 'flex-end', gap: 6, marginBottom: 12 }}>
                <img src={manhAvatar} alt="ManH" style={{ width: 22, height: 22, borderRadius: '50%', objectFit: 'cover', flexShrink: 0 }} />
                <div style={{ ...assistantBubble, opacity: 0.6 }}><TypingDots /></div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
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
              style={{ ...sendBtnStyle, opacity: loading || !input.trim() ? 0.4 : 1 }}
            >
              ↑
            </button>
          </div>
          <div style={{ textAlign: 'center', fontSize: 10, color: 'var(--text-secondary)', opacity: 0.45, paddingBottom: 6 }}>
            Enter to send · Shift+Enter for new line
          </div>
        </div>
      )}
    </>
  );
}

function formatText(text) {
  // Render markdown-lite: **bold**, bullet points, newlines
  const lines = text.split('\n');
  return lines.map((line, i) => {
    const parts = line.split(/(\*\*[^*]+\*\*)/g).map((part, j) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={j}>{part.slice(2, -2)}</strong>;
      }
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
      <style>{`@keyframes manhDot { 0%,80%,100%{transform:scale(0.6);opacity:0.4} 40%{transform:scale(1);opacity:1} }`}</style>
    </span>
  );
}

const bubbleStyle = {
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
  width: 370, maxHeight: 540,
  background: 'var(--surface-card)',
  border: '1px solid var(--border-soft)',
  borderRadius: 18,
  display: 'flex', flexDirection: 'column',
  zIndex: 8000, boxShadow: '0 16px 50px rgba(0,0,0,0.2)',
  overflow: 'hidden',
};

const headerStyle = {
  padding: '12px 14px',
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

const userBubble = {
  maxWidth: '80%',
  background: 'var(--accent)', color: '#fff',
  borderRadius: '14px 14px 2px 14px',
  padding: '9px 13px', fontSize: 13, lineHeight: 1.5, wordBreak: 'break-word',
};

const assistantBubble = {
  maxWidth: '85%',
  background: 'var(--surface-soft)', color: 'var(--text-primary)',
  borderRadius: '14px 14px 14px 2px',
  padding: '9px 13px', fontSize: 13, lineHeight: 1.6, wordBreak: 'break-word',
  border: '1px solid var(--border-soft)',
};

const inputAreaStyle = {
  padding: '10px 10px 6px',
  borderTop: '1px solid var(--border-soft)',
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
