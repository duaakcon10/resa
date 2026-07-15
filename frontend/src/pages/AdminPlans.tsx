import React, { useState, useEffect } from 'react';
import { api } from '../utils/api';
import { Plus, Pencil, Trash2, X, Save } from 'lucide-react';
import { useToast } from '../components/Toast';

const ALL_METHODS = ['MEGA','TLS_EXHAUST','HTTP','SLOWLORIS','GAME'];

export default function Plans() {
  const { toast } = useToast();
  const [plans, setPlans] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<any | null>(null);
  const [showForm, setShowForm] = useState(false);

  const fetch = async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/api/admin/plans');
      setPlans(data);
    } catch { toast('Load failed', 'error'); }
    setLoading(false);
  };

  useEffect(() => { fetch(); }, []);

  const save = async () => {
    if (!editing?.name || !editing?.slug) { toast('Name and slug required', 'error'); return; }
    try {
      if (editing.id) {
        await api.patch(`/api/admin/plans/${editing.id}`, editing);
        toast('Plan updated', 'success');
      } else {
        await api.post('/api/admin/plans', editing);
        toast('Plan created', 'success');
      }
      setShowForm(false); setEditing(null); fetch();
    } catch (e: any) { toast(e.response?.data?.detail || 'Save failed', 'error'); }
  };

  const del = async (id: string) => {
    if (!confirm('Delete this plan?')) return;
    try { await api.delete(`/api/admin/plans/${id}`); toast('Deleted', 'success'); fetch(); }
    catch (e: any) { toast(e.response?.data?.detail || 'Delete failed', 'error'); }
  };

  const toggleMethod = (m: string) => {
    const cur = editing.allowed_methods || [];
    setEditing({ ...editing, allowed_methods: cur.includes(m) ? cur.filter((x: string) => x !== m) : [...cur, m] });
  };

  const input = "w-full bg-[var(--bg-primary)] border border-[var(--border)] rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-emerald-600 transition-colors";
  const label = "text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider block mb-1.5";

  return (
    <div className="p-6 md:p-8 animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold">Plan Management</h2>
          <p className="text-sm text-[var(--text-muted)] mt-1">Tạo, sửa, xoá gói cước</p>
        </div>
        <button onClick={() => { setEditing({ name: '', slug: '', max_bots: 1, max_concurrent: 1, max_attack_secs: 120, cooldown_secs: 300, max_pps_per_bot: 500000, allowed_methods: [...ALL_METHODS], price_vnd: 10000, price_usd: 0.5, is_active: true }); setShowForm(true); }} className="flex items-center gap-2 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-700 rounded-xl text-sm font-semibold transition-colors">
          <Plus className="w-4 h-4" /> New Plan
        </button>
      </div>

      {loading ? <p className="text-center text-[var(--text-muted)] py-12">Loading…</p> : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {plans.map(p => (
            <div key={p.id} className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-2xl p-5">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h3 className="font-bold text-sm">{p.name}</h3>
                  <code className="text-[10px] text-[var(--text-muted)]">{p.slug}</code>
                </div>
                <div className="flex gap-1">
                  <button onClick={() => { setEditing(p); setShowForm(true); }} className="p-1.5 hover:bg-emerald-600/10 rounded-lg text-emerald-400 transition-colors"><Pencil className="w-3.5 h-3.5" /></button>
                  <button onClick={() => del(p.id)} className="p-1.5 hover:bg-red-600/10 rounded-lg text-red-400 transition-colors"><Trash2 className="w-3.5 h-3.5" /></button>
                </div>
              </div>
              <div className="space-y-1 text-xs text-[var(--text-secondary)]">
                <div className="flex justify-between"><span>Bots</span><span className="font-mono">{p.max_bots}</span></div>
                <div className="flex justify-between"><span>Concurrent</span><span className="font-mono">{p.max_concurrent}</span></div>
                <div className="flex justify-between"><span>Max dur</span><span className="font-mono">{p.max_attack_secs}s</span></div>
                <div className="flex justify-between"><span>Cooldown</span><span className="font-mono">{p.cooldown_secs}s</span></div>
                <div className="flex justify-between"><span>PPS/bot</span><span className="font-mono">{p.max_pps_per_bot?.toLocaleString()}</span></div>
                <div className="flex justify-between"><span>Price</span><span className="font-mono text-emerald-400">{p.price_vnd?.toLocaleString()}₫</span></div>
              </div>
              <div className="flex flex-wrap gap-1 mt-3">
                {p.allowed_methods?.map(m => <span key={m} className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-[var(--bg-primary)] border border-[var(--border)] text-[var(--text-muted)]">{m}</span>)}
              </div>
              {!p.is_active && <div className="mt-2 text-[10px] text-red-400">INACTIVE</div>}
            </div>
          ))}
        </div>
      )}

      {/* Modal */}
      {showForm && editing && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4" onClick={() => setShowForm(false)}>
          <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-2xl p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold">{editing.id ? 'Edit Plan' : 'New Plan'}</h3>
              <button onClick={() => setShowForm(false)} className="p-2 hover:bg-[var(--bg-hover)] rounded-lg"><X className="w-4 h-4" /></button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div><label className={label}>Name</label><input className={input} value={editing.name} onChange={e => setEditing({ ...editing, name: e.target.value })} /></div>
              <div><label className={label}>Slug</label><input className={input} value={editing.slug} onChange={e => setEditing({ ...editing, slug: e.target.value })} /></div>
              <div><label className={label}>Max Bots</label><input type="number" className={input} value={editing.max_bots} onChange={e => setEditing({ ...editing, max_bots: +e.target.value })} /></div>
              <div><label className={label}>Max Concurrent</label><input type="number" className={input} value={editing.max_concurrent} onChange={e => setEditing({ ...editing, max_concurrent: +e.target.value })} /></div>
              <div><label className={label}>Max Attack Secs</label><input type="number" className={input} value={editing.max_attack_secs} onChange={e => setEditing({ ...editing, max_attack_secs: +e.target.value })} /></div>
              <div><label className={label}>Cooldown Secs</label><input type="number" className={input} value={editing.cooldown_secs} onChange={e => setEditing({ ...editing, cooldown_secs: +e.target.value })} /></div>
              <div><label className={label}>PPS per bot</label><input type="number" className={input} value={editing.max_pps_per_bot} onChange={e => setEditing({ ...editing, max_pps_per_bot: +e.target.value })} /></div>
              <div><label className={label}>Price VND</label><input type="number" className={input} value={editing.price_vnd} onChange={e => setEditing({ ...editing, price_vnd: +e.target.value })} /></div>
              <div><label className={label}>Price USD</label><input type="number" step="0.01" className={input} value={editing.price_usd} onChange={e => setEditing({ ...editing, price_usd: +e.target.value })} /></div>
              <div className="flex items-end pb-2"><label className="flex items-center gap-3 cursor-pointer"><input type="checkbox" className="w-4 h-4 accent-emerald-600" checked={editing.is_active} onChange={e => setEditing({ ...editing, is_active: e.target.checked })} /><span className="text-sm">Active</span></label></div>
            </div>
            <div className="mt-4">
              <label className={label}>Allowed Methods</label>
              <div className="flex flex-wrap gap-2">
                {ALL_METHODS.map(m => (
                  <button key={m} onClick={() => toggleMethod(m)} className={`px-3 py-1.5 rounded-lg text-xs font-mono border transition-colors ${(editing.allowed_methods || []).includes(m) ? 'bg-emerald-600/15 border-emerald-600/40 text-emerald-400' : 'bg-[var(--bg-primary)] border-[var(--border)] text-[var(--text-muted)]'}`}>{m}</button>
                ))}
              </div>
            </div>
            <div className="mt-3">
              <label className={label}>Description</label>
              <textarea rows={2} className={input} value={editing.description || ''} onChange={e => setEditing({ ...editing, description: e.target.value })} />
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <button onClick={() => setShowForm(false)} className="px-4 py-2.5 bg-[var(--bg-primary)] border border-[var(--border)] rounded-xl text-sm hover:bg-[var(--bg-hover)] transition-colors">Cancel</button>
              <button onClick={save} className="flex items-center gap-2 px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 rounded-xl text-sm font-semibold transition-colors"><Save className="w-4 h-4" /> Save</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
