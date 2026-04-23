import React, { useEffect, useMemo, useState } from 'react';

const majorTimezones = [
  'UTC', 'Asia/Kolkata', 'Europe/London', 'Europe/Berlin', 'Europe/Paris',
  'America/New_York', 'America/Chicago', 'America/Denver', 'America/Los_Angeles',
  'America/Toronto', 'America/Sao_Paulo', 'Africa/Johannesburg', 'Asia/Dubai',
  'Asia/Singapore', 'Asia/Tokyo', 'Asia/Seoul', 'Asia/Bangkok', 'Asia/Jakarta',
  'Australia/Sydney', 'Pacific/Auckland',
];

export default function Settings({ currentUser, API_BASE_URL, initialTab = 'profile', onThemeChange, onTimezoneChange, onLogout }) {
  const [activeTab, setActiveTab] = useState(initialTab);
  const [profile, setProfile] = useState({ full_name: currentUser.full_name || '', timezone: 'UTC' });
  const [preferences, setPreferences] = useState({
    timezone: 'UTC',
    theme: 'light',
    language: 'en',
    ceo_mode: false,
    notification_density: 'all',
    default_landing_page: currentUser.role === 'platform_owner' ? 'owner' : currentUser.role === 'ceo' ? 'ceo' : 'dashboard',
    email_notifications: true,
    weekly_digest: true,
  });
  const [passwordForm, setPasswordForm] = useState({ current_password: '', new_password: '', confirm_password: '' });
  const [supportForm, setSupportForm] = useState({ subject: '', body: '', priority: 'medium' });
  const [message, setMessage] = useState('');
  const [billingMessage, setBillingMessage] = useState('');

  const token = localStorage.getItem('token');
  const headers = useMemo(() => ({
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
  }), [token]);

  useEffect(() => {
    setActiveTab(initialTab);
  }, [initialTab]);

  useEffect(() => {
    fetch(`${API_BASE_URL}/settings/me`, { headers })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!data) return;
        setProfile({
          full_name: data.user.full_name || '',
          timezone: data.preferences.timezone || 'UTC',
        });
        setPreferences((current) => ({
          ...current,
          ...data.preferences,
        }));
      });
  }, [API_BASE_URL]);

  const updateProfile = async () => {
    const res = await fetch(`${API_BASE_URL}/settings/profile`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify(profile),
    });
    const data = await res.json();
    if (res.ok) {
      onTimezoneChange(data.preferences.timezone);
      setMessage('Profile updated.');
    } else {
      setMessage(data.detail || 'Could not update profile.');
    }
  };

  const updatePreferences = async () => {
    const res = await fetch(`${API_BASE_URL}/settings/preferences`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify(preferences),
    });
    const data = await res.json();
    if (res.ok) {
      if (preferences.theme) onThemeChange(preferences.theme);
      if (preferences.timezone) onTimezoneChange(preferences.timezone);
      setMessage('Preferences saved.');
    } else {
      setMessage(data.detail || 'Could not save preferences.');
    }
  };

  const changePassword = async () => {
    if (passwordForm.new_password !== passwordForm.confirm_password) {
      setMessage('New password and confirm password must match.');
      return;
    }
    const res = await fetch(`${API_BASE_URL}/settings/change-password`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        current_password: passwordForm.current_password,
        new_password: passwordForm.new_password,
      }),
    });
    const data = await res.json();
    setMessage(data.message || data.detail || 'Password update completed.');
  };

  const submitSupport = async () => {
    const res = await fetch(`${API_BASE_URL}/settings/support`, {
      method: 'POST',
      headers,
      body: JSON.stringify(supportForm),
    });
    const data = await res.json();
    if (res.ok) {
      setMessage('Your ticket has been submitted. We\'ll respond to your email.');
      setSupportForm({ subject: '', body: '', priority: 'medium' });
    } else {
      setMessage(data.detail || 'Could not submit support request.');
    }
  };

  const exportData = async () => {
    const res = await fetch(`${API_BASE_URL}/settings/export`, { headers });
    const data = await res.json();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'orchestrator-user-export.json';
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const startSubscription = async (planTier) => {
    const res = await fetch(`${API_BASE_URL}/billing/subscribe`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ plan_tier: planTier }),
    });
    const data = await res.json();
    if (data.checkout_url) {
      window.open(data.checkout_url, '_blank');
    } else {
      setBillingMessage(data.detail || 'Billing checkout is unavailable.');
    }
  };

  const openBillingPortal = async () => {
    const res = await fetch(`${API_BASE_URL}/billing/portal`, { headers });
    const data = await res.json();
    if (data.url) {
      window.open(data.url, '_blank');
    } else {
      setBillingMessage(data.detail || 'Billing portal is unavailable.');
    }
  };

  const tabs = [
    ['profile', 'Profile'],
    ['preferences', 'Preferences'],
    ['security', 'Security'],
    ['support', 'Support'],
    ['privacy', 'Data & Privacy'],
  ];
  if (currentUser.role === 'admin' || currentUser.role === 'ceo') {
    tabs.push(['billing', 'Billing']);
  }

  return (
    <div className="dashboard">
      <div className="card full-width">
        <p className="eyebrow">Settings</p>
        <h2>Personalization and account controls</h2>
        {message && <p>{message}</p>}
        <div style={{ display: 'grid', gridTemplateColumns: '240px 1fr', gap: 20, marginTop: 20 }}>
          <div style={{ display: 'grid', gap: 10 }}>
            {tabs.map(([key, label]) => (
              <button key={key} className={`btn ${activeTab === key ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setActiveTab(key)}>
                {label}
              </button>
            ))}
          </div>
          <div className="card">
            {activeTab === 'profile' && (
              <div style={{ display: 'grid', gap: 12 }}>
                <input value={profile.full_name} onChange={(e) => setProfile((current) => ({ ...current, full_name: e.target.value }))} placeholder="Full name" />
                <input value={currentUser.email} readOnly />
                <input value={currentUser.role} readOnly />
                <select value={profile.timezone} onChange={(e) => setProfile((current) => ({ ...current, timezone: e.target.value }))}>
                  {majorTimezones.map((timezone) => <option key={timezone} value={timezone}>{timezone}</option>)}
                </select>
                <button className="btn btn-primary" onClick={updateProfile}>Save Profile</button>
              </div>
            )}

            {activeTab === 'preferences' && (
              <div style={{ display: 'grid', gap: 12 }}>
                <select value={preferences.theme} onChange={(e) => setPreferences((current) => ({ ...current, theme: e.target.value }))}>
                  <option value="light">Light</option>
                  <option value="dark">Dark</option>
                </select>
                <select value={preferences.language} onChange={(e) => setPreferences((current) => ({ ...current, language: e.target.value }))}>
                  <option value="en">English</option>
                </select>
                <select value={preferences.default_landing_page} onChange={(e) => setPreferences((current) => ({ ...current, default_landing_page: e.target.value }))}>
                  <option value="dashboard">Dashboard</option>
                  <option value="projects">Projects</option>
                  {currentUser.role === 'ceo' && <option value="ceo">CEO Dashboard</option>}
                  {currentUser.role === 'platform_owner' && <option value="owner">Owner Panel</option>}
                </select>
                <label><input type="checkbox" checked={preferences.email_notifications} onChange={(e) => setPreferences((current) => ({ ...current, email_notifications: e.target.checked }))} /> Email notifications</label>
                <label><input type="checkbox" checked={preferences.weekly_digest} onChange={(e) => setPreferences((current) => ({ ...current, weekly_digest: e.target.checked }))} /> Weekly digest</label>
                {currentUser.role === 'ceo' && (
                  <label><input type="checkbox" checked={preferences.ceo_mode} onChange={(e) => setPreferences((current) => ({ ...current, ceo_mode: e.target.checked }))} /> Technical View Access</label>
                )}
                <button className="btn btn-primary" onClick={updatePreferences}>Save Preferences</button>
              </div>
            )}

            {activeTab === 'security' && (
              <div style={{ display: 'grid', gap: 12 }}>
                <input type="password" placeholder="Current password" value={passwordForm.current_password} onChange={(e) => setPasswordForm((current) => ({ ...current, current_password: e.target.value }))} />
                <input type="password" placeholder="New password" value={passwordForm.new_password} onChange={(e) => setPasswordForm((current) => ({ ...current, new_password: e.target.value }))} />
                <input type="password" placeholder="Confirm new password" value={passwordForm.confirm_password} onChange={(e) => setPasswordForm((current) => ({ ...current, confirm_password: e.target.value }))} />
                <button className="btn btn-primary" onClick={changePassword}>Change Password</button>
              </div>
            )}

            {activeTab === 'support' && (
              <div style={{ display: 'grid', gap: 12 }}>
                <select value={supportForm.priority} onChange={(e) => setSupportForm((current) => ({ ...current, priority: e.target.value }))}>
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </select>
                <input value={supportForm.subject} onChange={(e) => setSupportForm((current) => ({ ...current, subject: e.target.value }))} placeholder="Subject" />
                <textarea value={supportForm.body} onChange={(e) => setSupportForm((current) => ({ ...current, body: e.target.value }))} placeholder="How can we help?" style={{ minHeight: 160 }} />
                <button className="btn btn-primary" onClick={submitSupport}>Submit Ticket</button>
              </div>
            )}

            {activeTab === 'privacy' && (
              <div style={{ display: 'grid', gap: 12 }}>
                <button className="btn btn-secondary" onClick={exportData}>Export My Data</button>
                <button className="btn btn-danger" onClick={() => window.alert('Delete-account flow is not wired yet. Contact platform support.')}>Delete Account</button>
                <button className="btn btn-secondary" onClick={onLogout}>Logout</button>
              </div>
            )}

            {activeTab === 'billing' && (
              <div style={{ display: 'grid', gap: 12 }}>
                {billingMessage && <p>{billingMessage}</p>}
                <p>Upgrade or manage your workspace billing from here.</p>
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                  <button className="btn btn-primary" onClick={() => startSubscription('starter')}>Starter Plan</button>
                  <button className="btn btn-primary" onClick={() => startSubscription('growth')}>Growth Plan</button>
                  <button className="btn btn-primary" onClick={() => startSubscription('enterprise')}>Enterprise Plan</button>
                </div>
                <button className="btn btn-secondary" onClick={openBillingPortal}>Manage Billing</button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
