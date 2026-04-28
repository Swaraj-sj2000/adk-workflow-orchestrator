import React, { useState, useEffect } from 'react';
import './App.css';
import { API_BASE_URL } from './config';
import synraLogo from './assets/synra_logo.svg';
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
import OnboardingWizard from './components/OnboardingWizard';
import PlatformAssistant from './components/PlatformAssistant';

function computeThemeVars(accent, isDark) {
  const { h, sHsl, l } = accent;
  const H = Math.round(h);
  if (isDark) {
    // In dark mode lighten the accent significantly (match existing dark palette behaviour)
    const darkL = Math.min(0.78, l + 0.28);
    const darkS = Math.min(1, sHsl * 0.85);
    return {
      '--accent':          `hsl(${H}, ${Math.round(darkS * 100)}%, ${Math.round(darkL * 100)}%)`,
      '--accent-strong':   `hsl(${H}, ${Math.round(darkS * 100)}%, ${Math.round(Math.max(darkL - 0.13, 0.3) * 100)}%)`,
      '--app-bg':          `hsl(${H}, 22%, 7%)`,
      '--surface-card':    `hsl(${H}, 18%, 11%)`,
      '--surface-soft':    `hsl(${H}, 16%, 14%)`,
      '--surface-pill':    `hsl(${H}, 14%, 17%)`,
      '--border-soft':     `hsl(${H}, 14%, 23%)`,
      '--text-primary':    `hsl(${H}, 18%, 92%)`,
      '--text-secondary':  `hsl(${H}, 10%, 63%)`,
    };
  }
  return {
    '--accent':          `hsl(${H}, ${Math.round(sHsl * 100)}%, ${Math.round(l * 100)}%)`,
    '--accent-strong':   `hsl(${H}, ${Math.round(sHsl * 100)}%, ${Math.round(Math.max(l - 0.12, 0.25) * 100)}%)`,
    '--app-bg':          `hsl(${H}, 20%, 95%)`,
    '--surface-card':    `hsl(${H}, 10%, 99%)`,
    '--surface-soft':    `hsl(${H}, 16%, 97%)`,
    '--surface-pill':    `hsl(${H}, 26%, 91%)`,
    '--border-soft':     `hsl(${H}, 20%, 85%)`,
    '--text-primary':    `hsl(${H}, 30%, 14%)`,
    '--text-secondary':  `hsl(${H}, 15%, 43%)`,
  };
}

