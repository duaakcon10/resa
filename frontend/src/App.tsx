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

type Page = 'dashboard' | 'bots' | 'bot-detail' | 'attack' | 'plans' | 'users' | 'logs';

function App() {
  const [token, setToken] = useState<string | null>(localStorage.getItem('c2_token'));
  const [page, setPage] = useState<Page>('dashboard');
  const [botDetailId, setBotDetailId] = useState<string | null>(null);

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
  };

  if (!token) return <Login onLogin={handleLogin} />;

  return (
    <div className="flex h-screen">
      <Sidebar activePage={page} onNavigate={navigate} onLogout={handleLogout} />
      <main className="flex-1 overflow-y-auto bg-[var(--bg-primary)]">
        {page === 'dashboard' && <Dashboard />}
        {page === 'bots' && <Bots onViewBot={(id) => navigate('bot-detail', id)} />}
        {page === 'bot-detail' && botDetailId && <BotDetail botId={botDetailId} onBack={() => navigate('bots')} />}
        {page === 'attack' && <Attack />}
        {page === 'plans' && <Plans />}
        {page === 'users' && <Users />}
        {page === 'logs' && <Logs />}
      </main>
    </div>
  );
}

export default App;