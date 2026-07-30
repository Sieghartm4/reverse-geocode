import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, path.resolve(__dirname, ".."), "");

  // Handle both VITE_FRONTEND_URL (for production domains) and separate host/port (for local dev)
  let host = "0.0.0.0";
  let port = 5173;

  if (env.VITE_FRONTEND_URL) {
    // Parse full URL like https://mywebsite.com or http://192.168.40.226:5173
    try {
      const url = new URL(env.VITE_FRONTEND_URL);
      host = url.hostname;
      port = url.port
        ? parseInt(url.port)
        : url.protocol === "https:"
          ? 443
          : 80;
    } catch (e) {
      console.warn(
        "Invalid VITE_FRONTEND_URL, falling back to host/port settings",
      );
    }
  }

  // Fallback to separate host/port if VITE_FRONTEND_URL not set or invalid
  if (!env.VITE_FRONTEND_URL) {
    host = env.VITE_HOST_FRONTEND || "0.0.0.0";
    port = parseInt(env.VITE_PORT_FRONTEND) || 5173;
  }

  const proxyTarget = env.VITE_API_BACKEND || "";
  const proxy = proxyTarget
    ? {
        "/tiles": {
          target: proxyTarget,
          changeOrigin: true,
          secure: false,
        },
        "/fonts": {
          target: proxyTarget,
          changeOrigin: true,
          secure: false,
        },
        "/reverse": {
          target: proxyTarget,
          changeOrigin: true,
          secure: false,
        },
        "/search": {
          target: proxyTarget,
          changeOrigin: true,
          secure: false,
        },
        "/cities": {
          target: proxyTarget,
          changeOrigin: true,
          secure: false,
        },
      }
    : undefined;

  return {
    plugins: [react()],
    server: {
      host,
      port,
      proxy,
    },
    envDir: path.resolve(__dirname, ".."),
  };
});
