import React, { useState, useEffect } from 'react';
import { API_BASE_URL } from '../config';

export default function OnboardingWizard({ currentUser, onComplete }) {
  const [steps, setSteps] = useState([]);
  const [current, setCurrent] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('token');
    fetch(`${API_BASE_URL}/assistant/onboarding-steps`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data?.steps) setSteps(data.steps);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const markComplete = async () => {
    const token = localStorage.getItem('token');
    try {
      await fetch(`${API_BASE_URL}/settings/preferences`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ onboarding_complete: true }),
      });
    } catch (_) {}
    onComplete();
  };

  const handleNext = () => {
    if (current < steps.length - 1) {
      setCurrent((c) => c + 1);
    } else {
      markComplete();
    }
  };

  const handleBack = () => setCurrent((c) => Math.max(0, c - 1));
  const handleSkip = () => markComplete();

  if (loading) return null;
  if (!steps.length) {
    markComplete();
    return null;
  }

  const step = steps[current];
  const isLast = current === steps.length - 1;

  return (
    <div style={overlay}>
      <div style={modal}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
          <div style={{ fontSize: 40, lineHeight: 1 }}>{step.icon}</div>
          <button onClick={handleSkip} style={skipBtn} title="Skip onboarding">✕</button>
        </div>

        {/* Content */}
        <h2 style={{ margin: '0 0 12px', fontSize: 20, color: 'var(--text-primary)', fontWeight: 700 }}>
          {step.title}
        </h2>
        <p style={{ margin: 0, fontSize: 15, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
          {step.body}
        </p>

        {/* Progress dots */}
        <div style={{ display: 'flex', gap: 6, marginTop: 28, marginBottom: 24, justifyContent: 'center' }}>
          {steps.map((_, i) => (
            <div
              key={i}
              onClick={() => setCurrent(i)}
              style={{
                width: i === current ? 20 : 8,
                height: 8,
                borderRadius: 4,
                background: i === current ? 'var(--accent)' : 'var(--border-soft)',
                cursor: 'pointer',
                transition: 'all 0.25s',
              }}
            />
          ))}
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', gap: 10, justifyContent: 'space-between', alignItems: 'center' }}>
          <button
            onClick={handleBack}
            disabled={current === 0}
            style={{
              ...btnBase,
              background: 'transparent',
              border: '1px solid var(--border-soft)',
              color: 'var(--text-secondary)',
              opacity: current === 0 ? 0.3 : 1,
            }}
          >
            ← Back
          </button>
          <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
            {current + 1} / {steps.length}
          </span>
          <button onClick={handleNext} style={{ ...btnBase, background: 'var(--accent)', color: '#fff' }}>
            {isLast ? 'Get Started →' : 'Next →'}
          </button>
        </div>
      </div>
    </div>
  );
}

const overlay = {
  position: 'fixed', inset: 0,
  background: 'rgba(0,0,0,0.55)',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  zIndex: 9000,
  backdropFilter: 'blur(2px)',
};

const modal = {
  background: 'var(--surface-card)',
  border: '1px solid var(--border-soft)',
  borderRadius: 18,
  padding: '32px 36px',
  width: '100%',
  maxWidth: 460,
  boxShadow: '0 24px 60px rgba(0,0,0,0.22)',
};

const skipBtn = {
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  color: 'var(--text-secondary)',
  fontSize: 18,
  padding: '2px 6px',
  borderRadius: 6,
  lineHeight: 1,
};

const btnBase = {
  padding: '10px 22px',
  borderRadius: 10,
  border: 'none',
  cursor: 'pointer',
  fontWeight: 600,
  fontSize: 14,
  transition: 'opacity 0.15s',
};
