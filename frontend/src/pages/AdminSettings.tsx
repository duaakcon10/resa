import React, { useState, useEffect } from 'react';
import { api } from '../utils/api';
import { Settings, Save, Building2, Globe, DollarSign } from 'lucide-react';
import { useToast } from '../components/Toast';

export default function AdminSettings() {
  const { toast } = useToast();
  const [form, setForm] = useState({
    site_name: '', site_url: '', telegram_bot_username: '',
    bank_account_name: '', bank_account_number: '', bank_name: 'MBBank', bank_bin: '970422',
    min_deposit: 10000, maintenance_mode: false,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get('/api/admin/settings').then(({ data }) => setForm(data)).catch(() => toast('Load failed', 'error')).finally(() => setLoading(false));
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      await api.patch('/api/admin/settings', form);
      toast('Settings saved', 'success');
    } catch { toast('Save failed', 'error'); }
    setSaving(false);
  };

  if (loading) return <div className="p-8 text-center text-[var(--text-muted)]">Loading…</div>;

  const input = "w-full bg-[var(--bg-primary)] border border-[var(--border)] rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-emerald-600 transition-colors";
  const label = "text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider block mb-2";

  return (
    <div className="p-6 md:p-8 animate-fade-in max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold">Admin Settings</h2>
          <p className="text-sm text-[var(--text-muted)] mt-1">Cấu hình hệ thống, ngân hàng, giá</p>
        </div>
        <button onClick={save} disabled={saving} className="flex items-center gap-2 px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 rounded-xl text-sm font-semibold transition-colors">
          <Save className="w-4 h-4" /> {saving ? 'Saving…' : 'Save'}
        </button>
      </div>

      <div className="space-y-6">
        {/* Site config */}
        <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-2xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <Globe className="w-4 h-4 text-emerald-400" />
            <h3 className="text-sm font-semibold">Site Configuration</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className={label}>Site Name</label>
              <input className={input} value={form.site_name} onChange={e => setForm(f => ({ ...f, site_name: e.target.value }))} />
            </div>
            <div>
              <label className={label}>Site URL</label>
              <input className={input} value={form.site_url} onChange={e => setForm(f => ({ ...f, site_url: e.target.value }))} placeholder="https://..." />
            </div>
            <div>
              <label className={label}>Telegram Bot Username</label>
              <input className={input} value={form.telegram_bot_username} onChange={e => setForm(f => ({ ...f, telegram_bot_username: e.target.value }))} placeholder="your_bot" />
            </div>
            <div className="flex items-end">
              <label className="flex items-center gap-3 cursor-pointer pb-3">
                <input type="checkbox" className="w-4 h-4 accent-emerald-600" checked={form.maintenance_mode} onChange={e => setForm(f => ({ ...f, maintenance_mode: e.target.checked }))} />
                <span className="text-sm">Maintenance Mode</span>
              </label>
            </div>
          </div>
        </div>

        {/* Bank config */}
        <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-2xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <Building2 className="w-4 h-4 text-emerald-400" />
            <h3 className="text-sm font-semibold">Bank Configuration</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className={label}>Account Name</label>
              <input className={input} value={form.bank_account_name} onChange={e => setForm(f => ({ ...f, bank_account_name: e.target.value }))} />
            </div>
            <div>
              <label className={label}>Account Number</label>
              <input className={input} value={form.bank_account_number} onChange={e => setForm(f => ({ ...f, bank_account_number: e.target.value }))} />
            </div>
            <div>
              <label className={label}>Bank Name</label>
              <input className={input} value={form.bank_name} onChange={e => setForm(f => ({ ...f, bank_name: e.target.value }))} />
            </div>
            <div>
              <label className={label}>Bank BIN</label>
              <input className={input} value={form.bank_bin} onChange={e => setForm(f => ({ ...f, bank_bin: e.target.value }))} placeholder="970422" />
            </div>
          </div>
        </div>

        {/* Pricing */}
        <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-2xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <DollarSign className="w-4 h-4 text-emerald-400" />
            <h3 className="text-sm font-semibold">Pricing</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className={label}>Min Deposit (VND)</label>
              <input type="number" className={input} value={form.min_deposit} onChange={e => setForm(f => ({ ...f, min_deposit: +e.target.value }))} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
