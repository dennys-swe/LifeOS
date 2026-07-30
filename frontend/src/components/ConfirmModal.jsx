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
      ? "bg-emerald-500 text-slate-950 hover:bg-emerald-400"
      : "bg-rose-500 text-white hover:bg-rose-400";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-gray-950/50 px-6 dark:bg-slate-950/80">
      <div className="w-full max-w-md rounded-2xl border border-gray-200 bg-white p-6 shadow-2xl dark:border-slate-800 dark:bg-slate-900">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">{title}</h2>
        {description && (
          <p className="mt-2 text-sm text-gray-500 dark:text-slate-400">{description}</p>
        )}
        <div className="mt-6 flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-full border border-gray-200 px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className={`rounded-full px-4 py-2 text-sm font-semibold transition ${confirmClass}`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}