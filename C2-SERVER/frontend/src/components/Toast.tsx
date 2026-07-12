import React, { createContext, useCallback, useContext, useState } from 'react';
import { CheckCircle2, XCircle, Info, X } from 'lucide-react';

type ToastKind = 'success' | 'error' | 'info';
type Toast = { id: number; kind: ToastKind; message: string };

const ToastCtx = createContext<{
  toast: (message: string, kind?: ToastKind) => void;
} | null>(null);

let _id = 0;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);

  const toast = useCallback((message: string, kind: ToastKind = 'info') => {
    const id = ++_id;
    setItems(prev => [...prev, { id, kind, message }]);
    setTimeout(() => setItems(prev => prev.filter(t => t.id !== id)), 4000);
  }, []);

  const dismiss = (id: number) => setItems(prev => prev.filter(t => t.id !== id));

  const icon = (k: ToastKind) => {
    if (k === 'success') return <CheckCircle2 className="w-4 h-4 text-emerald-400" />;
    if (k === 'error') return <XCircle className="w-4 h-4 text-red-400" />;
    return <Info className="w-4 h-4 text-blue-400" />;
  };

  const border = (k: ToastKind) => {
    if (k === 'success') return 'border-emerald-600/25 bg-emerald-600/10';
    if (k === 'error') return 'border-red-600/25 bg-red-600/10';
    return 'border-blue-600/25 bg-blue-600/10';
  };

  return (
    <ToastCtx.Provider value={{ toast }}>
      {children}
      <div className="fixed top-4 right-4 z-[100] flex flex-col gap-2 max-w-sm w-full pointer-events-none">
        {items.map(t => (
          <div
            key={t.id}
            className={`pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-xl border shadow-xl backdrop-blur-md animate-slide-in ${border(t.kind)}`}
          >
            {icon(t.kind)}
            <p className="text-xs text-[var(--text-primary)] flex-1 leading-relaxed">{t.message}</p>
            <button onClick={() => dismiss(t.id)} className="text-[var(--text-muted)] hover:text-[var(--text-primary)]">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastCtx);
  if (!ctx) return { toast: (_m: string, _k?: ToastKind) => {} };
  return ctx;
}
