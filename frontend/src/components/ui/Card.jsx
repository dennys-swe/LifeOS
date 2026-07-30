export default function Card({ className = "", children, ...props }) {
  return (
    <div
      className={`rounded-2xl border border-slate-200/80 bg-white/80 backdrop-blur-md shadow-sm transition-all duration-300 dark:border-slate-800/80 dark:bg-slate-900/70 dark:backdrop-blur-xl ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({ title, subtitle, action }) {
  return (
    <div className="mb-4 flex items-center justify-between gap-3">
      <div>
        <h2 className="font-display text-sm font-bold tracking-tight text-slate-900 dark:text-white">{title}</h2>
        {subtitle && <p className="text-xs text-slate-400 dark:text-slate-500">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}
