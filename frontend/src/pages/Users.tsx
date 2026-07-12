import React, { useEffect, useState } from 'react';
import { api } from '../utils/api';
import { Ban, CheckCircle, Search, UserPlus, X } from 'lucide-react';
import { useToast } from '../components/Toast';

interface User {
  id: string; username: string; email: string; role: string;
  is_banned: boolean; created_at: string;
}

interface Plan {
  id: string; name: string; slug: string;
}

export default function Users() {
  const { toast } = useToast();
  const [users, setUsers] = useState<User[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ username: '', password: '', email: '', role: 'user' });
  const [creating, setCreating] = useState(false);
  const [planUser, setPlanUser] = useState<string | null>(null);
  const [planId, setPlanId] = useState('');
  const [planDays, setPlanDays] = useState(30);

  const load = () => {
    setLoading(true);
    api.get('/api/admin/users')
      .then(r => setUsers(Array.isArray(r.data) ? r.data : r.data?.items || []))
      .catch(() => toast('Failed to load users', 'error'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    api.get('/api/plans/').then(r => setPlans(Array.isArray(r.data) ? r.data : [])).catch(() => {});
  }, []);

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

  const createUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    try {
      await api.post('/api/admin/users', form);
      toast('User created', 'success');
      setShowCreate(false);
      setForm({ username: '', password: '', email: '', role: 'user' });
      load();
    } catch (err: any) {
      toast(err?.response?.data?.detail || 'Create failed', 'error');
    }
    setCreating(false);
  };

  const assignPlan = async () => {
    if (!planUser || !planId) return;
    try {
      await api.post(`/api/admin/users/${planUser}/plan`, { plan_id: planId, days: planDays });
      toast('Plan assigned', 'success');
      setPlanUser(null);
    } catch (err: any) {
      toast(err?.response?.data?.detail || 'Assign failed', 'error');
    }
  };

  const filtered = users.filter(u =>
    u.username?.toLowerCase().includes(search.toLowerCase()) ||
    (u.email && u.email.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <div className="p-6 md:p-8 animate-fade-in">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <div>
          <h2 className="text-2xl font-bold">User Management</h2>
          <p className="text-xs text-[var(--text-muted)] mt-1">{users.length} accounts · create, ban, assign plans</p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-700 rounded-xl text-xs font-semibold transition-colors"
        >
          <UserPlus className="w-3.5 h-3.5" /> Create User
        </button>
      </div>

      {showCreate && (
        <form onSubmit={createUser} className="mb-6 p-5 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-2xl space-y-4 relative">
          <button type="button" onClick={() => setShowCreate(false)} className="absolute right-4 top-4 text-[var(--text-muted)] hover:text-white">
            <X className="w-4 h-4" />
          </button>
          <h3 className="text-sm font-semibold">New account</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <input required placeholder="Username" className="bg-[var(--bg-primary)] border border-[var(--border)] rounded-xl px-3 py-2 text-xs" value={form.username} onChange={e => setForm(f => ({ ...f, username: e.target.value }))} />
            <input required type="password" placeholder="Password" className="bg-[var(--bg-primary)] border border-[var(--border)] rounded-xl px-3 py-2 text-xs" value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))} />
            <input type="email" placeholder="Email (optional)" className="bg-[var(--bg-primary)] border border-[var(--border)] rounded-xl px-3 py-2 text-xs" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} />
            <select className="bg-[var(--bg-primary)] border border-[var(--border)] rounded-xl px-3 py-2 text-xs" value={form.role} onChange={e => setForm(f => ({ ...f, role: e.target.value }))}>
              <option value="user">User</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          <button type="submit" disabled={creating} className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 rounded-xl text-xs font-semibold disabled:opacity-50">
            {creating ? 'Creating…' : 'Create'}
          </button>
        </form>
      )}

      {planUser && (
        <div className="mb-6 p-5 bg-[var(--bg-secondary)] border border-emerald-600/20 rounded-2xl space-y-3">
          <div className="flex justify-between items-center">
            <h3 className="text-sm font-semibold">Assign plan</h3>
            <button type="button" onClick={() => setPlanUser(null)} className="text-[var(--text-muted)]"><X className="w-4 h-4" /></button>
          </div>
          <select className="w-full bg-[var(--bg-primary)] border border-[var(--border)] rounded-xl px-3 py-2 text-xs" value={planId} onChange={e => setPlanId(e.target.value)}>
            <option value="">Select plan…</option>
            {plans.map(p => <option key={p.id} value={p.id}>{p.name} ({p.slug})</option>)}
          </select>
          <input type="number" min={1} max={365} className="w-full bg-[var(--bg-primary)] border border-[var(--border)] rounded-xl px-3 py-2 text-xs" value={planDays} onChange={e => setPlanDays(parseInt(e.target.value) || 30)} />
          <button type="button" onClick={assignPlan} className="px-4 py-2 bg-emerald-600 rounded-xl text-xs font-semibold">Assign</button>
        </div>
      )}

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
          <table className="w-full min-w-[720px]">
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
                    <div className="flex items-center gap-1">
                      <button onClick={() => { setPlanUser(u.id); setPlanId(plans[0]?.id || ''); }} className="px-2 py-1 text-[10px] rounded-lg border border-[var(--border)] hover:border-emerald-600/30 text-[var(--text-muted)] hover:text-emerald-400">Plan</button>
                      {u.is_banned ? (
                        <button onClick={() => toggleBan(u.id, false)} className="p-1.5 hover:bg-emerald-600/10 rounded-lg text-emerald-400 transition-colors" title="Unban">
                          <CheckCircle className="w-3.5 h-3.5" />
                        </button>
                      ) : (
                        <button onClick={() => toggleBan(u.id, true)} className="p-1.5 hover:bg-red-600/10 rounded-lg text-red-400 transition-colors" title="Ban">
                          <Ban className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
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
