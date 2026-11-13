import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig, type ProxyOptions } from "vite";

const apiTarget = process.env.API_PROXY_TARGET ?? "http://localhost:8000";
const agentTarget = process.env.AGENT_PROXY_TARGET ?? "http://localhost:8001";
const previewsTarget = process.env.PREVIEWS_PROXY_TARGET ?? "http://localhost:8002";
const agentServiceToken = process.env.AGENT_SERVICE_TOKEN ?? "";

const proxy: Record<string, string | ProxyOptions> = {
  "/api": apiTarget,
  "/openapi.json": apiTarget,
  "/health": apiTarget,
  // agent/previews services serve unprefixed routes — strip the proxy prefix
  "/agent-api": {
    target: agentTarget,
    rewrite: (path: string) => path.replace(/^\/agent-api/, ""),
    // the browser must never see the service token: inject it server-side
    configure: (p) => {
      if (agentServiceToken) p.on("proxyReq", (proxyReq) => proxyReq.setHeader("X-Agent-Token", agentServiceToken));
    },
  },
  "/previews-api": { target: previewsTarget, rewrite: (path: string) => path.replace(/^\/previews-api/, "") },
};

export default defineConfig({
  plugins: [sveltekit()],
  server: { proxy },
  preview: { proxy },
});
