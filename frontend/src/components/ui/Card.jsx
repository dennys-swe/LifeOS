// Classe de card repetida literalmente em toda página do projeto — só
// consolidando o que já era o padrão de fato.
export default function Card({ className = "", children, ...props }) {
  return (
    <div
      className={`rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900 ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({ title, subtitle, action }) {
  return (
    <div className="mb-4 flex items-center justify-between gap-2">
      <h2 className="text-sm font-semibold text-gray-900 dark:text-slate-100">{title}</h2>
      {subtitle && <p className="text-xs text-gray-400 dark:text-slate-500">{subtitle}</p>}
      {action}
    </div>
  );
}
