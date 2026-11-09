import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vite";

const apiTarget = process.env.API_PROXY_TARGET ?? "http://localhost:8000";
const agentTarget = process.env.AGENT_PROXY_TARGET ?? "http://localhost:8001";
const proxy = {
  "/api": apiTarget,
  "/openapi.json": apiTarget,
  "/health": apiTarget,
  "/agent-api": agentTarget,
};

export default defineConfig({
  plugins: [sveltekit()],
  server: { proxy },
  preview: { proxy },
});
