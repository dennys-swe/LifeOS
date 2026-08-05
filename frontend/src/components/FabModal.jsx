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
  is_transfer: false,
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
  "mt-1.5 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-900 transition focus:border-emerald-500 focus:outline-none dark:border-slate-700 dark:bg-slate-900 dark:text-white";

const LABEL_CLASS =
  "flex flex-col text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400";

export default function FabModal({ onCreated } = {}) {
  const { refresh, categories = [] } = useFinance() ?? {};
  const [open, setOpen] = useState(false);
  const [formType, setFormType] = useState(FORM_TYPES.payable);
  const [transactionData, setTransactionData] = useState(INITIAL_TRANSACTION);
  const [payableData, setPayableData] = useState(INITIAL_PAYABLE);
  const [status, setStatus] = useState("idle");
  const [message, setMessage] = useState("");

  const isTransaction = formType === FORM_TYPES.transaction;

  // Conta a pagar é sempre despesa; transação segue o tipo escolhido. Oferecer
  // as duas listas juntas deixaria "Salário" a um clique de virar gasto.
  const wantedKind =
    isTransaction && transactionData.type === "INCOME" ? "INCOME" : "EXPENSE";
  const availableCategories = categories.filter(
    (c) => !c.kind || c.kind === wantedKind
  );

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
      if (isTransaction) {
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
      setMessage("Não foi possível salvar. Tente novamente.");
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
        <div className="fixed inset-0 z-40 flex items-center justify-center overflow-y-auto bg-slate-950/60 px-4 py-6 backdrop-blur-sm">
          <div className="my-auto w-full max-w-xl rounded-2xl border border-slate-200/80 bg-white/95 shadow-2xl backdrop-blur-xl dark:border-slate-800/80 dark:bg-slate-900/95">
            <div className="p-6">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-display text-xs font-semibold uppercase tracking-widest text-slate-400 dark:text-slate-500">
                    Novo registro
                  </p>
                  <h2 className="mt-1 font-display text-xl font-bold tracking-tight text-slate-900 dark:text-white">
                    Adicionar manualmente
                  </h2>
                </div>
                <button
                  type="button"
                  onClick={handleClose}
                  className="rounded-xl border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 transition hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
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
                    <option value={FORM_TYPES.transaction}>Transação</option>
                  </select>
                </label>

                {!isTransaction && (
                  // O dono lançava as faturas na mão e passou a ter duplicata
                  // quando a sincronização começou a criá-las sozinha.
                  <p className="rounded-xl border border-sky-500/30 bg-sky-500/10 px-3.5 py-2.5 text-xs font-medium text-sky-700 dark:text-sky-300">
                    Fatura de cartão de banco conectado é criada automaticamente
                    pela sincronização — não precisa lançar aqui.
                  </p>
                )}

                {isTransaction ? (
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
                      Descrição
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
                        onChange={(e) =>
                          setTransactionData((p) => ({ ...p, type: e.target.value, category_id: "" }))
                        }
                        className={INPUT_CLASS}
                      >
                        <option value="INCOME">Entrada</option>
                        <option value="EXPENSE">Saída</option>
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
                        {availableCategories.map((category) => (
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
                      Título
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
                        {availableCategories.map((category) => (
                          <option key={category.id} value={category.id}>
                            {category.name}
                          </option>
                        ))}
                      </select>
                    </label>
                  </>
                )}

                {message && (
                  <div className={`rounded-xl border px-4 py-3 text-xs font-semibold ${
                    status === "success"
                      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
                      : status === "error"
                      ? "border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-400"
                      : "border-slate-200 bg-slate-50 text-slate-600 dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-300"
                  }`}>
                    {message}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={isLoading}
                  className="rounded-xl bg-emerald-600 px-6 py-3 font-display text-sm font-bold text-white shadow-sm transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-60"
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
