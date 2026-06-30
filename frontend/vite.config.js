import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, path.resolve(__dirname, ".."), "");

  return {
    plugins: [react()],
    server: {
      host: env.VITE_HOST_FRONTEND || "0.0.0.0",
      port: parseInt(env.VITE_PORT_FRONTEND) || 5173,
    },
    envDir: path.resolve(__dirname, ".."),
  };
});
