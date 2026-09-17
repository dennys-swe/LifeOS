import axios from "axios";

import { clearFinanceCache } from "../lib/financeCache";

const TOKEN_KEY = "lifeos_token";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
});

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
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
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
