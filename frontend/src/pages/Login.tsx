import React, { useState } from 'react';
import { Shield, KeyRound, Send, ArrowRight } from 'lucide-react';
import type { Role } from '../App';

export default function Login({
  onLogin,
}: {
  onLogin: (token: string, role: Role, username: string) => void;
}) {
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!code.trim()) {
      setError('Vui lòng nhập mã đăng nhập');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const res = await fetch('/api/auth/telegram', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: code.trim() }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || 'Mã không hợp lệ hoặc đã hết hạn');
      if (!data.access_token) throw new Error('Không nhận được token');
      const role: Role = data.role === 'admin' ? 'admin' : 'user';
      onLogin(data.access_token, role, code.trim());
    } catch (err: any) {
      setError(err.message || 'Đăng nhập thất bại');
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen w-full bg-[var(--bg-primary)] flex items-center justify-center p-4 relative overflow-hidden">
      {/* Animated background glow */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-1/4 -left-1/4 w-1/2 h-1/2 rounded-full bg-emerald-600/5 blur-3xl animate-pulse" />
        <div className="absolute -bottom-1/4 -right-1/4 w-1/2 h-1/2 rounded-full bg-blue-600/5 blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />
      </div>

      <div className="w-full max-w-md animate-fade-in relative z-10">
        {/* Logo + Title */}
        <div className="text-center mb-12">
          <div className="w-20 h-20 rounded-3xl bg-gradient-to-br from-emerald-500/15 via-emerald-600/5 to-transparent border border-emerald-600/20 flex items-center justify-center mx-auto mb-6 shadow-[0_0_60px_rgba(16,185,129,0.12)]">
            <Shield className="w-10 h-10 text-emerald-400" />
          </div>
          <h1 className="text-3xl font-bold tracking-tight">C2 Command Center</h1>
          <p className="text-sm text-[var(--text-muted)] mt-3">
            Xác thực qua Telegram để tiếp tục
          </p>
        </div>

        {/* Login Card */}
        <div className="bg-[var(--bg-secondary)]/80 backdrop-blur-xl border border-[var(--border)] rounded-3xl p-8 shadow-2xl">
          {/* Steps */}
          <div className="mb-8 space-y-3">
            <div className="flex items-start gap-3">
              <div className="w-6 h-6 rounded-full bg-emerald-600/10 border border-emerald-600/30 flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-[10px] font-bold text-emerald-400">1</span>
              </div>
              <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                Mở Telegram bot, gõ <code className="px-1.5 py-0.5 rounded bg-[var(--bg-primary)] border border-[var(--border)] text-emerald-400 font-mono text-[11px]">/start</code> để nhận mã
              </p>
            </div>
            <div className="flex items-start gap-3">
              <div className="w-6 h-6 rounded-full bg-emerald-600/10 border border-emerald-600/30 flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-[10px] font-bold text-emerald-400">2</span>
              </div>
              <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                Nhập mã đăng nhập vào ô bên dưới
              </p>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider block mb-2">
                Mã đăng nhập
              </label>
              <div className="relative">
                <KeyRound className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
                <input
                  type="text"
                  className="w-full bg-[var(--bg-primary)] border border-[var(--border)] rounded-2xl pl-12 pr-4 py-4 text-sm font-mono tracking-wider uppercase focus:outline-none focus:border-emerald-600/50 focus:ring-2 focus:ring-emerald-600/10 transition-all placeholder:text-[var(--text-muted)] placeholder:normal-case placeholder:tracking-normal"
                  placeholder="C2-XXXXXXXX"
                  value={code}
                  onChange={e => setCode(e.target.value)}
                  autoFocus
                  autoComplete="off"
                  spellCheck={false}
                />
              </div>
            </div>

            {error && (
              <div className="p-4 bg-red-600/5 border border-red-600/15 rounded-2xl flex items-start gap-2.5">
                <span className="w-1.5 h-1.5 rounded-full bg-red-400 flex-shrink-0 mt-1.5" />
                <p className="text-xs text-red-400 leading-relaxed">{error}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !code.trim()}
              className="w-full flex items-center justify-center gap-2 px-6 py-4 bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 disabled:opacity-40 disabled:cursor-not-allowed rounded-2xl text-sm font-semibold transition-all shadow-lg shadow-emerald-600/20 hover:shadow-emerald-500/30"
            >
              {loading ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <>
                  Đăng nhập
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          {/* Telegram link */}
          <div className="mt-6 pt-6 border-t border-[var(--border)]/50">
            <a
              href="https://t.me/"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-center gap-2 text-xs text-[var(--text-muted)] hover:text-emerald-400 transition-colors group"
            >
              <Send className="w-3.5 h-3.5 group-hover:scale-110 transition-transform" />
              Mở Telegram Bot
            </a>
          </div>
        </div>

        <p className="text-center text-[11px] text-[var(--text-muted)] mt-6">
          Mã có hiệu lực 10 phút · Một lần sử dụng
        </p>
      </div>
    </div>
  );
}