export default function App() {
  const [currentUser, setCurrentUser] = useState(null);
  const [currentPage, setCurrentPage] = useState('dashboard');
  const [selectedId, setSelectedId] = useState(null);
  const [theme, setTheme] = useState('light');
  const [customAccent, setCustomAccent] = useState(null); // { h, s, v, accent, accentStrong }
  const [userTimezone, setUserTimezone] = useState(Intl.DateTimeFormat().resolvedOptions().timeZone);
  const [settingsTab, setSettingsTab] = useState('profile');
  const [onboardingComplete, setOnboardingComplete] = useState(true);
  const [tenantName, setTenantName] = useState(null);
  const [tenantLogoUrl, setTenantLogoUrl] = useState(null);
  const [loginToast, setLoginToast] = useState(null);
  const [overdueCount, setOverdueCount] = useState(0);

  useEffect(() => {
    const user = localStorage.getItem('user');
    if (user) setCurrentUser(JSON.parse(user));
    const storedTheme = localStorage.getItem('theme');
    if (storedTheme === 'dark' || storedTheme === 'light') {
      setTheme(storedTheme);
    }
    try {
      const storedAccent = localStorage.getItem('customAccent');
      if (storedAccent) setCustomAccent(JSON.parse(storedAccent));
    } catch (_) {}
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
        setOnboardingComplete(!!data.preferences.onboarding_complete);
        if (data.user?.tenant_name) setTenantName(data.user.tenant_name);
        if (data.user?.tenant_logo_url !== undefined) setTenantLogoUrl(data.user.tenant_logo_url || null);
        if (data.user) {
          const merged = { ...currentUser, ...data.user, currency: data.preferences.currency || 'USD' };
          setCurrentUser(merged);
          localStorage.setItem('user', JSON.stringify(merged));
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
  }, [currentUser?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (currentUser) {
      localStorage.setItem('theme', theme);
    }
  }, [theme, currentUser]);

  useEffect(() => {
    if (!currentUser) return;
    const token = localStorage.getItem('token');
    fetch(`${API_BASE_URL}/tasks/overdue-count`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.ok ? r.json() : { count: 0 })
      .then((d) => setOverdueCount(d.count || 0))
      .catch(() => {});
  }, [currentUser?.id]);

  const handleLoginSuccess = (user) => {
    setLoginToast(user);
    setTimeout(() => setLoginToast(null), 4000);
  };

  const handleAccentChange = (v) => {
    setCustomAccent(v);
    localStorage.setItem('customAccent', JSON.stringify(v));
  };

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
    return <LoginPage setCurrentUser={setCurrentUser} onLoginSuccess={handleLoginSuccess} />;
  }

  const accentStyle = customAccent ? computeThemeVars(customAccent, theme === 'dark') : {};

  return (
    <div className={`app theme-${theme}`} style={accentStyle}>
      <img
        src={synraLogo}
        aria-hidden="true"
        style={{
          position: 'fixed',
          bottom: 32,
          right: 32,
          width: 320,
          opacity: theme === 'dark' ? 0.04 : 0.055,
          pointerEvents: 'none',
          userSelect: 'none',
          zIndex: 0,
          filter: theme === 'dark' ? 'invert(1)' : 'none',
        }}
      />
      {loginToast && (
        <div style={{
          position: 'fixed', top: 20, right: 24, zIndex: 9999,
          background: 'var(--surface-card)', color: 'var(--text-primary)',
          border: '1px solid var(--border-soft)',
          borderRadius: 14, padding: '14px 20px',
          boxShadow: '0 8px 32px rgba(0,0,0,0.18)',
          display: 'flex', alignItems: 'center', gap: 12,
          animation: 'fadeSlideIn 0.3s ease',
          minWidth: 260,
        }}>
          <span style={{ fontSize: 22 }}>👋</span>
          <div>
            <div style={{ fontWeight: 700, fontSize: 15 }}>
              Welcome back, {loginToast.full_name?.split(' ')[0] || loginToast.email}
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2, textTransform: 'capitalize' }}>
              Signed in as {loginToast.role?.replace('_', ' ')}
            </div>
          </div>
        </div>
      )}
      <Navbar
        user={currentUser}
        tenantName={tenantName}
        tenantLogoUrl={tenantLogoUrl}
        onLogout={handleLogout}
        setPage={setCurrentPage}
        theme={theme}
        onToggleTheme={toggleTheme}
        onOpenSettings={handleSettingsOpen}
        customAccent={customAccent}
        onAccentChange={handleAccentChange}
        overdueCount={overdueCount}
      />
      <div className="container">
        {currentPage === 'dashboard' && currentUser.role !== 'platform_owner' && currentUser.role !== 'ceo' && <Dashboard role={currentUser.role} />}
        {currentPage === 'ceo' && currentUser.role === 'ceo' && (
          <CEODashboard
            currentUser={currentUser}
            API_BASE_URL={API_BASE_URL}
            onNavigate={setCurrentPage}
            tenantLogoUrl={tenantLogoUrl}
            onCompanyUpdate={(updated) => {
              if (updated.name) setTenantName(updated.name);
              if (updated.logo_url !== undefined) setTenantLogoUrl(updated.logo_url || null);
            }}
          />
        )}
        {currentPage === 'owner' && currentUser.role === 'platform_owner' && (
          <OwnerPanel currentUser={currentUser} API_BASE_URL={API_BASE_URL} />
        )}
        {currentPage === 'projects' && <Projects role={currentUser.role} currency={currentUser.currency || 'USD'} />}
        {currentPage === 'employees' && <EmployeeView role={currentUser.role} currency={currentUser.currency || 'USD'} />}
        {currentPage === 'task' && selectedId && <TaskDetail taskId={selectedId} userTimezone={userTimezone} />}
        {currentPage === 'decisions' && <Decisions />}
        {currentPage === 'multi-agent' && (currentUser.role === 'admin' || currentUser.role === 'ceo') && <MultiAgentWorkbench />}
        {currentPage === 'settings' && (
          <Settings
            currentUser={currentUser}
            API_BASE_URL={API_BASE_URL}
            initialTab={settingsTab}
            onThemeChange={setTheme}
            onTimezoneChange={setUserTimezone}
            onLogout={handleLogout}
            onProfileUpdate={(updated) => {
              const merged = { ...currentUser, ...updated };
              setCurrentUser(merged);
              localStorage.setItem('user', JSON.stringify(merged));
            }}
          />
        )}
      </div>

      {!onboardingComplete && (
        <OnboardingWizard
          currentUser={currentUser}
          onComplete={() => setOnboardingComplete(true)}
        />
      )}

      <PlatformAssistant currentUser={currentUser} />
    </div>
  );
}

