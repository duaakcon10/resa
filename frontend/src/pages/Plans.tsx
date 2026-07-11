import React, { useEffect, useState } from 'react';
import { api } from '../utils/api';
import { Check, Building2, Zap, Shield, Copy, CheckCheck } from 'lucide-react';
import { useToast } from '../components/Toast';

interface Plan {
  id: string; name: string; slug: string; max_bots: number;
  max_concurrent: number; max_attack_secs: number; cooldown_secs: number;
  max_pps_per_bot: number; allowed_methods: string[];
  price_monthly: number; price_vnd: number;
}

export default function Plans() {
  const { toast } = useToast();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [buying, setBuying] = useState<string | null>(null);
  const [result, setResult] = useState<{ amount: number; description: string; bank_account: string; bank_name?: string } | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  useEffect(() => {
    api.get('/api/plans/').then(r => setPlans(Array.isArray(r.data) ? r.data : [])).catch(() => toast('Failed to load plans', 'error'));
  }, [toast]);

  const buy = async (slug: string) => {
    setBuying(slug);
    setResult(null);
    try {
      const { data } = await api.post('/api/payment/mbank/create', { plan: slug });
      setResult(data);
      toast('Payment order created', 'success');
    } catch (e: any) {
      toast(e.response?.data?.detail || e.message || 'Payment failed', 'error');
    }
    setBuying(null);
  };

  const copy = async (text: string, key: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(key);
      toast('Copied', 'success');
      setTimeout(() => setCopied(null), 2000);
    } catch {
      toast('Copy failed', 'error');
    }
  };

  return (
    <div className="p-6 md:p-8 animate-fade-in">
      <div className="mb-8">
        <h2 className="text-2xl font-bold">Plans & Pricing</h2>
        <p className="text-sm text-[var(--text-muted)] mt-1">Choose your firepower · auto-activate via MB Bank</p>
      </div>

      {plans.length === 0 ? (
        <div className="text-center py-16 text-[var(--text-muted)] text-sm">No plans available</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {plans.map((p, idx) => (
            <div
              key={p.id}
              className={`bg-[var(--bg-secondary)] border rounded-2xl p-6 flex flex-col transition-all hover:border-[var(--border-light)] ${
                idx === 1 ? 'border-emerald-600/30 shadow-[0_0_40px_rgba(16,185,129,0.06)]' : 'border-[var(--border)]'
              }`}
            >
              {idx === 1 && (
                <div className="text-[10px] font-semibold text-emerald-400 uppercase tracking-wider mb-2">Popular</div>
              )}
              <div className="mb-4">
                <h3 className="text-lg font-bold">{p.name}</h3>
                <p className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.1em] mt-0.5">{p.slug}</p>
              </div>
              <div className="mb-6">
                <div className="text-3xl font-bold text-emerald-400 tabular-nums">
                  {(p.price_vnd || 0).toLocaleString()}đ
                  <span className="text-sm font-normal text-[var(--text-muted)]">/th</span>
                </div>
                <div className="text-sm text-[var(--text-muted)] mt-1">${p.price_monthly ?? 0}/mo</div>
              </div>
              <div className="space-y-2.5 mb-8 flex-1">
                {[
                  `${p.max_bots} bots max`,
                  `${p.max_concurrent} concurrent`,
                  `${p.max_attack_secs}s duration`,
                  `${p.cooldown_secs}s cooldown`,
                  `${(p.max_pps_per_bot || 0).toLocaleString()} PPS/bot`,
                ].map((f, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
                    <Check className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />{f}
                  </div>
                ))}
                <div className="pt-2 border-t border-[var(--border)]">
                  <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.08em] mb-1.5">Methods</div>
                  <div className="flex flex-wrap gap-1">
                    {(p.allowed_methods || []).map(m => (
                      <span key={m} className="px-2 py-0.5 bg-[var(--bg-primary)] border border-[var(--border)] rounded text-[10px] text-[var(--text-muted)]">{m}</span>
                    ))}
                  </div>
                </div>
              </div>
              <button
                onClick={() => buy(p.slug)}
                disabled={buying === p.slug}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 rounded-xl text-xs font-semibold transition-colors"
              >
                <Building2 className="w-3.5 h-3.5" />
                {buying === p.slug ? 'Processing…' : 'Buy via MB Bank'}
              </button>
            </div>
          ))}
        </div>
      )}

      {result && (
        <div className="mt-8 bg-[var(--bg-secondary)] border border-emerald-600/20 rounded-2xl p-6 animate-fade-in">
          <h3 className="text-sm font-semibold flex items-center gap-2 mb-4">
            <Shield className="w-4 h-4 text-emerald-400" />Payment instructions
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {[
              { label: 'Bank', value: result.bank_name || 'MB Bank', key: 'bank' },
              { label: 'Account', value: String(result.bank_account || ''), key: 'acc' },
              { label: 'Amount', value: `${(result.amount || 0).toLocaleString()}đ`, key: 'amt' },
              { label: 'Transfer content', value: result.description || '', key: 'desc', accent: 'text-yellow-400' },
            ].map(({ label, value, key, accent }) => (
              <div key={key} className="bg-[var(--bg-primary)] border border-[var(--border)] rounded-xl p-4">
                <div className="flex items-center justify-between mb-1">
                  <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.08em]">{label}</div>
                  {value && (
                    <button onClick={() => copy(value, key)} className="p-1 rounded hover:bg-[var(--bg-hover)] text-[var(--text-muted)]">
                      {copied === key ? <CheckCheck className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                    </button>
                  )}
                </div>
                <div className={`text-sm font-mono font-bold ${accent || ''}`}>{value || '—'}</div>
              </div>
            ))}
          </div>
          <p className="text-xs text-[var(--text-muted)] mt-4 flex items-center gap-1.5">
            <Zap className="w-3 h-3 text-emerald-400" />
            System scans transactions every 30s and activates your plan automatically.
          </p>
        </div>
      )}
    </div>
  );
}
