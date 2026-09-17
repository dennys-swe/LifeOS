export default function PageLoader() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-slate-950">
      <div className="flex flex-col items-center gap-3">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-emerald-500 border-t-transparent" />
        <p className="font-display text-xs font-semibold uppercase tracking-widest text-slate-400 dark:text-slate-500">
          LifeOS · Carregando...
        </p>
      </div>
    </div>
  );
}
