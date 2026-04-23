import React, { useMemo, useState } from 'react';
import './Navbar.css';

export default function Navbar({
  user,
  onLogout,
  setPage,
  theme,
  palette,
  onChangePalette,
  onToggleTheme,
  onOpenSettings,
}) {
  const role = user?.role;
  const [menuOpen, setMenuOpen] = useState(false);

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
        <label className="palette-picker">
          <span>Palette</span>
          <select value={palette} onChange={(event) => onChangePalette(event.target.value)}>
            <option value="sage">Sage</option>
            <option value="ocean">Ocean</option>
            <option value="sunset">Sunset</option>
          </select>
        </label>
        <div className="avatar-menu">
          <button className="avatar-btn" onClick={() => setMenuOpen((current) => !current)}>
            {user?.full_name?.[0] || user?.email?.[0] || 'U'}
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
