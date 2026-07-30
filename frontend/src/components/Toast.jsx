export default function Toast({ open, message, actionLabel, onAction, onClose }) {
  if (!open) return null;

  return (
    <div className="fixed bottom-6 left-1/2 z-50 w-[min(92vw,420px)] -translate-x-1/2 rounded-2xl border border-gray-200 bg-white/95 px-4 py-3 shadow-2xl dark:border-slate-800 dark:bg-slate-900/95">
      <div className="flex items-center justify-between gap-4">
        <p className="text-sm text-gray-700 dark:text-slate-200">{message}</p>
        <div className="flex items-center gap-2">
          {actionLabel && (
            <button
              type="button"
              onClick={onAction}
              className="rounded-full border border-emerald-500/50 px-3 py-1 text-xs font-semibold text-emerald-700 hover:bg-emerald-50 dark:text-emerald-300 dark:hover:bg-emerald-500/10"
            >
              {actionLabel}
            </button>
          )}
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-gray-200 px-2 py-1 text-xs text-gray-500 hover:bg-gray-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            Fechar
          </button>
        </div>
      </div>
    </div>
  );
}