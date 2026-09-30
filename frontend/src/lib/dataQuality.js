// Textos e agrupamento da tela Saúde dos dados (#200). O backend devolve códigos
// (`kind`, `severity`, `field`); a redação fica aqui.

export const SEVERITY_ORDER = ["high", "warn", "info"];

export const SEVERITY_LABEL = {
  high: "Precisa de atenção",
  warn: "Vale conferir",
  info: "Para sua revisão",
};

export const SEVERITY_TONE = {
  high: "border-rose-500/30 bg-rose-500/10 text-rose-600 dark:text-rose-400",
  warn: "border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400",
  info: "border-slate-400/30 bg-slate-500/10 text-slate-600 dark:text-slate-400",
};

export const KIND_COPY = {
  system_says_transfer: {
    title: "Parece dinheiro que só mudou de lugar",
    text: "Pelas regras do LifeOS, isto é pagamento de fatura ou transferência entre contas suas, mas está contando como renda ou gasto.",
  },
  unmarked_mirror: {
    title: "Saída e entrada do mesmo valor",
    text: "A saída já está marcada como transferência, mas a entrada de mesmo valor continua contando como renda.",
  },
  unlinked_reversal: {
    title: "Crédito que anula uma cobrança",
    text: "Este crédito desfaz uma cobrança de mesmo valor. Sem ligar os dois, a cobrança conta como gasto e o crédito como renda.",
  },
  large_unusual_income: {
    title: "Entrada grande fora do padrão",
    text: "Confira se é renda mesmo. Se for, é só marcar que está certo.",
  },
  uncategorized_expense: {
    title: "Despesa sem categoria",
    text: "Escolha uma categoria para ela entrar nos gastos por categoria.",
  },
};

const FALLBACK_COPY = { title: "Possível problema nos dados", text: "" };

export function issueCopy(kind) {
  return KIND_COPY[kind] ?? FALLBACK_COPY;
}

export function groupBySeverity(issues) {
  const groups = SEVERITY_ORDER.map((severity) => ({
    severity,
    issues: issues.filter((i) => i.severity === severity),
  }));
  return groups.filter((g) => g.issues.length > 0);
}

// Uma linha da prévia: o que vai mudar em qual transação.
export function describeChange(change) {
  if (change.field === "is_transfer") {
    return `Marcar como transferência: ${change.description}`;
  }
  if (change.field === "category_id") {
    return `Categoria de "${change.description}": ${change.old} → ${change.new}`;
  }
  return change.description;
}

export function previewEffects(preview, fmt) {
  const effects = [];
  if (Number(preview.income_removed) > 0) {
    effects.push(`Sai da renda: ${fmt(Number(preview.income_removed))}`);
  }
  if (Number(preview.expense_removed) > 0) {
    effects.push(`Sai dos gastos: ${fmt(Number(preview.expense_removed))}`);
  }
  return effects;
}

export function openCountLabel(n) {
  return n === 1 ? "1 possível erro nos seus dados" : `${n} possíveis erros nos seus dados`;
}
