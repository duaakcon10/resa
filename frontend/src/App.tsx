import React, { useState, useEffect } from 'react';
import Login from './pages/Login';
import Landing from './pages/Landing';
import Dashboard from './pages/Dashboard';
import Bots from './pages/Bots';
import BotDetail from './pages/BotDetail';
import Attack from './pages/Attack';
import Plans from './pages/AdminPlans';
import AdminSettings from './pages/AdminSettings';
import Users from './pages/Users';
import Logs from './pages/Logs';
import Sidebar from './components/Sidebar';
import { ToastProvider } from './components/Toast';
import { Menu } from 'lucide-react';

export type Page = 'dashboard' | 'bots' | 'bot-detail' | 'attack' | 'plans' | 'admin-settings' | 'users' | 'logs';
export type Role = 'admin' | 'user';
export type AuthState = 'landing' | 'login' | 'app';

function App() {
  const [token, setToken] = useState<string | null>(localStorage.getItem('c2_token'));
  const [role, setRole] = useState<Role>((localStorage.getItem('c2_role') as Role) || 'user');
  const [username, setUsername] = useState(localStorage.getItem('c2_user') || '');
  const [page, setPage] = useState<Page>('dashboard');
  const [botDetailId, setBotDetailId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [authState, setAuthState] = useState<AuthState>(token ? 'app' : 'landing');

  const handleLogin = (t: string, r: Role, u: string) => {
    localStorage.setItem('c2_token', t);
    localStorage.setItem('c2_role', r);
    localStorage.setItem('c2_user', u);
    setToken(t); setRole(r); setUsername(u); setAuthState('app');
    // Redirect to admin pages or user pages
    setPage(r === 'admin' ? 'dashboard' : 'attack');
  };

  const handleLogout = () => {
    localStorage.removeItem('c2_token');
    localStorage.removeItem('c2_role');
    localStorage.removeItem('c2_user');
    setToken(null); setRole('user'); setUsername(''); setAuthState('landing'); setPage('dashboard');
  };

  const navigate = (p: Page, id?: string) => {
    if (role !== 'admin' && (p === 'users' || p === 'logs' || p === 'admin-settings')) {
      setPage('dashboard'); setSidebarOpen(false); return;
    }
    if (p === 'bot-detail' && id) setBotDetailId(id);
    setPage(p); setSidebarOpen(false);
  };

  if (authState === 'landing') {
    return (
      <ToastProvider>
        <Landing onLogin={() => setAuthState('login')} />
      </ToastProvider>
    );
  }

  if (authState === 'login' || !token) {
    return (
      <ToastProvider>
        <Login onLogin={handleLogin} />
      </ToastProvider>
    );
  }

  return (
    <ToastProvider>
      <div className="flex h-screen overflow-hidden">
        <div className="scanline-overlay" />
        {sidebarOpen && (
          <div className="fixed inset-0 bg-black/60 z-20 lg:hidden" onClick={() => setSidebarOpen(false)} />
        )}

        <div className={`fixed lg:static inset-y-0 left-0 z-30 transform transition-transform duration-200 ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}`}>
          <Sidebar activePage={page} onNavigate={navigate} onLogout={handleLogout} role={role} username={username} />
        </div>

        <main className="flex-1 overflow-y-auto bg-[var(--bg-primary)] min-w-0">
          <div className="lg:hidden sticky top-0 z-10 flex items-center gap-3 px-4 py-3 bg-[var(--bg-secondary)]/90 backdrop-blur border-b border-[var(--border)]">
            <button onClick={() => setSidebarOpen(true)} className="p-2 rounded-lg hover:bg-[var(--bg-hover)] text-[var(--text-secondary)]">
              <Menu className="w-5 h-5" />
            </button>
            <span className="text-sm font-semibold">C2 Center</span>
            <span className="ml-auto text-[10px] text-[var(--text-muted)] uppercase">{role}</span>
          </div>

          {page === 'dashboard' && <Dashboard onNavigate={navigate} role={role} />}
          {page === 'bots' && <Bots onViewBot={(id) => navigate('bot-detail', id)} role={role} />}
          {page === 'bot-detail' && botDetailId && <BotDetail botId={botDetailId} onBack={() => navigate('bots')} role={role} />}
          {page === 'attack' && <Attack role={role} />}
          {page === 'plans' && role === 'admin' && <Plans />}
          {page === 'admin-settings' && role === 'admin' && <AdminSettings />}
          {page === 'users' && role === 'admin' && <Users />}
          {page === 'logs' && role === 'admin' && <Logs />}
        </main>
      </div>
    </ToastProvider>
  );
}

export default App;
