// Cache de dados financeiros por mês-ano nesta sessão do navegador (issue
// #66), em módulo próprio (não dentro de FinanceContext.jsx) pra
// `services/api.js` poder limpá-lo em `clearToken()` sem criar import
// circular (FinanceContext já importa `api`).
const SESSION_CACHE_KEY = "lifeos-finance-cache-v1";

export function loadFinanceCache() {
  const raw = sessionStorage.getItem(SESSION_CACHE_KEY);
  return raw ? new Map(Object.entries(JSON.parse(raw))) : new Map();
}

export function saveFinanceCache(cache) {
  sessionStorage.setItem(SESSION_CACHE_KEY, JSON.stringify(Object.fromEntries(cache)));
}

// Chamado junto de clearToken(): sem isso, o cache de um usuário (payables,
// categorias, summary) sobrevivia ao logout em sessionStorage, e o próximo
// usuário a logar na mesma aba via a tela inicial com o dado financeiro do
// anterior por um instante, antes do fetch fresco sobrescrever — vazamento
// entre contas num SaaS multi-tenant.
export function clearFinanceCache() {
  sessionStorage.removeItem(SESSION_CACHE_KEY);
}
