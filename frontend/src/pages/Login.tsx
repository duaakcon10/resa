import React, { useState, useEffect, useRef } from 'react';
import { Shield, ArrowRight, Send, Lock, Mail, Terminal, Loader2, CheckCircle2, ExternalLink } from 'lucide-react';
import type { Role } from '../App';

export default function Login({ onLogin }: { onLogin: (token: string, role: Role, username: string) => void }) {
  const [mode, setMode] = useState<'select' | 'user' | 'admin-step1' | 'admin-step2'>('select');
  const [tgUsername, setTgUsername] = useState('');
  const [deepLink, setDeepLink] = useState('');
  const [loginToken, setLoginToken] = useState('');
  const [polling, setPolling] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [verifyCode, setVerifyCode] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const pollRef = useRef<number | null>(null);

  // Step 1: Init login → get deep link
  const initLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!tgUsername.trim()) { setError('Nhập Telegram username'); return; }
    setLoading(true); setError('');
    try {
      const res = await fetch('/api/auth/telegram/init', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ telegram_username: tgUsername.trim().lstrip?.('@') || tgUsername.trim().replace(/^@/, '') }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || 'Init failed');
      setDeepLink(data.deep_link);
      setLoginToken(data.token);
      setPolling(true);
      // Start polling
      pollRef.current = window.setInterval(checkLogin, 2000);
    } catch (err: any) { setError(err.message); }
    setLoading(false);
  };

  // Step 3: Poll check endpoint
  const checkLogin = async () => {
    if (!loginToken) return;
    try {
      const res = await fetch('/api/auth/telegram/check', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: loginToken }),
      });
      if (res.status === 202) return; // still pending
      const data = await res.json().catch(() => ({}));
      if (res.ok && data.access_token) {
        setPolling(false);
        if (pollRef.current) clearInterval(pollRef.current);
        onLogin(data.access_token, 'user', tgUsername);
      } else if (res.status !== 202) {
        setError(data.detail || 'Login failed');
        setPolling(false);
        if (pollRef.current) clearInterval(pollRef.current);
      }
    } catch { /* retry */ }
  };

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  const adminStep1 = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) { setError('Nhập đầy đủ email và mật khẩu'); return; }
    setLoading(true); setError('');
    try {
      const res = await fetch('/api/auth/admin/login', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || 'Sai email hoặc mật khẩu');
      setMode('admin-step2');
    } catch (err: any) { setError(err.message); }
    setLoading(false);
  };

  const adminStep2 = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!verifyCode.trim()) { setError('Nhập mã xác thực'); return; }
    setLoading(true); setError('');
    try {
      const res = await fetch('/api/auth/admin/verify', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, code: verifyCode.trim() }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || 'Mã xác thực sai hoặc hết hạn');
      onLogin(data.access_token, 'admin', email);
    } catch (err: any) { setError(err.message); }
    setLoading(false);
  };

  const input = "w-full bg-[var(--bg-primary)] border border-[var(--border)] rounded-xl pl-12 pr-4 py-3.5 text-sm focus:outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-glow)] transition-all placeholder:text-[var(--text-muted)]";
  const label = "text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider block mb-2";
  const btn = "w-full flex items-center justify-center gap-2 px-6 py-3.5 cyber-button rounded-xl text-sm transition-all";

  return (
    <div className="min-h-screen w-full bg-[var(--bg-primary)] flex items-center justify-center p-4 relative overflow-hidden">
      <div className="scanline-overlay" />
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-1/4 -left-1/4 w-1/2 h-1/2 rounded-full bg-[var(--accent-glow)] blur-3xl animate-pulse" />
        <div className="absolute -bottom-1/4 -right-1/4 w-1/2 h-1/2 rounded-full bg-[var(--cyan-glow)] blur-3xl animate-pulse" style={{ animationDelay: '1.5s' }} />
      </div>

      <div className="w-full max-w-md animate-fade-in relative z-10">
        <div className="text-center mb-10">
          <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-[var(--accent-glow)] to-transparent border border-[var(--accent)]/30 flex items-center justify-center mx-auto mb-6 cyber-glow">
            <Shield className="w-10 h-10 text-[var(--accent)]" />
          </div>
          <h1 className="text-3xl font-bold tracking-tight cyber-text-glow">C2 Command Center</h1>
          <p className="text-sm text-[var(--text-muted)] mt-3">
            {mode === 'select' && 'Chọn phương thức đăng nhập'}
            {mode === 'user' && !deepLink && 'Nhập Telegram username'}
            {mode === 'user' && deepLink && 'Xác thực qua Telegram'}
            {mode === 'admin-step1' && 'Admin Login — Bước 1/2'}
            {mode === 'admin-step2' && 'Admin Login — Bước 2/2'}
          </p>
        </div>

        <div className="cyber-card p-8 cyber-border-glow">
          {/* Mode: Select */}
          {mode === 'select' && (
            <div className="space-y-3">
              <button onClick={() => setMode('user')} className="w-full flex items-center gap-3 p-4 bg-[var(--bg-primary)] border border-[var(--border)] rounded-xl hover:border-[var(--accent)]/40 transition-all group">
                <div className="w-10 h-10 rounded-xl bg-[var(--accent-glow)] flex items-center justify-center">
                  <Send className="w-5 h-5 text-[var(--accent)]" />
                </div>
                <div className="text-left">
                  <div className="text-sm font-semibold">User Login</div>
                  <div className="text-[11px] text-[var(--text-muted)]">Telegram deep link verify</div>
                </div>
                <ArrowRight className="w-4 h-4 text-[var(--text-muted)] ml-auto group-hover:text-[var(--accent)] transition-colors" />
              </button>
              <button onClick={() => setMode('admin-step1')} className="w-full flex items-center gap-3 p-4 bg-[var(--bg-primary)] border border-[var(--border)] rounded-xl hover:border-[var(--cyan)]/40 transition-all group">
                <div className="w-10 h-10 rounded-xl bg-[var(--cyan-glow)] flex items-center justify-center">
                  <Lock className="w-5 h-5 text-[var(--cyan)]" />
                </div>
                <div className="text-left">
                  <div className="text-sm font-semibold">Admin Login</div>
                  <div className="text-[11px] text-[var(--text-muted)]">Email + mật khẩu + mã 2FA</div>
                </div>
                <ArrowRight className="w-4 h-4 text-[var(--text-muted)] ml-auto group-hover:text-[var(--cyan)] transition-colors" />
              </button>
            </div>
          )}

          {/* Mode: User (Telegram deep link) */}
          {mode === 'user' && !deepLink && (
            <form onSubmit={initLogin} className="space-y-4">
              <div>
                <label className={label}>Telegram Username</label>
                <div className="relative">
                  <Send className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
                  <input type="text" className={input} placeholder="@username" value={tgUsername} onChange={e => setTgUsername(e.target.value)} autoFocus />
                </div>
              </div>
              {error && <div className="p-3 bg-[var(--danger)]/5 border border-[var(--danger)]/15 rounded-xl flex items-center gap-2"><span className="w-1.5 h-1.5 rounded-full bg-[var(--danger)] flex-shrink-0" /><p className="text-xs text-[var(--danger)]">{error}</p></div>}
              <button type="submit" disabled={loading || !tgUsername.trim()} className={btn}>
                {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <><span>Tạo link đăng nhập</span><ArrowRight className="w-4 h-4" /></>}
              </button>
              <button type="button" onClick={() => { setMode('select'); setError(''); }} className="w-full text-xs text-[var(--text-muted)] hover:text-[var(--accent)] transition-colors">← Quay lại</button>
            </form>
          )}

          {/* Mode: User — deep link generated, waiting for verify */}
          {mode === 'user' && deepLink && (
            <div className="space-y-5">
              <div className="text-center">
                {polling ? (
                  <>
                    <div className="w-14 h-14 mx-auto rounded-full bg-[var(--accent-glow)] border border-[var(--accent)]/30 flex items-center justify-center mb-4">
                      <Loader2 className="w-7 h-7 text-[var(--accent)] animate-spin" />
                    </div>
                    <p className="text-sm font-semibold text-[var(--accent)] mb-1">Đang chờ xác thực...</p>
                    <p className="text-[11px] text-[var(--text-muted)]">Click link Telegram để đăng nhập</p>
                  </>
                ) : (
                  <CheckCircle2 className="w-12 h-12 text-[var(--accent)] mx-auto" />
                )}
              </div>
              <a href={deepLink} target="_blank" rel="noopener noreferrer" className="flex items-center justify-center gap-2 px-6 py-4 cyber-button rounded-xl text-sm font-bold transition-all">
                <Send className="w-5 h-5" />
                Mở Telegram Bot
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
              <p className="text-[10px] text-[var(--text-muted)] text-center">Link hết hạn sau 10 phút. Đăng nhập tự động khi bạn xác thực trên Telegram.</p>
              {error && <div className="p-3 bg-[var(--danger)]/5 border border-[var(--danger)]/15 rounded-xl flex items-center gap-2"><span className="w-1.5 h-1.5 rounded-full bg-[var(--danger)] flex-shrink-0" /><p className="text-xs text-[var(--danger)]">{error}</p></div>}
              <button type="button" onClick={() => { setDeepLink(''); setLoginToken(''); setPolling(false); if (pollRef.current) clearInterval(pollRef.current); setMode('select'); setError(''); }} className="w-full text-xs text-[var(--text-muted)] hover:text-[var(--accent)] transition-colors">← Quay lại</button>
            </div>
          )}

          {/* Admin Step 1 */}
          {mode === 'admin-step1' && (
            <form onSubmit={adminStep1} className="space-y-4">
              <div>
                <label className={label}>Email</label>
                <div className="relative">
                  <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
                  <input type="email" className={input} placeholder="admin@c2.local" value={email} onChange={e => setEmail(e.target.value)} autoFocus />
                </div>
              </div>
              <div>
                <label className={label}>Mật khẩu</label>
                <div className="relative">
                  <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
                  <input type="password" className={input} placeholder="••••••••" value={password} onChange={e => setPassword(e.target.value)} />
                </div>
              </div>
              {error && <div className="p-3 bg-[var(--danger)]/5 border border-[var(--danger)]/15 rounded-xl flex items-center gap-2"><span className="w-1.5 h-1.5 rounded-full bg-[var(--danger)] flex-shrink-0" /><p className="text-xs text-[var(--danger)]">{error}</p></div>}
              <button type="submit" disabled={loading} className={btn} style={{ background: 'linear-gradient(135deg, #0066aa, #00d4ff)', color: '#050510' }}>
                {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <><span>Gửi mã xác thực</span><ArrowRight className="w-4 h-4" /></>}
              </button>
              <button type="button" onClick={() => { setMode('select'); setError(''); }} className="w-full text-xs text-[var(--text-muted)] hover:text-[var(--cyan)] transition-colors">← Quay lại</button>
            </form>
          )}

          {/* Admin Step 2 */}
          {mode === 'admin-step2' && (
            <form onSubmit={adminStep2} className="space-y-4">
              <div className="text-center mb-2">
                <Terminal className="w-8 h-8 text-[var(--cyan)] mx-auto mb-2" />
                <p className="text-xs text-[var(--text-secondary)]">Mã xác thực 6 số đã được gửi qua Telegram</p>
                <p className="text-[10px] text-[var(--text-muted)] mt-1">Hết hạn sau 5 phút</p>
              </div>
              <div>
                <label className={label}>Mã xác thực</label>
                <div className="relative">
                  <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
                  <input type="text" className={`${input} font-mono text-center text-2xl tracking-[0.5em]`} placeholder="000000" maxLength={6} value={verifyCode} onChange={e => setVerifyCode(e.target.value.replace(/\D/g, ''))} autoFocus />
                </div>
              </div>
              {error && <div className="p-3 bg-[var(--danger)]/5 border border-[var(--danger)]/15 rounded-xl flex items-center gap-2"><span className="w-1.5 h-1.5 rounded-full bg-[var(--danger)] flex-shrink-0" /><p className="text-xs text-[var(--danger)]">{error}</p></div>}
              <button type="submit" disabled={loading || verifyCode.length < 6} className={btn} style={{ background: 'linear-gradient(135deg, #0066aa, #00d4ff)', color: '#050510' }}>
                {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <><span>Xác thực</span><ArrowRight className="w-4 h-4" /></>}
              </button>
              <button type="button" onClick={() => { setMode('admin-step1'); setError(''); setVerifyCode(''); }} className="w-full text-xs text-[var(--text-muted)] hover:text-[var(--cyan)] transition-colors">← Quay lại</button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
