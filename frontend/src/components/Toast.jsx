export default function Toast({ open, message, actionLabel, onAction, onClose }) {
  if (!open) return null;

  return (
    <div className="fixed bottom-20 md:bottom-8 left-1/2 z-50 w-[min(92vw,420px)] -translate-x-1/2 rounded-2xl border border-slate-200/80 bg-white/95 px-5 py-3.5 shadow-2xl backdrop-blur-xl dark:border-slate-800/80 dark:bg-slate-900/95 animate-in fade-in slide-in-from-bottom-4 duration-300">
      <div className="flex items-center justify-between gap-4">
        <p className="text-xs font-semibold text-slate-800 dark:text-slate-200">{message}</p>
        <div className="flex items-center gap-2">
          {actionLabel && (
            <button
              type="button"
              onClick={onAction}
              className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-bold text-emerald-600 transition hover:bg-emerald-500/20 dark:text-emerald-400"
            >
              {actionLabel}
            </button>
          )}
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-500 hover:bg-slate-100 dark:border-slate-800 dark:text-slate-400 dark:hover:bg-slate-800"
          >
            Fechar
          </button>
        </div>
      </div>
    </div>
  );
}