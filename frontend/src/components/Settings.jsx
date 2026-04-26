import React, { useEffect, useMemo, useRef, useState } from 'react';

const TIMEZONES = [
  'UTC','Asia/Kolkata','Asia/Dubai','Asia/Singapore','Asia/Tokyo','Asia/Seoul',
  'Asia/Bangkok','Asia/Jakarta','Europe/London','Europe/Berlin','Europe/Paris',
  'America/New_York','America/Chicago','America/Los_Angeles','America/Toronto',
  'America/Sao_Paulo','Africa/Johannesburg','Australia/Sydney','Pacific/Auckland',
];

const LOCATIONS = [
  'Bangalore, India','Mumbai, India','Delhi, India','Hyderabad, India','Chennai, India',
  'Pune, India','Kolkata, India','Ahmedabad, India','Jaipur, India',
  'London, UK','Manchester, UK','Berlin, Germany','Paris, France','Amsterdam, Netherlands',
  'Dubai, UAE','Singapore','Tokyo, Japan','Sydney, Australia','Toronto, Canada',
  'New York, USA','San Francisco, USA','Seattle, USA','Austin, USA',
  'Other',
];

const POSITIONS = [
  'Software Engineer','Senior Software Engineer','Staff Engineer','Principal Engineer',
  'Engineering Manager','VP of Engineering','CTO','Chief Technology Officer',
  'Product Manager','Senior Product Manager','VP of Product','CPO',
  'Data Scientist','ML Engineer','AI Engineer','Data Engineer',
  'Designer','UX Designer','Product Designer','UI Developer',
  'DevOps Engineer','SRE','Platform Engineer','Cloud Architect',
  'Business Analyst','Project Manager','Delivery Manager','Scrum Master',
  'Sales Manager','Account Executive','Customer Success Manager',
  'Marketing Manager','Content Strategist',
  'CEO','COO','CFO','Founder','Co-founder',
  'Consultant','Freelancer','Intern','Associate',
  'Other',
];

function EyeIcon({ open }) {
  return open ? (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
      <circle cx="12" cy="12" r="3"/>
    </svg>
  ) : (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94"/>
      <path d="M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19"/>
      <line x1="1" y1="1" x2="23" y2="23"/>
    </svg>
  );
}

function PeekInput({ placeholder, value, onChange, autoComplete }) {
  const [show, setShow] = useState(false);
  return (
    <div style={{ position: 'relative' }}>
      <input
        type={show ? 'text' : 'password'}
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        autoComplete={autoComplete}
        style={{ paddingRight: 40 }}
      />
      <button
        type="button"
        onClick={() => setShow((s) => !s)}
        style={{
          position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)',
          background: 'none', border: 'none', cursor: 'pointer', opacity: 0.5, padding: 2,
        }}
        tabIndex={-1}
      >
        <EyeIcon open={show} />
      </button>
    </div>
  );
}

function AvatarUpload({ avatarUrl, onChange }) {
  const inputRef = useRef();
  const handleFile = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) { alert('Image must be under 2 MB.'); return; }
    const reader = new FileReader();
    reader.onload = (ev) => onChange(ev.target.result);
    reader.readAsDataURL(file);
  };
  const initials = '?';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 8 }}>
      <div
        onClick={() => inputRef.current.click()}
        style={{
          width: 80, height: 80, borderRadius: '50%', overflow: 'hidden',
          border: '2px dashed var(--border-soft)', cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'var(--bg-soft, #f5f5f5)', flexShrink: 0,
          position: 'relative',
        }}
      >
        {avatarUrl ? (
          <img src={avatarUrl} alt="avatar" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        ) : (
          <span style={{ fontSize: 28, opacity: 0.3 }}>{initials}</span>
        )}
        <div style={{
          position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.35)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          opacity: 0, transition: 'opacity 0.2s',
        }}
          onMouseEnter={e => e.currentTarget.style.opacity = 1}
          onMouseLeave={e => e.currentTarget.style.opacity = 0}
        >
          <span style={{ color: '#fff', fontSize: 12, fontWeight: 600 }}>Change</span>
        </div>
      </div>
      <div>
        <button className="btn btn-secondary" style={{ fontSize: 13 }} onClick={() => inputRef.current.click()}>
          Upload Photo
        </button>
        {avatarUrl && (
          <button className="btn btn-secondary" style={{ fontSize: 13, marginLeft: 8 }} onClick={() => onChange(null)}>
            Remove
          </button>
        )}
        <p style={{ fontSize: 12, opacity: 0.55, margin: '4px 0 0' }}>JPG or PNG, max 2 MB</p>
      </div>
      <input ref={inputRef} type="file" accept="image/jpeg,image/png,image/webp" style={{ display: 'none' }} onChange={handleFile} />
    </div>
  );
}

