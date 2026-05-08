import axios from "axios";

const rawBase = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim();
// 开发环境默认走 Vite 代理（见 vite.config.ts），这样用手机/局域网 IP 打开页面时 API 仍可用
const baseURL =
  (rawBase && rawBase.replace(/\/+$/, "")) ||
  (import.meta.env.DEV ? "/api" : "http://127.0.0.1:3000/api");

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
