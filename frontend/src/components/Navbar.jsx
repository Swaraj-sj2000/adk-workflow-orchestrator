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
            <button 
              onClick={() => setPage('dashboard')} 
              className="nav-btn"
              data-tooltip="View active projects, team workload, and operational metrics"
            >
              Admin Dashboard
            </button>
            <button 
              onClick={() => setPage('projects')} 
              className="nav-btn"
              data-tooltip="Manage all projects, approve team plans, track delivery status"
            >
              Projects
            </button>
            <button 
              onClick={() => setPage('employees')} 
              className="nav-btn"
              data-tooltip="View team members, their skills, availability, and current assignments"
            >
              Team Dashboard
            </button>
            <button 
              onClick={() => setPage('decisions')} 
              className="nav-btn"
              data-tooltip="Monitor AI agent decisions, confidence scores, and escalation alerts"
            >
              Agentic Dashboard
            </button>

            <button 
              onClick={() => setPage('multi-agent')} 
              className="nav-btn"
              data-tooltip="Execute full workflow: AI planning → team assignment → execution"
            >
              Multi-Agent
            </button>
          </>
        )}
        {role === 'employee' && (
          <>
            <button 
              onClick={() => setPage('dashboard')} 
              className="nav-btn"
              data-tooltip="Your personal dashboard with assigned projects and tasks"
            >
              My Dashboard
            </button>
            <button 
              onClick={() => setPage('projects')} 
              className="nav-btn"
              data-tooltip="Projects you're involved in and your progress"
            >
              My Projects
            </button>
            <button 
              onClick={() => setPage('employees')} 
              className="nav-btn"
              data-tooltip="Your work assignments and workload"
            >
              My Work
            </button>
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
          onClick={onToggleTheme} 
          className="theme-toggle-btn"
          data-tooltip={theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}
          title={theme === 'light' ? 'Dark Mode' : 'Light Mode'}
        >
          {theme === 'light' ? '🌙' : '☀️'}
        </button>
        <button onClick={onLogout} className="logout-btn">Logout</button>
      </div>
    </nav>
  );
}
