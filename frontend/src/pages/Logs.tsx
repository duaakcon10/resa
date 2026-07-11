import React, { useEffect, useState } from 'react';
import { api } from '../utils/api';
import { ScrollText, Search } from 'lucide-react';
import { useToast } from '../components/Toast';

interface Log {
  id: number; action: string; target_type: string | null;
  target_id: string | null; details: any; created_at: string;
}

export default function Logs() {
  const { toast } = useToast();
  const [logs, setLogs] = useState<Log[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/api/admin/logs?limit=200')
      .then(r => setLogs(Array.isArray(r.data) ? r.data : r.data?.items || []))
      .catch(() => toast('Failed to load logs', 'error'))
      .finally(() => setLoading(false));
  }, [toast]);

  const filtered = logs.filter(l => (l.action || '').toLowerCase().includes(search.toLowerCase()));
  const ac = (a: string) =>
    a.includes('ban') ? 'text-red-400' :
    a.includes('toggle') ? 'text-yellow-400' :
    a.includes('assign') ? 'text-blue-400' :
    a.includes('throttle') ? 'text-purple-400' : 'text-[var(--text-secondary)]';

  return (
    <div className="p-6 md:p-8 animate-fade-in">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <ScrollText className="w-5 h-5 text-[var(--text-muted)]" />Admin Logs
        </h2>
        <div className="text-xs text-[var(--text-muted)]">{logs.length} entries</div>
      </div>
      <div className="relative mb-6 max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--text-muted)]" />
        <input
          placeholder="Filter by action..."
          className="w-full bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl pl-10 pr-4 py-2.5 text-xs focus:outline-none focus:border-emerald-600 transition-colors"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>
      <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[700px]">
            <thead>
              <tr className="border-b border-[var(--border)] text-left text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.08em]">
                <th className="p-4 w-16">#</th>
                <th className="p-4">Action</th>
                <th className="p-4">Target</th>
                <th className="p-4">Details</th>
                <th className="p-4">Time</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={5} className="p-12 text-center text-[var(--text-muted)]">Loading…</td></tr>
              ) : filtered.length === 0 ? (
                <tr><td colSpan={5} className="p-12 text-center text-[var(--text-muted)]">No logs</td></tr>
              ) : filtered.map(l => (
                <tr key={l.id} className="border-b border-[var(--border)]/50 text-xs hover:bg-[var(--bg-hover)]/40">
                  <td className="p-4 text-[var(--text-muted)]">{l.id}</td>
                  <td className={`p-4 font-mono text-[11px] ${ac(l.action || '')}`}>{l.action}</td>
                  <td className="p-4 text-[var(--text-muted)]">
                    {l.target_type ? `${l.target_type}:${l.target_id?.slice(0, 8)}` : '—'}
                  </td>
                  <td className="p-4 text-[var(--text-muted)] max-w-xs truncate" title={l.details ? JSON.stringify(l.details) : ''}>
                    {l.details ? JSON.stringify(l.details) : '—'}
                  </td>
                  <td className="p-4 text-[var(--text-muted)] whitespace-nowrap">
                    {l.created_at ? new Date(l.created_at).toLocaleString() : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
