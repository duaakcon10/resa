import React, { useEffect, useState } from 'react';
import { api } from '../utils/api';
import { Ban, CheckCircle, Search } from 'lucide-react';
import { useToast } from '../components/Toast';

interface User {
  id: string; username: string; email: string; role: string;
  is_banned: boolean; created_at: string;
}

export default function Users() {
  const { toast } = useToast();
  const [users, setUsers] = useState<User[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    api.get('/api/admin/users')
      .then(r => setUsers(Array.isArray(r.data) ? r.data : r.data?.items || []))
      .catch(() => toast('Failed to load users', 'error'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const toggleBan = async (id: string, ban: boolean) => {
    try {
      if (ban) await api.post(`/api/admin/users/${id}/ban`);
      else await api.post(`/api/admin/users/${id}/unban`);
      setUsers(prev => prev.map(u => u.id === id ? { ...u, is_banned: ban } : u));
      toast(ban ? 'User banned' : 'User unbanned', 'success');
    } catch {
      toast('Action failed', 'error');
    }
  };

  const filtered = users.filter(u =>
    u.username?.toLowerCase().includes(search.toLowerCase()) ||
    (u.email && u.email.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <div className="p-6 md:p-8 animate-fade-in">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <h2 className="text-2xl font-bold">User Management</h2>
        <div className="text-xs text-[var(--text-muted)]">{users.length} users</div>
      </div>
      <div className="relative mb-6 max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--text-muted)]" />
        <input
          placeholder="Search users..."
          className="w-full bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl pl-10 pr-4 py-2.5 text-xs focus:outline-none focus:border-emerald-600 transition-colors"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>
      <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px]">
            <thead>
              <tr className="border-b border-[var(--border)] text-left text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.08em]">
                <th className="p-4">Username</th>
                <th className="p-4">Email</th>
                <th className="p-4">Role</th>
                <th className="p-4">Status</th>
                <th className="p-4">Created</th>
                <th className="p-4">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={6} className="p-12 text-center text-[var(--text-muted)]">Loading…</td></tr>
              ) : filtered.length === 0 ? (
                <tr><td colSpan={6} className="p-12 text-center text-[var(--text-muted)]">No users</td></tr>
              ) : filtered.map(u => (
                <tr key={u.id} className="border-b border-[var(--border)]/50 text-xs hover:bg-[var(--bg-hover)]/40">
                  <td className="p-4 font-medium">{u.username}</td>
                  <td className="p-4 text-[var(--text-muted)]">{u.email || '—'}</td>
                  <td className="p-4">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-medium border ${
                      u.role === 'admin'
                        ? 'bg-purple-600/10 text-purple-400 border-purple-600/20'
                        : 'bg-gray-600/10 text-[var(--text-muted)] border-gray-600/20'
                    }`}>{u.role}</span>
                  </td>
                  <td className="p-4">
                    {u.is_banned
                      ? <span className="text-red-400 text-[10px] font-medium">Banned</span>
                      : <span className="text-emerald-400 text-[10px] font-medium">Active</span>}
                  </td>
                  <td className="p-4 text-[var(--text-muted)]">
                    {u.created_at ? new Date(u.created_at).toLocaleDateString() : '—'}
                  </td>
                  <td className="p-4">
                    {u.is_banned ? (
                      <button onClick={() => toggleBan(u.id, false)} className="p-1.5 hover:bg-emerald-600/10 rounded-lg text-emerald-400 transition-colors" title="Unban">
                        <CheckCircle className="w-3.5 h-3.5" />
                      </button>
                    ) : (
                      <button onClick={() => toggleBan(u.id, true)} className="p-1.5 hover:bg-red-600/10 rounded-lg text-red-400 transition-colors" title="Ban">
                        <Ban className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
