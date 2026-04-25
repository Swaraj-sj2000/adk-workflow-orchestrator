import React, { useState, useRef, useEffect } from 'react';
import { API_BASE_URL } from '../config';

const SOURCE_LABEL = { llm: '✦ AI', keyword: '⌘ Quick answer', fallback: '💡 Tip' };

export default function PlatformAssistant({ currentUser }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      text: `Hi ${currentUser?.full_name?.split(' ')[0] || 'there'}! 👋 I'm your platform assistant. Ask me anything about navigating the platform, your role, or how features work.`,
      source: null,
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (open && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, open]);

  useEffect(() => {
    if (open && inputRef.current) {
      inputRef.current.focus();
    }
  }, [open]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;

    setMessages((prev) => [...prev, { role: 'user', text }]);
    setInput('');
    setLoading(true);

    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_BASE_URL}/assistant/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ message: text }),
      });

      if (res.ok) {
        const data = await res.json();
        setMessages((prev) => [...prev, { role: 'assistant', text: data.reply, source: data.source }]);
      } else {
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', text: "Sorry, I couldn't process that right now. Try again in a moment.", source: null },
        ]);
      }
    } catch (_) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', text: "Network error — please check your connection.", source: null },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <>
      {/* Floating bubble */}
      <button
        onClick={() => setOpen((o) => !o)}
        style={bubbleStyle}
        title="Platform Assistant"
        aria-label="Open Platform Assistant"
      >
        {open ? (
          <span style={{ fontSize: 20, lineHeight: 1 }}>✕</span>
        ) : (
          <span style={{ fontSize: 22, lineHeight: 1 }}>🤖</span>
        )}
      </button>

      {/* Chat panel */}
      {open && (
        <div style={panelStyle}>
          {/* Header */}
          <div style={headerStyle}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 20 }}>🤖</span>
              <div>
                <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--text-primary)' }}>Platform Assistant</div>
                <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>AI-powered · always here to help</div>
              </div>
            </div>
            <button
              onClick={() => setMessages([{
                role: 'assistant',
                text: `Hi ${currentUser?.full_name?.split(' ')[0] || 'there'}! 👋 How can I help you?`,
                source: null,
              }])}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-secondary)', fontSize: 12, padding: '4px 8px', borderRadius: 6 }}
              title="Clear chat"
            >
              Clear
            </button>
          </div>

          {/* Messages */}
          <div style={messagesAreaStyle}>
            {messages.map((msg, i) => (
              <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start', marginBottom: 12 }}>
                <div style={msg.role === 'user' ? userBubble : assistantBubble}>
                  {msg.text}
                </div>
                {msg.role === 'assistant' && msg.source && (
                  <span style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 3, marginLeft: 4, opacity: 0.7 }}>
                    {SOURCE_LABEL[msg.source] || msg.source}
                  </span>
                )}
              </div>
            ))}
            {loading && (
              <div style={{ display: 'flex', alignItems: 'flex-start', marginBottom: 12 }}>
                <div style={{ ...assistantBubble, opacity: 0.6 }}>
                  <TypingDots />
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div style={inputAreaStyle}>
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask anything about the platform…"
              rows={2}
              style={textareaStyle}
              disabled={loading}
            />
            <button
              onClick={sendMessage}
              disabled={loading || !input.trim()}
              style={{
                ...sendBtnStyle,
                opacity: loading || !input.trim() ? 0.4 : 1,
              }}
            >
              ↑
            </button>
          </div>
          <div style={{ textAlign: 'center', fontSize: 10, color: 'var(--text-secondary)', opacity: 0.5, paddingBottom: 6 }}>
            Powered by Gemini 2.5 Flash · Enter to send
          </div>
        </div>
      )}
    </>
  );
}

function TypingDots() {
  return (
    <span style={{ display: 'inline-flex', gap: 3, alignItems: 'center', height: 16 }}>
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          style={{
            width: 6, height: 6, borderRadius: '50%',
            background: 'var(--text-secondary)',
            display: 'inline-block',
            animation: `assistantDot 1.2s ease-in-out ${i * 0.2}s infinite`,
            opacity: 0.6,
          }}
        />
      ))}
      <style>{`
        @keyframes assistantDot {
          0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
          40% { transform: scale(1); opacity: 1; }
        }
      `}</style>
    </span>
  );
}

const bubbleStyle = {
  position: 'fixed',
  bottom: 28,
  right: 28,
  width: 52,
  height: 52,
  borderRadius: '50%',
  background: 'var(--accent)',
  border: 'none',
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 8000,
  boxShadow: '0 4px 20px rgba(0,0,0,0.25)',
  transition: 'transform 0.2s, box-shadow 0.2s',
  color: '#fff',
};

const panelStyle = {
  position: 'fixed',
  bottom: 92,
  right: 28,
  width: 360,
  maxHeight: 520,
  background: 'var(--surface-card)',
  border: '1px solid var(--border-soft)',
  borderRadius: 18,
  display: 'flex',
  flexDirection: 'column',
  zIndex: 8000,
  boxShadow: '0 16px 50px rgba(0,0,0,0.2)',
  overflow: 'hidden',
};

const headerStyle = {
  padding: '14px 16px',
  borderBottom: '1px solid var(--border-soft)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  flexShrink: 0,
};

const messagesAreaStyle = {
  flex: 1,
  overflowY: 'auto',
  padding: '14px 14px 6px',
  display: 'flex',
  flexDirection: 'column',
};

const userBubble = {
  maxWidth: '80%',
  background: 'var(--accent)',
  color: '#fff',
  borderRadius: '14px 14px 2px 14px',
  padding: '9px 13px',
  fontSize: 13,
  lineHeight: 1.5,
  wordBreak: 'break-word',
};

const assistantBubble = {
  maxWidth: '85%',
  background: 'var(--surface-soft)',
  color: 'var(--text-primary)',
  borderRadius: '14px 14px 14px 2px',
  padding: '9px 13px',
  fontSize: 13,
  lineHeight: 1.5,
  wordBreak: 'break-word',
  border: '1px solid var(--border-soft)',
};

const inputAreaStyle = {
  padding: '10px 10px 6px',
  borderTop: '1px solid var(--border-soft)',
  display: 'flex',
  gap: 8,
  alignItems: 'flex-end',
  flexShrink: 0,
};

const textareaStyle = {
  flex: 1,
  resize: 'none',
  border: '1px solid var(--border-soft)',
  borderRadius: 10,
  padding: '8px 10px',
  fontSize: 13,
  background: 'var(--surface-soft)',
  color: 'var(--text-primary)',
  lineHeight: 1.4,
  outline: 'none',
  fontFamily: 'inherit',
};

const sendBtnStyle = {
  width: 36,
  height: 36,
  borderRadius: '50%',
  background: 'var(--accent)',
  color: '#fff',
  border: 'none',
  cursor: 'pointer',
  fontSize: 18,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  flexShrink: 0,
  transition: 'opacity 0.15s',
};
