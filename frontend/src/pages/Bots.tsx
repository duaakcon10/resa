import React, { useEffect, useState, useCallback } from 'react';
import { api } from '../utils/api';
import { Search, Power, PowerOff, Ban, ChevronLeft, ChevronRight, RefreshCw } from 'lucide-react';
import { useToast } from '../components/Toast';

interface Bot {
  id: string; bot_identifier: string; nickname: string | null;
  ip_address: string | null; country: string | null; os_name: string | null;
  cpu_cores: number; ram_total_mb: number; net_speed_mbps: number;
  status: string; is_rented: boolean; max_pps: number;
  enabled_methods: string[]; last_heartbeat_at: string | null; bot_version: string;
}

export default function Bots({ onViewBot, role = 'user' }: { onViewBot: (id: string) => void; role?: 'admin' | 'user' }) {
  const { toast } = useToast();
  const [bots, setBots] = useState<Bot[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({ status: '', is_rented: '', search: '' });
  const [loading, setLoading] = useState(true);

  const fetchBots = useCallback(async () => {
    setLoading(true);
    try {
      const p = new URLSearchParams();
      if (filters.status) p.set('status', filters.status);
      if (filters.is_rented) p.set('is_rented', filters.is_rented);
      if (filters.search) p.set('search', filters.search);
      p.set('page', String(page));
      p.set('per_page', '50');
      const { data } = await api.get(`/api/bots/?${p}`);
      setBots(data.items || []);
      setTotal(data.total || 0);
    } catch {
      toast('Failed to load bots', 'error');
    }
    setLoading(false);
  }, [page, filters, toast]);

  useEffect(() => {
    fetchBots();
    const i = setInterval(fetchBots, 10000);
    return () => clearInterval(i);
  }, [fetchBots]);

  const toggle = async (id: string, on: boolean) => {
    try {
      await api.patch(`/api/bots/${id}/toggle`, { enabled: on });
      toast(on ? 'Bot enabled' : 'Bot disabled', 'success');
      fetchBots();
    } catch {
      toast('Toggle failed', 'error');
    }
  };

  const ban = async (id: string) => {
    if (!confirm('Ban this bot permanently?')) return;
    try {
      await api.post(`/api/bots/${id}/ban`);
      toast('Bot banned', 'success');
      fetchBots();
    } catch {
      toast('Ban failed', 'error');
    }
  };

  const statusDot = (s: string) =>
    s === 'online' ? 'bg-emerald-400' :
    s === 'attacking' ? 'bg-yellow-400' :
    s === 'banned' ? 'bg-red-400' : 'bg-gray-600';

  const statusBadge = (s: string) => {
    const map: Record<string, string> = {
      online: 'bg-emerald-600/10 text-emerald-400 border-emerald-600/20',
      attacking: 'bg-yellow-600/10 text-yellow-400 border-yellow-600/20',
      banned: 'bg-red-600/10 text-red-400 border-red-600/20',
      offline: 'bg-gray-600/10 text-gray-500 border-gray-600/20',
    };
    return map[s] || map.offline;
  };

  const onlineCount = bots.filter(b => b.status === 'online').length;
  const tp = Math.max(1, Math.ceil(total / 50));

  return (
    <div className="p-6 md:p-8 animate-fade-in">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h2 className="text-2xl font-bold">{role === 'admin' ? 'Bot Management' : 'My Bots'}</h2>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            {total} bots · <span className="text-emerald-400">{onlineCount}</span> online on this page
          </p>
        </div>
        <button
          onClick={fetchBots}
          className="flex items-center gap-2 px-3 py-2 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors self-start"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </button>
      </div>

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
        <select
          className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl px-4 py-2.5 text-sm text-[var(--text-secondary)] focus:outline-none cursor-pointer"
          value={filters.status}
          onChange={e => { setFilters(f => ({ ...f, status: e.target.value })); setPage(1); }}
        >
          <option value="">All Status</option>
          <option value="online">Online</option>
          <option value="offline">Offline</option>
          <option value="attacking">Attacking</option>
          <option value="banned">Banned</option>
        </select>
        <select
          className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl px-4 py-2.5 text-sm text-[var(--text-secondary)] focus:outline-none cursor-pointer"
          value={filters.is_rented}
          onChange={e => { setFilters(f => ({ ...f, is_rented: e.target.value })); setPage(1); }}
        >
          <option value="">All Rentals</option>
          <option value="true">Rented</option>
          <option value="false">Available</option>
        </select>
      </div>

      <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px]">
            <thead>
              <tr className="border-b border-[var(--border)] text-left text-[11px] text-[var(--text-muted)] uppercase tracking-[0.08em]">
                <th className="p-4 w-10" />
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
              {loading && bots.length === 0 ? (
                <tr><td colSpan={10} className="p-12 text-center text-[var(--text-muted)]">Loading…</td></tr>
              ) : bots.length === 0 ? (
                <tr>
                  <td colSpan={10} className="p-12 text-center">
                    <p className="text-[var(--text-muted)] mb-1">No bots found</p>
                    <p className="text-[10px] text-[var(--text-muted)]">Connect a bot via WSS to see it here</p>
                  </td>
                </tr>
              ) : bots.map(bot => (
                <tr
                  key={bot.id}
                  className="border-b border-[var(--border)]/50 hover:bg-[var(--bg-hover)] cursor-pointer transition-colors"
                  onClick={() => onViewBot(bot.id)}
                >
                  <td className="p-4"><div className={`w-2.5 h-2.5 rounded-full ${statusDot(bot.status)}`} /></td>
                  <td className="p-4 font-mono text-xs">
                    <div className="truncate max-w-[140px]" title={bot.bot_identifier}>{bot.bot_identifier}</div>
                    {bot.bot_version && <div className="text-[10px] text-[var(--text-muted)]">v{bot.bot_version}</div>}
                  </td>
                  <td className="p-4 text-xs text-[var(--text-muted)] font-mono">{bot.ip_address || '—'}</td>
                  <td className="p-4 text-xs">{bot.country || '—'}</td>
                  <td className="p-4 text-xs text-[var(--text-muted)] max-w-[120px] truncate">{bot.os_name || '—'}</td>
                  <td className="p-4 text-xs text-[var(--text-muted)] tabular-nums">{bot.cpu_cores ?? '—'}c / {bot.ram_total_mb ?? '—'}MB</td>
                  <td className="p-4 text-xs text-[var(--text-muted)] tabular-nums">{bot.net_speed_mbps ?? '—'} Mbps</td>
                  <td className="p-4">
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-medium border ${statusBadge(bot.status)}`}>
                      {bot.status}
                    </span>
                  </td>
                  <td className="p-4 text-xs">
                    {bot.is_rented
                      ? <span className="text-blue-400 font-medium">Yes</span>
                      : <span className="text-[var(--text-muted)]">Free</span>}
                  </td>
                  <td className="p-4" onClick={e => e.stopPropagation()}>
                    {role === 'admin' ? (
                      <div className="flex items-center gap-1.5">
                        {bot.status === 'online' ? (
                          <button onClick={() => toggle(bot.id, false)} className="p-1.5 hover:bg-yellow-600/10 rounded-lg text-yellow-400 transition-colors" title="Disable">
                            <PowerOff className="w-3.5 h-3.5" />
                          </button>
                        ) : (
                          <button onClick={() => toggle(bot.id, true)} className="p-1.5 hover:bg-emerald-600/10 rounded-lg text-emerald-400 transition-colors" title="Enable">
                            <Power className="w-3.5 h-3.5" />
                          </button>
                        )}
                        <button onClick={() => ban(bot.id)} className="p-1.5 hover:bg-red-600/10 rounded-lg text-red-400 transition-colors" title="Ban">
                          <Ban className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ) : (
                      <span className="text-[10px] text-[var(--text-muted)]">View</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="flex items-center justify-between mt-4">
        <div className="text-xs text-[var(--text-muted)]">Page {page} of {tp} ({total} total)</div>
        <div className="flex gap-2">
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="p-2 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-lg disabled:opacity-30 hover:bg-[var(--bg-hover)] transition-colors">
            <ChevronLeft className="w-4 h-4" />
          </button>
          <button onClick={() => setPage(p => Math.min(tp, p + 1))} disabled={page >= tp} className="p-2 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-lg disabled:opacity-30 hover:bg-[var(--bg-hover)] transition-colors">
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
