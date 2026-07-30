// Antes redefinido em 4 páginas (Dashboard, Transactions, BankAccounts,
// Payables) — cada uma com uma pequena variação de nome/assinatura.

export const fmt = (value) =>
  Number(value ?? 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

/** Forma compacta para espaço apertado (rótulo central de gráfico, chip). */
export const fmtCompact = (value) => {
  const n = Number(value ?? 0);
  if (Math.abs(n) >= 1000) return `R$${(n / 1000).toFixed(1)}k`;
  return `R$${n.toFixed(0)}`;
};

export const fmtPct = (value, digits = 1) => `${Number(value ?? 0).toFixed(digits)}%`;

/** `YYYY-MM-DD` → `DD/MM`. As datas do backend nunca devem virar `new Date(...)`
 * direto (desloca um dia pelo fuso) — ver invariante no CLAUDE.md. */
export const fmtDayMonth = (isoDate) => {
  const [, m, d] = isoDate.split("-");
  return `${d}/${m}`;
};

export const fmtDate = (isoDate) => {
  const [y, m, d] = isoDate.split("-");
  return `${d}/${m}/${y}`;
};
