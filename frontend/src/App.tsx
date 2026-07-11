import React, { useState, useEffect } from 'react';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Bots from './pages/Bots';
import BotDetail from './pages/BotDetail';
import Attack from './pages/Attack';
import Plans from './pages/Plans';
import Users from './pages/Users';
import Logs from './pages/Logs';
import Sidebar from './components/Sidebar';
import { ToastProvider } from './components/Toast';
import { Menu } from 'lucide-react';

export type Page = 'dashboard' | 'bots' | 'bot-detail' | 'attack' | 'plans' | 'users' | 'logs';

function App() {
  const [token, setToken] = useState<string | null>(localStorage.getItem('c2_token'));
  const [page, setPage] = useState<Page>('dashboard');
  const [botDetailId, setBotDetailId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem('c2_token');
    if (stored !== token) setToken(stored);
  }, []);

  const handleLogin = (t: string) => {
    localStorage.setItem('c2_token', t);
    setToken(t);
  };

  const handleLogout = () => {
    localStorage.removeItem('c2_token');
    setToken(null);
  };

  const navigate = (p: Page, id?: string) => {
    if (p === 'bot-detail' && id) setBotDetailId(id);
    setPage(p);
    setSidebarOpen(false);
  };

  if (!token) {
    return (
      <ToastProvider>
        <Login onLogin={handleLogin} />
      </ToastProvider>
    );
  }

  return (
    <ToastProvider>
      <div className="flex h-screen overflow-hidden">
        {/* Mobile overlay */}
        {sidebarOpen && (
          <div
            className="fixed inset-0 bg-black/60 z-20 lg:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        <div className={`
          fixed lg:static inset-y-0 left-0 z-30 transform transition-transform duration-200
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        `}>
          <Sidebar activePage={page} onNavigate={navigate} onLogout={handleLogout} />
        </div>

        <main className="flex-1 overflow-y-auto bg-[var(--bg-primary)] min-w-0">
          {/* Mobile top bar */}
          <div className="lg:hidden sticky top-0 z-10 flex items-center gap-3 px-4 py-3 bg-[var(--bg-secondary)]/90 backdrop-blur border-b border-[var(--border)]">
            <button
              onClick={() => setSidebarOpen(true)}
              className="p-2 rounded-lg hover:bg-[var(--bg-hover)] text-[var(--text-secondary)]"
            >
              <Menu className="w-5 h-5" />
            </button>
            <span className="text-sm font-semibold">C2 Center</span>
          </div>

          {page === 'dashboard' && <Dashboard onNavigate={navigate} />}
          {page === 'bots' && <Bots onViewBot={(id) => navigate('bot-detail', id)} />}
          {page === 'bot-detail' && botDetailId && (
            <BotDetail botId={botDetailId} onBack={() => navigate('bots')} />
          )}
          {page === 'attack' && <Attack />}
          {page === 'plans' && <Plans />}
          {page === 'users' && <Users />}
          {page === 'logs' && <Logs />}
        </main>
      </div>
    </ToastProvider>
  );
}

export default App;
