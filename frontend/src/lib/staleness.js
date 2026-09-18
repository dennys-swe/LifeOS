// Compartilhado por FinanceContext (issue #110) e BankAccountsPage (issue
// #116) — a partir de quando um dado cacheado/carregado é "velho" o
// bastante pra merecer revalidação silenciosa ao focar a aba.
export const STALE_TTL_MS = 3 * 60 * 1000;
