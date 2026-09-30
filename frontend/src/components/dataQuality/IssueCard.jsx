import { useState } from "react";

import Card from "../ui/Card";
import { describeChange, issueCopy, previewEffects, SEVERITY_LABEL, SEVERITY_TONE } from "../../lib/dataQuality";
import { fmt } from "../../lib/format";
import api from "../../services/api";

function errorMessage(err) {
  return err?.response?.data?.detail || "Não foi possível concluir. Tente de novo.";
}

function dateLabel(iso) {
  const [y, m, d] = String(iso).split("-");
  return `${d}/${m}/${y}`;
}

// `onDone(issue, message)` é chamado depois de aplicar ou dispensar com sucesso.
export default function IssueCard({ issue, expenseCategories, onDone }) {
  const copy = issueCopy(issue.kind);
  const [categoryId, setCategoryId] = useState("");
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const canPreview = issue.fix_available && (!issue.needs_category || categoryId);

  const handlePreview = async () => {
    setBusy(true);
    setError("");
    try {
      const params = categoryId ? { category_id: categoryId } : undefined;
      const { data } = await api.get(`/data-quality/issues/${issue.id}/preview`, { params });
      setPreview(data);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const handleApply = async () => {
    setBusy(true);
    setError("");
    try {
      await api.post(`/data-quality/issues/${issue.id}/apply`, {
        category_id: categoryId || null,
      });
      onDone(issue, "Correção aplicada.");
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  };

  const handleDismiss = async () => {
    setBusy(true);
    setError("");
    try {
      await api.post(`/data-quality/issues/${issue.id}/dismiss`);
      onDone(issue, "Marcado como correto.");
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  };

  return (
    <Card className="p-5" data-testid="issue-card">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-bold ${SEVERITY_TONE[issue.severity]}`}
        >
          {SEVERITY_LABEL[issue.severity]}
        </span>
        <h3 className="font-display text-sm font-bold text-slate-900 dark:text-white">{copy.title}</h3>
      </div>
      {copy.text && <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{copy.text}</p>}

      <ul className="mt-3 flex flex-col gap-1.5">
        {issue.transactions.map((t) => (
          <li
            key={t.id}
            className="flex items-baseline justify-between gap-3 rounded-xl bg-slate-50 px-3 py-2 text-xs dark:bg-slate-900/60"
          >
            <span className="min-w-0 truncate text-slate-700 dark:text-slate-200">
              <span className="mr-2 text-slate-400">{dateLabel(t.date)}</span>
              {t.description}
              {t.is_transfer && (
                <span className="ml-2 rounded-full border border-slate-300 px-1.5 text-[10px] text-slate-500 dark:border-slate-700">
                  transferência
                </span>
              )}
            </span>
            <span
              className={`flex-shrink-0 font-bold ${
                t.type === "INCOME" ? "text-emerald-600 dark:text-emerald-400" : "text-slate-900 dark:text-white"
              }`}
            >
              {t.type === "INCOME" ? "+" : "−"}
              {fmt(Number(t.amount))}
            </span>
          </li>
        ))}
      </ul>

      {issue.needs_category && (
        <select
          aria-label="Escolher categoria"
          value={categoryId}
          onChange={(e) => {
            setCategoryId(e.target.value);
            setPreview(null);
          }}
          className="mt-3 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
        >
          <option value="">Escolha uma categoria…</option>
          {expenseCategories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      )}

      {preview && (
        <div
          className="mt-3 rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-3"
          data-testid="issue-preview"
        >
          {preview.already_fixed ? (
            <p className="text-xs font-semibold text-slate-600 dark:text-slate-300">
              Isto já foi corrigido. Ao confirmar, o aviso é fechado e nada muda.
            </p>
          ) : (
            <>
              <p className="text-xs font-bold text-slate-800 dark:text-slate-100">O que vai mudar</p>
              <ul className="mt-1 list-disc pl-4 text-xs text-slate-600 dark:text-slate-300">
                {preview.changes.map((c) => (
                  <li key={`${c.transaction_id}-${c.field}`}>{describeChange(c)}</li>
                ))}
              </ul>
              {previewEffects(preview, fmt).map((line) => (
                <p key={line} className="mt-1 text-xs font-semibold text-emerald-700 dark:text-emerald-400">
                  {line}
                </p>
              ))}
            </>
          )}
        </div>
      )}

      {error && <p className="mt-2 text-xs font-semibold text-rose-600 dark:text-rose-400">{error}</p>}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {preview ? (
          <>
            <button
              type="button"
              disabled={busy}
              onClick={handleApply}
              className="rounded-xl bg-emerald-600 px-3.5 py-1.5 text-xs font-bold text-white transition hover:bg-emerald-500 disabled:opacity-50"
            >
              {busy ? "Aplicando..." : "Aplicar correção"}
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => setPreview(null)}
              className="rounded-xl border border-slate-200 px-3.5 py-1.5 text-xs font-bold text-slate-600 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              Cancelar
            </button>
          </>
        ) : (
          issue.fix_available && (
            <button
              type="button"
              disabled={busy || !canPreview}
              onClick={handlePreview}
              className="rounded-xl bg-emerald-600 px-3.5 py-1.5 text-xs font-bold text-white transition hover:bg-emerald-500 disabled:opacity-50"
            >
              Ver o que muda
            </button>
          )
        )}
        <button
          type="button"
          disabled={busy}
          onClick={handleDismiss}
          className="rounded-xl border border-slate-200 px-3.5 py-1.5 text-xs font-bold text-slate-600 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          Está certo
        </button>
      </div>
    </Card>
  );
}
