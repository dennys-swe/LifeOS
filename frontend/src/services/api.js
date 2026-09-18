import axios from "axios";

import { clearFinanceCache } from "../lib/financeCache";

const TOKEN_KEY = "lifeos_token";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
});

// Issue #23 (P2): o backend Render Free hiberna por inatividade e demora
// 50s+ pra voltar (o keep-alive da issue #112 reduz a incidência a quase
// zero, mas não garante — um deploy reinicia o dyno, o pinger pode falhar).
// Sem aviso nenhum, essa primeira resposta lenta parece a tela travada, não
// "o servidor tá ligando". Rastreado aqui (não num interceptor separado)
// pra não duplicar a lógica de pegar o timestamp de cada request.
//
// "Qualquer request pendente há mais de N segundos" sozinho seria
// enganoso: um sync manual de verdade (Pluggy) ou uma query mais pesada
// podem passar de 5s com o backend já bem acordado, e o aviso diria
// "aquecendo o servidor" pra uma lentidão que não tem nada a ver com cold
// start — minando a confiança na mensagem justo quando ela importa de
// verdade. Por isso a checagem exige as DUAS coisas: uma request pendente
// há tempo (`pendingThresholdMs`) E a última resposta bem-sucedida ter sido
// há mais tempo ainda do que a janela de hibernação do Render
// (`idleGapMs`, com folga) — só nesse cenário composto é plausível que o
// dyno estivesse mesmo dormindo.
const pendingRequestStartedAt = new Map();
let lastSuccessAt = null;

// Funções puras (sem depender do axios de verdade) pra ficarem testáveis
// isoladas — os interceptors abaixo só chamam elas.
export function trackRequestStart(config, now = Date.now()) {
  pendingRequestStartedAt.set(config, now);
}

export function trackRequestEnd(config) {
  pendingRequestStartedAt.delete(config);
}

export function trackRequestSuccess(now = Date.now()) {
  lastSuccessAt = now;
}

// Só pra teste: volta ao estado "nunca teve resposta bem-sucedida ainda" —
// sem isso, `lastSuccessAt` (estado de módulo) vazaria de um `it()` pro
// outro no mesmo arquivo de teste.
export function __resetRequestTrackingForTests() {
  pendingRequestStartedAt.clear();
  lastSuccessAt = null;
}

const DEFAULT_PENDING_THRESHOLD_MS = 5000;
// Achado no code-review: tinha 10min aqui, MENOR que os ~15min de
// hibernação do Render — invertia a própria margem que o comentário lá em
// cima promete, disparando o banner pra uma request pesada num backend que
// nunca dormiu (só ficou 11-14min sem receber nada).
const DEFAULT_IDLE_GAP_MS = 16 * 60 * 1000; // > ~15min de hibernação do Render Free, com folga

export function shouldShowColdStartBanner({
  pendingThresholdMs = DEFAULT_PENDING_THRESHOLD_MS,
  idleGapMs = DEFAULT_IDLE_GAP_MS,
} = {}) {
  const now = Date.now();
  // `lastSuccessAt === null`: nenhuma resposta bem-sucedida ainda nesta
  // sessão (ex: 1ª requisição depois de abrir o app) — não tem como saber
  // há quanto tempo o dyno está parado, e é exatamente o cenário clássico
  // de cold start, então conta como "inativo há tempo o bastante".
  const idleLongEnough = lastSuccessAt === null || now - lastSuccessAt > idleGapMs;
  if (!idleLongEnough) return false;

  for (const startedAt of pendingRequestStartedAt.values()) {
    if (now - startedAt > pendingThresholdMs) return true;
  }
  return false;
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
  // Sem isso, o cache financeiro (payables/categorias/summary) de um usuário
  // sobrevivia em sessionStorage e vazava pro próximo que logasse na mesma
  // aba — clearToken() é o ponto único de "esta sessão acabou" (logout
  // explícito e o interceptor de 401 abaixo chamam os dois daqui).
  clearFinanceCache();
}

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  trackRequestStart(config);
  return config;
});

api.interceptors.response.use(
  (response) => {
    trackRequestEnd(response.config);
    trackRequestSuccess();
    return response;
  },
  (error) => {
    trackRequestEnd(error.config);
    if (error.response?.status === 401) {
      clearToken();
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export default api;
