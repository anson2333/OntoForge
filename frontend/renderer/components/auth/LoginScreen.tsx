/**
 * Sign-in / registration screen.
 * Shown whenever no valid backend session is available.
 */

import { FormEvent, useState } from 'react';
import { useAuthStore } from '../../services/auth';

export function LoginScreen() {
  const { login, register, isSubmitting, error, clearError } = useAuthStore();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');

  const switchMode = (nextMode: 'login' | 'register') => {
    setMode(nextMode);
    clearError();
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!username.trim() || !password) {
      return;
    }
    try {
      if (mode === 'login') {
        await login(username.trim(), password);
      } else {
        await register(username.trim(), password, displayName.trim() || undefined);
      }
    } catch {
      // Error is surfaced through the auth store.
    }
  };

  const inputStyle = {
    width: '100%',
    padding: '10px 12px',
    borderRadius: '4px',
    border: '1px solid var(--border-strong)',
    backgroundColor: 'var(--surface-bg)',
    color: 'var(--text-primary)',
    fontSize: '14px',
    boxSizing: 'border-box' as const
  };

  return (
    <div
      style={{
        height: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'var(--app-bg, #1e1e1e)',
        color: 'var(--text-primary, #e0e0e0)'
      }}
    >
      <form
        onSubmit={handleSubmit}
        style={{
          width: '360px',
          padding: '28px',
          borderRadius: '8px',
          border: '1px solid var(--border-color, #3c3c3c)',
          backgroundColor: 'var(--panel-bg, #252526)',
          display: 'flex',
          flexDirection: 'column',
          gap: '14px'
        }}
      >
        <div>
          <h1 style={{ margin: 0, fontSize: '22px' }}>OntoForge</h1>
          <p style={{ margin: '6px 0 0', fontSize: '13px', opacity: 0.7 }}>
            {mode === 'login'
              ? 'Sign in to open your research workspaces.'
              : 'Create an account to start building your evidence graph.'}
          </p>
        </div>

        <div style={{ display: 'flex', gap: '8px' }}>
          {(['login', 'register'] as const).map((candidate) => (
            <button
              key={candidate}
              type="button"
              onClick={() => switchMode(candidate)}
              style={{
                flex: 1,
                padding: '7px 10px',
                borderRadius: '4px',
                border: '1px solid var(--border-strong, #555)',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '13px',
                backgroundColor:
                  mode === candidate ? 'var(--primary-color, #0e639c)' : 'var(--surface-bg)',
                color: mode === candidate ? '#ffffff' : 'var(--text-primary)'
              }}
            >
              {candidate === 'login' ? 'Sign in' : 'Register'}
            </button>
          ))}
        </div>

        <label style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '13px' }}>
          Username
          <input
            style={inputStyle}
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoFocus
            autoComplete="username"
          />
        </label>

        {mode === 'register' && (
          <label style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '13px' }}>
            Display name (optional)
            <input
              style={inputStyle}
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              autoComplete="name"
            />
          </label>
        )}

        <label style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '13px' }}>
          Password
          <input
            style={inputStyle}
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
          />
        </label>

        {error && (
          <div
            role="alert"
            style={{
              padding: '8px 10px',
              borderRadius: '4px',
              fontSize: '12px',
              color: '#f48771',
              border: '1px solid #f48771',
              backgroundColor: 'rgba(244, 135, 113, 0.12)'
            }}
          >
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={isSubmitting || !username.trim() || !password}
          style={{
            padding: '10px 12px',
            borderRadius: '4px',
            border: 'none',
            cursor: isSubmitting ? 'wait' : 'pointer',
            fontWeight: 600,
            fontSize: '14px',
            backgroundColor: 'var(--primary-color, #0e639c)',
            color: '#ffffff',
            opacity: isSubmitting || !username.trim() || !password ? 0.6 : 1
          }}
        >
          {isSubmitting
            ? 'Please wait...'
            : mode === 'login'
              ? 'Sign in'
              : 'Create account'}
        </button>

        {mode === 'login' && (
          <p style={{ margin: 0, fontSize: '12px', opacity: 0.6 }}>
            First run seeds a demo account: <strong>demo / demo1234</strong>
          </p>
        )}
      </form>
    </div>
  );
}

export default LoginScreen;
