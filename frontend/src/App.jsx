import React, { useState, useEffect } from 'react';
import './App.css';
import Navbar from './components/Navbar';
import Dashboard from './components/Dashboard';
import EmployeeView from './components/EmployeeView';
import TaskDetail from './components/TaskDetail';
import Decisions from './components/Decisions';

export default function App() {
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
        {currentPage === 'employees' && <EmployeeView role={currentUser.role} />}
        {currentPage === 'task' && selectedId && <TaskDetail taskId={selectedId} />}
        {currentPage === 'decisions' && <Decisions />}
      </div>
    </div>
  );
}

function LoginPage({ setCurrentUser }) {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('employee');
  const [fullName, setFullName] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage('');
    try {
      const res = await fetch('http://localhost:8000/auth/login', {
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
      const res = await fetch('http://localhost:8000/auth/register', {
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
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
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
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
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
