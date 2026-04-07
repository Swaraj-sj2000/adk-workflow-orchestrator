import React from 'react';
import './Navbar.css';

export default function Navbar({ user, onLogout, setPage, theme, onToggleTheme }) {
  const role = user?.role;

  return (
    <nav className="navbar">
      <div className="nav-left">
        <h1 onClick={() => setPage('dashboard')} className="logo">
          🧠 Orchestrator
        </h1>
      </div>
      <div className="nav-center">
        {role === 'admin' && (
          <>
            <button onClick={() => setPage('dashboard')} className="nav-btn">Admin Dashboard</button>
            <button onClick={() => setPage('projects')} className="nav-btn">Projects</button>
            <button onClick={() => setPage('employees')} className="nav-btn">Team Dashboard</button>
            <button onClick={() => setPage('decisions')} className="nav-btn">Agentic Dashboard</button>
            <button onClick={() => setPage('multi-agent')} className="nav-btn">Multi-Agent</button>
          </>
        )}
        {role === 'employee' && (
          <>
            <button onClick={() => setPage('dashboard')} className="nav-btn">My Dashboard</button>
            <button onClick={() => setPage('projects')} className="nav-btn">My Projects</button>
            <button onClick={() => setPage('employees')} className="nav-btn">My Work</button>
          </>
        )}
        {role === 'client' && (
          <>
            <button onClick={() => setPage('dashboard')} className="nav-btn">Client Dashboard</button>
            <button onClick={() => setPage('projects')} className="nav-btn">Project Status</button>
          </>
        )}
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
          {theme === 'light' ? 'Dark' : 'Light'}
        </button>
        <button onClick={onLogout} className="logout-btn">Logout</button>
      </div>
    </nav>
  );
}
