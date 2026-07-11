import React, { useEffect, useState } from 'react';
import { api } from '../utils/api';
import { Bot, Crosshair, Users, Zap, Activity, Shield, TrendingUp, Server, ShoppingCart } from 'lucide-react';

interface Stats {
  total_bots: number; online_bots: number; rented_bots: number;
  active_attacks: number; total_users: number;
  total_packets: number; total_bandwidth_gb: number;
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    const fetch = () => api.get('/api/admin/stats')
      .then(r => { setStats(r.data); setError(false); })
      .catch(() => setError(true));
    fetch();
    const interval = setInterval(fetch, 5000);
    return () => clearInterval(interval);
  }, []);

  if (error && !stats) return (
    <div className="p-8 flex items-center justify-center h-full">
      <div className="text-center">
        <Server className="w-12 h-12 text-[var(--text-muted)] mx-auto mb-4" />
        <p className="text-[var(--text-secondary)]">Failed to load dashboard</p>
        <button onClick={() => window.location.reload()} className="mt-4 px-4 py-2 bg-emerald-600 rounded-lg text-sm">Retry</button>
      </div>
    </div>
  );

  if (!stats) return (
    <div className="p-8">
      <div className="skeleton h-8 w-48 mb-8" />
      <div className="grid grid-cols-3 gap-4 mb-8">
        {[...Array(6)].map((_, i) => <div key={i} className="skeleton h-28 rounded-2xl" />)}
      </div>
    </div>
  );

  const cards = [
    { label: 'Online Bots', value: stats.online_bots, sub: `${stats.total_bots} total`, icon: Bot, color: '#10b981', bg: 'rgba(16,185,129,0.06)', border: 'rgba(16,185,129,0.15)' },
    { label: 'Active Attacks', value: stats.active_attacks, sub: 'Running now', icon: Crosshair, color: '#ef4444', bg: 'rgba(239,68,68,0.06)', border: 'rgba(239,68,68,0.15)' },
    { label: 'Rented Bots', value: stats.rented_bots, sub: 'In use', icon: Users, color: '#3b82f6', bg: 'rgba(59,130,246,0.06)', border: 'rgba(59,130,246,0.15)' },
    { label: 'Total Users', value: stats.total_users, sub: 'Registered', icon: Users, color: '#8b5cf6', bg: 'rgba(139,92,246,0.06)', border: 'rgba(139,92,246,0.15)' },
    { label: 'Total Packets', value: fmt(stats.total_packets), sub: 'Lifetime', icon: Zap, color: '#f59e0b', bg: 'rgba(245,158,11,0.06)', border: 'rgba(245,158,11,0.15)' },
    { label: 'Bandwidth', value: `${stats.total_bandwidth_gb.toFixed(1)} GB`, sub: 'Lifetime', icon: Activity, color: '#f97316', bg: 'rgba(249,115,22,0.06)', border: 'rgba(249,115,22,0.15)' },
  ];

  return (
    <div className="p-8 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h2 className="text-2xl font-bold">Dashboard</h2>
          <p className="text-sm text-[var(--text-muted)] mt-1">Real-time system overview</p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-600/5 border border-emerald-600/15 rounded-full">
          <div className="relative">
            <div className="w-2 h-2 rounded-full bg-emerald-400" />
            <div className="w-2 h-2 rounded-full bg-emerald-400 absolute inset-0 animate-pulse-glow" />
          </div>
          <span className="text-[11px] font-medium text-emerald-400">Operational</span>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        {cards.map(({ label, value, sub, icon: Icon, color, bg, border }) => (
          <div
            key={label}
            className="rounded-2xl p-5 border transition-all hover:scale-[1.02] duration-200"
            style={{ background: bg, borderColor: border }}
          >
            <div className="flex items-center justify-between mb-4">
              <span className="text-[11px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.1em]">{label}</span>
              <Icon className="w-5 h-5" style={{ color }} />
            </div>
            <div className="text-3xl font-bold mb-1" style={{ color }}>{value}</div>
            <div className="text-[11px] text-[var(--text-muted)]">{sub}</div>
          </div>
        ))}
      </div>

      {/* Bottom Row */}
      <div className="grid grid-cols-2 gap-6">
        {/* Quick Actions */}
        <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-2xl p-6">
          <h3 className="text-sm font-semibold flex items-center gap-2 mb-5">
            <TrendingUp className="w-4 h-4 text-emerald-400" />Quick Actions
          </h3>
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: 'Manage Bots', icon: Bot },
              { label: 'Launch Attack', icon: Crosshair },
              { label: 'User Management', icon: Users },
              { label: 'Plans & Pricing', icon: ShoppingCart },
            ].map(({ label, icon: Icon }) => (
              <button key={label} className="flex flex-col items-center gap-2 p-5 bg-[var(--bg-primary)] border border-[var(--border)] rounded-xl hover:border-emerald-600/30 hover:bg-emerald-600/3 transition-all text-xs text-[var(--text-secondary)] group">
                <Icon className="w-5 h-5 text-[var(--text-muted)] group-hover:text-emerald-400 transition-colors" />
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* System Status */}
        <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-2xl p-6">
          <h3 className="text-sm font-semibold flex items-center gap-2 mb-5">
            <Shield className="w-4 h-4 text-emerald-400" />System Status
          </h3>
          <div className="space-y-2">
            {[
              'API Server', 'WebSocket Gateway', 'PostgreSQL',
              'Redis Cache', 'MB Bank Scanner', 'Telegram Bot',
            ].map(name => (
              <div key={name} className="flex items-center justify-between py-2.5 px-3 rounded-lg bg-[var(--bg-primary)] border border-[var(--border)]">
                <span className="text-xs text-[var(--text-secondary)]">{name}</span>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-emerald-400" />
                  <span className="text-[10px] text-[var(--text-muted)] font-medium">online</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function fmt(n: number): string {
  if (n >= 1e9) return (n / 1e9).toFixed(1) + 'B';
  if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
  if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
  return n.toLocaleString();
}