function LoginPage({ setCurrentUser, onLoginSuccess }) {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [role, setRole] = useState('employee');
  const [fullName, setFullName] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  // Forgot-password flow: null | 'email' | 'reset'
  const [forgotStep, setForgotStep] = useState(null);
  const [forgotEmail, setForgotEmail] = useState('');
  const [devResetToken, setDevResetToken] = useState('');
  const [resetToken, setResetToken] = useState('');
  const [resetNewPw, setResetNewPw] = useState('');
  const [resetConfirmPw, setResetConfirmPw] = useState('');
  const [showResetPw, setShowResetPw] = useState(false);

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
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Login failed');
      localStorage.setItem('token', data.access_token);
      localStorage.setItem('user', JSON.stringify(data.user));
      setCurrentUser(data.user);
      onLoginSuccess?.(data.user);
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
        body: JSON.stringify({
          email, password, full_name: fullName, role,
          ...(companyName && { tenant_name: companyName }),
        })
      });
      if (res.ok) {
        setMessage('Registration successful! Please login.');
        setIsLogin(true);
        setEmail('');
        setPassword('');
        setFullName('');
        setCompanyName('');
      } else {
        const data = await res.json();
        setMessage('Registration failed: ' + (data.detail || 'Unknown error'));
      }
    } catch (err) {
      setMessage('Registration failed: ' + err.message);
    }
    setLoading(false);
  };

  const handleForgotRequest = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage('');
    try {
      const res = await fetch(`${API_BASE_URL}/auth/forgot-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: forgotEmail }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Request failed');
      setForgotStep('reset');
      if (data.dev_reset_token) {
        setDevResetToken(data.dev_reset_token);
        setResetToken(data.dev_reset_token);
      }
    } catch (err) {
      setMessage(err.message);
    }
    setLoading(false);
  };

  const handleResetPassword = async (e) => {
    e.preventDefault();
    if (resetNewPw !== resetConfirmPw) { setMessage('Passwords do not match.'); return; }
    if (resetNewPw.length < 8) { setMessage('Password must be at least 8 characters.'); return; }
    setLoading(true);
    setMessage('');
    try {
      const res = await fetch(`${API_BASE_URL}/auth/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: resetToken, new_password: resetNewPw }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Reset failed');
      // Success — go back to login with a success message
      setForgotStep(null);
      setForgotEmail('');
      setResetToken('');
      setResetNewPw('');
      setResetConfirmPw('');
      setDevResetToken('');
      setIsLogin(true);
      setMessage('Password updated successfully. Please log in.');
    } catch (err) {
      setMessage(err.message);
    }
    setLoading(false);
  };

  const exitForgot = () => {
    setForgotStep(null);
    setForgotEmail('');
    setResetToken('');
    setResetNewPw('');
    setResetConfirmPw('');
    setDevResetToken('');
    setMessage('');
  };

  return (
    <div className="login-page">
      {/* Neural network background */}
      <svg className="login-neural-bg" viewBox="0 0 1440 900" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <defs>
          <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="3.5" result="blur"/>
            <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
          </filter>
          <radialGradient id="fade" cx="50%" cy="50%" r="55%">
            <stop offset="0%"   stopColor="#07071c" stopOpacity="0.7"/>
            <stop offset="100%" stopColor="#07071c" stopOpacity="0"/>
          </radialGradient>
        </defs>
        {/* edges */}
        {[
          [120,80,310,190],[310,190,540,120],[540,120,720,260],[720,260,950,180],[950,180,1180,90],[1180,90,1360,210],
          [120,80,80,320],[80,320,210,480],[210,480,310,190],[310,190,480,380],[480,380,540,120],
          [540,120,700,60],[700,60,950,180],[950,180,1100,340],[1100,340,1360,210],
          [80,320,180,620],[180,620,420,700],[420,700,480,380],[480,380,660,540],[660,540,720,260],
          [720,260,900,480],[900,480,1100,340],[1100,340,1280,560],[1280,560,1360,210],
          [180,620,300,820],[300,820,580,780],[580,780,660,540],[660,540,840,740],[840,740,900,480],
          [900,480,1060,720],[1060,720,1280,560],[300,820,1060,720],[840,740,1060,720],
          [1360,210,1420,480],[1420,480,1280,560],[1420,480,1380,720],[1380,720,1060,720],
        ].map(([x1,y1,x2,y2],i) => (
          <line key={i} x1={x1} y1={y1} x2={x2} y2={y2}
            stroke="rgba(80,80,200,0.35)" strokeWidth="0.8"/>
        ))}
        {/* dim nodes */}
        {[
          [700,60],[1180,90],[80,320],[210,480],[480,380],[660,540],[900,480],[1100,340],[1280,560],
          [180,620],[420,700],[580,780],[840,740],[1060,720],[1380,720],[1360,210],[1420,480],[300,820],
        ].map(([cx,cy],i) => (
          <circle key={i} cx={cx} cy={cy} r="4" fill="rgba(100,100,210,0.4)" filter="url(#glow)"/>
        ))}
        {/* bright nodes */}
        {[
          [120,80],[310,190],[540,120],[720,260],[950,180],[1360,210],
          [80,320],[480,380],[660,540],[900,480],[1060,720],[300,820],
        ].map(([cx,cy],i) => (
          <g key={i} filter="url(#glow)">
            <circle cx={cx} cy={cy} r="7" fill="rgba(48,48,180,0.18)"/>
            <circle cx={cx} cy={cy} r="3.5" fill="rgba(120,120,230,0.75)"/>
          </g>
        ))}
        {/* centre vignette — darkens the card area so the card pops */}
        <rect x="0" y="0" width="1440" height="900" fill="url(#fade)"/>
      </svg>
      <div className="login-card">
        <img src={synraLogo} alt="SynRA" style={{ width: '100%', maxWidth: 260, margin: '0 auto 8px', display: 'block' }} />
        
        {!forgotStep && (
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
        )}
        {forgotStep === 'email' && (
          <div style={{ textAlign: 'center', marginBottom: 20, fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>
            Reset Password
          </div>
        )}
        {forgotStep === 'reset' && (
          <div style={{ textAlign: 'center', marginBottom: 20, fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>
            Set New Password
          </div>
        )}

        {message && (
          <div className={`auth-message ${message.includes('successful') ? 'success' : 'error'}`}>
            {message}
          </div>
        )}

        {/* ── Forgot password — step 1: enter email ── */}
        {forgotStep === 'email' && (
          <form onSubmit={handleForgotRequest}>
            <p style={{ margin: '0 0 16px', fontSize: 14, color: 'var(--text-secondary)', textAlign: 'center' }}>
              Enter your account email. We'll send you a reset link.
            </p>
            <input
              type="email"
              placeholder="your@email.com"
              value={forgotEmail}
              onChange={(e) => setForgotEmail(e.target.value)}
              autoFocus
              required
            />
            <button type="submit" disabled={loading || !forgotEmail.trim()}>
              {loading ? 'Sending...' : 'Send Reset Link →'}
            </button>
            <button type="button" onClick={exitForgot}
              style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, color: 'var(--text-secondary)', textDecoration: 'underline', width: '100%', marginTop: 8 }}
            >
              ← Back to login
            </button>
          </form>
        )}

        {/* ── Forgot password — step 2: enter token + new password ── */}
        {forgotStep === 'reset' && (
          <form onSubmit={handleResetPassword}>
            <p style={{ margin: '0 0 12px', fontSize: 14, color: 'var(--text-secondary)', textAlign: 'center' }}>
              Check your email for the reset code and set a new password.
            </p>
            {devResetToken && (
              <div style={{
                background: 'rgba(234,179,8,0.12)', border: '1px solid rgba(234,179,8,0.4)',
                borderRadius: 8, padding: '10px 12px', marginBottom: 12,
              }}>
                <p style={{ margin: '0 0 4px', fontSize: 11, fontWeight: 700, color: '#92400e', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
                  Dev mode — no email provider configured
                </p>
                <p style={{ margin: 0, fontSize: 12, color: '#78350f', wordBreak: 'break-all' }}>
                  Token: <strong>{devResetToken}</strong>
                </p>
                <p style={{ margin: '4px 0 0', fontSize: 11, color: '#92400e' }}>
                  Pre-filled below. This box won't appear in production.
                </p>
              </div>
            )}
            <input
              type="text"
              placeholder="Paste reset token from email"
              value={resetToken}
              onChange={(e) => setResetToken(e.target.value.trim())}
              required
              style={{ fontFamily: 'monospace', fontSize: 13 }}
            />
            <PasswordField
              value={resetNewPw}
              onChange={(e) => setResetNewPw(e.target.value)}
              showPassword={showResetPw}
              onToggleVisibility={() => setShowResetPw((s) => !s)}
              placeholder="New password (min 8 chars)"
            />
            <PasswordField
              value={resetConfirmPw}
              onChange={(e) => setResetConfirmPw(e.target.value)}
              showPassword={showResetPw}
              onToggleVisibility={() => setShowResetPw((s) => !s)}
              placeholder="Confirm new password"
            />
            {resetConfirmPw && resetNewPw !== resetConfirmPw && (
              <p style={{ fontSize: 12, color: '#e53935', margin: '-8px 0 8px' }}>Passwords do not match.</p>
            )}
            <button
              type="submit"
              disabled={loading || !resetToken || !resetNewPw || resetNewPw !== resetConfirmPw || resetNewPw.length < 8}
            >
              {loading ? 'Updating...' : 'Set New Password →'}
            </button>
            <button type="button" onClick={exitForgot}
              style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, color: 'var(--text-secondary)', textDecoration: 'underline', width: '100%', marginTop: 8 }}
            >
              ← Back to login
            </button>
          </form>
        )}

        {/* ── Normal login / register forms ── */}
        {!forgotStep && (isLogin ? (
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
            <button
              type="button"
              onClick={() => { setForgotStep('email'); setForgotEmail(email); setMessage(''); }}
              style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, color: 'var(--text-secondary)', textDecoration: 'underline', width: '100%', marginTop: 8 }}
            >
              Forgot password?
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
            <select value={role} onChange={(e) => { setRole(e.target.value); setCompanyName(''); }}>
              <option value="employee">Employee — join via invite</option>
              <option value="admin">Admin — set up a team</option>
              <option value="ceo">CEO — register my company</option>
              <option value="client">Client</option>
            </select>
            {(role === 'ceo' || role === 'admin') && (
              <input
                type="text"
                placeholder="Company name *"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                required
              />
            )}
            {role === 'employee' && (
              <p style={{ margin: 0, fontSize: 12, color: '#888', lineHeight: 1.5 }}>
                Your admin will send you an invite link. Register here with the same email to accept it automatically.
              </p>
            )}
            <button type="submit" disabled={loading}>
              {loading ? 'Registering...' : role === 'ceo' ? 'Create Company Account →' : 'Register'}
            </button>
          </form>
        ))}
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
