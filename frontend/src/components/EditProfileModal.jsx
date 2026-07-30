import { useState } from "react";
import { useAuth } from "../context/AuthContext";

export default function EditProfileModal({ open, onClose }) {
  const { user, updateProfile } = useAuth();
  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [email, setEmail] = useState(user?.email ?? "");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");
  const [msgType, setMsgType] = useState("success");

  if (!open) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMsg("");
    try {
      const payload = {};
      if (fullName !== user?.full_name) payload.full_name = fullName;
      if (email !== user?.email) payload.email = email;
      if (password.trim()) payload.password = password.trim();

      if (Object.keys(payload).length === 0) {
        setMsg("Nenhuma alteração informada.", "error");
        setLoading(false);
        return;
      }

      await updateProfile(payload);
      setMsg("Perfil atualizado com sucesso!");
      setMsgType("success");
      setTimeout(() => {
        onClose();
      }, 1000);
    } catch {
      setMsg("Falha ao atualizar perfil. Verifique os dados.");
      setMsgType("error");
    } finally {
      setLoading(false);
    }
  };

  const inputCls = "mt-1.5 w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-xs font-semibold text-slate-900 focus:border-emerald-500 focus:outline-none dark:border-slate-800 dark:bg-slate-900 dark:text-white";
  const labelCls = "flex flex-col text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 backdrop-blur-sm px-4">
      <div className="w-full max-w-md rounded-3xl border border-slate-200/80 bg-white/95 p-6 shadow-2xl backdrop-blur-xl dark:border-slate-800/80 dark:bg-slate-900/95 animate-in fade-in zoom-in duration-200">
        <div className="flex items-center justify-between border-b border-slate-100 pb-4 dark:border-slate-800/60">
          <div>
            <h2 className="font-display text-lg font-bold text-slate-900 dark:text-white">Editar Perfil</h2>
            <p className="text-xs text-slate-400 dark:text-slate-500">Atualize suas informações pessoais</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl border border-slate-200 p-2 text-slate-400 hover:bg-slate-100 dark:border-slate-800 dark:hover:bg-slate-800"
            title="Fechar"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-5 flex flex-col gap-4">
          {msg && (
            <p className={`text-xs font-bold ${msgType === "error" ? "text-rose-500" : "text-emerald-600 dark:text-emerald-400"}`}>
              {msg}
            </p>
          )}

          <label className={labelCls}>
            Nome Completo
            <input
              type="text"
              value={fullName}
              placeholder="ex: Dennys Alves"
              onChange={(e) => setFullName(e.target.value)}
              className={inputCls}
            />
          </label>

          <label className={labelCls}>
            E-mail
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={inputCls}
            />
          </label>

          <label className={labelCls}>
            Nova Senha (deixe em branco para não alterar)
            <input
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={inputCls}
            />
          </label>

          <div className="mt-2 flex items-center justify-end gap-3 pt-4 border-t border-slate-100 dark:border-slate-800/60">
            <button
              type="button"
              onClick={onClose}
              className="rounded-xl border border-slate-200 px-4 py-2.5 text-xs font-semibold text-slate-600 hover:bg-slate-100 dark:border-slate-800 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={loading}
              className="rounded-xl bg-emerald-600 px-5 py-2.5 text-xs font-bold text-white shadow-md shadow-emerald-500/20 hover:bg-emerald-500 disabled:opacity-50"
            >
              {loading ? "Salvando..." : "Salvar Alterações"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
