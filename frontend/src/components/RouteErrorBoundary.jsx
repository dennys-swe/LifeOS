import { Component } from "react";

// Falha de import() dinâmico (issue #11): depois de um deploy, uma aba aberta
// na versão anterior tenta baixar um chunk cujo arquivo/hash não existe mais
// e cai aqui em vez de branquear a tela. Recarregar resolve — pega o
// index.html novo com as referências de chunk atuais.
export default class RouteErrorBoundary extends Component {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error) {
    console.error("Falha ao carregar parte da aplicação:", error);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-slate-950">
          <div className="flex flex-col items-center gap-4 text-center">
            <p className="font-display text-sm font-semibold text-slate-600 dark:text-slate-300">
              Uma nova versão do LifeOS está disponível.
            </p>
            <button
              onClick={() => window.location.reload()}
              className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-600"
            >
              Recarregar
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
