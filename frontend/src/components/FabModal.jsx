import { useEffect, useState } from "react";

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

export default function FabModal({ onCreated } = {}) {
  const { refresh } = useFinance() ?? {};
  const [open, setOpen] = useState(false);
  const [formType, setFormType] = useState(FORM_TYPES.payable);
  const [transactionData, setTransactionData] = useState(INITIAL_TRANSACTION);
  const [payableData, setPayableData] = useState(INITIAL_PAYABLE);
  const [categories, setCategories] = useState([]);
  const [status, setStatus] = useState("idle");
  const [message, setMessage] = useState("");

  const resetState = () => {
    setTransactionData(INITIAL_TRANSACTION);
    setPayableData(INITIAL_PAYABLE);
    setStatus("idle");
    setMessage("");
  };

  useEffect(() => {
    const loadCategories = async () => {
      try {
        const response = await api.get("/categories");
        setCategories(response.data ?? []);
      } catch {
        setCategories([]);
      }
    };

    loadCategories();
  }, []);

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
        className="fixed bottom-6 right-6 z-30 flex h-14 w-14 items-center justify-center rounded-full bg-emerald-500 text-2xl font-semibold text-slate-950 shadow-xl transition hover:bg-emerald-400"
      >
        +
      </button>

      {open && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/80 px-6">
          <div className="w-full max-w-xl rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-[0.3em] text-slate-500">
                  Novo registro
                </p>
                <h2 className="text-xl font-semibold text-white">
                  Adicionar manualmente
                </h2>
              </div>
              <button
                type="button"
                onClick={handleClose}
                className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300"
              >
                Fechar
              </button>
            </div>

            <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
              <label className="text-sm text-slate-300">
                Tipo de cadastro
                <select
                  value={formType}
                  onChange={(event) => setFormType(event.target.value)}
                  className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
                >
                  <option value={FORM_TYPES.payable}>Conta a pagar</option>
                  <option value={FORM_TYPES.transaction}>Transacao</option>
                </select>
              </label>

              {formType === FORM_TYPES.transaction ? (
                <>
                  <label className="text-sm text-slate-300">
                    Data
                    <input
                      type="date"
                      value={transactionData.date}
                      onChange={(event) =>
                        setTransactionData((prev) => ({
                          ...prev,
                          date: event.target.value,
                        }))
                      }
                      required
                      className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
                    />
                  </label>
                  <label className="text-sm text-slate-300">
                    Descricao
                    <input
                      type="text"
                      value={transactionData.description}
                      onChange={(event) =>
                        setTransactionData((prev) => ({
                          ...prev,
                          description: event.target.value,
                        }))
                      }
                      required
                      className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
                    />
                  </label>
                  <label className="text-sm text-slate-300">
                    Valor
                    <input
                      type="number"
                      step="0.01"
                      value={transactionData.amount}
                      onChange={(event) =>
                        setTransactionData((prev) => ({
                          ...prev,
                          amount: event.target.value,
                        }))
                      }
                      required
                      className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
                    />
                  </label>
                  <label className="text-sm text-slate-300">
                    Tipo
                    <select
                      value={transactionData.type}
                      onChange={(event) =>
                        setTransactionData((prev) => ({
                          ...prev,
                          type: event.target.value,
                        }))
                      }
                      className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
                    >
                      <option value="INCOME">Entrada</option>
                      <option value="EXPENSE">Saida</option>
                    </select>
                  </label>
                  <label className="text-sm text-slate-300">
                    Origem (opcional)
                    <input
                      type="text"
                      value={transactionData.source}
                      onChange={(event) =>
                        setTransactionData((prev) => ({
                          ...prev,
                          source: event.target.value,
                        }))
                      }
                      className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
                    />
                  </label>
                  <label className="text-sm text-slate-300">
                    Categoria
                    <select
                      value={transactionData.category_id}
                      onChange={(event) =>
                        setTransactionData((prev) => ({
                          ...prev,
                          category_id: event.target.value,
                        }))
                      }
                      className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
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
                  <label className="text-sm text-slate-300">
                    Titulo
                    <input
                      type="text"
                      value={payableData.title}
                      onChange={(event) =>
                        setPayableData((prev) => ({
                          ...prev,
                          title: event.target.value,
                        }))
                      }
                      required
                      className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
                    />
                  </label>
                  <label className="text-sm text-slate-300">
                    Valor
                    <input
                      type="number"
                      step="0.01"
                      value={payableData.amount}
                      onChange={(event) =>
                        setPayableData((prev) => ({
                          ...prev,
                          amount: event.target.value,
                        }))
                      }
                      required
                      className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
                    />
                  </label>
                  <label className="text-sm text-slate-300">
                    Vencimento
                    <input
                      type="date"
                      value={payableData.due_date}
                      onChange={(event) =>
                        setPayableData((prev) => ({
                          ...prev,
                          due_date: event.target.value,
                        }))
                      }
                      required
                      className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
                    />
                  </label>
                  <label className="text-sm text-slate-300">
                    Status
                    <select
                      value={payableData.status}
                      onChange={(event) =>
                        setPayableData((prev) => ({
                          ...prev,
                          status: event.target.value,
                        }))
                      }
                      className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
                    >
                      <option value="PENDING">Pendente</option>
                      <option value="PAID">Pago</option>
                    </select>
                  </label>
                  <label className="text-sm text-slate-300">
                    Data de pagamento (opcional)
                    <input
                      type="date"
                      value={payableData.payment_date}
                      onChange={(event) =>
                        setPayableData((prev) => ({
                          ...prev,
                          payment_date: event.target.value,
                        }))
                      }
                      className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
                    />
                  </label>
                  <label className="text-sm text-slate-300">
                    Categoria
                    <select
                      value={payableData.category_id}
                      onChange={(event) =>
                        setPayableData((prev) => ({
                          ...prev,
                          category_id: event.target.value,
                        }))
                      }
                      className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
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

              <div className="rounded-xl border border-slate-800 bg-slate-950/60 px-4 py-3 text-sm text-slate-300">
                {message}
              </div>

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
      )}
    </>
  );
}