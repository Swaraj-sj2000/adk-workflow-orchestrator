import React, { useMemo, useRef, useState } from 'react';
import './Navbar.css';
import ColorPicker from './ColorPicker';

export default function Navbar({
  user,
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

  const navItems = useMemo(() => {
    if (role === 'platform_owner') {
      return [{ label: 'Owner Panel', page: 'owner' }];
    }
    if (role === 'ceo') {
      return [
        { label: 'CEO Dashboard', page: 'ceo' },
        { label: 'Projects', page: 'projects' },
      ];
    }
    if (role === 'admin') {
      return [
        { label: 'Admin Dashboard', page: 'dashboard' },
        { label: 'Projects', page: 'projects' },
        { label: 'Team Dashboard', page: 'employees' },
        { label: 'Agentic Dashboard', page: 'decisions' },
        { label: 'Multi-Agent', page: 'multi-agent' },
      ];
    }
    if (role === 'employee') {
      return [
        { label: 'My Dashboard', page: 'dashboard' },
        { label: 'My Projects', page: 'projects' },
        { label: 'My Work', page: 'employees' },
      ];
    }
    return [
      { label: 'Client Dashboard', page: 'dashboard' },
      { label: 'Project Status', page: 'projects' },
    ];
  }, [role]);

  return (
    <nav className="navbar">
      <div className="nav-left">
        <h1 onClick={() => setPage(role === 'platform_owner' ? 'owner' : role === 'ceo' ? 'ceo' : 'dashboard')} className="logo">
          🧠 Orchestrator
        </h1>
      </div>
      <div className="nav-center">
        {navItems.map((item) => (
          <button key={item.page} onClick={() => setPage(item.page)} className="nav-btn">{item.label}</button>
        ))}
      </div>
      <div className="nav-right">
        <span className="user-info">
          {user?.email} <span className="role-badge">{user?.role}</span>
        </span>
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
            data-tooltip="Colour palette"
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              fontSize: 13, fontWeight: 600, padding: '6px 12px',
            }}
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
        <div className="avatar-menu">
          <button className="avatar-btn" onClick={() => setMenuOpen((current) => !current)}
            style={{ overflow: 'hidden', padding: user?.avatar_url ? 0 : undefined }}>
            {user?.avatar_url
              ? <img src={user.avatar_url} alt="avatar" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
              : (user?.full_name?.[0] || user?.email?.[0] || 'U')}
          </button>
          {menuOpen && (
            <div className="avatar-dropdown">
              <button onClick={() => { onOpenSettings('profile'); setMenuOpen(false); }}>Settings</button>
              <button onClick={() => { onOpenSettings('support'); setMenuOpen(false); }}>Support</button>
              <button onClick={() => { onLogout(); setMenuOpen(false); }}>Logout</button>
            </div>
          )}
        </div>
      </div>
    </nav>
  );
}
