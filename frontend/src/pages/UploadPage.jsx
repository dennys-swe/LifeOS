import { useEffect, useMemo, useRef, useState } from "react";
import api from "../services/api";
import { useFinance } from "../context/FinanceContext";

const STATUS = { idle: "idle", uploading: "uploading", success: "success", error: "error" };
const PAGES = { dashboard: "dashboard" };

export default function UploadPage({ onNavigate }) {
  const { refresh } = useFinance() ?? {};
  const [status, setStatus] = useState(STATUS.idle);
  const [message, setMessage] = useState("");
  const [fileName, setFileName] = useState("");
  const [selectedFile, setSelectedFile] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const [confirming, setConfirming] = useState(new Set());
  const inputRef = useRef(null);

  const isUploading = status === STATUS.uploading;

  const handleFile = async (file) => {
    if (!file) return;
    const isCsv = file.name.toLowerCase().endsWith(".csv");
    if (!isCsv) {
      setStatus(STATUS.error);
      setMessage("Formato invalido. Envie um arquivo .csv.");
      setFileName(file.name);
      setSelectedFile(false);
      return;
    }

    setFileName(file.name);
    setSelectedFile(true);
    setStatus(STATUS.uploading);
    setMessage("Enviando...");
    setSuggestions([]);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await api.post("/transactions/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      const data = response.data;
      const importedCount = data.transactions?.length ?? 0;
      const suggestionsData = data.suggestions ?? [];
      setStatus(STATUS.success);
      setMessage(`Sucesso! ${importedCount} transacoes importadas`);
      setSuggestions(suggestionsData);
      if (suggestionsData.length === 0) refresh?.();
    } catch {
      setStatus(STATUS.error);
      setMessage("Nao foi possivel processar o arquivo.");
    }
  };

  const handleChange = (e) => handleFile(e.target.files?.[0]);
  const handleDrop = (e) => { e.preventDefault(); if (!isUploading) handleFile(e.dataTransfer.files?.[0]); };
  const handleDragOver = (e) => e.preventDefault();

  const handleConfirmSuggestion = async (suggestion) => {
    setConfirming((prev) => new Set([...prev, suggestion.payable_id]));
    try {
      await api.patch(`/payables/${suggestion.payable_id}/reconcile?transaction_id=${suggestion.transaction_id}`);
      setSuggestions((prev) => prev.filter((s) => s.payable_id !== suggestion.payable_id));
    } catch {
      setMessage("Erro ao conciliar. Tente novamente.");
    } finally {
      setConfirming((prev) => { const n = new Set(prev); n.delete(suggestion.payable_id); return n; });
    }
  };

  const handleIgnoreSuggestion = (payableId) => {
    setSuggestions((prev) => prev.filter((s) => s.payable_id !== payableId));
  };

  const handleConfirmAll = async () => {
    for (const s of suggestions) {
      await handleConfirmSuggestion(s);
    }
    refresh?.();
  };

  useEffect(() => {
    if (suggestions.length === 0 && status === STATUS.success) refresh?.();
  }, [suggestions, status, refresh]);

  useEffect(() => {
    if (status !== STATUS.success || suggestions.length > 0) return;
    const timeout = setTimeout(() => { onNavigate?.(PAGES.dashboard); }, 3000);
    return () => clearTimeout(timeout);
  }, [status, suggestions, onNavigate]);

  const statusColor = useMemo(() => {
    if (status === STATUS.success) return "text-emerald-400";
    if (status === STATUS.error) return "text-rose-400";
    return "text-slate-300";
  }, [status]);

  const confidenceColor = (score) => {
    if (score >= 0.9) return "bg-emerald-500";
    if (score >= 0.7) return "bg-amber-400";
    return "bg-rose-500";
  };

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-8 px-6 py-10">
      <header className="flex flex-col gap-3">
        <p className="text-xs uppercase tracking-[0.4em] text-slate-500">Importação de Extratos</p>
        <h1 className="text-3xl font-semibold text-white md:text-4xl">Enviar arquivo CSV</h1>
        <p className="text-slate-400">
          Arraste o arquivo ou toque para selecionar. O arquivo sera processado e importado automaticamente.
        </p>
      </header>

      <section
        className={`flex flex-col items-center justify-center gap-4 rounded-3xl border-2 border-dashed px-6 py-12 text-center shadow-lg transition ${
          selectedFile ? "border-emerald-400 bg-emerald-500/10" : "border-emerald-500/50 bg-slate-900/70"
        }`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
      >
        <div className="flex h-20 w-20 items-center justify-center rounded-full border border-emerald-500/40 bg-emerald-500/10 text-2xl font-semibold text-emerald-300">
          UP
        </div>
        <div>
          <p className="text-lg font-semibold text-white">Clique ou arraste</p>
          <p className="text-sm text-slate-400">CSV exportado do seu banco</p>
        </div>
        <button type="button" onClick={() => inputRef.current?.click()} disabled={isUploading}
          className="rounded-full bg-emerald-500 px-6 py-3 text-sm font-semibold text-slate-950 transition hover:bg-emerald-400 disabled:opacity-60">
          Selecionar arquivo
        </button>
        <input ref={inputRef} type="file" accept=".csv" className="hidden" onChange={handleChange} disabled={isUploading} />
        {fileName && <p className="text-xs text-slate-400">Arquivo: {fileName}</p>}
      </section>

      <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
        <p className={`text-sm font-medium ${statusColor}`}>{message}</p>
        {status === STATUS.success && suggestions.length === 0 && onNavigate && (
          <button type="button" onClick={() => onNavigate(PAGES.dashboard)}
            className="mt-3 rounded-full border border-emerald-500/60 px-4 py-2 text-sm font-semibold text-emerald-300 hover:bg-emerald-500/10">
            Ir para o Dashboard
          </button>
        )}
      </section>

      {suggestions.length > 0 && (
        <section className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">
              Sugestões de Conciliação ({suggestions.length})
            </h2>
            <button type="button" onClick={handleConfirmAll}
              className="rounded-full bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-emerald-400">
              Confirmar Todas
            </button>
          </div>
          <p className="text-sm text-slate-400">
            Encontramos possíveis correspondências entre as transações importadas e suas contas a pagar. Confirme para marcar como pago automaticamente.
          </p>

          {suggestions.map((s) => (
            <div key={s.payable_id} className="flex flex-col gap-3 rounded-xl border border-slate-800 bg-slate-950/60 p-4 md:flex-row md:items-center md:justify-between">
              <div className="flex flex-col gap-1">
                <div className="flex items-center gap-2 text-xs text-slate-500 uppercase tracking-wider">
                  <span>Transação</span>
                </div>
                <p className="text-sm text-white">{s.transaction_description}</p>
                <p className="text-xs text-slate-400">R$ {Number(s.transaction_amount).toFixed(2)}</p>
              </div>

              <div className="flex flex-col items-center gap-1">
                <div className="flex items-center gap-1">
                  <div className={`h-2 rounded-full ${confidenceColor(s.confidence_score)}`} style={{ width: `${Math.round(s.confidence_score * 48)}px` }} />
                </div>
                <span className="text-xs text-slate-500">{Math.round(s.confidence_score * 100)}% match</span>
              </div>

              <div className="flex flex-col gap-1">
                <div className="flex items-center gap-2 text-xs text-slate-500 uppercase tracking-wider">
                  <span>Conta a Pagar</span>
                </div>
                <p className="text-sm text-white">{s.payable_title}</p>
                <p className="text-xs text-slate-400">R$ {Number(s.payable_amount).toFixed(2)}</p>
              </div>

              <div className="flex gap-2">
                <button type="button" disabled={confirming.has(s.payable_id)} onClick={() => handleConfirmSuggestion(s)}
                  className="rounded-full border border-emerald-500/40 px-3 py-1 text-xs text-emerald-300 transition hover:bg-emerald-500/10 disabled:opacity-50">
                  {confirming.has(s.payable_id) ? "..." : "Confirmar"}
                </button>
                <button type="button" onClick={() => handleIgnoreSuggestion(s.payable_id)}
                  className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300 hover:bg-slate-900">
                  Ignorar
                </button>
              </div>
            </div>
          ))}
        </section>
      )}
    </div>
  );
}
