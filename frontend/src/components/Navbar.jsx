const PAGES = {
  dashboard: "dashboard",
  payables: "payables",
  upload: "upload",
};

export default function Navbar({ activePage, onNavigate }) {
  return (
    <nav className="sticky top-0 z-20 border-b border-slate-800 bg-slate-950/90 backdrop-blur">
      <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-4">
        <div>
          <p className="text-xs uppercase tracking-[0.4em] text-slate-500">
            Controle Financeiro
          </p>
          <p className="text-sm font-semibold text-white">Painel</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => onNavigate(PAGES.dashboard)}
            className={`rounded-full px-4 py-2 text-sm font-medium transition ${
              activePage === PAGES.dashboard
                ? "bg-emerald-500/20 text-emerald-300"
                : "text-slate-300 hover:bg-slate-900"
            }`}
          >
            Inicio
          </button>
          <button
            type="button"
            onClick={() => onNavigate(PAGES.payables)}
            className={`rounded-full px-4 py-2 text-sm font-medium transition ${
              activePage === PAGES.payables
                ? "bg-emerald-500/20 text-emerald-300"
                : "text-slate-300 hover:bg-slate-900"
            }`}
          >
            Contas
          </button>
          <button
            type="button"
            onClick={() => onNavigate(PAGES.upload)}
            className={`rounded-full px-4 py-2 text-sm font-medium transition ${
              activePage === PAGES.upload
                ? "bg-emerald-500/20 text-emerald-300"
                : "text-slate-300 hover:bg-slate-900"
            }`}
          >
            Importar
          </button>
        </div>
      </div>
    </nav>
  );
}
