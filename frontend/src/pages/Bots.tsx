import React, { useEffect, useState, useCallback } from 'react';
import { api } from '../utils/api';
import { Search, Power, PowerOff, Ban, Trash2, ChevronLeft, ChevronRight, RefreshCw, CheckSquare, Square, LogOut, RotateCcw } from 'lucide-react';
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
  const [selected, setSelected] = useState<Set<string>>(new Set());

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

  const toggleSelect = (id: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const selectAll = () => {
    if (selected.size === bots.length) setSelected(new Set());
    else setSelected(new Set(bots.map(b => b.id)));
  };

  const bulkAction = async (action: string) => {
    if (selected.size === 0) return;
    const ids = Array.from(selected);
    const labels: Record<string, string> = { delete: 'DELETE', ban: 'BAN', unban: 'UNBAN', kick: 'KICK' };
    if (!confirm(`Bulk ${labels[action] || action} ${ids.length} bots?`)) return;
    try {
      const { data } = await api.post('/api/bots/bulk', { bot_ids: ids, action });
      toast(`${data.affected} bots ${action}d${data.failed ? ` (${data.failed} failed)` : ''}`, 'success');
      setSelected(new Set());
      fetchBots();
    } catch {
      toast('Bulk action failed', 'error');
    }
  };

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

  const deleteBot = async (id: string) => {
    if (!confirm('Delete this bot permanently from database?')) return;
    try {
      await api.delete(`/api/bots/${id}`);
      toast('Bot deleted', 'success');
      fetchBots();
    } catch {
      toast('Delete failed', 'error');
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
  const isAdmin = role === 'admin';

  return (
    <div className="p-6 md:p-8 animate-fade-in">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h2 className="text-2xl font-bold">{isAdmin ? 'Bot Management' : 'My Bots'}</h2>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            {total} bots · <span className="text-emerald-400">{onlineCount}</span> online
            {selected.size > 0 && <> · <span className="text-blue-400">{selected.size} selected</span></>}
          </p>
        </div>
        <button
          onClick={fetchBots}
          className="flex items-center gap-2 px-3 py-2 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors self-start"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </button>
      </div>

      {/* Bulk Action Bar */}
      {isAdmin && selected.size > 0 && (
        <div className="flex items-center gap-2 mb-4 p-3 bg-blue-600/5 border border-blue-600/20 rounded-2xl animate-fade-in">
          <span className="text-xs font-medium text-blue-400 mr-2">{selected.size} selected</span>
          <button onClick={() => bulkAction('kick')} className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-lg text-xs hover:bg-yellow-600/10 hover:text-yellow-400 transition-colors">
            <LogOut className="w-3.5 h-3.5" /> Kick
          </button>
          <button onClick={() => bulkAction('ban')} className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-lg text-xs hover:bg-red-600/10 hover:text-red-400 transition-colors">
            <Ban className="w-3.5 h-3.5" /> Ban
          </button>
          <button onClick={() => bulkAction('unban')} className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-lg text-xs hover:bg-emerald-600/10 hover:text-emerald-400 transition-colors">
            <RotateCcw className="w-3.5 h-3.5" /> Unban
          </button>
          <button onClick={() => bulkAction('delete')} className="flex items-center gap-1.5 px-3 py-1.5 bg-red-600/10 border border-red-600/20 rounded-lg text-xs text-red-400 hover:bg-red-600/20 transition-colors">
            <Trash2 className="w-3.5 h-3.5" /> Delete
          </button>
          <button onClick={() => setSelected(new Set())} className="ml-auto text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] px-2 py-1.5">
            Clear
          </button>
        </div>
      )}

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
                {isAdmin && (
                  <th className="p-4 w-10">
                    <button onClick={selectAll} className="hover:text-emerald-400 transition-colors">
                      {selected.size === bots.length && bots.length > 0 ? <CheckSquare className="w-4 h-4 text-emerald-400" /> : <Square className="w-4 h-4" />}
                    </button>
                  </th>
                )}
                <th className="p-4 w-10" />
                <th className="p-4 font-semibold">Identifier</th>
                <th className="p-4 font-semibold">IP</th>
                <th className="p-4 font-semibold">Country</th>
                <th className="p-4 font-semibold">Specs</th>
                <th className="p-4 font-semibold">Status</th>
                <th className="p-4 font-semibold">Rented</th>
                {isAdmin && <th className="p-4 font-semibold">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {loading && bots.length === 0 ? (
                <tr><td colSpan={isAdmin ? 9 : 8} className="p-12 text-center text-[var(--text-muted)]">Loading…</td></tr>
              ) : bots.length === 0 ? (
                <tr>
                  <td colSpan={isAdmin ? 9 : 8} className="p-12 text-center">
                    <p className="text-[var(--text-muted)] mb-1">No bots found</p>
                    <p className="text-[10px] text-[var(--text-muted)]">Connect a bot via WSS to see it here</p>
                  </td>
                </tr>
              ) : bots.map(bot => (
                <tr
                  key={bot.id}
                  className={`border-b border-[var(--border)]/50 hover:bg-[var(--bg-hover)] transition-colors ${selected.has(bot.id) ? 'bg-blue-600/5' : ''}`}
                >
                  {isAdmin && (
                    <td className="p-4" onClick={e => e.stopPropagation()}>
                      <button onClick={() => toggleSelect(bot.id)} className="hover:text-emerald-400 transition-colors">
                        {selected.has(bot.id) ? <CheckSquare className="w-4 h-4 text-blue-400" /> : <Square className="w-4 h-4 text-[var(--text-muted)]" />}
                      </button>
                    </td>
                  )}
                  <td className="p-4 cursor-pointer" onClick={() => onViewBot(bot.id)}>
                    <div className={`w-2.5 h-2.5 rounded-full ${statusDot(bot.status)}`} />
                  </td>
                  <td className="p-4 font-mono text-xs cursor-pointer" onClick={() => onViewBot(bot.id)}>
                    <div className="truncate max-w-[140px]" title={bot.bot_identifier}>{bot.bot_identifier}</div>
                    {bot.bot_version && <div className="text-[10px] text-[var(--text-muted)]">v{bot.bot_version}</div>}
                  </td>
                  <td className="p-4 text-xs text-[var(--text-muted)] font-mono cursor-pointer" onClick={() => onViewBot(bot.id)}>{bot.ip_address || '—'}</td>
                  <td className="p-4 text-xs cursor-pointer" onClick={() => onViewBot(bot.id)}>{bot.country || '—'}</td>
                  <td className="p-4 text-xs text-[var(--text-muted)] tabular-nums cursor-pointer" onClick={() => onViewBot(bot.id)}>
                    {bot.cpu_cores ?? '—'}c / {bot.ram_total_mb ?? '—'}MB / {bot.net_speed_mbps ?? '—'}Mbps
                  </td>
                  <td className="p-4 cursor-pointer" onClick={() => onViewBot(bot.id)}>
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-medium border ${statusBadge(bot.status)}`}>
                      {bot.status}
                    </span>
                  </td>
                  <td className="p-4 text-xs cursor-pointer" onClick={() => onViewBot(bot.id)}>
                    {bot.is_rented
                      ? <span className="text-blue-400 font-medium">Yes</span>
                      : <span className="text-[var(--text-muted)]">Free</span>}
                  </td>
                  {isAdmin && (
                    <td className="p-4" onClick={e => e.stopPropagation()}>
                      <div className="flex items-center gap-1.5">
                        {bot.status === 'online' ? (
                          <button onClick={() => toggle(bot.id, false)} className="p-1.5 hover:bg-yellow-600/10 rounded-lg text-yellow-400 transition-colors" title="Disable">
                            <PowerOff className="w-3.5 h-3.5" />
                          </button>
                        ) : bot.status !== 'banned' ? (
                          <button onClick={() => toggle(bot.id, true)} className="p-1.5 hover:bg-emerald-600/10 rounded-lg text-emerald-400 transition-colors" title="Enable">
                            <Power className="w-3.5 h-3.5" />
                          </button>
                        ) : null}
                        {bot.status === 'banned' ? (
                          <button onClick={() => bulkAction.call(null, bot.id)} className="p-1.5 hover:bg-emerald-600/10 rounded-lg text-emerald-400 transition-colors" title="Unban" onClickCapture={async (e) => { e.preventDefault(); try { await api.post(`/api/bots/${bot.id}/unban`); toast('Bot unbanned', 'success'); fetchBots(); } catch { toast('Unban failed', 'error'); } }}>
                            <RotateCcw className="w-3.5 h-3.5" />
                          </button>
                        ) : (
                          <button onClick={() => ban(bot.id)} className="p-1.5 hover:bg-red-600/10 rounded-lg text-red-400 transition-colors" title="Ban">
                            <Ban className="w-3.5 h-3.5" />
                          </button>
                        )}
                        <button onClick={() => deleteBot(bot.id)} className="p-1.5 hover:bg-red-600/10 rounded-lg text-red-500 transition-colors" title="Delete">
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  )}
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
