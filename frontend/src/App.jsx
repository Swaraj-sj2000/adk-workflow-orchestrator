import React, { useState, useEffect } from 'react';
import './App.css';
import { BrowserRouter, Route, Routes, useParams } from 'react-router-dom';
import { apiFetchJson } from './lib/http';
import Navbar from './components/Navbar';
import Dashboard from './components/Dashboard';
import Projects from './components/Projects';
import EmployeeView from './components/EmployeeView';
import TaskDetail from './components/TaskDetail';
import Decisions from './components/Decisions';
import MultiAgentWorkbench from './components/MultiAgentWorkbench';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/accept-invite/:inviteCode" element={<AcceptInvitePage />} />
        <Route path="*" element={<AppShell />} />
      </Routes>
    </BrowserRouter>
  );
}

function AppShell() {
  const [currentUser, setCurrentUser] = useState(null);
  const [currentPage, setCurrentPage] = useState('dashboard');
  const [selectedId, setSelectedId] = useState(null);

  useEffect(() => {
    const user = localStorage.getItem('user');
    if (user) setCurrentUser(JSON.parse(user));
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('user');
    localStorage.removeItem('token');
    setCurrentUser(null);
  };

  if (!currentUser) {
    return <LoginPage setCurrentUser={setCurrentUser} />;
  }

  return (
    <div className="app">
      <Navbar user={currentUser} onLogout={handleLogout} setPage={setCurrentPage} />
      <div className="container">
        {currentPage === 'dashboard' && <Dashboard role={currentUser.role} />}
        {currentPage === 'projects' && <Projects role={currentUser.role} />}
        {currentPage === 'employees' && <EmployeeView role={currentUser.role} />}
        {currentPage === 'task' && selectedId && <TaskDetail taskId={selectedId} />}
        {currentPage === 'decisions' && <Decisions />}
        {currentPage === 'multi-agent' && currentUser.role === 'admin' && <MultiAgentWorkbench />}
      </div>
    </div>
  );
}

function AcceptInvitePage() {
  const { inviteCode } = useParams();
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [inviteDetails, setInviteDetails] = useState(null);
  const [message, setMessage] = useState('');
  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  useEffect(() => {
    const validateInvite = async () => {
      if (!inviteCode) {
        setMessage('Invalid invite link.');
        setLoading(false);
        return;
      }

      try {
        const data = await apiFetchJson(
          `/api/v1/auth/validate-invite?invite_code=${encodeURIComponent(inviteCode)}`
        );
        if (!data.valid) {
          setMessage(data.message || 'This invite is invalid or expired.');
          setLoading(false);
          return;
        }

        setInviteDetails(data);
        if (data.email) setEmail(data.email);
      } catch (err) {
        setMessage('Could not validate invite: ' + err.message);
      } finally {
        setLoading(false);
      }
    };

    validateInvite();
  }, [inviteCode]);

  const handleAcceptInvite = async (e) => {
    e.preventDefault();
    setMessage('');

    if (password !== confirmPassword) {
      setMessage('Passwords do not match.');
      return;
    }

    setSubmitting(true);
    try {
      const data = await apiFetchJson('/api/v1/auth/accept-invite', {
        method: 'POST',
        body: {
          invite_code: inviteCode,
          full_name: fullName,
          email,
          password,
          skills: [],
          experience_years: null
        }
      });

      const user = {
        id: data.user_id,
        email: data.email,
        full_name: data.full_name,
        organization_id: data.organization_id,
        organization_slug: data.organization_slug,
        role: data.role
      };

      localStorage.setItem('token', data.access_token);
      localStorage.setItem('user', JSON.stringify(user));
      window.location.assign('/');
    } catch (err) {
      setMessage('Could not accept invite: ' + err.message);
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="login-page">
        <div className="login-card">
          <h1>AI Workforce Orchestrator</h1>
          <p>Validating invite...</p>
        </div>
      </div>
    );
  }

  if (!inviteDetails) {
    return (
      <div className="login-page">
        <div className="login-card">
          <h1>Invite Unavailable</h1>
          <p>{message || 'This invite is invalid or expired.'}</p>
          <a href="/">Back to login</a>
        </div>
      </div>
    );
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <h1>Join {inviteDetails.organization_name || 'your organization'}</h1>
        <p>Complete your account to accept this invite.</p>

        {message && (
          <div className={`auth-message ${message.includes('successful') ? 'success' : 'error'}`}>
            {message}
          </div>
        )}

        <form onSubmit={handleAcceptInvite}>
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
          <input
            type="password"
            placeholder="Password (min 8 chars)"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={8}
            required
          />
          <input
            type="password"
            placeholder="Confirm Password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            minLength={8}
            required
          />
          <button type="submit" disabled={submitting}>
            {submitting ? 'Creating account...' : 'Accept Invite'}
          </button>
        </form>
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
  const [inviteCodeInput, setInviteCodeInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  const goToInvitePage = () => {
    const trimmed = inviteCodeInput.trim();
    if (!trimmed) {
      setMessage('Please enter an invite code.');
      return;
    }
    window.location.assign(`/accept-invite/${encodeURIComponent(trimmed)}`);
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage('');
    try {
      const data = await apiFetchJson('/api/v1/auth/login', {
        method: 'POST',
        body: { email, password }
      });

      const user = {
        id: data.user_id,
        email: data.email,
        full_name: data.full_name,
        organization_id: data.organization_id,
        organization_slug: data.organization_slug,
        role: data.role
      };

      localStorage.setItem('token', data.access_token);
      localStorage.setItem('user', JSON.stringify(user));
      setCurrentUser(user);
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
      await apiFetchJson('/api/v1/auth/signup', {
        method: 'POST',
        body: { email, password, full_name: fullName, role }
      });
      setMessage('Registration successful! Please login.');
      setIsLogin(true);
      setEmail('');
      setPassword('');
      setFullName('');
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
          <>
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

            <div style={{ marginTop: '14px' }}>
              <input
                type="text"
                placeholder="Have an invite code? Paste it here"
                value={inviteCodeInput}
                onChange={(e) => setInviteCodeInput(e.target.value)}
              />
              <button type="button" onClick={goToInvitePage} style={{ marginTop: '8px' }}>
                Accept Invite
              </button>
            </div>
          </>
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
              <option value="client">Client</option>
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
