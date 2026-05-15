import { useState } from "react";

import api from "../services/api";
import { useFinance } from "../context/FinanceContext";

const FORM_TYPES = {
  transaction: "transaction",
  payable: "payable",
};

const INITIAL_TRANSACTION = {
  date: "",
  description: "",
  amount: "",
  type: "EXPENSE",
  source: "",
  category_id: "",
};

const INITIAL_PAYABLE = {
  title: "",
  amount: "",
  due_date: "",
  status: "PENDING",
  payment_date: "",
  category_id: "",
};

const INPUT_CLASS =
  "mt-2 w-full rounded-xl border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-slate-700 dark:bg-slate-950 dark:text-white";

const LABEL_CLASS = "text-sm text-gray-700 dark:text-slate-300";

export default function FabModal({ onCreated } = {}) {
  const { refresh, categories = [] } = useFinance() ?? {};
  const [open, setOpen] = useState(false);
  const [formType, setFormType] = useState(FORM_TYPES.payable);
  const [transactionData, setTransactionData] = useState(INITIAL_TRANSACTION);
  const [payableData, setPayableData] = useState(INITIAL_PAYABLE);
  const [status, setStatus] = useState("idle");
  const [message, setMessage] = useState("");

  const resetState = () => {
    setTransactionData(INITIAL_TRANSACTION);
    setPayableData(INITIAL_PAYABLE);
    setStatus("idle");
    setMessage("");
  };

  const handleClose = () => {
    setOpen(false);
    resetState();
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setStatus("loading");
    setMessage("Salvando...");

    try {
      if (formType === FORM_TYPES.transaction) {
        await api.post("/transactions", {
          ...transactionData,
          amount: Number(transactionData.amount),
          source: transactionData.source || null,
          category_id: transactionData.category_id || null,
        });
      } else {
        await api.post("/payables", {
          ...payableData,
          amount: Number(payableData.amount),
          payment_date: payableData.payment_date || null,
          category_id: payableData.category_id || null,
        });
      }

      setStatus("success");
      setMessage("Registro adicionado com sucesso!");
      refresh?.();
      if (onCreated) onCreated();
    } catch {
      setStatus("error");
      setMessage("Nao foi possivel salvar. Tente novamente.");
    }
  };

  const isLoading = status === "loading";

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed bottom-20 right-4 z-30 flex h-14 w-14 items-center justify-center rounded-full bg-emerald-500 text-2xl font-semibold text-slate-950 shadow-xl transition hover:bg-emerald-400 md:bottom-6 md:right-6"
      >
        +
      </button>

      {open && (
        <div className="fixed inset-0 z-40 flex items-center justify-center overflow-y-auto bg-slate-950/80 px-4 py-6">
          <div className="my-auto w-full max-w-xl rounded-2xl border border-gray-200 bg-white shadow-2xl dark:border-slate-800 dark:bg-slate-900">
            <div className="p-6">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-[0.3em] text-gray-400 dark:text-slate-500">
                    Novo registro
                  </p>
                  <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                    Adicionar manualmente
                  </h2>
                </div>
                <button
                  type="button"
                  onClick={handleClose}
                  className="rounded-full border border-gray-200 px-3 py-1 text-xs text-gray-600 hover:bg-gray-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                >
                  Fechar
                </button>
              </div>

              <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
                <label className={LABEL_CLASS}>
                  Tipo de cadastro
                  <select
                    value={formType}
                    onChange={(event) => setFormType(event.target.value)}
                    className={INPUT_CLASS}
                  >
                    <option value={FORM_TYPES.payable}>Conta a pagar</option>
                    <option value={FORM_TYPES.transaction}>Transacao</option>
                  </select>
                </label>

                {formType === FORM_TYPES.transaction ? (
                  <>
                    <label className={LABEL_CLASS}>
                      Data
                      <input
                        type="date"
                        value={transactionData.date}
                        onChange={(e) => setTransactionData((p) => ({ ...p, date: e.target.value }))}
                        required
                        className={INPUT_CLASS}
                      />
                    </label>
                    <label className={LABEL_CLASS}>
                      Descricao
                      <input
                        type="text"
                        value={transactionData.description}
                        onChange={(e) => setTransactionData((p) => ({ ...p, description: e.target.value }))}
                        required
                        className={INPUT_CLASS}
                      />
                    </label>
                    <label className={LABEL_CLASS}>
                      Valor
                      <input
                        type="number"
                        step="0.01"
                        value={transactionData.amount}
                        onChange={(e) => setTransactionData((p) => ({ ...p, amount: e.target.value }))}
                        required
                        className={INPUT_CLASS}
                      />
                    </label>
                    <label className={LABEL_CLASS}>
                      Tipo
                      <select
                        value={transactionData.type}
                        onChange={(e) => setTransactionData((p) => ({ ...p, type: e.target.value }))}
                        className={INPUT_CLASS}
                      >
                        <option value="INCOME">Entrada</option>
                        <option value="EXPENSE">Saida</option>
                      </select>
                    </label>
                    <label className={LABEL_CLASS}>
                      Origem (opcional)
                      <input
                        type="text"
                        value={transactionData.source}
                        onChange={(e) => setTransactionData((p) => ({ ...p, source: e.target.value }))}
                        className={INPUT_CLASS}
                      />
                    </label>
                    <label className={LABEL_CLASS}>
                      Categoria
                      <select
                        value={transactionData.category_id}
                        onChange={(e) => setTransactionData((p) => ({ ...p, category_id: e.target.value }))}
                        className={INPUT_CLASS}
                      >
                        <option value="">Sem categoria</option>
                        {categories.map((category) => (
                          <option key={category.id} value={category.id}>
                            {category.name}
                          </option>
                        ))}
                      </select>
                    </label>
                  </>
                ) : (
                  <>
                    <label className={LABEL_CLASS}>
                      Titulo
                      <input
                        type="text"
                        value={payableData.title}
                        onChange={(e) => setPayableData((p) => ({ ...p, title: e.target.value }))}
                        required
                        className={INPUT_CLASS}
                      />
                    </label>
                    <label className={LABEL_CLASS}>
                      Valor
                      <input
                        type="number"
                        step="0.01"
                        value={payableData.amount}
                        onChange={(e) => setPayableData((p) => ({ ...p, amount: e.target.value }))}
                        required
                        className={INPUT_CLASS}
                      />
                    </label>
                    <label className={LABEL_CLASS}>
                      Vencimento
                      <input
                        type="date"
                        value={payableData.due_date}
                        onChange={(e) => setPayableData((p) => ({ ...p, due_date: e.target.value }))}
                        required
                        className={INPUT_CLASS}
                      />
                    </label>
                    <label className={LABEL_CLASS}>
                      Status
                      <select
                        value={payableData.status}
                        onChange={(e) => setPayableData((p) => ({ ...p, status: e.target.value }))}
                        className={INPUT_CLASS}
                      >
                        <option value="PENDING">Pendente</option>
                        <option value="PAID">Pago</option>
                      </select>
                    </label>
                    <label className={LABEL_CLASS}>
                      Data de pagamento (opcional)
                      <input
                        type="date"
                        value={payableData.payment_date}
                        onChange={(e) => setPayableData((p) => ({ ...p, payment_date: e.target.value }))}
                        className={INPUT_CLASS}
                      />
                    </label>
                    <label className={LABEL_CLASS}>
                      Categoria
                      <select
                        value={payableData.category_id}
                        onChange={(e) => setPayableData((p) => ({ ...p, category_id: e.target.value }))}
                        className={INPUT_CLASS}
                      >
                        <option value="">Sem categoria</option>
                        {categories.map((category) => (
                          <option key={category.id} value={category.id}>
                            {category.name}
                          </option>
                        ))}
                      </select>
                    </label>
                  </>
                )}

                {message && (
                  <div className={`rounded-xl border px-4 py-3 text-sm ${
                    status === "success"
                      ? "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-400"
                      : status === "error"
                      ? "border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-400"
                      : "border-gray-200 bg-gray-50 text-gray-600 dark:border-slate-800 dark:bg-slate-950/60 dark:text-slate-300"
                  }`}>
                    {message}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={isLoading}
                  className="rounded-full bg-emerald-500 px-6 py-3 text-sm font-semibold text-slate-950 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isLoading ? "Salvando..." : "Salvar"}
                </button>
              </form>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
