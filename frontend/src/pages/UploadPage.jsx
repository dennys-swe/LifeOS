import { useEffect, useMemo, useRef, useState } from "react";

import api from "../services/api";

const STATUS = {
  idle: "idle",
  uploading: "uploading",
  success: "success",
  error: "error",
};

const PAGES = {
  dashboard: "dashboard",
};

export default function UploadPage({ onNavigate }) {
  const [status, setStatus] = useState(STATUS.idle);
  const [message, setMessage] = useState("");
  const [fileName, setFileName] = useState("");
  const [selectedFile, setSelectedFile] = useState(false);
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

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await api.post("/transactions/upload", formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      });
      setStatus(STATUS.success);
      const importedCount = Array.isArray(response?.data)
        ? response.data.length
        : 0;
      setMessage(`Sucesso! ${importedCount} transacoes importadas`);
    } catch (error) {
      setStatus(STATUS.error);
      setMessage("Nao foi possivel processar o arquivo.");
    }
  };

  const handleChange = (event) => {
    const file = event.target.files?.[0];
    handleFile(file);
  };

  const handleDrop = (event) => {
    event.preventDefault();
    if (isUploading) return;
    const file = event.dataTransfer.files?.[0];
    handleFile(file);
  };

  const handleDragOver = (event) => {
    event.preventDefault();
  };

  const statusColor = useMemo(() => {
    if (status === STATUS.success) return "text-emerald-400";
    if (status === STATUS.error) return "text-rose-400";
    return "text-slate-300";
  }, [status]);

  useEffect(() => {
    if (status !== STATUS.success) return undefined;

    const timeout = setTimeout(() => {
      if (onNavigate) {
        onNavigate(PAGES.dashboard);
      }
    }, 3000);

    return () => clearTimeout(timeout);
  }, [status, onNavigate]);

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-8 px-6 py-10">
      <header className="flex flex-col gap-3">
        <p className="text-xs uppercase tracking-[0.4em] text-slate-500">
          Importacao de Extratos
        </p>
        <h1 className="text-3xl font-semibold text-white md:text-4xl">
          Enviar arquivo CSV
        </h1>
        <p className="text-slate-400">
          Arraste o arquivo ou toque para selecionar. O arquivo sera processado e
          importado automaticamente.
        </p>
      </header>

      <section
        className={`flex flex-col items-center justify-center gap-4 rounded-3xl border-2 border-dashed px-6 py-12 text-center shadow-lg transition ${
          selectedFile
            ? "border-emerald-400 bg-emerald-500/10 shadow-emerald-500/20"
            : "border-emerald-500/50 bg-slate-900/70"
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
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={isUploading}
          className="rounded-full bg-emerald-500 px-6 py-3 text-sm font-semibold text-slate-950 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-60"
        >
          Selecionar arquivo
        </button>
        <input
          ref={inputRef}
          type="file"
          accept=".csv"
          className="hidden"
          onChange={handleChange}
          disabled={isUploading}
        />
        {fileName && (
          <p className="text-xs text-slate-400">Arquivo: {fileName}</p>
        )}
      </section>

      <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
        <p className={`text-sm font-medium ${statusColor}`}>{message}</p>
        {status === STATUS.success && onNavigate && (
          <button
            type="button"
            onClick={() => onNavigate(PAGES.dashboard)}
            className="mt-3 rounded-full border border-emerald-500/60 px-4 py-2 text-sm font-semibold text-emerald-300 transition hover:bg-emerald-500/10"
          >
            Ir para o Dashboard
          </button>
        )}
      </section>
    </div>
  );
}
