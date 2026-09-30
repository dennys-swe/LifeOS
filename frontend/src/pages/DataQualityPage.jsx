import { useCallback, useEffect, useMemo, useState } from "react";

import IssueCard from "../components/dataQuality/IssueCard";
import Card, { CardHeader } from "../components/ui/Card";
import EmptyState from "../components/ui/EmptyState";
import Skeleton from "../components/ui/Skeleton";
import { useFinance } from "../context/FinanceContext";
import { groupBySeverity, SEVERITY_LABEL } from "../lib/dataQuality";
import api from "../services/api";

function lastCheckLabel(iso) {
  if (!iso) return "Ainda não verificado";
  return `Última verificação: ${new Date(iso).toLocaleString("pt-BR")}`;
}

export default function DataQualityPage() {
  const { categories, refresh } = useFinance();
  const [issues, setIssues] = useState(null);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");
  const [checking, setChecking] = useState(false);
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    try {
      const [list, sum] = await Promise.all([
        api.get("/data-quality/issues"),
        api.get("/data-quality/summary"),
      ]);
      setIssues(list.data);
      setSummary(sum.data);
      setError("");
    } catch {
      setError("Não foi possível carregar os avisos agora.");
      setIssues((current) => current ?? []);
    }
  }, []);

  useEffect(() => {
    // Busca inicial; `load` só atualiza estado depois do await.
    load();
  }, [load]);

  const expenseCategories = useMemo(
    () => (categories ?? []).filter((c) => !c.kind || c.kind === "EXPENSE"),
    [categories]
  );

  const handleCheck = async () => {
    setChecking(true);
    setNotice("");
    try {
      await api.post("/data-quality/run");
      await load();
    } catch {
      setError("Não foi possível verificar agora.");
    } finally {
      setChecking(false);
    }
  };

  const handleDone = (issue, message) => {
    setIssues((list) => (list ?? []).filter((i) => i.id !== issue.id));
    setNotice(message);
    // A correção muda totais do dashboard; `refresh` é a convenção do projeto após mutação.
    refresh();
    api
      .get("/data-quality/summary")
      .then((res) => setSummary(res.data))
      .catch(() => {});
  };

  const groups = groupBySeverity(issues ?? []);

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-xl font-extrabold text-slate-900 dark:text-white">
            Saúde dos dados
          </h1>
          <p className="text-xs text-slate-400 dark:text-slate-500">
            {lastCheckLabel(summary?.last_detected_at)}. Nada é alterado sem você ver o que muda.
          </p>
        </div>
        <button
          type="button"
          disabled={checking}
          onClick={handleCheck}
          className="rounded-xl bg-emerald-600 px-4 py-2 text-xs font-bold text-white shadow-sm transition hover:bg-emerald-500 disabled:opacity-50"
        >
          {checking ? "Verificando..." : "Verificar agora"}
        </button>
      </header>

      {notice && <p className="text-xs font-bold text-emerald-600 dark:text-emerald-400">{notice}</p>}
      {error && <p className="text-xs font-bold text-rose-600 dark:text-rose-400">{error}</p>}

      {issues === null ? (
        <Card className="p-6">
          <Skeleton className="h-24" />
        </Card>
      ) : groups.length === 0 ? (
        <Card className="p-6">
          <CardHeader title="Tudo certo por aqui" subtitle="nenhum aviso aberto" />
          <EmptyState className="h-auto py-6">
            Nenhum problema encontrado nos seus dados. Use &quot;Verificar agora&quot; depois de um
            sync para conferir de novo.
          </EmptyState>
        </Card>
      ) : (
        groups.map((group) => (
          <section key={group.severity} className="flex flex-col gap-3" data-testid={`group-${group.severity}`}>
            <h2 className="font-display text-sm font-bold text-slate-700 dark:text-slate-200">
              {SEVERITY_LABEL[group.severity]}{" "}
              <span className="font-semibold text-slate-400">({group.issues.length})</span>
            </h2>
            {group.issues.map((issue) => (
              <IssueCard
                key={issue.id}
                issue={issue}
                expenseCategories={expenseCategories}
                onDone={handleDone}
              />
            ))}
          </section>
        ))
      )}
    </div>
  );
}
