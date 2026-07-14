import React, { useState, useEffect } from 'react';
import { Shield, Zap, Globe, Server, ArrowRight, Check } from 'lucide-react';

export default function Landing({ onLogin }: { onLogin: () => void }) {
  const [settings, setSettings] = useState({ site_name: 'C2 Command Center', telegram_bot_username: 'atk_vip_bot' });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/admin/public/settings').then(r => r.json()).then(setSettings).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const features = [
    { icon: Zap, title: '7 Attack Methods', desc: 'MEGA TCP, TLS, HTTP Proxy, Game Socket, Slowloris, UDP' },
    { icon: Globe, title: 'Multi-IP via Proxy', desc: 'Auto-fetch free proxies, bypass CF/WAF rate-limiting' },
    { icon: Server, title: 'Bot Fleet Management', desc: 'Bulk operations, live monitoring, resource guards' },
    { icon: Shield, title: 'Telegram Auth', desc: 'Secure login via /start code, no passwords to leak' },
  ];

  const plans = [
    { name: 'Starter', price: '10K', bots: 1, dur: 120, methods: ['MEGA','TLS','SLOWLORIS'] },
    { name: 'Pro', price: '50K', bots: 5, dur: 300, methods: ['MEGA','TLS','HTTP','PROXY','GAME'] },
    { name: 'Enterprise', price: '200K', bots: 20, dur: 600, methods: ['ALL 7 Methods'] },
  ];

  return (
    <div className="min-h-screen bg-[var(--bg-primary)] text-[var(--text-primary)] relative overflow-hidden">
      {/* Animated bg */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-1/4 -left-1/4 w-1/2 h-1/2 rounded-full bg-emerald-600/5 blur-3xl animate-pulse" />
        <div className="absolute top-1/3 right-0 w-1/3 h-1/3 rounded-full bg-blue-600/5 blur-3xl animate-pulse" style={{ animationDelay: '1.5s' }} />
      </div>

      <div className="relative z-10">
        {/* Nav */}
        <nav className="flex items-center justify-between px-6 md:px-12 py-5">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500/20 to-transparent border border-emerald-600/20 flex items-center justify-center">
              <Shield className="w-5 h-5 text-emerald-400" />
            </div>
            <span className="font-bold text-sm">{settings.site_name}</span>
          </div>
          <button onClick={onLogin} className="flex items-center gap-2 px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 rounded-xl text-sm font-semibold transition-colors">
            Login <ArrowRight className="w-4 h-4" />
          </button>
        </nav>

        {/* Hero */}
        <section className="text-center px-6 py-20 md:py-32 max-w-4xl mx-auto">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-600/10 border border-emerald-600/20 text-[11px] text-emerald-400 font-medium mb-6">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" /> System Online
          </div>
          <h1 className="text-4xl md:text-6xl font-bold tracking-tight mb-6 bg-gradient-to-b from-white to-white/60 bg-clip-text text-transparent">
            Command & Control<br/>Center
          </h1>
          <p className="text-base md:text-lg text-[var(--text-muted)] max-w-2xl mx-auto mb-8 leading-relaxed">
            Botnet management platform with multi-method attack capabilities,
            proxy rotation, Telegram authentication, and real-time bot fleet monitoring.
          </p>
          <div className="flex items-center justify-center gap-3">
            <button onClick={onLogin} className="flex items-center gap-2 px-6 py-3.5 bg-emerald-600 hover:bg-emerald-700 rounded-2xl text-sm font-semibold transition-colors shadow-lg shadow-emerald-600/20">
              Get Started <ArrowRight className="w-4 h-4" />
            </button>
            {settings.telegram_bot_username && (
              <a href={`https://t.me/${settings.telegram_bot_username}`} target="_blank" rel="noopener noreferrer" className="px-6 py-3.5 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-2xl text-sm font-semibold hover:bg-[var(--bg-hover)] transition-colors">
                Telegram Bot
              </a>
            )}
          </div>
        </section>

        {/* Features */}
        <section className="px-6 md:px-12 py-16 max-w-6xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
            {features.map((f, i) => (
              <div key={i} className="bg-[var(--bg-secondary)]/60 backdrop-blur border border-[var(--border)] rounded-2xl p-6 hover:border-emerald-600/30 transition-colors">
                <div className="w-10 h-10 rounded-xl bg-emerald-600/10 flex items-center justify-center mb-4">
                  <f.icon className="w-5 h-5 text-emerald-400" />
                </div>
                <h3 className="font-semibold text-sm mb-2">{f.title}</h3>
                <p className="text-xs text-[var(--text-muted)] leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Pricing */}
        <section className="px-6 md:px-12 py-16 max-w-5xl mx-auto">
          <h2 className="text-2xl font-bold text-center mb-12">Pricing Plans</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {plans.map((p, i) => (
              <div key={i} className={`bg-[var(--bg-secondary)] border rounded-2xl p-6 ${i === 1 ? 'border-emerald-600/40 shadow-lg shadow-emerald-600/10' : 'border-[var(--border)]'}`}>
                {i === 1 && <div className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider mb-3">Popular</div>}
                <h3 className="font-bold text-lg mb-1">{p.name}</h3>
                <div className="flex items-baseline gap-1 mb-4">
                  <span className="text-3xl font-bold">{p.price}</span>
                  <span className="text-xs text-[var(--text-muted)]">₫</span>
                </div>
                <div className="space-y-2 mb-4">
                  <div className="flex items-center gap-2 text-xs text-[var(--text-secondary)]"><Check className="w-3.5 h-3.5 text-emerald-400" /> {p.bots} bots</div>
                  <div className="flex items-center gap-2 text-xs text-[var(--text-secondary)]"><Check className="w-3.5 h-3.5 text-emerald-400" /> {p.dur}s max duration</div>
                  <div className="flex items-center gap-2 text-xs text-[var(--text-secondary)]"><Check className="w-3.5 h-3.5 text-emerald-400" /> {p.methods.join(', ')}</div>
                </div>
                <button onClick={onLogin} className={`w-full py-2.5 rounded-xl text-sm font-semibold transition-colors ${i === 1 ? 'bg-emerald-600 hover:bg-emerald-700' : 'bg-[var(--bg-primary)] border border-[var(--border)] hover:bg-[var(--bg-hover)]'}`}>
                  Choose
                </button>
              </div>
            ))}
          </div>
        </section>

        {/* Footer */}
        <footer className="px-6 py-8 text-center text-[11px] text-[var(--text-muted)]">
          © 2024 {settings.site_name} · Telegram-secured · All rights reserved
        </footer>
      </div>
    </div>
  );
}
