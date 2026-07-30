// "Sem categoria" não tem UUID (category_id é null) — usa esse sentinel na URL
// e a página de detalhe traduz de volta para `uncategorized=true` no filtro
// de GET /transactions.
export const UNCATEGORIZED_SLUG = "sem-categoria";

export function categoryDetailPath(categoryId, month, year) {
  const id = categoryId ?? UNCATEGORIZED_SLUG;
  return `/categoria/${id}?month=${month}&year=${year}`;
}
