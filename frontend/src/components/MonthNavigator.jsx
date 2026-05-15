const MONTH_FORMATTER = new Intl.DateTimeFormat("pt-BR", {
  month: "long",
  year: "numeric",
});

export default function MonthNavigator({ month, year, onChange }) {
  const date = new Date(year, month - 1, 1);
  const label = MONTH_FORMATTER.format(date);

  const handlePrev = () => {
    const prev = new Date(year, month - 2, 1);
    onChange(prev.getMonth() + 1, prev.getFullYear());
  };

  const handleNext = () => {
    const next = new Date(year, month, 1);
    onChange(next.getMonth() + 1, next.getFullYear());
  };

  return (
    <div className="flex items-center gap-2 text-sm">
      <button
        type="button"
        onClick={handlePrev}
        className="flex h-8 w-8 items-center justify-center rounded-lg border border-gray-200 text-gray-500 transition hover:bg-gray-100 dark:border-slate-700 dark:text-slate-400 dark:hover:bg-slate-900"
      >
        &lt;
      </button>
      <span className="min-w-[140px] text-center font-semibold text-gray-800 capitalize dark:text-slate-200">
        {label}
      </span>
      <button
        type="button"
        onClick={handleNext}
        className="flex h-8 w-8 items-center justify-center rounded-lg border border-gray-200 text-gray-500 transition hover:bg-gray-100 dark:border-slate-700 dark:text-slate-400 dark:hover:bg-slate-900"
      >
        &gt;
      </button>
    </div>
  );
}