function PositionField({ value, onChange, API_BASE_URL, headers }) {
  const [custom, setCustom] = useState(false);
  const [customVal, setCustomVal] = useState('');
  const [validating, setValidating] = useState(false);
  const [validResult, setValidResult] = useState(null); // {valid, suggestion, reason}
  const debounceRef = useRef(null);

  // If the saved value isn't in our dropdown list, treat as custom
  useEffect(() => {
    if (value && !POSITIONS.includes(value)) {
      setCustom(true);
      setCustomVal(value);
    }
  }, []);

  const handleDropdown = (e) => {
    const v = e.target.value;
    if (v === 'Other') { setCustom(true); setCustomVal(''); onChange(''); }
    else { setCustom(false); onChange(v); setValidResult(null); }
  };

  const handleCustom = (e) => {
    const v = e.target.value;
    setCustomVal(v);
    setValidResult(null);
    clearTimeout(debounceRef.current);
    if (v.trim().length < 2) { onChange(v); return; }
    debounceRef.current = setTimeout(async () => {
      setValidating(true);
      try {
        const res = await fetch(`${API_BASE_URL}/settings/validate-position`, {
          method: 'POST', headers,
          body: JSON.stringify({ position: v }),
        });
        const data = await res.json();
        setValidResult(data);
        if (data.valid) onChange(data.suggestion || v);
      } catch { /* ignore */ }
      setValidating(false);
    }, 600);
  };

  const dropdownValue = custom ? 'Other' : (value || '');

  return (
    <div>
      <label style={{ fontSize: 13, opacity: 0.7, display: 'block', marginBottom: 4 }}>
        Position / Job Title
      </label>
      <select value={dropdownValue} onChange={handleDropdown} style={{ marginBottom: custom ? 8 : 0 }}>
        <option value="">— Select position —</option>
        {POSITIONS.map((p) => <option key={p} value={p}>{p}</option>)}
      </select>
      {custom && (
        <div>
          <div style={{ position: 'relative' }}>
            <input
              value={customVal}
              onChange={handleCustom}
              placeholder="Type your position title…"
              style={{
                borderColor: validResult
                  ? validResult.valid ? '#2e7d32' : '#e53935'
                  : undefined,
              }}
            />
            {validating && (
              <span style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', fontSize: 12, opacity: 0.5 }}>
                checking…
              </span>
            )}
          </div>
          {validResult && !validResult.valid && (
            <p style={{ fontSize: 12, color: '#e53935', margin: '4px 0 0' }}>
              {validResult.reason}
              {validResult.suggestion && ` — did you mean "${validResult.suggestion}"?`}
            </p>
          )}
          {validResult && validResult.valid && (
            <p style={{ fontSize: 12, color: '#2e7d32', margin: '4px 0 0' }}>Looks good ✓</p>
          )}
        </div>
      )}
    </div>
  );
}

