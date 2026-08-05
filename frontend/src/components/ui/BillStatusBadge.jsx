// Compartilhado entre o dashboard e a lista de contas: a mesma fatura aparece
// nas duas telas, e rótulos diferentes para o mesmo estado ("Aberta" de um
// lado, "Valor estimado" do outro) faziam parecer coisas distintas.
export default function BillStatusBadge({ status }) {
  const isOpen = status === "OPEN";
  return (
    <span
      title={
        isOpen
          ? "O banco ainda não fechou esta fatura — valor reconstruído dos lançamentos do ciclo e sujeito a mudar"
          : "Fatura fechada pelo banco — valor definitivo"
      }
      className={`inline-flex flex-shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold ${
        isOpen
          ? "border border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400"
          : "border border-slate-400/30 bg-slate-500/10 text-slate-600 dark:text-slate-400"
      }`}
    >
      {isOpen ? "Aberta" : "Fechada"}
    </span>
  );
}
