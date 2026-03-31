import React from 'react';
import './Navbar.css';

export default function Navbar({ user, onLogout, setPage }) {
  return (
    <nav className="navbar">
      <div className="nav-left">
        <h1 onClick={() => setPage('dashboard')} className="logo">
          🧠 Orchestrator
        </h1>
      </div>
      <div className="nav-center">
        <button onClick={() => setPage('dashboard')} className="nav-btn">Dashboard</button>
        <button onClick={() => setPage('projects')} className="nav-btn">Projects</button>
        <button onClick={() => setPage('employees')} className="nav-btn">Employees</button>
        {user?.role === 'admin' && (
          <>
            <button onClick={() => setPage('decisions')} className="nav-btn">Decisions</button>
            <button onClick={() => setPage('autopm')} className="nav-btn">AutoPM</button>
          </>
        )}
      </div>
      <div className="nav-right">
        <span className="user-info">
          {user?.email} <span className="role-badge">{user?.role}</span>
        </span>
        <button onClick={onLogout} className="logout-btn">Logout</button>
      </div>
    </nav>
  );
}
