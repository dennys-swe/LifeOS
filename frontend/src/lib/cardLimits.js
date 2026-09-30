// Faixas de uso do limite do cartão (#204): abaixo de 60% é folga, acima de 85% é aperto.
export function usageTone(pct) {
  if (pct == null) return "slate";
  if (pct >= 85) return "rose";
  if (pct >= 60) return "amber";
  return "emerald";
}
