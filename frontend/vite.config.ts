import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vite";

const apiTarget = process.env.API_PROXY_TARGET ?? "http://localhost:8000";
const agentTarget = process.env.AGENT_PROXY_TARGET ?? "http://localhost:8001";
const previewsTarget = process.env.PREVIEWS_PROXY_TARGET ?? "http://localhost:8002";
const proxy = {
  "/api": apiTarget,
  "/openapi.json": apiTarget,
  "/health": apiTarget,
  // agent/previews services serve unprefixed routes — strip the proxy prefix
  "/agent-api": { target: agentTarget, rewrite: (path: string) => path.replace(/^\/agent-api/, "") },
  "/previews-api": { target: previewsTarget, rewrite: (path: string) => path.replace(/^\/previews-api/, "") },
};

export default defineConfig({
  plugins: [sveltekit()],
  server: { proxy },
  preview: { proxy },
});
