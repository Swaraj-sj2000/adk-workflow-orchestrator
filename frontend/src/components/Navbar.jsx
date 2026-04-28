import React, { useMemo, useState } from 'react';
import './Navbar.css';
import ColorPicker from './ColorPicker';
import synraLogo from '../assets/synra_logo.svg';

const NAV_TIPS = {
  'owner':       'Platform-wide admin panel — tenants, billing, and system health',
  'ceo':         'CEO overview — company metrics, AI risk signals, and executive insights',
  'dashboard':   'Your main dashboard with live project and team metrics',
  'projects':    'Browse all projects, progress, and task breakdowns',
  'employees':   'Team workspace — tasks, blockers, and workload management',
  'decisions':   'AI decision log — review and audit all agent-generated decisions',
  'multi-agent': 'Run the multi-agent orchestration workflow on a new or live project',
};

export default function Navbar({
  user,
  tenantName,
  tenantLogoUrl,
  onLogout,
  setPage,
  theme,
  onToggleTheme,
  onOpenSettings,
  customAccent,
  onAccentChange,
}) {
  const role = user?.role;
  const [menuOpen, setMenuOpen] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [avatarHover, setAvatarHover] = useState(false);

  const isPlatformOwner = role === 'platform_owner';

  const navItems = useMemo(() => {
    if (role === 'platform_owner') return [{ label: 'Owner Panel', page: 'owner' }];
    if (role === 'ceo') return [
      { label: 'CEO Dashboard', page: 'ceo' },
      { label: 'Projects', page: 'projects' },
    ];
    if (role === 'admin') return [
      { label: 'Admin Dashboard', page: 'dashboard' },
      { label: 'Projects', page: 'projects' },
      { label: 'Team Dashboard', page: 'employees' },
      { label: 'Agentic Dashboard', page: 'decisions' },
      { label: 'Multi-Agent', page: 'multi-agent' },
    ];
    if (role === 'employee') return [
      { label: 'My Dashboard', page: 'dashboard' },
      { label: 'My Projects', page: 'projects' },
      { label: 'My Work', page: 'employees' },
    ];
    return [
      { label: 'Client Dashboard', page: 'dashboard' },
      { label: 'Project Status', page: 'projects' },
    ];
  }, [role]);

  const logoContent = isPlatformOwner ? (
    <img src={synraLogo} alt="SynRA" className="nav-platform-logo" />
  ) : tenantLogoUrl ? (
    <img src={tenantLogoUrl} alt={tenantName || 'Company'} className="nav-company-logo" />
  ) : tenantName ? (
    <div className="nav-company-initials">
      {tenantName.split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase()}
    </div>
  ) : (
    <img src={synraLogo} alt="SynRA" className="nav-platform-logo" />
  );

  return (
    <nav className="navbar">
      <div className="nav-left">
        <div
          className="nav-logo-row"
          onClick={() => setPage(isPlatformOwner ? 'owner' : role === 'ceo' ? 'ceo' : 'dashboard')}
          style={{ cursor: 'pointer' }}
        >
          {logoContent}
          {!isPlatformOwner && tenantName && !tenantLogoUrl && (
            <span className="nav-company-name">{tenantName}</span>
          )}
        </div>
      </div>

      <div className="nav-center">
        {navItems.map((item) => (
          <button
            key={item.page}
            onClick={() => setPage(item.page)}
            className="nav-btn"
            data-tooltip={NAV_TIPS[item.page] || item.label}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="nav-right">
        <button
          type="button"
          className="theme-toggle-btn"
          onClick={onToggleTheme}
          data-tooltip={theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}
        >
          {theme === 'light' ? '🌙' : '☀️'}
        </button>

        <div style={{ position: 'relative' }}>
          <button
            type="button"
            className="theme-toggle-btn"
            onClick={() => setPickerOpen((o) => !o)}
            data-tooltip="Pick a colour theme for the whole interface"
            style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 600, padding: '6px 12px' }}
          >
            <span style={{
              width: 16, height: 16, borderRadius: '50%',
              background: customAccent?.accent || 'var(--accent)',
              display: 'inline-block', flexShrink: 0,
              border: '2px solid rgba(255,255,255,0.4)',
              boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
            }} />
            Palette
          </button>
          {pickerOpen && (
            <ColorPicker
              currentAccent={customAccent}
              onAccentChange={(v) => { onAccentChange(v); }}
              onClose={() => setPickerOpen(false)}
            />
          )}
        </div>

        <div
          className="avatar-menu"
          onMouseEnter={() => setAvatarHover(true)}
          onMouseLeave={() => setAvatarHover(false)}
        >
          <button
            className="avatar-btn"
            onClick={() => setMenuOpen((c) => !c)}
            style={{ overflow: 'hidden', padding: user?.avatar_url ? 0 : undefined }}
          >
            {user?.avatar_url
              ? <img src={user.avatar_url} alt="avatar" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
              : (user?.full_name?.[0] || user?.email?.[0] || 'U')}
          </button>

          {avatarHover && !menuOpen && (
            <div className="avatar-hover-card">
              <div className="avatar-hover-avatar">
                {user?.avatar_url
                  ? <img src={user.avatar_url} alt="avatar" style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '50%' }} />
                  : (user?.full_name?.[0] || user?.email?.[0] || 'U')}
              </div>
              <div className="avatar-hover-name">{user?.full_name || user?.email}</div>
              {!isPlatformOwner && tenantName && <div className="avatar-hover-company">{tenantName}</div>}
              <div className="avatar-hover-rows">
                <div><span>Role</span><strong>{user?.role}</strong></div>
                {user?.id && <div><span>ID</span><strong>#{user.id}</strong></div>}
                <div><span>Email</span><strong>{user?.email}</strong></div>
                {user?.phone && <div><span>Phone</span><strong>{user.phone}</strong></div>}
                {user?.position && <div><span>Position</span><strong>{user.position}</strong></div>}
              </div>
            </div>
          )}

          {menuOpen && (
            <div className="avatar-dropdown">
              <button data-tooltip="Edit profile, timezone, and preferences" onClick={() => { onOpenSettings('profile'); setMenuOpen(false); }}>Settings</button>
              <button data-tooltip="Submit a support ticket or view platform help" onClick={() => { onOpenSettings('support'); setMenuOpen(false); }}>Support</button>
              <button data-tooltip="Sign out of your account" onClick={() => { onLogout(); setMenuOpen(false); }}>Logout</button>
            </div>
          )}
        </div>
      </div>
    </nav>
  );
}
