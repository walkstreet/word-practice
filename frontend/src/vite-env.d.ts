/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 后端 API 根地址，须与后端的 API_PREFIX 一致，例如 http://127.0.0.1:3000/api 或 .../api/v1 */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
