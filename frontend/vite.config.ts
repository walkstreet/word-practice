import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // 监听所有网卡；若启动命令带上 --host 127.0.0.1 会覆盖此处，导致局域网 IP 无法访问
    host: true,
    proxy: {
      // 浏览器始终请求当前页面的同源 /api，再由 Vite 转到本机后端（避免写死 127.0.0.1）
      "/api": {
        target: "http://127.0.0.1:3000",
        changeOrigin: true
      }
    }
  }
});