export default function Settings({ currentUser, API_BASE_URL, initialTab = 'profile', onThemeChange, onTimezoneChange, onLogout, onProfileUpdate }) {
  const [activeTab, setActiveTab]   = useState(initialTab);
  const [editingProfile, setEditingProfile] = useState(false);
  const [profileLoading, setProfileLoading] = useState(true);
  const [profile, setProfile]       = useState({
    first_name: '', last_name: '', phone: '', secondary_email: '',
    position: '', location: '', avatar_url: null, timezone: 'UTC',
  });
  const [savedProfile, setSavedProfile] = useState(null); // what came from server
  const [preferences, setPreferences] = useState({
    timezone: 'UTC', theme: 'light', language: 'en', ceo_mode: false,
    notification_density: 'all', default_landing_page: 'dashboard',
    email_notifications: true, weekly_digest: true, currency: 'USD',
  });
  const [pwForm, setPwForm]         = useState({ current_password: '', new_password: '', confirm_password: '' });
  const [supportForm, setSupportForm] = useState({ subject: '', body: '', priority: 'medium' });
  const [msg, setMsg]               = useState('');
  const [billingMsg, setBillingMsg] = useState('');
  const [locationOther, setLocationOther] = useState(false);

  const token   = localStorage.getItem('token');
  const headers = useMemo(() => ({ Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }), [token]);

  useEffect(() => { setActiveTab(initialTab); }, [initialTab]);

  const loadProfile = () => {
    fetch(`${API_BASE_URL}/settings/me`, { headers })
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        if (!data) { setProfileLoading(false); return; }
        const u = data.user;

        // Fall back: split full_name into first/last if the new columns are empty
        let firstName = u.first_name || '';
        let lastName  = u.last_name  || '';
        if (!firstName && !lastName && u.full_name) {
          const parts = u.full_name.trim().split(/\s+/);
          firstName = parts[0] || '';
          lastName  = parts.slice(1).join(' ') || '';
        }

        const loaded = {
          first_name:      firstName,
          last_name:       lastName,
          phone:           u.phone      || '',
          secondary_email: u.secondary_email || '',
          position:        u.position   || '',
          location:        u.location   || '',
          avatar_url:      u.avatar_url || null,
          timezone:        data.preferences.timezone || 'UTC',
          email:           u.email,
          role:            u.role,
        };
        setProfile(loaded);
        setSavedProfile(loaded);
        if (u.location && !LOCATIONS.includes(u.location)) setLocationOther(true);
        setPreferences((p) => ({ ...p, ...data.preferences }));
        setProfileLoading(false);
      })
      .catch(() => setProfileLoading(false));
  };

  useEffect(() => { loadProfile(); }, [API_BASE_URL]);

  const flash = (m) => { setMsg(m); setTimeout(() => setMsg(''), 4000); };

  const saveProfile = async () => {
    const res = await fetch(`${API_BASE_URL}/settings/profile`, {
      method: 'PATCH', headers, body: JSON.stringify(profile),
    });
    const data = await res.json();
    if (res.ok) {
      onTimezoneChange(data.preferences.timezone);
      if (onProfileUpdate) onProfileUpdate(data.user);
      loadProfile();
      setEditingProfile(false);
      flash('Profile saved.');
    } else flash(data.detail || 'Could not save profile.');
  };

  const cancelEdit = () => {
    if (savedProfile) {
      setProfile(savedProfile);
      setLocationOther(savedProfile.location && !LOCATIONS.includes(savedProfile.location));
    }
    setEditingProfile(false);
  };

  const savePreferences = async () => {
    const res = await fetch(`${API_BASE_URL}/settings/preferences`, {
      method: 'PATCH', headers, body: JSON.stringify(preferences),
    });
    const data = await res.json();
    if (res.ok) {
      if (preferences.theme)    onThemeChange(preferences.theme);
      if (preferences.timezone) onTimezoneChange(preferences.timezone);
      // Persist currency onto cached user so getCurrency() reads it immediately
      try {
        const u = JSON.parse(localStorage.getItem('user') || '{}');
        localStorage.setItem('user', JSON.stringify({ ...u, currency: preferences.currency || 'USD' }));
      } catch {}
      if (onProfileUpdate) onProfileUpdate({ currency: preferences.currency || 'USD' });
      flash('Preferences saved.');
    } else flash(data.detail || 'Could not save preferences.');
  };

  const changePassword = async () => {
    if (pwForm.new_password !== pwForm.confirm_password) { flash('Passwords do not match.'); return; }
    const res = await fetch(`${API_BASE_URL}/settings/change-password`, {
      method: 'POST', headers,
      body: JSON.stringify({ current_password: pwForm.current_password, new_password: pwForm.new_password }),
    });
    const data = await res.json();
    flash(data.message || data.detail || 'Done.');
    if (res.ok) setPwForm({ current_password: '', new_password: '', confirm_password: '' });
  };

  const submitSupport = async () => {
    const res = await fetch(`${API_BASE_URL}/settings/support`, {
      method: 'POST', headers, body: JSON.stringify(supportForm),
    });
    const data = await res.json();
    if (res.ok) { flash("Ticket submitted — we'll reply to your email."); setSupportForm({ subject: '', body: '', priority: 'medium' }); }
    else flash(data.detail || 'Could not submit ticket.');
  };

  const exportData = async () => {
    const res  = await fetch(`${API_BASE_URL}/settings/export`, { headers });
    const data = await res.json();
    const url  = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }));
    Object.assign(document.createElement('a'), { href: url, download: 'orchestrator-export.json' }).click();
    URL.revokeObjectURL(url);
  };

  const startSubscription = async (plan) => {
    const res  = await fetch(`${API_BASE_URL}/billing/subscribe`, { method: 'POST', headers, body: JSON.stringify({ plan_tier: plan }) });
    const data = await res.json();
    data.checkout_url ? window.open(data.checkout_url, '_blank') : setBillingMsg(data.detail || 'Unavailable.');
  };

  const openBillingPortal = async () => {
    const res  = await fetch(`${API_BASE_URL}/billing/portal`, { headers });
    const data = await res.json();
    data.url ? window.open(data.url, '_blank') : setBillingMsg(data.detail || 'Unavailable.');
  };

  const tabs = [
    ['profile', 'Profile'], ['preferences', 'Preferences'],
    ['security', 'Security'], ['support', 'Support'], ['privacy', 'Data & Privacy'],
  ];
  if (['admin', 'ceo'].includes(currentUser.role)) tabs.push(['billing', 'Billing']);

  const pSet = (field) => (e) => setProfile((p) => ({ ...p, [field]: e.target.value }));

  return (
    <div className="dashboard">
      <div className="card full-width">
        <p className="eyebrow">Settings</p>
        <h2>Account &amp; Personalization</h2>
        {msg && <p style={{ padding: '8px 12px', borderRadius: 8, background: 'rgba(46,125,50,0.1)', color: '#2e7d32', marginTop: 8 }}>{msg}</p>}

        <div style={{ display: 'grid', gridTemplateColumns: '200px 1fr', gap: 20, marginTop: 20 }}>
          {/* Sidebar */}
          <div style={{ display: 'grid', gap: 8, alignContent: 'start' }}>
            {tabs.map(([key, label]) => (
              <button key={key} className={`btn ${activeTab === key ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setActiveTab(key)}>
                {label}
              </button>
            ))}
          </div>

          {/* Content */}
          <div className="card">

            {/* ── PROFILE ─────────────────────────────────────── */}
            {activeTab === 'profile' && profileLoading && (
              <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}>
                <div className="spinner" />
              </div>
            )}
            {activeTab === 'profile' && !profileLoading && !savedProfile && (
              <p style={{ color: 'var(--text-secondary)', fontSize: 14 }}>
                Could not load profile. Please refresh the page.
              </p>
            )}
            {activeTab === 'profile' && !editingProfile && savedProfile && (
              <div style={{ display: 'grid', gap: 20 }}>
                {/* Avatar + name header */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
                  <div style={{
                    width: 72, height: 72, borderRadius: '50%', overflow: 'hidden', flexShrink: 0,
                    background: 'var(--surface-pill)', display: 'flex', alignItems: 'center',
                    justifyContent: 'center', fontSize: 28, fontWeight: 700, color: 'var(--text-secondary)',
                    border: '2px solid var(--border-soft)',
                  }}>
                    {savedProfile.avatar_url
                      ? <img src={savedProfile.avatar_url} alt="avatar" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                      : (savedProfile.first_name?.[0] || currentUser.email?.[0] || '?').toUpperCase()}
                  </div>
                  <div style={{ flex: 1 }}>
                    <h3 style={{ margin: 0, fontSize: 20 }}>
                      {[savedProfile.first_name, savedProfile.last_name].filter(Boolean).join(' ') || currentUser.full_name || currentUser.email}
                    </h3>
                    <p style={{ margin: '2px 0 0', fontSize: 13, color: 'var(--text-secondary)' }}>
                      {savedProfile.position || '—'} {savedProfile.location ? `· ${savedProfile.location}` : ''}
                    </p>
                  </div>
                  <button
                    onClick={() => setEditingProfile(true)}
                    style={{
                      background: 'none', border: '1px solid var(--border-soft)', borderRadius: 8,
                      padding: '5px 12px', cursor: 'pointer', fontSize: 13,
                      color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 5,
                    }}
                  >
                    ✏ Edit
                  </button>
                </div>

                {/* Info grid */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 0, borderTop: '1px solid var(--border-soft)' }}>
                  {[
                    ['Primary Email',    savedProfile.email || currentUser.email],
                    ['Secondary Email',  savedProfile.secondary_email || '—'],
                    ['Phone',            savedProfile.phone || '—'],
                    ['Role',             currentUser.role],
                    ['Timezone',         savedProfile.timezone],
                    ['Location',         savedProfile.location || '—'],
                  ].map(([label, val]) => (
                    <div key={label} style={{ padding: '12px 0', borderBottom: '1px solid var(--border-soft)' }}>
                      <p style={{ margin: 0, fontSize: 12, color: 'var(--text-secondary)', marginBottom: 2 }}>{label}</p>
                      <p style={{ margin: 0, fontSize: 14, fontWeight: 500 }}>{val}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {activeTab === 'profile' && editingProfile && (
              <div style={{ display: 'grid', gap: 16 }}>
                {/* Edit header */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <h3 style={{ margin: 0 }}>Edit Profile</h3>
                  <button onClick={cancelEdit} style={{
                    background: 'none', border: 'none', cursor: 'pointer',
                    fontSize: 20, color: 'var(--text-secondary)', lineHeight: 1,
                  }}>✕</button>
                </div>

                <AvatarUpload avatarUrl={profile.avatar_url} onChange={(v) => setProfile((p) => ({ ...p, avatar_url: v }))} />

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div>
                    <label style={{ fontSize: 13, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
                      First Name <span style={{ color: '#e53935' }}>*</span>
                    </label>
                    <input value={profile.first_name} onChange={pSet('first_name')} placeholder="First name" />
                  </div>
                  <div>
                    <label style={{ fontSize: 13, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
                      Last Name <span style={{ color: '#e53935' }}>*</span>
                    </label>
                    <input value={profile.last_name} onChange={pSet('last_name')} placeholder="Last name" />
                  </div>
                </div>

                <div>
                  <label style={{ fontSize: 13, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>Primary Email</label>
                  <input value={currentUser.email} readOnly style={{ opacity: 0.5, cursor: 'not-allowed' }} />
                  <p style={{ fontSize: 12, color: 'var(--text-secondary)', margin: '3px 0 0', opacity: 0.7 }}>Contact support to change primary email.</p>
                </div>

                <div>
                  <label style={{ fontSize: 13, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>Secondary Email</label>
                  <input value={profile.secondary_email} onChange={pSet('secondary_email')} placeholder="secondary@email.com (optional)" type="email" />
                </div>

                <div>
                  <label style={{ fontSize: 13, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>Phone / Mobile</label>
                  <input value={profile.phone} onChange={pSet('phone')} placeholder="+91 98765 43210" type="tel" />
                </div>

                <PositionField
                  value={profile.position}
                  onChange={(v) => setProfile((p) => ({ ...p, position: v }))}
                  API_BASE_URL={API_BASE_URL}
                  headers={headers}
                />

                <div>
                  <label style={{ fontSize: 13, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>Location</label>
                  <select
                    value={locationOther ? 'Other' : (profile.location || '')}
                    onChange={(e) => {
                      if (e.target.value === 'Other') { setLocationOther(true); setProfile((p) => ({ ...p, location: '' })); }
                      else { setLocationOther(false); setProfile((p) => ({ ...p, location: e.target.value })); }
                    }}
                    style={{ marginBottom: locationOther ? 8 : 0 }}
                  >
                    <option value="">— Select location —</option>
                    {LOCATIONS.map((l) => <option key={l} value={l}>{l}</option>)}
                  </select>
                  {locationOther && (
                    <input value={profile.location} onChange={pSet('location')} placeholder="City, Country" />
                  )}
                </div>

                <div>
                  <label style={{ fontSize: 13, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>Timezone</label>
                  <select value={profile.timezone} onChange={pSet('timezone')}>
                    {TIMEZONES.map((tz) => <option key={tz} value={tz}>{tz}</option>)}
                  </select>
                </div>

                <div style={{ display: 'flex', gap: 10 }}>
                  <button
                    className="btn btn-primary"
                    disabled={!profile.first_name.trim() || !profile.last_name.trim()}
                    onClick={saveProfile}
                    style={{ flex: 1 }}
                  >
                    Save Changes
                  </button>
                  <button className="btn btn-secondary" onClick={cancelEdit}>Cancel</button>
                </div>
              </div>
            )}

            {/* ── PREFERENCES ─────────────────────────────────── */}
            {activeTab === 'preferences' && (
              <div style={{ display: 'grid', gap: 12 }}>
                <div>
                  <label style={{ fontSize: 13, opacity: 0.7, display: 'block', marginBottom: 4 }}>Theme</label>
                  <select value={preferences.theme} onChange={(e) => setPreferences((p) => ({ ...p, theme: e.target.value }))}>
                    <option value="light">Light</option>
                    <option value="dark">Dark</option>
                    <option value="ocean">Ocean</option>
                    <option value="earth">Earth</option>
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: 13, opacity: 0.7, display: 'block', marginBottom: 4 }}>Language</label>
                  <select value={preferences.language} onChange={(e) => setPreferences((p) => ({ ...p, language: e.target.value }))}>
                    <option value="en">English</option>
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: 13, opacity: 0.7, display: 'block', marginBottom: 4 }}>Default Landing Page</label>
                  <select value={preferences.default_landing_page} onChange={(e) => setPreferences((p) => ({ ...p, default_landing_page: e.target.value }))}>
                    <option value="dashboard">Dashboard</option>
                    <option value="projects">Projects</option>
                    {currentUser.role === 'ceo' && <option value="ceo">CEO Dashboard</option>}
                    {currentUser.role === 'platform_owner' && <option value="owner">Owner Panel</option>}
                  </select>
                </div>
                <label style={{ display: 'flex', gap: 8, alignItems: 'center', cursor: 'pointer' }}>
                  <input type="checkbox" checked={preferences.email_notifications} onChange={(e) => setPreferences((p) => ({ ...p, email_notifications: e.target.checked }))} />
                  Email notifications
                </label>
                <label style={{ display: 'flex', gap: 8, alignItems: 'center', cursor: 'pointer' }}>
                  <input type="checkbox" checked={preferences.weekly_digest} onChange={(e) => setPreferences((p) => ({ ...p, weekly_digest: e.target.checked }))} />
                  Weekly digest email
                </label>
                <div>
                  <label style={{ fontSize: 13, opacity: 0.7, display: 'block', marginBottom: 4 }}>Currency</label>
                  <select value={preferences.currency || 'USD'} onChange={(e) => setPreferences((p) => ({ ...p, currency: e.target.value }))}>
                    <option value="USD">USD — US Dollar ($)</option>
                    <option value="INR">INR — Indian Rupee (₹)</option>
                  </select>
                </div>
                {currentUser.role === 'ceo' && (
                  <label style={{ display: 'flex', gap: 8, alignItems: 'center', cursor: 'pointer' }}>
                    <input type="checkbox" checked={preferences.ceo_mode} onChange={(e) => setPreferences((p) => ({ ...p, ceo_mode: e.target.checked }))} />
                    Technical view (CEO mode)
                  </label>
                )}
                <button className="btn btn-primary" onClick={savePreferences}>Save Preferences</button>

                {/* Onboarding re-trigger */}
                <div style={{ marginTop: 8, paddingTop: 16, borderTop: '1px solid var(--border-soft)' }}>
                  <p style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>Platform Onboarding</p>
                  <p style={{ fontSize: 12, color: 'var(--text-secondary)', margin: '0 0 10px' }}>
                    Replay the step-by-step onboarding guide for your role at any time.
                  </p>
                  <button
                    className="btn btn-secondary"
                    onClick={async () => {
                      const token = localStorage.getItem('token');
                      await fetch(`${API_BASE_URL}/settings/preferences`, {
                        method: 'PATCH',
                        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
                        body: JSON.stringify({ onboarding_complete: false }),
                      });
                      flash('Onboarding will show on your next page load.');
                    }}
                  >
                    🎓 Replay Onboarding Wizard
                  </button>
                </div>
              </div>
            )}

            {/* ── SECURITY ─────────────────────────────────────── */}
            {activeTab === 'security' && (
              <div style={{ display: 'grid', gap: 12 }}>
                <p className="eyebrow" style={{ marginBottom: 4 }}>Change Password</p>
                <PeekInput placeholder="Current password" value={pwForm.current_password}
                  onChange={(e) => setPwForm((p) => ({ ...p, current_password: e.target.value }))}
                  autoComplete="current-password" />
                <PeekInput placeholder="New password" value={pwForm.new_password}
                  onChange={(e) => setPwForm((p) => ({ ...p, new_password: e.target.value }))}
                  autoComplete="new-password" />
                <PeekInput placeholder="Confirm new password" value={pwForm.confirm_password}
                  onChange={(e) => setPwForm((p) => ({ ...p, confirm_password: e.target.value }))}
                  autoComplete="new-password" />
                {pwForm.confirm_password && pwForm.new_password !== pwForm.confirm_password && (
                  <p style={{ fontSize: 13, color: '#e53935', margin: 0 }}>Passwords do not match.</p>
                )}
                <button
                  className="btn btn-primary"
                  disabled={!pwForm.current_password || !pwForm.new_password || pwForm.new_password !== pwForm.confirm_password}
                  onClick={changePassword}
                >
                  Change Password
                </button>
              </div>
            )}

            {/* ── SUPPORT ──────────────────────────────────────── */}
            {activeTab === 'support' && (
              <div style={{ display: 'grid', gap: 12 }}>
                <div>
                  <label style={{ fontSize: 13, opacity: 0.7, display: 'block', marginBottom: 4 }}>Priority</label>
                  <select value={supportForm.priority} onChange={(e) => setSupportForm((p) => ({ ...p, priority: e.target.value }))}>
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                  </select>
                </div>
                <input value={supportForm.subject} onChange={(e) => setSupportForm((p) => ({ ...p, subject: e.target.value }))} placeholder="Subject" />
                <textarea value={supportForm.body} onChange={(e) => setSupportForm((p) => ({ ...p, body: e.target.value }))} placeholder="How can we help?" style={{ minHeight: 160 }} />
                <button className="btn btn-primary" disabled={!supportForm.subject.trim() || !supportForm.body.trim()} onClick={submitSupport}>
                  Submit Ticket
                </button>
              </div>
            )}

            {/* ── PRIVACY ──────────────────────────────────────── */}
            {activeTab === 'privacy' && (
              <div style={{ display: 'grid', gap: 12 }}>
                <button className="btn btn-secondary" onClick={exportData}>Export My Data (JSON)</button>
                <button className="btn btn-danger" onClick={() => alert('Delete-account flow — contact platform support.')}>Delete Account</button>
                <button className="btn btn-secondary" onClick={onLogout}>Logout</button>
              </div>
            )}

            {/* ── BILLING ──────────────────────────────────────── */}
            {activeTab === 'billing' && (
              <div style={{ display: 'grid', gap: 12 }}>
                {billingMsg && <p style={{ color: '#e53935' }}>{billingMsg}</p>}
                <p style={{ opacity: 0.7 }}>Upgrade or manage your workspace plan.</p>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))', gap: 12 }}>
                  {[['starter','Starter — ₹1,000/mo'],['pro','Pro — ₹5,000/6mo'],['enterprise','Enterprise — ₹15,000/yr']].map(([tier, label]) => (
                    <button key={tier} className="btn btn-primary" onClick={() => startSubscription(tier)}>{label}</button>
                  ))}
                </div>
                <button className="btn btn-secondary" onClick={openBillingPortal}>Manage Billing Portal</button>
              </div>
            )}

          </div>
        </div>
      </div>
    </div>
  );
}
