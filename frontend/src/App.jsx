import React, { useState, useEffect } from 'react';
import './App.css';
import { API_BASE_URL } from './config';
import Navbar from './components/Navbar';
import Dashboard from './components/Dashboard';
import Projects from './components/Projects';
import EmployeeView from './components/EmployeeView';
import TaskDetail from './components/TaskDetail';
import Decisions from './components/Decisions';
import MultiAgentWorkbench from './components/MultiAgentWorkbench';
import CEODashboard from './components/CEODashboard';
import OwnerPanel from './components/OwnerPanel';
import Settings from './components/Settings';

export default function App() {
  const [currentUser, setCurrentUser] = useState(null);
  const [currentPage, setCurrentPage] = useState('dashboard');
  const [selectedId, setSelectedId] = useState(null);
  const [theme, setTheme] = useState('light');
  const [palette, setPalette] = useState('sage');
  const [userTimezone, setUserTimezone] = useState(Intl.DateTimeFormat().resolvedOptions().timeZone);
  const [settingsTab, setSettingsTab] = useState('profile');

  useEffect(() => {
    const user = localStorage.getItem('user');
    if (user) setCurrentUser(JSON.parse(user));
    const storedTheme = localStorage.getItem('theme');
    if (storedTheme === 'dark' || storedTheme === 'light') {
      setTheme(storedTheme);
    }
    const storedPalette = localStorage.getItem('palette');
    if (storedPalette) {
      setPalette(storedPalette);
    }
  }, []);

  useEffect(() => {
    if (!currentUser) return;

    const token = localStorage.getItem('token');
    const headers = token ? { Authorization: `Bearer ${token}` } : {};

    fetch(`${API_BASE_URL}/settings/me`, { headers })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!data?.preferences) return;
        if (data.preferences.theme === 'light' || data.preferences.theme === 'dark') {
          setTheme(data.preferences.theme);
        }
        if (data.preferences.timezone) {
          setUserTimezone(data.preferences.timezone);
        }
        if (currentUser.role === 'platform_owner') {
          setCurrentPage('owner');
        } else if (currentUser.role === 'ceo') {
          setCurrentPage('ceo');
        } else if (data.preferences.default_landing_page) {
          setCurrentPage(data.preferences.default_landing_page);
        }
      })
      .catch(() => {
        if (currentUser.role === 'platform_owner') {
          setCurrentPage('owner');
        } else if (currentUser.role === 'ceo') {
          setCurrentPage('ceo');
        }
      });
  }, [currentUser]);

  useEffect(() => {
    if (currentUser) {
      localStorage.setItem('theme', theme);
      localStorage.setItem('palette', palette);
    }
  }, [theme, palette, currentUser]);

  const handleLogout = () => {
    localStorage.removeItem('user');
    localStorage.removeItem('token');
    setCurrentUser(null);
  };

  const handleSettingsOpen = (tab = 'profile') => {
    setSettingsTab(tab);
    setCurrentPage('settings');
  };

  const toggleTheme = () => {
    setTheme((current) => (current === 'light' ? 'dark' : 'light'));
  };

  if (!currentUser) {
    return <LoginPage setCurrentUser={setCurrentUser} />;
  }

  return (
    <div className={`app theme-${theme} palette-${palette}`}>
      <Navbar
        user={currentUser}
        onLogout={handleLogout}
        setPage={setCurrentPage}
        theme={theme}
        palette={palette}
        onChangePalette={setPalette}
        onToggleTheme={toggleTheme}
        onOpenSettings={handleSettingsOpen}
      />
      <div className="container">
        {currentPage === 'dashboard' && <Dashboard role={currentUser.role} />}
        {currentPage === 'ceo' && currentUser.role === 'ceo' && (
          <CEODashboard currentUser={currentUser} API_BASE_URL={API_BASE_URL} onNavigate={setCurrentPage} />
        )}
        {currentPage === 'owner' && currentUser.role === 'platform_owner' && (
          <OwnerPanel currentUser={currentUser} API_BASE_URL={API_BASE_URL} />
        )}
        {currentPage === 'projects' && <Projects role={currentUser.role} />}
        {currentPage === 'employees' && <EmployeeView role={currentUser.role} />}
        {currentPage === 'task' && selectedId && <TaskDetail taskId={selectedId} userTimezone={userTimezone} />}
        {currentPage === 'decisions' && <Decisions />}
        {currentPage === 'multi-agent' && currentUser.role === 'admin' && <MultiAgentWorkbench />}
        {currentPage === 'settings' && (
          <Settings
            currentUser={currentUser}
            API_BASE_URL={API_BASE_URL}
            initialTab={settingsTab}
            onThemeChange={setTheme}
            onTimezoneChange={setUserTimezone}
            onLogout={handleLogout}
          />
        )}
      </div>
    </div>
  );
}

function LoginPage({ setCurrentUser }) {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [role, setRole] = useState('employee');
  const [fullName, setFullName] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage('');
    try {
      const res = await fetch(`${API_BASE_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });
      if (!res.ok) throw new Error('Login failed');
      const data = await res.json();
      localStorage.setItem('token', data.access_token);
      localStorage.setItem('user', JSON.stringify(data.user));
      setCurrentUser(data.user);
    } catch (err) {
      setMessage('Login failed: ' + err.message);
    }
    setLoading(false);
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage('');
    try {
      const res = await fetch(`${API_BASE_URL}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, full_name: fullName, role })
      });
      if (res.ok) {
        setMessage('Registration successful! Please login.');
        setIsLogin(true);
        setEmail('');
        setPassword('');
        setFullName('');
      } else {
        const data = await res.json();
        setMessage('Registration failed: ' + (data.detail || 'Unknown error'));
      }
    } catch (err) {
      setMessage('Registration failed: ' + err.message);
    }
    setLoading(false);
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <h1>🧠 AI Workforce Orchestrator</h1>
        
        <div className="auth-tabs">
          <button 
            className={`tab ${isLogin ? 'active' : ''}`}
            onClick={() => setIsLogin(true)}
          >
            Login
          </button>
          <button 
            className={`tab ${!isLogin ? 'active' : ''}`}
            onClick={() => setIsLogin(false)}
          >
            Register
          </button>
        </div>

        {message && (
          <div className={`auth-message ${message.includes('successful') ? 'success' : 'error'}`}>
            {message}
          </div>
        )}

        {isLogin ? (
          <form onSubmit={handleLogin}>
            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <PasswordField
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              showPassword={showPassword}
              onToggleVisibility={() => setShowPassword((current) => !current)}
              placeholder="Password"
            />
            <button type="submit" disabled={loading}>
              {loading ? 'Logging in...' : 'Login'}
            </button>
          </form>
        ) : (
          <form onSubmit={handleRegister}>
            <input
              type="text"
              placeholder="Full Name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
            />
            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <PasswordField
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              showPassword={showPassword}
              onToggleVisibility={() => setShowPassword((current) => !current)}
              placeholder="Password"
            />
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="employee">Employee</option>
              <option value="admin">Admin</option>
              <option value="ceo">CEO</option>
              <option value="client">Client</option>
              <option value="platform_owner">Platform Owner</option>
            </select>
            <button type="submit" disabled={loading}>
              {loading ? 'Registering...' : 'Register'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

function PasswordField({ value, onChange, showPassword, onToggleVisibility, placeholder }) {
  return (
    <div className="password-field">
      <input
        type={showPassword ? 'text' : 'password'}
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        required
      />
      <button
        type="button"
        className="password-toggle"
        onClick={onToggleVisibility}
      >
        {showPassword ? 'Hide' : 'Peek'}
      </button>
    </div>
  );
}
