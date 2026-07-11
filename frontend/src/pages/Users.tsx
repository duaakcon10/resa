import React, { useEffect, useState } from 'react';
import { api } from '../utils/api';
import { Ban, CheckCircle, Search } from 'lucide-react';

interface User { id: string; username: string; email: string; role: string; is_banned: boolean; created_at: string; }

export default function Users() {
  const [users, setUsers] = useState<User[]>([]);
  const [search, setSearch] = useState('');

  useEffect(() => { api.get('/api/admin/users').then(r => setUsers(r.data)).catch(() => {}); }, []);

  const toggleBan = async (id: string, ban: boolean) => {
    if (ban) await api.post(`/api/admin/users/${id}/ban`);
    else await api.post(`/api/admin/users/${id}/unban`);
    setUsers(prev => prev.map(u => u.id === id ? { ...u, is_banned: ban } : u));
  };

  const filtered = users.filter(u =>
    u.username.toLowerCase().includes(search.toLowerCase()) ||
    (u.email && u.email.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <div className="p-8 animate-fade-in">
      <div className="flex items-center justify-between mb-6"><h2 className="text-2xl font-bold">User Management</h2><div className="text-xs text-[var(--text-muted)]">{users.length} users</div></div>
      <div className="relative mb-6 max-w-md"><Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--text-muted)]" /><input placeholder="Search users..." className="w-full bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl pl-10 pr-4 py-2.5 text-xs focus:outline-none focus:border-emerald-600 transition-colors" value={search} onChange={e => setSearch(e.target.value)} /></div>
      <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-2xl overflow-hidden">
        <table className="w-full">
          <thead><tr className="border-b border-[var(--border)] text-left text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.08em]"><th className="p-4">Username</th><th className="p-4">Email</th><th className="p-4">Role</th><th className="p-4">Status</th><th className="p-4">Created</th><th className="p-4">Actions</th></tr></thead>
          <tbody>{filtered.map(u => (
            <tr key={u.id} className="border-b border-[var(--border)]/50 text-xs">
              <td className="p-4 font-medium">{u.username}</td>
              <td className="p-4 text-[var(--text-muted)]">{u.email || '—'}</td>
              <td className="p-4"><span className={`px-2 py-0.5 rounded text-[10px] font-medium border ${u.role === 'admin' ? 'bg-purple-600/10 text-purple-400 border-purple-600/20' : 'bg-gray-600/10 text-[var(--text-muted)] border-gray-600/20'}`}>{u.role}</span></td>
              <td className="p-4">{u.is_banned ? <span className="text-red-400 text-[10px] font-medium">Banned</span> : <span className="text-emerald-400 text-[10px] font-medium">Active</span>}</td>
              <td className="p-4 text-[var(--text-muted)]">{new Date(u.created_at).toLocaleDateString()}</td>
              <td className="p-4">{u.is_banned ? <button onClick={() => toggleBan(u.id, false)} className="p-1.5 hover:bg-emerald-600/10 rounded-lg text-emerald-400 transition-colors"><CheckCircle className="w-3.5 h-3.5" /></button> : <button onClick={() => toggleBan(u.id, true)} className="p-1.5 hover:bg-red-600/10 rounded-lg text-red-400 transition-colors"><Ban className="w-3.5 h-3.5" /></button>}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </div>
  );
}