export default function ConfirmModal({
  open,
  title,
  description,
  confirmLabel = "Confirmar",
  cancelLabel = "Cancelar",
  variant = "danger",
  onCancel,
  onConfirm,
}) {
  if (!open) return null;

  const confirmClass =
    variant === "success"
      ? "bg-emerald-600 text-white hover:bg-emerald-500 shadow-md shadow-emerald-500/20"
      : "bg-rose-600 text-white hover:bg-rose-500 shadow-md shadow-rose-500/20";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 backdrop-blur-sm px-6">
      <div className="w-full max-w-md rounded-2xl border border-slate-200/80 bg-white/95 p-6 shadow-2xl backdrop-blur-xl dark:border-slate-800/80 dark:bg-slate-900/95 animate-in fade-in zoom-in duration-200">
        <h2 className="font-display text-lg font-bold text-slate-900 dark:text-white">{title}</h2>
        {description && (
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">{description}</p>
        )}
        <div className="mt-6 flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-xl border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 transition dark:border-slate-800 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className={`rounded-xl px-4 py-2 text-xs font-semibold transition ${confirmClass}`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}