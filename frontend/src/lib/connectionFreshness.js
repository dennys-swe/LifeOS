// Textos da "idade real do dado" de uma conexão (#214). O backend devolve códigos
// (`state`, `reason`) e a redação fica aqui. `freshness` é o objeto calculado em
// `GET /bank-accounts`.

export function formatDataAge(hours) {
  if (hours == null) return null;
  if (hours < 1) return "menos de 1 hora";
  if (hours < 48) return `${Math.round(hours)} h`;
  return `${Math.round(hours / 24)} dias`;
}

const STATE_LABEL = {
  fresh: "Atualizada",
  stale: "Desatualizada",
  attention: "Precisa de atenção",
  unknown: "Sem informação",
};

export function describeFreshness(freshness) {
  if (!freshness) return null;
  const age = formatDataAge(freshness.data_age_hours);
  const { state, reason } = freshness;

  let detail;
  if (state === "fresh") {
    detail = age ? `Dados do banco atualizados há ${age}.` : "Dados do banco atualizados.";
  } else if (state === "stale") {
    detail =
      reason === "no_auto_sync"
        ? `Sem atualização há ${age}: o banco não está atualizando sozinho. Reconecte para buscar dados novos.`
        : `Sem atualização há ${age}: a atualização automática está atrasada. Se continuar, reconecte o banco.`;
  } else if (state === "attention") {
    detail = "O banco precisa da sua autorização de novo. Reconecte para voltar a atualizar.";
  } else {
    detail = "Ainda sem informação de quando o banco foi atualizado pela última vez.";
  }

  const consent =
    freshness.consent_expiring && freshness.consent_days_left != null
      ? freshness.consent_days_left < 0
        ? "A autorização do banco venceu."
        : `A autorização do banco vence em ${freshness.consent_days_left} dias.`
      : null;

  return { state, label: STATE_LABEL[state] ?? STATE_LABEL.unknown, detail, consent };
}
