import React from 'react';
import {
  LayoutDashboard, Bot, Crosshair, ShoppingCart, Users, ScrollText, LogOut, Shield, Activity
} from 'lucide-react';

type Page = 'dashboard' | 'bots' | 'bot-detail' | 'attack' | 'plans' | 'users' | 'logs';

const navItems: { page: Page; label: string; icon: React.ElementType }[] = [
  { page: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { page: 'bots', label: 'Bots', icon: Bot },
  { page: 'attack', label: 'Attack', icon: Crosshair },
  { page: 'plans', label: 'Plans', icon: ShoppingCart },
  { page: 'users', label: 'Users', icon: Users },
  { page: 'logs', label: 'Logs', icon: ScrollText },
];

export default function Sidebar({
  activePage, onNavigate, onLogout,
}: {
  activePage: Page;
  onNavigate: (p: Page) => void;
  onLogout: () => void;
}) {
  return (
    <aside className="w-60 bg-[var(--bg-secondary)] border-r border-[var(--border)] flex flex-col select-none z-10">
      {/* Header */}
      <div className="p-5 border-b border-[var(--border)]">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-emerald-600/10 border border-emerald-600/20 flex items-center justify-center">
            <Shield className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <h1 className="text-base font-bold tracking-tight leading-none">C2 Center</h1>
            <p className="text-[10px] text-[var(--text-muted)] mt-0.5">v4.0.0 — Ultimate</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
        <div className="px-3 py-2">
          <p className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.15em]">Menu</p>
        </div>
        {navItems.map(({ page, label, icon: Icon }) => {
          const active = activePage === page || (activePage === 'bot-detail' && page === 'bots');
          return (
            <button
              key={page}
              onClick={() => onNavigate(page)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-150 group
                ${active
                  ? 'bg-emerald-600/10 text-emerald-400 font-medium border border-emerald-600/15'
                  : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] border border-transparent'
                }`}
            >
              <Icon className={`w-4 h-4 transition-colors ${active ? 'text-emerald-400' : 'text-[var(--text-muted)] group-hover:text-[var(--text-secondary)]'}`} />
              {label}
              {active && <div className="ml-auto w-1.5 h-1.5 rounded-full bg-emerald-400" />}
            </button>
          );
        })}
      </nav>

      {/* Status */}
      <div className="px-3 pb-1">
        <div className="px-3 py-2.5 rounded-lg bg-[var(--bg-card)] border border-[var(--border)]">
          <div className="flex items-center gap-2">
            <div className="relative">
              <div className="w-2 h-2 rounded-full bg-emerald-400" />
              <div className="w-2 h-2 rounded-full bg-emerald-400 absolute inset-0 animate-pulse-glow" />
            </div>
            <span className="text-[11px] text-[var(--text-muted)]">System Online</span>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-[var(--border)]">
        <div className="flex items-center justify-between mb-3 px-1">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-full bg-emerald-600/10 border border-emerald-600/20 flex items-center justify-center">
              <Activity className="w-3.5 h-3.5 text-emerald-400" />
            </div>
            <div>
              <p className="text-[11px] font-medium text-[var(--text-primary)]">Admin</p>
              <p className="text-[9px] text-[var(--text-muted)]">Super Admin</p>
            </div>
          </div>
        </div>
        <button
          onClick={onLogout}
          className="w-full flex items-center justify-center gap-2 px-3 py-2.5 text-sm text-[var(--text-muted)] hover:text-red-400 rounded-lg hover:bg-red-400/5 border border-transparent hover:border-red-400/10 transition-all"
        >
          <LogOut className="w-4 h-4" />
          Sign Out
        </button>
      </div>
    </aside>
  );
}