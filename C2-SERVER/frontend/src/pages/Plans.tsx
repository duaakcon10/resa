import React, { useEffect, useState } from 'react';
import { api } from '../utils/api';
import { Check, Building2, Zap, Shield } from 'lucide-react';

interface Plan { id: string; name: string; slug: string; max_bots: number; max_concurrent: number; max_attack_secs: number; cooldown_secs: number; max_pps_per_bot: number; allowed_methods: string[]; price_monthly: number; price_vnd: number; }

export default function Plans() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [buying, setBuying] = useState<string | null>(null);
  const [result, setResult] = useState<{ amount: number; description: string; bank_account: string } | null>(null);

  useEffect(() => { api.get('/api/plans/').then(r => setPlans(r.data)).catch(() => {}); }, []);

  const buy = async (slug: string) => {
    setBuying(slug); setResult(null);
    try {
      const { data } = await api.post('/api/payment/mbank/create', { plan: slug });
      setResult(data);
    } catch (e: any) {
      alert('Error: ' + (e.response?.data?.detail || e.message));
    }
    setBuying(null);
  };

  return (
    <div className="p-8 animate-fade-in">
      <div className="mb-8"><h2 className="text-2xl font-bold">Plans & Pricing</h2><p className="text-sm text-[var(--text-muted)] mt-1">Choose your firepower</p></div>

      <div className="grid grid-cols-3 gap-6">
        {plans.map(p => (
          <div key={p.id} className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-2xl p-6 flex flex-col hover:border-[var(--border-light)] transition-all">
            <div className="mb-4"><h3 className="text-lg font-bold">{p.name}</h3><p className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.1em] mt-0.5">{p.slug}</p></div>
            <div className="mb-6">
              <div className="text-3xl font-bold text-emerald-400">{p.price_vnd.toLocaleString()}đ<span className="text-sm font-normal text-[var(--text-muted)]">/th</span></div>
              <div className="text-sm text-[var(--text-muted)] mt-1">${p.price_monthly}/mo</div>
            </div>
            <div className="space-y-2.5 mb-8 flex-1">
              {[`${p.max_bots} bots tối đa`, `${p.max_concurrent} concurrent`, `${p.max_attack_secs}s thời gian`, `${p.cooldown_secs}s cooldown`, `${p.max_pps_per_bot.toLocaleString()} PPS/bot`].map((f, i) => (
                <div key={i} className="flex items-center gap-2 text-xs text-[var(--text-secondary)]"><Check className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />{f}</div>
              ))}
              <div className="pt-2 border-t border-[var(--border)]">
                <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.08em] mb-1.5">Methods</div>
                <div className="flex flex-wrap gap-1">{p.allowed_methods.map(m => <span key={m} className="px-2 py-0.5 bg-[var(--bg-primary)] border border-[var(--border)] rounded text-[10px] text-[var(--text-muted)]">{m}</span>)}</div>
              </div>
            </div>
            <button onClick={() => buy(p.slug)} disabled={buying === p.slug} className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 rounded-xl text-xs font-semibold transition-colors">
              <Building2 className="w-3.5 h-3.5" />{buying === p.slug ? 'Đang xử lý...' : 'Mua qua MB Bank'}
            </button>
          </div>
        ))}
      </div>

      {result && (
        <div className="mt-8 bg-[var(--bg-secondary)] border border-emerald-600/20 rounded-2xl p-6 animate-fade-in">
          <h3 className="text-sm font-semibold flex items-center gap-2 mb-4"><Shield className="w-4 h-4 text-emerald-400" />Hướng dẫn thanh toán</h3>
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-[var(--bg-primary)] border border-[var(--border)] rounded-xl p-4">
              <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.08em] mb-1">Ngân hàng</div>
              <div className="text-sm font-bold">MB Bank (Quân Đội)</div>
            </div>
            <div className="bg-[var(--bg-primary)] border border-[var(--border)] rounded-xl p-4">
              <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.08em] mb-1">Số tài khoản</div>
              <div className="text-sm font-mono font-bold text-emerald-400">{result.bank_account}</div>
            </div>
            <div className="bg-[var(--bg-primary)] border border-[var(--border)] rounded-xl p-4">
              <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.08em] mb-1">Số tiền</div>
              <div className="text-sm font-bold">{result.amount.toLocaleString()}đ</div>
            </div>
            <div className="bg-[var(--bg-primary)] border border-[var(--border)] rounded-xl p-4">
              <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.08em] mb-1">Nội dung chuyển khoản</div>
              <div className="text-sm font-mono font-bold text-yellow-400">{result.description}</div>
            </div>
          </div>
          <p className="text-xs text-[var(--text-muted)] mt-4 flex items-center gap-1.5"><Zap className="w-3 h-3 text-emerald-400" />Hệ thống sẽ tự động quét giao dịch mỗi 30 giây và kích hoạt plan của bạn.</p>
        </div>
      )}
    </div>
  );
}