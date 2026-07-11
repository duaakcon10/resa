import React, { useEffect, useState, useCallback } from 'react';
import { api } from '../utils/api';
import { Search, Power, PowerOff, Ban, ChevronLeft, ChevronRight, Filter, RefreshCw } from 'lucide-react';

interface Bot {
  id: string; bot_identifier: string; nickname: string | null;
  ip_address: string | null; country: string | null; os_name: string | null;
  cpu_cores: number; ram_total_mb: number; net_speed_mbps: number;
  status: string; is_rented: boolean; max_pps: number;
  enabled_methods: string[]; last_heartbeat_at: string | null; bot_version: string;
}

export default function Bots({ onViewBot }: { onViewBot: (id: string) => void }) {
  const [bots, setBots] = useState<Bot[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({ status: '', is_rented: '', search: '' });
  const [loading, setLoading] = useState(true);

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const p = new URLSearchParams();
      if (filters.status) p.set('status', filters.status);
      if (filters.is_rented) p.set('is_rented', filters.is_rented);
      if (filters.search) p.set('search', filters.search);
      p.set('page', String(page)); p.set('per_page', '50');
      const { data } = await api.get(`/api/bots/?${p}`);
      setBots(data.items); setTotal(data.total);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [page, filters]);

  useEffect(() => { fetch(); const i = setInterval(fetch, 10000); return () => clearInterval(i); }, [fetch]);

  const toggle = async (id: string, on: boolean) => { await api.patch(`/api/bots/${id}/toggle`, { enabled: on }); fetch(); };
  const ban = async (id: string) => { if (!confirm('Ban this bot permanently?')) return; await api.post(`/api/bots/${id}/ban`); fetch(); };

  const statusDot = (s: string) => s === 'online' ? 'bg-emerald-400' : s === 'attacking' ? 'bg-yellow-400' : s === 'banned' ? 'bg-red-400' : 'bg-gray-600';
  const statusBadge = (s: string) => {
    const map: Record<string, string> = {
      online: 'bg-emerald-600/10 text-emerald-400 border-emerald-600/20',
      attacking: 'bg-yellow-600/10 text-yellow-400 border-yellow-600/20',
      banned: 'bg-red-600/10 text-red-400 border-red-600/20',
      offline: 'bg-gray-600/10 text-gray-500 border-gray-600/20',
    };
    return map[s] || map.offline;
  };

  const tp = Math.ceil(total / 50);

  return (
    <div className="p-8 animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold">Bot Management</h2>
          <p className="text-sm text-[var(--text-muted)] mt-1">{total} bots · {bots.filter(b => b.status === 'online').length} online</p>
        </div>
        <button onClick={fetch} className="flex items-center gap-2 px-3 py-2 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-lg text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors">
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-6 flex-wrap">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
          <input
            placeholder="Search by ID, IP, nickname..."
            className="w-full bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl pl-10 pr-4 py-2.5 text-sm focus:outline-none focus:border-emerald-600 transition-colors placeholder:text-[var(--text-muted)]"
            value={filters.search}
            onChange={e => { setFilters(f => ({ ...f, search: e.target.value })); setPage(1); }}
          />
        </div>
        <select className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl px-4 py-2.5 text-sm text-[var(--text-secondary)] focus:outline-none cursor-pointer" value={filters.status} onChange={e => { setFilters(f => ({ ...f, status: e.target.value })); setPage(1); }}>
          <option value="">All Status</option><option value="online">Online</option><option value="offline">Offline</option><option value="attacking">Attacking</option><option value="banned">Banned</option>
        </select>
        <select className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl px-4 py-2.5 text-sm text-[var(--text-secondary)] focus:outline-none cursor-pointer" value={filters.is_rented} onChange={e => { setFilters(f => ({ ...f, is_rented: e.target.value })); setPage(1); }}>
          <option value="">All Rentals</option><option value="true">Rented</option><option value="false">Available</option>
        </select>
      </div>

      {/* Table */}
      <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-[var(--border)] text-left text-[11px] text-[var(--text-muted)] uppercase tracking-[0.08em]">
                <th className="p-4 w-10"></th>
                <th className="p-4 font-semibold">Identifier</th>
                <th className="p-4 font-semibold">IP</th>
                <th className="p-4 font-semibold">Country</th>
                <th className="p-4 font-semibold">OS</th>
                <th className="p-4 font-semibold">Specs</th>
                <th className="p-4 font-semibold">Speed</th>
                <th className="p-4 font-semibold">Status</th>
                <th className="p-4 font-semibold">Rented</th>
                <th className="p-4 font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={10} className="p-12 text-center text-[var(--text-muted)]">Loading...</td></tr>
              ) : bots.length === 0 ? (
                <tr><td colSpan={10} className="p-12 text-center text-[var(--text-muted)]">No bots found</td></tr>
              ) : bots.map(bot => (
                <tr
                  key={bot.id}
                  className="border-b border-[var(--border)]/50 hover:bg-[var(--bg-hover)] cursor-pointer transition-colors"
                  onClick={() => onViewBot(bot.id)}
                >
                  <td className="p-4"><div className={`w-2.5 h-2.5 rounded-full ${statusDot(bot.status)}`} /></td>
                  <td className="p-4 font-mono text-xs">{bot.bot_identifier}</td>
                  <td className="p-4 text-xs text-[var(--text-muted)]">{bot.ip_address || '—'}</td>
                  <td className="p-4 text-xs">{bot.country || '—'}</td>
                  <td className="p-4 text-xs text-[var(--text-muted)]">{bot.os_name || '—'}</td>
                  <td className="p-4 text-xs text-[var(--text-muted)]">{bot.cpu_cores}c / {bot.ram_total_mb}MB</td>
                  <td className="p-4 text-xs text-[var(--text-muted)]">{bot.net_speed_mbps} Mbps</td>
                  <td className="p-4">
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-medium border ${statusBadge(bot.status)}`}>
                      {bot.status}
                    </span>
                  </td>
                  <td className="p-4 text-xs">
                    {bot.is_rented ? <span className="text-blue-400 font-medium">Yes</span> : <span className="text-[var(--text-muted)]">Free</span>}
                  </td>
                  <td className="p-4" onClick={e => e.stopPropagation()}>
                    <div className="flex items-center gap-1.5">
                      {bot.status === 'online' ? (
                        <button onClick={() => toggle(bot.id, false)} className="p-1.5 hover:bg-yellow-600/10 rounded-lg text-yellow-400 transition-colors" title="Disable"><PowerOff className="w-3.5 h-3.5" /></button>
                      ) : (
                        <button onClick={() => toggle(bot.id, true)} className="p-1.5 hover:bg-emerald-600/10 rounded-lg text-emerald-400 transition-colors" title="Enable"><Power className="w-3.5 h-3.5" /></button>
                      )}
                      <button onClick={() => ban(bot.id)} className="p-1.5 hover:bg-red-600/10 rounded-lg text-red-400 transition-colors" title="Ban"><Ban className="w-3.5 h-3.5" /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between mt-4">
        <div className="text-xs text-[var(--text-muted)]">Page {page} of {tp} ({total} total)</div>
        <div className="flex gap-2">
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="p-2 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-lg disabled:opacity-30 hover:bg-[var(--bg-hover)] transition-colors"><ChevronLeft className="w-4 h-4" /></button>
          <button onClick={() => setPage(p => Math.min(tp, p + 1))} disabled={page >= tp} className="p-2 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-lg disabled:opacity-30 hover:bg-[var(--bg-hover)] transition-colors"><ChevronRight className="w-4 h-4" /></button>
        </div>
      </div>
    </div>
  );
}