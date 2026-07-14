import React from 'react';
import {
  LayoutDashboard, Bot, Crosshair, ShoppingCart, Users, ScrollText, LogOut, Shield, Activity, Settings, CreditCard
} from 'lucide-react';
import type { Page, Role } from '../App';

const allNav: { page: Page; label: string; icon: React.ElementType; desc: string; adminOnly?: boolean }[] = [
  { page: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, desc: 'Overview' },
  { page: 'bots', label: 'Bots', icon: Bot, desc: 'Fleet' },
  { page: 'attack', label: 'Attack', icon: Crosshair, desc: 'Launch' },
  { page: 'plans', label: 'Plans', icon: ShoppingCart, desc: 'Billing', adminOnly: true },
  { page: 'admin-settings', label: 'Settings', icon: Settings, desc: 'Config', adminOnly: true },
  { page: 'users', label: 'Users', icon: Users, desc: 'Accounts', adminOnly: true },
  { page: 'logs', label: 'Logs', icon: ScrollText, desc: 'Audit', adminOnly: true },
];

export default function Sidebar({
  activePage, onNavigate, onLogout, role, username,
}: {
  activePage: Page;
  onNavigate: (p: Page) => void;
  onLogout: () => void;
  role: Role;
  username: string;
}) {
  const navItems = allNav.filter(n => !n.adminOnly || role === 'admin');

  return (
    <aside className="w-64 h-full bg-[var(--bg-secondary)] border-r border-[var(--border)] flex flex-col select-none relative">
      {/* Cyber top accent line */}
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-[var(--accent)] to-transparent opacity-30" />
      <div className="p-5 border-b border-[var(--border)]">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[var(--accent-glow)] to-transparent border border-[var(--accent)]/30 flex items-center justify-center cyber-glow">
            <Shield className="w-5 h-5 text-[var(--accent)]" />
          </div>
          <div>
            <h1 className="text-base font-bold tracking-tight leading-none cyber-text-glow">C2 Center</h1>
            <p className="text-[10px] text-[var(--text-muted)] mt-1">v4.0 · Cyber</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
        <div className="px-3 py-2">
          <p className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.15em]">
            {role === 'admin' ? '⚙ Admin' : '👤 Client'}
          </p>
        </div>
        {navItems.map(({ page, label, icon: Icon, desc }) => {
          const active = activePage === page || (activePage === 'bot-detail' && page === 'bots');
          return (
            <button
              key={page}
              onClick={() => onNavigate(page)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all duration-150 group
                ${active
                  ? 'bg-[var(--accent-glow)] text-[var(--accent)] font-medium border border-[var(--accent)]/20 cyber-glow'
                  : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] border border-transparent'
                }`}
            >
              <Icon className={`w-4 h-4 flex-shrink-0 transition-colors ${active ? 'text-emerald-400' : 'text-[var(--text-muted)] group-hover:text-[var(--text-secondary)]'}`} />
              <span className="flex-1 text-left">{label}</span>
              <span className={`text-[10px] ${active ? 'text-emerald-500/70' : 'text-[var(--text-muted)]/60'}`}>{desc}</span>
            </button>
          );
        })}
      </nav>

      <div className="px-3 pb-2">
        <div className="px-3 py-2.5 rounded-xl bg-[var(--bg-card)] border border-[var(--border)]">
          <div className="flex items-center gap-2">
            <div className="relative">
              <div className="w-2 h-2 rounded-full bg-emerald-400" />
              <div className="w-2 h-2 rounded-full bg-emerald-400 absolute inset-0 animate-pulse-glow" />
            </div>
            <span className="text-[11px] text-[var(--text-muted)]">Gateway online</span>
          </div>
        </div>
      </div>

      <div className="p-3 border-t border-[var(--border)]">
        <div className="flex items-center justify-between mb-3 px-1">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-full bg-emerald-600/10 border border-emerald-600/20 flex items-center justify-center">
              <Activity className="w-3.5 h-3.5 text-emerald-400" />
            </div>
            <div>
              <p className="text-xs font-medium text-[var(--text-primary)] truncate max-w-[120px]">
                {username || (role === 'admin' ? 'Admin' : 'User')}
              </p>
              <p className="text-[10px] text-[var(--text-muted)] capitalize">{role} access</p>
            </div>
          </div>
        </div>
        <button
          onClick={onLogout}
          className="w-full flex items-center justify-center gap-2 px-3 py-2.5 text-sm text-[var(--text-muted)] hover:text-red-400 rounded-xl hover:bg-red-400/5 border border-transparent hover:border-red-400/10 transition-all"
        >
          <LogOut className="w-4 h-4" />
          Sign Out
        </button>
      </div>
    </aside>
  );
}
