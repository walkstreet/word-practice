import axios from "axios";

const rawBase = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim();
// 开发环境走 Vite 代理；生产环境默认用当前页面同源主机 + 后端端口访问 API（局域网用 IP 打开即可）。

function defaultProdApiBase(): string {
  const rawPort = (import.meta.env.VITE_BACKEND_PORT as string | undefined)?.trim();
  const port = rawPort && /^\d+$/.test(rawPort) ? rawPort : "3000";
  const { hostname, protocol } = window.location;
  return `${protocol}//${hostname}:${port}/api`;
}

const baseURL =
  (rawBase && rawBase.replace(/\/+$/, "")) ||
  (import.meta.env.DEV ? "/api" : defaultProdApiBase());

export const api = axios.create({
  baseURL
});

export function setAuthToken(token: string | null) {
  if (token) {
    api.defaults.headers.common.Authorization = `Bearer ${token}`;
  } else {
    delete api.defaults.headers.common.Authorization;
  }
}

export function loadToken() {
  return localStorage.getItem("token");
}

const AUTH_USERNAME_KEY = "wp_auth_username";

export function saveAuthUsername(username: string) {
  localStorage.setItem(AUTH_USERNAME_KEY, username.trim());
}

export function loadAuthUsername() {
  return localStorage.getItem(AUTH_USERNAME_KEY)?.trim() || "";
}

export function clearAuthUsername() {
  localStorage.removeItem(AUTH_USERNAME_KEY);
}
