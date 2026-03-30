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
    <div className="flex items-center gap-3 text-sm text-slate-300">
      <button
        type="button"
        onClick={handlePrev}
        className="rounded-full border border-slate-700 px-3 py-1 hover:bg-slate-900"
      >
        &lt;
      </button>
      <span className="min-w-[140px] text-center font-semibold text-slate-100">
        {label}
      </span>
      <button
        type="button"
        onClick={handleNext}
        className="rounded-full border border-slate-700 px-3 py-1 hover:bg-slate-900"
      >
        &gt;
      </button>
    </div>
  );
}